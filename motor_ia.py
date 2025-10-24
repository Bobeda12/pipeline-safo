# motor_ia.py
import os
import numpy as np
from sqlalchemy import create_engine, text
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import traceback # Para logs de erro mais detalhados

# --- Configuração do Banco de Dados ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("A variável de ambiente DATABASE_URL não foi configurada.")

# Cria o engine do SQLAlchemy para PostgreSQL
# Pode ser definido globalmente para reutilização
try:
    engine = create_engine(DATABASE_URL)
except Exception as e:
    print(f"Erro ao criar engine SQLAlchemy: {e}")
    # Considerar lançar o erro ou ter um fallback dependendo do contexto
    engine = None

class MotorDeCompatibilidade:
    def __init__(self, load_model=False):
        """
        Inicializa o motor.
        load_model=True: Carrega o modelo SentenceTransformer (uso no worker).
        load_model=False: Modo leve para a aplicação web.
        """
        self.engine = engine # Usa o engine global
        if self.engine is None:
             raise ConnectionError("Falha ao inicializar o engine do banco de dados.")

        self.model = None
        if load_model:
            print("Carregando modelo de IA (modo worker)...")
            try:
                from sentence_transformers import SentenceTransformer
                # Certifique-se de que o modelo está acessível/baixado no ambiente de execução
                self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                print("Modelo de IA carregado.")
            except Exception as e:
                print(f"Erro ao carregar o modelo SentenceTransformer: {e}")
                self.model = None # Garante que o modelo não seja usado se falhar ao carregar
        else:
            print("Motor de IA em modo de leitura (ultra-leve).")

    def _execute_query(self, query: str, params: dict = None, fetch_one=False, fetch_all=False):
        """Função auxiliar para executar consultas SQL de forma segura."""
        if not self.engine:
            print("Erro: Engine do banco de dados não inicializado.")
            return None
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text(query), params or {})
                if fetch_one:
                    row = result.fetchone()
                    return dict(zip(result.keys(), row)) if row else None
                elif fetch_all:
                    rows = result.fetchall()
                    keys = result.keys()
                    return [dict(zip(keys, row)) for row in rows]
                else: # Para INSERT, UPDATE, DELETE - inicia transação
                     with connection.begin(): # Garante commit ou rollback
                         # A execução já ocorreu, apenas garante a transação
                         pass
                     return True # Indica sucesso na execução
        except Exception as e:
            print(f"Erro ao executar query: {query} com params {params}. Erro: {e}")
            traceback.print_exc() # Imprime stack trace para depuração
            return None if (fetch_one or fetch_all) else False # Indica falha

    # --- Métodos de Acesso a Dados (Adaptados) ---

    def check_user(self, email, password):
        """Verifica as credenciais do usuário no banco de dados."""
        query = "SELECT * FROM users WHERE email = :email AND password = :password"
        params = {"email": email, "password": password}
        return self._execute_query(query, params, fetch_one=True)

    def get_linhas_by_user(self, user_id):
        """Busca todas as linhas de pesquisa associadas a um user_id."""
        query = "SELECT * FROM linha_ime WHERE user_id = :user_id ORDER BY programa, linha"
        params = {"user_id": user_id}
        return self._execute_query(query, params, fetch_all=True)

    def get_linha_by_id(self, linha_id, user_id):
        """Busca uma linha de pesquisa específica pelo ID e user_id."""
        query = "SELECT * FROM linha_ime WHERE id = :id AND user_id = :user_id"
        params = {"id": linha_id, "user_id": user_id}
        return self._execute_query(query, params, fetch_one=True)

    def add_linha(self, data, user_id):
        """Adiciona uma nova linha de pesquisa."""
        # Assume que 'data' é um dicionário com 'programa', 'linha', 'descricao', 'emails_contato'
        query = """
            INSERT INTO linha_ime (programa, linha, descricao, emails_contato, user_id)
            VALUES (:programa, :linha, :descricao, :emails_contato, :user_id)
        """
        params = {**data, "user_id": user_id}
        return self._execute_query(query, params)

    def update_linha(self, linha_id, data, user_id):
        """Atualiza uma linha de pesquisa existente."""
        query = """
            UPDATE linha_ime
            SET programa = :programa, linha = :linha, descricao = :descricao, emails_contato = :emails_contato
            WHERE id = :id AND user_id = :user_id
        """
        params = {**data, "id": linha_id, "user_id": user_id}
        return self._execute_query(query, params)

    def obter_linhas_de_pesquisa_publico(self):
        """Busca ID, linha e programa de todas as linhas para exibição pública."""
        query = "SELECT id, linha, programa FROM linha_ime ORDER BY programa, linha"
        return self._execute_query(query, fetch_all=True)

    def encontrar_matches_publico(self):
        """Busca todos os matches calculados para exibição pública."""
        query = "SELECT * FROM match ORDER BY score DESC" # Ordenar aqui pode ser útil
        return self._execute_query(query, fetch_all=True)

    def get_edital_details(self, edital_id):
        """Busca detalhes de um edital específico pelo ID."""
        query = "SELECT * FROM edital WHERE id = :id"
        params = {"id": edital_id}
        return self._execute_query(query, params, fetch_one=True)

    # --- Método Principal de Cálculo (Worker) ---

    def encontrar_e_salvar_matches(self, top_n=5, limiar_minimo=0.60):
        """
        Calcula a similaridade entre editais e linhas, salvando os melhores matches.
        Esta função é PESADA e deve ser executada pelo worker (load_model=True).
        """
        if self.model is None:
            print("Erro: Modelo de IA não carregado. Não é possível calcular matches.")
            return 0
        if not self.engine:
            print("Erro: Engine do banco de dados não disponível.")
            return 0

        print("Calculando matches...")
        start_time_calc = pd.Timestamp.now()

        try:
            # Carregar dados usando Pandas (eficiente para DataFrames)
            df_editais = pd.read_sql_table('edital', self.engine)
            # Lê embeddings como string no formato '[1.2,3.4,...]' ou array se o driver suportar
            df_linhas = pd.read_sql_table('linha_ime', self.engine)

            # Filtrar editais abertos
            df_editais_abertos = df_editais[df_editais['status'].str.lower() == 'aberto'].copy()
            if df_editais_abertos.empty:
                print("Nenhum edital aberto encontrado.")
                return 0

            # Lidar com embeddings ausentes ou em formato incorreto
            if 'embedding' not in df_linhas.columns or df_linhas['embedding'].isnull().all():
                 print("Erro: Coluna 'embedding' não encontrada ou está vazia na tabela 'linha_ime'. Pré-calcule os embeddings.")
                 return 0

            # Converter embeddings da string '[1.2,3.4,...]' para numpy array
            # NOTA: Se usar pgvector nativamente, a query de similaridade seria feita no DB.
            valid_embeddings = []
            valid_indices = []
            for index, emb_str in df_linhas['embedding'].items():
                if isinstance(emb_str, str) and emb_str.startswith('[') and emb_str.endswith(']'):
                    try:
                        # Remove colchetes e divide pela vírgula
                        emb_array = np.fromstring(emb_str[1:-1], sep=',', dtype=np.float32)
                        # Verifique se a dimensão está correta (ex: 768)
                        if emb_array.shape == (768,):
                            valid_embeddings.append(emb_array)
                            valid_indices.append(index) # Guarda o índice original do DataFrame
                        else:
                            print(f"Alerta: Embedding da linha ID {df_linhas.loc[index, 'id']} tem dimensão incorreta {emb_array.shape}, ignorando.")
                    except ValueError:
                         print(f"Alerta: Falha ao converter embedding da linha ID {df_linhas.loc[index, 'id']}, ignorando.")
                elif isinstance(emb_str, (np.ndarray, list)): # Se já vier como array/lista
                     emb_array = np.array(emb_str, dtype=np.float32)
                     if emb_array.shape == (768,):
                         valid_embeddings.append(emb_array)
                         valid_indices.append(index)
                     else:
                          print(f"Alerta: Embedding (já array) da linha ID {df_linhas.loc[index, 'id']} tem dimensão incorreta {emb_array.shape}, ignorando.")
                else:
                    print(f"Alerta: Embedding da linha ID {df_linhas.loc[index, 'id']} está em formato inválido ou nulo, ignorando.")


            if not valid_embeddings:
                print("Nenhum embedding válido encontrado nas linhas de pesquisa.")
                return 0

            embeddings_linhas = np.array(valid_embeddings)
            df_linhas_validas = df_linhas.loc[valid_indices] # DataFrame apenas com linhas que têm embeddings válidos

            # Calcular embeddings para os textos dos editais
            textos_editais = (df_editais_abertos['titulo'].fillna('') + '. ' + df_editais_abertos['texto_pdf'].fillna('')).tolist()
            if not textos_editais:
                 print("Nenhum texto de edital encontrado para processar.")
                 return 0

            embeddings_editais = self.model.encode(textos_editais, show_progress_bar=True)

            # Calcular similaridade de cosseno
            matriz_similaridade = cosine_similarity(embeddings_editais, embeddings_linhas)

            # Encontrar os top N matches para cada linha de pesquisa válida
            lista_matches = []
            current_time = pd.Timestamp.now(tz='UTC') # Usar timezone aware para timestamptz

            for idx_linha_matriz, idx_df_original in enumerate(valid_indices):
                linha = df_linhas_validas.loc[idx_df_original] # Pega a linha original do df_linhas_validas
                scores_para_esta_linha = matriz_similaridade[:, idx_linha_matriz]
                # Pega os índices dos editais com maiores scores para esta linha
                indices_top_n_editais = np.argsort(scores_para_esta_linha)[-top_n:][::-1]

                for idx_edital_matriz in indices_top_n_editais:
                    score = scores_para_esta_linha[idx_edital_matriz]
                    if score >= limiar_minimo:
                        # Obtém o edital correspondente do DataFrame de editais abertos
                        edital = df_editais_abertos.iloc[idx_edital_matriz]
                        match = {
                            'edital_id': int(edital['id']),
                            'edital_titulo': edital['titulo'],
                            'linha_id': int(linha['id']),
                            'linha_nome': linha['linha'],
                            'programa': linha['programa'],
                            'score': round(float(score), 4),
                            'data_calculo': current_time, # Adiciona timestamp
                            'notificado': False          # Adiciona flag de notificação
                        }
                        lista_matches.append(match)

            if not lista_matches:
                print("Nenhum match encontrado acima do limiar.")
                return 0

            # Salvar no banco de dados, substituindo a tabela 'match'
            df_matches = pd.DataFrame(lista_matches).drop_duplicates()
            with self.engine.connect() as connection:
                # Usar transação para garantir atomicidade
                with connection.begin():
                    # Opcional: Limpar tabela antiga antes de inserir (se if_exists='replace' não funcionar como esperado)
                    # connection.execute(text("DELETE FROM match"))
                    df_matches.to_sql('match', connection, if_exists='replace', index=False,
                                      dtype={'data_calculo': pd.TIMESTAMP(timezone=True)}) # Especifica o tipo para timestamp com timezone
            print(f"Salvos {len(df_matches)} matches no banco de dados.")
            end_time_calc = pd.Timestamp.now()
            print(f"Cálculo e salvamento de matches concluído em {(end_time_calc - start_time_calc).total_seconds():.2f} segundos.")
            return len(df_matches)

        except Exception as e:
            print(f"Erro GERAL ao encontrar e salvar matches: {e}")
            traceback.print_exc()
            return 0
