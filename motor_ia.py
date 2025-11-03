# motor_ia.py (Versão Local SQLite, com Hashing de Senha)
import sqlite3
import os
import numpy as np
from dotenv import load_dotenv
import traceback
import datetime # Import datetime for type conversion
# Import para hashing de senha
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv() # Carrega variáveis do .env assim que o módulo é importado

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

try:
    import pandas as pd
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    pd = None
    cosine_similarity = None


class MotorDeCompatibilidade:
    def __init__(self, load_model=True):
        self.db_name = os.getenv("DB_NAME", "projeto_grande.db")
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.db_name)
        self.model = None

        if load_model:
            if SentenceTransformer is None:
                print("AVISO: Biblioteca sentence-transformers não encontrada.")
            else:
                try:
                    print("Carregando modelo de IA (modo local)...")
                    self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                    print("Modelo de IA carregado.")
                except Exception as e:
                    print(f"Erro ao carregar o modelo de IA: {e}")
                    self.model = None
        else:
            # Mensagem ajustada para refletir o uso no app.py
            print("Motor de IA em modo ultra-leve (servidor web).")

    def _get_db_conn(self):
        try:
            # Garante que adaptadores/conversores sejam registrados
            sqlite3.register_adapter(np.ndarray, lambda arr: arr.astype(np.float32).tobytes())
            sqlite3.register_converter("vector", lambda b: np.frombuffer(b, dtype=np.float32))
            conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
            conn.row_factory = self._dict_factory
            return conn
        except sqlite3.Error as e:
            # --- DEBUG ADICIONADO ---
            print(f"--- [DEBUG] MOTOR_IA: Erro ao CONECTAR ao banco de dados SQLite '{self.db_path}': {e} ---")
            # --- FIM DEBUG ---
            return None

    def _dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    # --- NOVO MÉTODO: Criar tabelas se não existirem ---
    def create_tables_if_not_exist(self):
        """
        Cria todas as tabelas necessárias (users, edital, linha_ime, match)
        se elas ainda não existirem no banco de dados.
        """
        conn = self._get_db_conn()
        if not conn:
            print("ERRO CRÍTICO: Não foi possível conectar ao DB para criar tabelas.")
            return
        try:
            cursor = conn.cursor()
            print("[DB Setup] Verificando e criando tabelas se não existirem...")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            );""")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS edital (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT,
                orgao TEXT,
                link_pagina TEXT UNIQUE, -- Chave única para evitar duplicatas
                texto_pdf TEXT,
                resumo_pdf TEXT,
                status TEXT,
                modalidade TEXT,
                prazo_submissao DATETIME,
                valor_estimado TEXT,
                elegibilidade TEXT,
                areas_tema TEXT,
                data_captura DATETIME DEFAULT CURRENT_TIMESTAMP
            );""")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS linha_ime (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                programa TEXT,
                linha TEXT,
                descricao TEXT,
                emails_contato TEXT,
                embedding BLOB,
                user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );""")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS match (
                edital_id INTEGER,
                edital_titulo TEXT,
                linha_id INTEGER,
                linha_nome TEXT,
                programa TEXT,
                score REAL,
                notificado BOOLEAN DEFAULT FALSE,
                data_calculo DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (edital_id) REFERENCES edital (id),
                FOREIGN KEY (linha_id) REFERENCES linha_ime (id)
            );""")

            conn.commit()
            print("[DB Setup] Tabelas verificadas/criadas com sucesso.")
        except sqlite3.Error as e:
            print(f"Erro ao criar tabelas: {e}")
            conn.rollback()
        finally:
            if conn:
                conn.close()

    # --- NOVO MÉTODO: Checar duplicata de edital ---
    def check_edital_exists(self, link_pagina):
        """Verifica se um edital com o mesmo link_pagina já existe."""
        conn = self._get_db_conn()
        if not conn: return False
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM edital WHERE link_pagina = ?", (link_pagina,))
            exists = cursor.fetchone()
            conn.close()
            return exists is not None
        except sqlite3.Error as e:
            print(f"Erro ao checar edital: {e}")
            if conn: conn.close()
            return False # Assume que não existe em caso de erro

    # --- NOVO MÉTODO: Inserir edital processado ---
    def insert_edital(self, edital_data):
        """
        Insere um único edital processado no banco de dados.
        Espera um dicionário com chaves correspondentes às colunas da tabela 'edital'.
        """
        conn = self._get_db_conn()
        if not conn:
            print(f"Erro de DB: Não foi possível inserir edital {edital_data.get('titulo')}")
            return False

        query = """
        INSERT INTO edital (
            titulo, orgao, link_pagina, texto_pdf, resumo_pdf, status, modalidade,
            prazo_submissao, valor_estimado, elegibilidade, areas_tema, data_captura
        ) VALUES (
            :titulo, :orgao, :link_pagina, :texto_pdf, "resumo_pdf, :status, :modalidade,
            :prazo_submissao, :valor_estimado, :elegibilidade, :areas_tema, :data_captura
        )
        """
        try:
            cursor = conn.cursor()
            cursor.execute(query, edital_data)
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            # Isso pode acontecer se houver uma condição de corrida,
            # mas a checagem anterior (check_edital_exists) deve prevenir 99%
            print(f"Aviso: Edital {edital_data.get('link_pagina')} já existia (IntegrityError).")
            conn.rollback()
            conn.close()
            return False
        except sqlite3.Error as e:
            print(f"Erro ao inserir edital {edital_data.get('titulo')}: {e}")
            conn.rollback()
            conn.close()
            return False

    # --- Métodos de Usuário (Atualizados com Hashing) ---
    def check_user(self, email, password):
        """Verifica o email e a senha (comparando o hash) no banco."""
        conn = self._get_db_conn()
        if not conn: return None
        try:
            cursor = conn.cursor()
            # Seleciona o usuário pelo email
            user_data = cursor.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            conn.close()

            # Verifica se o usuário existe e se a senha corresponde ao hash armazenado
            if user_data and check_password_hash(user_data['password'], password):
                return user_data # Retorna os dados do usuário se a senha estiver correta
            else:
                return None # Usuário não encontrado ou senha incorreta
        except sqlite3.Error as e:
            print(f"Erro ao verificar usuário: {e}")
            if conn: conn.close()
            return None

    def add_user(self, email, password):
        """Adiciona um novo usuário ao banco de dados, salvando o hash da senha."""
        conn = self._get_db_conn()
        if not conn:
            return False, "Erro ao conectar ao banco de dados."

        # Gera o hash da senha
        password_hash = generate_password_hash(password)

        try:
            cursor = conn.cursor()
            # Insere o email e o HASH da senha
            cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password_hash))
            conn.commit()
            conn.close()
            return True, "Usuário criado com sucesso."
        except sqlite3.IntegrityError: # Trata erro se o email já existir (UNIQUE constraint)
            conn.rollback()
            conn.close()
            return False, "Este e-mail já está cadastrado."
        except sqlite3.Error as e:
            print(f"Erro ao adicionar usuário: {e}")
            traceback.print_exc()
            conn.rollback()
            conn.close()
            return False, f"Erro interno ao criar usuário: {e}"

    # --- Métodos de Linha de Pesquisa (sem alterações) ---
    def get_linhas_by_user(self, user_id):
        # ... (código existente mantido) ...
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
        # ... (código existente mantido) ...
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
        # ... (código existente mantido) ...
        conn = self._get_db_conn()
        if not conn: return
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO linha_ime (programa, linha, descricao, emails_contato, user_id, embedding) VALUES (?, ?, ?, ?, ?, NULL)",
                           (data['programa'], data['linha'], data['descricao'], data['emails_contato'], user_id))
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            print(f"Erro ao adicionar linha: {e}")
            conn.rollback()
            conn.close()
            raise # Re-levanta a exceção para que o Flask possa tratá-la

    def update_linha(self, linha_id, data, user_id):
        # ... (código existente mantido) ...
         conn = self._get_db_conn()
         if not conn: return
         try:
             cursor = conn.cursor()
             cursor.execute("UPDATE linha_ime SET programa = ?, linha = ?, descricao = ?, emails_contato = ?, embedding = NULL WHERE id = ? AND user_id = ?",
                            (data['programa'], data['linha'], data['descricao'], data['emails_contato'], linha_id, user_id))
             conn.commit()
             conn.close()
         except sqlite3.Error as e:
             print(f"Erro ao atualizar linha: {e}")
             conn.rollback()
             conn.close()
             raise # Re-levanta a exceção

    # --- Métodos Públicos e de Matches (sem alterações) ---
    def obter_linhas_de_pesquisa_publico(self):
        conn = self._get_db_conn()
        if not conn:
            # --- DEBUG ADICIONADO ---
            print(f"--- [DEBUG] MOTOR_IA: obter_linhas_de_pesquisa_publico falhou em _get_db_conn() ---")
            # --- FIM DEBUG ---
            return []
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
        if not conn:
            # --- DEBUG ADICIONADO ---
            print(f"--- [DEBUG] MOTOR_IA: encontrar_matches_publico falhou em _get_db_conn() ---")
            # --- FIM DEBUG ---
            return []
        try:
            cursor = conn.cursor()
            # --- MODIFICADO PARA DEMONSTRAÇÃO ---
            # Ordena por score descendente e limita a 10 resultados GLOBAIS
            matches = cursor.execute("SELECT * FROM match ORDER BY score DESC LIMIT 10").fetchall()
            conn.close()
            return matches
        except sqlite3.OperationalError:
            print("Tabela 'match' não encontrada. Execute 'run_update.py' primeiro.")
            conn.close()
            return []
        except sqlite3.Error as e:
            print(f"Erro ao buscar matches públicos: {e}")
            conn.close()
            return []


    def get_edital_details(self, edital_id):
        conn = self._get_db_conn()
        if not conn:
            # --- DEBUG ADICIONADO ---
            print(f"--- [DEBUG] MOTOR_IA: get_edital_details falhou em _get_db_conn() ---")
            # --- FIM DEBUG ---
            return None
        try:
            cursor = conn.cursor()
            detalhes = cursor.execute("SELECT * FROM edital WHERE id = ?", (edital_id,)).fetchone()
            conn.close()
            # Converte string de data de volta para objeto datetime
            # Esta conversão é útil se o DB não usar 'detect_types'
            if detalhes and 'prazo_submissao' in detalhes and isinstance(detalhes['prazo_submissao'], str):
                 try:
                     detalhes['prazo_submissao'] = datetime.datetime.fromisoformat(detalhes['prazo_submissao'])
                 except (ValueError, TypeError):
                     pass # Ignora se não for formato ISO
            if detalhes and 'data_captura' in detalhes and isinstance(detalhes['data_captura'], str):
                 try:
                    detalhes['data_captura'] = datetime.datetime.fromisoformat(detalhes['data_captura'])
                 except (ValueError, TypeError):
                    pass # Ignora se não for formato ISO
            return detalhes
        except sqlite3.Error as e:
            print(f"Erro ao buscar detalhes do edital: {e}")
            conn.close()
            return None

    # --- Método pesado de cálculo ---
    # --- MODIFICADO PARA DEMONSTRAÇÃO ---
    # Parâmetros top_n e limiar_minimo são ignorados; limite_demonstracao controla
    def encontrar_e_salvar_matches(self, top_n=5, limiar_minimo=0.10, limite_demonstracao=10):
        if self.model is None:
            print("Modelo de IA não carregado. Não é possível calcular matches.")
            return 0
        if pd is None or cosine_similarity is None:
             print("Erro: Pandas ou Scikit-learn não instalados.")
             return 0

        conn_pd = None
        try:
            conn_pd = sqlite3.connect(self.db_path)
            df_editais = pd.read_sql_query("SELECT * FROM edital", conn_pd)
            df_linhas = pd.read_sql_query("SELECT * FROM linha_ime", conn_pd)
        except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
            print(f"Erro ao ler dados do SQLite para calcular matches: {e}")
            traceback.print_exc()
            if conn_pd: conn_pd.close()
            return 0
        finally:
            if conn_pd: conn_pd.close()

        print(f"Primeiras 5 linhas lidas da tabela 'edital':")
        print(df_editais.head())
        if 'status' in df_editais.columns:
             print(f"Valores únicos na coluna 'status': {df_editais['status'].unique()}")
        else:
             print("AVISO: Coluna 'status' não encontrada no DataFrame 'edital'.")
             return 0

        if df_editais.empty or df_linhas.empty:
            print("Tabelas de editais ou linhas estão vazias.")
            return 0

        # --- MODO DEMONSTRAÇÃO ATIVO (inclui editais encerrados) ---
        df_editais_elegiveis = df_editais

        if df_editais_elegiveis.empty:
            print("Nenhum edital elegível encontrado.") # Mensagem ajustada
            return 0

        if 'embedding' not in df_linhas.columns or df_linhas['embedding'].isnull().all():
             print("AVISO: Coluna 'embedding' faltando ou vazia.")
             print("Executando cálculo de embedding para linhas pendentes...")
             self.calcular_embeddings_pendentes()
             try:
                 conn_pd = sqlite3.connect(self.db_path)
                 df_linhas = pd.read_sql_query("SELECT * FROM linha_ime", conn_pd)
             finally:
                 if conn_pd: conn_pd.close()
             if 'embedding' not in df_linhas.columns or df_linhas['embedding'].isnull().all():
                 print("ERRO: Mesmo após recalcular, embeddings não foram encontrados.")
                 return 0

        embeddings_linhas = []
        df_linhas_com_embedding = df_linhas.dropna(subset=['embedding']).copy()
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
            embeddings_editais = self.model.encode(textos_editais, show_progress_bar=False)
            matriz_similaridade = cosine_similarity(embeddings_editais, embeddings_linhas)
            print("Matriz de similaridade calculada.")
        except Exception as e:
             print(f"Erro ao calcular similaridade com o modelo: {e}")
             traceback.print_exc()
             return 0

        lista_matches = []
        matches_encontrados = 0 # Contador para o limite de demonstração

        # --- MODIFICADO PARA DEMONSTRAÇÃO ---
        # Itera linha por linha, depois edital por edital, parando quando atingir o limite
        for idx_linha_relativo, (linha_id_real, linha) in enumerate(df_linhas_com_embedding.iterrows()):
            if matches_encontrados >= limite_demonstracao:
                print(f"Limite de {limite_demonstracao} matches para demonstração atingido. Parando busca.")
                break # Sai do loop das linhas

            scores_para_esta_linha = matriz_similaridade[:, idx_linha_relativo]
            # Ordena os editais por score para esta linha
            indices_editais_ordenados = np.argsort(scores_para_esta_linha)[::-1]

            for idx_edital_relativo in indices_editais_ordenados:
                if matches_encontrados >= limite_demonstracao:
                    break # Sai do loop dos editais para esta linha

                score = scores_para_esta_linha[idx_edital_relativo]
                if score >= limiar_minimo:
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
                    matches_encontrados += 1 # Incrementa o contador

        if not lista_matches:
            print("Nenhum match encontrado acima do limiar.")
            return 0

        conn_save = self._get_db_conn()
        if not conn_save:
            print("Erro: Não foi possível conectar ao DB para salvar matches.")
            return 0
        try:
            cursor = conn_save.cursor()
            cursor.execute("DELETE FROM match") # Limpa os matches antigos
            match_tuples = [
                (m['edital_id'], m['edital_titulo'], m['linha_id'], m['linha_nome'], m['programa'], m['score'], m['notificado'])
                for m in lista_matches # Salva apenas os matches encontrados até o limite
            ]
            cursor.executemany("""
                INSERT INTO match (edital_id, edital_titulo, linha_id, linha_nome, programa, score, notificado)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, match_tuples)
            conn_save.commit()
            print(f"{len(lista_matches)} matches salvos no banco de dados (limite de demonstração: {limite_demonstracao}).")
            return len(lista_matches)
        except sqlite3.Error as e:
            print(f"Erro ao salvar matches no SQLite: {e}")
            traceback.print_exc()
            conn_save.rollback()
            return 0
        finally:
            if conn_save: conn_save.close()


    # --- NOVO MÉTODO: Calcular embeddings pendentes ---
    def calcular_embeddings_pendentes(self):
        """
        Calcula e salva embeddings para qualquer 'linha_ime' que esteja com
        o campo 'embedding' como NULL.
        """
        if self.model is None:
            print("Modelo de IA não carregado. Não é possível calcular embeddings.")
            return 0

        # --- CORREÇÃO: Conexão para Pandas NÃO DEVE ter row_factory ---
        # Usar o db_path diretamente para o Pandas
        conn_pd = None
        print("[Embeddings] Buscando linhas de pesquisa com embeddings pendentes...")
        try:
            # Criar uma conexão limpa SÓ PARA O PANDAS
            conn_pd = sqlite3.connect(self.db_path)
            df_linhas_pendentes = pd.read_sql_query(
                "SELECT id, descricao FROM linha_ime WHERE embedding IS NULL AND (descricao IS NOT NULL AND descricao != '')",
                conn_pd # <-- Usar a conexão limpa
            )
        except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
            print(f"Erro ao ler linhas pendentes: {e}")
            if conn_pd:
                conn_pd.close()
            return 0
        finally:
            # Fechar a conexão do pandas
            if conn_pd:
                conn_pd.close()

        if df_linhas_pendentes.empty:
            print("[Embeddings] Nenhuma linha de pesquisa pendente encontrada.")
            # Não precisamos fechar 'conn' aqui, pois 'conn_pd' já foi fechada.
            return 0

        print(f"[Embeddings] Calculando embeddings para {len(df_linhas_pendentes)} linhas...")
        try:
            embeddings = self.model.encode(df_linhas_pendentes['descricao'].tolist(), show_progress_bar=True)
            print("[Embeddings] Cálculo concluído. Salvando no banco de dados...")
        except Exception as e:
            print(f"Erro durante o encode do modelo: {e}")
            # conn.close() foi removido daqui pois 'conn' não existe neste escopo
            return 0

        # Salvar embeddings no banco
        embeddings_saved_count = 0
        update_data = []

        # --- CORREÇÃO: Usar tolist() para evitar problemas de indexação com iloc ---
        # Criamos uma lista de IDs que corresponde à ordem dos embeddings
        ids_list = df_linhas_pendentes['id'].tolist()

        for index, embedding in enumerate(embeddings):
            # Usamos o 'index' para pegar o ID da 'ids_list' na mesma ordem
            linha_id = int(ids_list[index])
            embedding_blob = embedding.astype(np.float32).tobytes()
            update_data.append((embedding_blob, linha_id))

        # --- CORREÇÃO: Obter uma nova conexão (com row_factory) SÓ PARA SALVAR ---
        conn_save = self._get_db_conn()
        if not conn_save:
            print("Erro de DB: Não foi possível conectar para salvar embeddings.")
            return 0

        try:
            cursor = conn_save.cursor()
            cursor.executemany("UPDATE linha_ime SET embedding = ? WHERE id = ?", update_data)
            conn_save.commit()
            embeddings_saved_count = len(update_data)
        except sqlite3.Error as update_err:
             print(f"Erro ao salvar embeddings em lote: {update_err}")
             conn_save.rollback()
        finally:
             conn_save.close() # <-- Fechar a conn_save

        print(f"[Embeddings] {embeddings_saved_count}/{len(df_linhas_pendentes)} Embeddings salvos.")
        return embeddings_saved_count

    # --- NOVO MÉTODO: Buscar matches para notificar ---
    def get_novos_matches_para_notificar(self, limiar_score):
        """
        Busca matches acima de um limiar que ainda não foram notificados.
        Junta com edital (para link/prazo) e linha_ime (para emails).
        """
        conn = self._get_db_conn()
        if not conn:
            print("[Notificador] Erro: Não foi possível conectar ao DB para buscar matches.")
            return []

        # Este query junta as 3 tabelas para pegar todas as infos necessárias
        query = """
        SELECT
            m.edital_id, m.linha_id, m.score,
            m.edital_titulo, m.linha_nome, m.programa,
            e.link_pagina, e.prazo_submissao,
            l.emails_contato
        FROM match AS m
        JOIN edital AS e ON m.edital_id = e.id
        JOIN linha_ime AS l ON m.linha_id = l.id
        WHERE m.notificado = FALSE AND m.score >= ?
        ORDER BY l.id, m.score DESC;
        """
        try:
            cursor = conn.cursor()
            matches = cursor.execute(query, (limiar_score,)).fetchall()
            return matches
        except sqlite3.Error as e:
            print(f"Erro ao buscar matches para notificar: {e}")
            return []
        finally:
            if conn:
                conn.close()

    # --- NOVO MÉTODO: Marcar matches como notificados ---
    def marcar_matches_como_notificados(self, match_keys):
        """
        Marca uma lista de matches (tuplas (edital_id, linha_id)) como notificados.
        """
        conn = self._get_db_conn()
        if not conn or not match_keys:
            print("[Notificador] Erro: Não foi possível conectar ao DB para marcar matches.")
            return False

        query = "UPDATE match SET notificado = TRUE WHERE edital_id = ? AND linha_id = ?"
        try:
            cursor = conn.cursor()
            # Usar executemany para atualizar em lote
            cursor.executemany(query, match_keys)
            conn.commit()
            print(f"[Notificador] Marcados {len(match_keys)} matches como notificados no DB.")
            return True
        except sqlite3.Error as e:
            print(f"Erro ao marcar matches em lote como notificados: {e}")
            conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

