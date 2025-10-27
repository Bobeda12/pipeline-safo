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
            matches = cursor.execute("SELECT * FROM match ORDER BY edital_id, score DESC").fetchall()
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

    # --- Método pesado de cálculo (sem alterações) ---
    def encontrar_e_salvar_matches(self, top_n=5, limiar_minimo=0.10):
        # ... (código existente mantido) ...
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
            if conn_pd: conn_pd.close() # Garante fechamento
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

        df_editais_abertos = df_editais[df_editais['status'] == 'aberto'].copy()
        
        df_editais_elegiveis = df_editais_abertos
        
        if df_editais_elegiveis.empty:
            print("Nenhum edital aberto encontrado.")
            return 0

        if 'embedding' not in df_linhas.columns or df_linhas['embedding'].isnull().all():
             print("AVISO: Coluna 'embedding' faltando ou vazia.")
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
        for idx_linha_relativo, (linha_id_real, linha) in enumerate(df_linhas_com_embedding.iterrows()): # Use iterrows para obter ID real
            scores_para_esta_linha = matriz_similaridade[:, idx_linha_relativo]
            indices_top_n_relativos = np.argsort(scores_para_esta_linha)[-top_n:][::-1]
            for idx_edital_relativo in indices_top_n_relativos:
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

        if not lista_matches:
            print("Nenhum match encontrado acima do limiar.")
            return 0

        conn_save = self._get_db_conn()
        if not conn_save:
            print("Erro: Não foi possível conectar ao DB para salvar matches.")
            return 0
        try:
            cursor = conn_save.cursor()
            cursor.execute("DELETE FROM match")
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

