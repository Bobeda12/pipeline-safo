# motor_ia.py
import sqlite3
import os
import numpy as np
from dotenv import load_dotenv # Ainda útil para outras configs se houver
import traceback # Para log detalhado

# Carrega variáveis de ambiente (se houver outras além do DB)
load_dotenv()

# Importações pesadas só serão chamadas se load_model=True
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None # Define como None se não estiver instalado

# Importações para cálculo de similaridade (movidas para o topo para clareza)
try:
    import pandas as pd
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    pd = None
    cosine_similarity = None


class MotorDeCompatibilidade:
    def __init__(self, load_model=True): # Alterado: load_model=True por padrão para local
        self.db_name = os.getenv("DB_NAME", "projeto_grande.db")
        # Constrói o caminho para o DB na mesma pasta do script
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.db_name)
        self.model = None

        if load_model:
            if SentenceTransformer is None:
                print("AVISO: Biblioteca sentence-transformers não encontrada. Instale com 'pip install sentence-transformers'.")
                print("O cálculo de similaridade NÃO funcionará.")
            else:
                try:
                    print("Carregando modelo de IA (modo local)...")
                    # Use um modelo que funcione bem localmente, pode ser o mesmo ou outro
                    self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                    print("Modelo de IA carregado.")
                except Exception as e:
                    print(f"Erro ao carregar o modelo de IA: {e}")
                    print("Verifique a instalação e a conexão com a internet se precisar baixar o modelo.")
                    self.model = None # Garante que o modelo é None se falhar
        else:
            print("Motor de IA em modo ultra-leve (sem cálculo de similaridade).")

    def _get_db_conn(self):
        """Retorna uma conexão sqlite3 direta."""
        try:
            # Garante detecção automática de tipos datetime
            conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            # Define o row_factory aqui para todos os cursores desta conexão
            conn.row_factory = self._dict_factory
            return conn
        except sqlite3.Error as e:
            print(f"Erro ao conectar ao banco de dados SQLite '{self.db_path}': {e}")
            return None # Retorna None se a conexão falhar

    def _dict_factory(self, cursor, row):
        """Converte uma linha do banco de dados (tuple) em um dicionário."""
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    # --- Métodos de acesso ao banco usando sqlite3 ---
    # (Métodos check_user, get_linhas_by_user, etc. - mantidos iguais à versão anterior do SQLite)
    def check_user(self, email, password):
        conn = self._get_db_conn()
        if not conn: return None
        try:
            cursor = conn.cursor()
            user = cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password)).fetchone()
            conn.close()
            return user
        except sqlite3.Error as e:
            print(f"Erro ao verificar usuário: {e}")
            conn.close()
            return None

    def get_linhas_by_user(self, user_id):
        conn = self._get_db_conn()
        if not conn: return []
        try:
            cursor = conn.cursor()
            linhas = cursor.execute("SELECT * FROM linha_ime WHERE user_id = ? ORDER BY programa, linha", (user_id,)).fetchall()
            conn.close()
            return linhas
        except sqlite3.Error as e:
            print(f"Erro ao buscar linhas por usuário: {e}")
            conn.close()
            return []

    def get_linha_by_id(self, linha_id, user_id):
        conn = self._get_db_conn()
        if not conn: return None
        try:
            cursor = conn.cursor()
            linha = cursor.execute("SELECT * FROM linha_ime WHERE id = ? AND user_id = ?", (linha_id, user_id)).fetchone()
            conn.close()
            return linha
        except sqlite3.Error as e:
            print(f"Erro ao buscar linha por ID: {e}")
            conn.close()
            return None

    def add_linha(self, data, user_id):
        conn = self._get_db_conn()
        if not conn: return
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO linha_ime (programa, linha, descricao, emails_contato, user_id) VALUES (?, ?, ?, ?, ?)",
                           (data['programa'], data['linha'], data['descricao'], data['emails_contato'], user_id))
            conn.commit()
            conn.close()
            # Recalcular embeddings/matches pode ser necessário aqui em um cenário real
        except sqlite3.Error as e:
            print(f"Erro ao adicionar linha: {e}")
            conn.rollback() # Desfaz a transação em caso de erro
            conn.close()


    def update_linha(self, linha_id, data, user_id):
        conn = self._get_db_conn()
        if not conn: return
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE linha_ime SET programa = ?, linha = ?, descricao = ?, emails_contato = ? WHERE id = ? AND user_id = ?",
                           (data['programa'], data['linha'], data['descricao'], data['emails_contato'], linha_id, user_id))
            conn.commit()
            conn.close()
            # Recalcular embeddings/matches pode ser necessário aqui em um cenário real
        except sqlite3.Error as e:
            print(f"Erro ao atualizar linha: {e}")
            conn.rollback()
            conn.close()

    def obter_linhas_de_pesquisa_publico(self):
        conn = self._get_db_conn()
        if not conn: return []
        try:
            cursor = conn.cursor()
            linhas = cursor.execute("SELECT id, linha, programa FROM linha_ime ORDER BY programa, linha").fetchall()
            conn.close()
            return linhas
        except sqlite3.Error as e:
            print(f"Erro ao obter linhas públicas: {e}")
            conn.close()
            return []

    def encontrar_matches_publico(self):
        conn = self._get_db_conn()
        if not conn: return []
        try:
            cursor = conn.cursor()
            matches = cursor.execute("SELECT * FROM match ORDER BY edital_id, score DESC").fetchall()
            conn.close()
            return matches
        except sqlite3.OperationalError: # A tabela 'match' pode não existir na primeira execução
            print("Tabela 'match' não encontrada. Execute 'run_update.py' primeiro.")
            conn.close()
            return []
        except sqlite3.Error as e:
            print(f"Erro ao buscar matches públicos: {e}")
            conn.close()
            return []

    def get_edital_details(self, edital_id):
        conn = self._get_db_conn()
        if not conn: return None
        try:
            cursor = conn.cursor()
            detalhes = cursor.execute("SELECT * FROM edital WHERE id = ?", (edital_id,)).fetchone()
            conn.close()
            return detalhes
        except sqlite3.Error as e:
            print(f"Erro ao buscar detalhes do edital: {e}")
            conn.close()
            return None


    # --- Método pesado de cálculo (ainda usa Pandas/Scikit-learn) ---
    def encontrar_e_salvar_matches(self, top_n=5, limiar_minimo=0.10): # Mantido limiar baixo para teste
        # Verifica se o modelo foi carregado
        if self.model is None:
            print("Modelo de IA não carregado. Não é possível calcular matches.")
            return 0
        # Verifica se Pandas e cosine_similarity foram importados
        if pd is None or cosine_similarity is None:
             print("Erro: Pandas ou Scikit-learn não instalados. Instale com 'pip install pandas scikit-learn'.")
             return 0

        # *** CORREÇÃO: Usar uma nova conexão para leitura com Pandas ***
        conn_pd = None
        try:
            conn_pd = sqlite3.connect(self.db_path) # Abre conexão específica para Pandas
            # Ler dados diretamente do SQLite usando Pandas com a nova conexão
            df_editais = pd.read_sql_query("SELECT * FROM edital", conn_pd)
            df_linhas = pd.read_sql_query("SELECT * FROM linha_ime", conn_pd)

        except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
            print(f"Erro ao ler dados do SQLite para calcular matches: {e}")
            traceback.print_exc() # Imprime traceback detalhado
            return 0
        finally:
            if conn_pd: conn_pd.close() # Garante que a conexão do Pandas seja fechada

        # --- DEBUG Prints (Mantidos para verificação) ---
        print(f"Primeiras 5 linhas lidas da tabela 'edital':")
        print(df_editais.head())
        if 'status' in df_editais.columns:
             print(f"Valores únicos na coluna 'status': {df_editais['status'].unique()}")
        else:
             print("AVISO: Coluna 'status' não encontrada no DataFrame 'edital'.")
             return 0 # Não podemos continuar sem a coluna status
        # --- Fim DEBUG Prints ---

        if df_editais.empty or df_linhas.empty:
            print("Tabelas de editais ou linhas estão vazias. Não há matches para calcular.")
            return 0

        # Lógica de filtro e cálculo de similaridade (mantida)
        df_editais_abertos = df_editais[df_editais['status'] == 'aberto'].copy()
        df_editais_elegiveis = df_editais_abertos # Simplificado (sem filtro de elegibilidade extra)

        if df_editais_elegiveis.empty:
            print("Nenhum edital aberto encontrado (após filtro 'status' == 'aberto').") # Mensagem mais clara
            return 0

        if 'embedding' not in df_linhas.columns or df_linhas['embedding'].isnull().all(): # Verifica se *todos* são nulos
             print("AVISO: Coluna 'embedding' faltando ou com todos os valores nulos em 'linha_ime'. Execute 'run_update.py' para calculá-los.")
             return 0 # Não podemos calcular sem embeddings

        # Certifica que embeddings são lidos corretamente do BLOB e lida com possíveis nulos
        embeddings_linhas = []
        df_linhas_com_embedding = df_linhas.dropna(subset=['embedding']).copy() # Cria cópia para evitar SettingWithCopyWarning
        if df_linhas_com_embedding.empty:
            print("Nenhuma linha com embedding válido encontrado.")
            return 0

        try:
            embeddings_linhas = np.array([np.frombuffer(blob, dtype=np.float32) for blob in df_linhas_com_embedding['embedding']])
        except Exception as e:
            print(f"Erro ao converter embeddings BLOB: {e}")
            traceback.print_exc()
            return 0

        if embeddings_linhas.size == 0:
            print("Nenhum embedding válido processado.")
            return 0


        textos_editais = (df_editais_elegiveis['titulo'].fillna('') + '. ' + df_editais_elegiveis['texto_pdf'].fillna('')).tolist()
        if not textos_editais:
            print("Nenhum texto de edital válido encontrado.")
            return 0

        try:
            print(f"Calculando similaridade entre {len(textos_editais)} editais e {len(embeddings_linhas)} linhas...")
            embeddings_editais = self.model.encode(textos_editais, show_progress_bar=False) # Roda localmente
            matriz_similaridade = cosine_similarity(embeddings_editais, embeddings_linhas)
            print("Matriz de similaridade calculada.")
        except Exception as e:
             print(f"Erro ao calcular similaridade com o modelo: {e}")
             traceback.print_exc()
             return 0

        lista_matches = []
        # Itera sobre o df_linhas_com_embedding que corresponde aos embeddings_linhas
        for idx_linha_relativo, (linha_id_real, linha) in enumerate(df_linhas_com_embedding.iterrows()):
            scores_para_esta_linha = matriz_similaridade[:, idx_linha_relativo] # Usa o índice relativo
            # Argsort retorna índices relativos a scores_para_esta_linha
            indices_top_n_relativos = np.argsort(scores_para_esta_linha)[-top_n:][::-1]
            for idx_edital_relativo in indices_top_n_relativos:
                score = scores_para_esta_linha[idx_edital_relativo]
                if score >= limiar_minimo:
                    # Usa o índice relativo para pegar o edital correto de df_editais_elegiveis
                    edital = df_editais_elegiveis.iloc[idx_edital_relativo]
                    match = {
                        'edital_id': int(edital['id']),
                        'edital_titulo': edital['titulo'],
                        'linha_id': int(linha['id']), # Usa o ID real da linha
                        'linha_nome': linha['linha'],
                        'programa': linha['programa'],
                        'score': round(float(score), 4),
                        'notificado': False
                    }
                    lista_matches.append(match)

        if not lista_matches:
            print("Nenhum match encontrado acima do limiar.")
            return 0

        # Salvar matches no SQLite (usando _get_db_conn para garantir consistência)
        conn_save = self._get_db_conn()
        if not conn_save:
            print("Erro: Não foi possível conectar ao DB para salvar matches.")
            return 0
        try:
            cursor = conn_save.cursor()
            # Limpa a tabela match antes de inserir novos
            cursor.execute("DELETE FROM match")
            # Converte dicts para tuplas na ordem correta das colunas
            match_tuples = [
                (m['edital_id'], m['edital_titulo'], m['linha_id'], m['linha_nome'], m['programa'], m['score'], m['notificado'])
                for m in lista_matches
            ]
            cursor.executemany("""
                INSERT INTO match (edital_id, edital_titulo, linha_id, linha_nome, programa, score, notificado)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, match_tuples)
            conn_save.commit()
            print(f"{len(lista_matches)} matches salvos no banco de dados.")
            return len(lista_matches)
        except sqlite3.Error as e:
            print(f"Erro ao salvar matches no SQLite: {e}")
            traceback.print_exc()
            conn_save.rollback()
            return 0
        finally:
            if conn_save: conn_save.close()

