# motor_ia.py
import sqlite3
import os
import numpy as np

# As importações pesadas só serão chamadas dentro dos métodos que as usam

class MotorDeCompatibilidade:
    def __init__(self, load_model=False):
        self.db_name = os.getenv("DB_NAME", "projeto_grande.db")
        # Constrói o caminho para o DB na mesma pasta do script
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.db_name)
        self.model = None

        if load_model:
            print("Carregando modelo de IA (modo worker)...")
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            print("Modelo de IA carregado.")
        else:
            print("Motor de IA em modo de leitura (ultra-leve).")

    def _get_db_conn(self):
        """Retorna uma conexão sqlite3 direta."""
        return sqlite3.connect(self.db_path)

    def _dict_factory(self, cursor, row):
        """Converte uma linha do banco de dados (tuple) em um dicionário."""
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def check_user(self, email, password):
        conn = self._get_db_conn()
        conn.row_factory = self._dict_factory
        cursor = conn.cursor()
        user = cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password)).fetchone()
        conn.close()
        return user

    def get_linhas_by_user(self, user_id):
        conn = self._get_db_conn()
        conn.row_factory = self._dict_factory
        cursor = conn.cursor()
        linhas = cursor.execute("SELECT * FROM linha_ime WHERE user_id = ? ORDER BY programa, linha", (user_id,)).fetchall()
        conn.close()
        return linhas

    def get_linha_by_id(self, linha_id, user_id):
        conn = self._get_db_conn()
        conn.row_factory = self._dict_factory
        cursor = conn.cursor()
        linha = cursor.execute("SELECT * FROM linha_ime WHERE id = ? AND user_id = ?", (linha_id, user_id)).fetchone()
        conn.close()
        return linha

    def add_linha(self, data, user_id):
        conn = self._get_db_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO linha_ime (programa, linha, descricao, emails_contato, user_id) VALUES (?, ?, ?, ?, ?)", 
                       (data['programa'], data['linha'], data['descricao'], data['emails_contato'], user_id))
        conn.commit()
        conn.close()

    def update_linha(self, linha_id, data, user_id):
        conn = self._get_db_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE linha_ime SET programa = ?, linha = ?, descricao = ?, emails_contato = ? WHERE id = ? AND user_id = ?",
                       (data['programa'], data['linha'], data['descricao'], data['emails_contato'], linha_id, user_id))
        conn.commit()
        conn.close()

    def obter_linhas_de_pesquisa_publico(self):
        conn = self._get_db_conn()
        conn.row_factory = self._dict_factory
        cursor = conn.cursor()
        linhas = cursor.execute("SELECT id, linha, programa FROM linha_ime ORDER BY programa, linha").fetchall()
        conn.close()
        return linhas

    def encontrar_matches_publico(self):
        conn = self._get_db_conn()
        conn.row_factory = self._dict_factory
        cursor = conn.cursor()
        try:
            matches = cursor.execute("SELECT * FROM match").fetchall()
            conn.close()
            return matches
        except sqlite3.OperationalError: # A tabela 'match' pode não existir
            conn.close()
            return []

    def get_edital_details(self, edital_id):
        conn = self._get_db_conn()
        conn.row_factory = self._dict_factory
        cursor = conn.cursor()
        detalhes = cursor.execute("SELECT * FROM edital WHERE id = ?", (edital_id,)).fetchone()
        conn.close()
        return detalhes

    # Este método pesado continua a usar Pandas e SQLAlchemy, pois só é chamado pelo worker
    def encontrar_e_salvar_matches(self, top_n=5, limiar_minimo=0.60):
        if self.model is None:
            raise Exception("O motor de IA não foi carregado. Inicialize com load_model=True.")
        
        from sqlalchemy import create_engine
        import pandas as pd
        from sklearn.metrics.pairwise import cosine_similarity

        engine = create_engine(f'sqlite:///{self.db_path}')
        df_editais = pd.read_sql_table('edital', engine)
        df_linhas = pd.read_sql_table('linha_ime', engine)
        
        # Lógica de filtro e cálculo de similaridade
        df_editais_abertos = df_editais[df_editais['status'] == 'aberto'].copy()
        df_editais_elegiveis = self._filtrar_por_elegibilidade(df_editais_abertos)
        if df_editais_elegiveis.empty: return 0

        if 'embedding' not in df_linhas.columns or df_linhas['embedding'].isnull().any():
             raise Exception("Embeddings não foram pré-calculados.")
        
        embeddings_linhas = np.array([np.frombuffer(blob, dtype=np.float32) for blob in df_linhas['embedding'].dropna()])
        textos_editais = (df_editais_elegiveis['titulo'] + '. ' + df_editais_elegiveis['texto_pdf']).tolist()
        embeddings_editais = self.model.encode(textos_editais, show_progress_bar=False)
        matriz_similaridade = cosine_similarity(embeddings_editais, embeddings_linhas)

        lista_matches = []
        for idx_linha, linha in df_linhas.iterrows():
            scores_para_esta_linha = matriz_similaridade[:, idx_linha]
            indices_top_n = scores_para_esta_linha.argsort()[-top_n:][::-1]
            for idx_edital in indices_top_n:
                score = scores_para_esta_linha[idx_edital]
                if score >= limiar_minimo:
                    edital = df_editais_elegiveis.iloc[idx_edital]
                    match = {
                        'edital_id': int(edital['id']),
                        'edital_titulo': edital['titulo'],
                        'linha_id': int(linha['id']),
                        'linha_nome': linha['linha'],
                        'programa': linha['programa'],
                        'score': round(float(score), 4)
                    }
                    lista_matches.append(match)
        
        if not lista_matches: return 0
            
        df_matches = pd.DataFrame(lista_matches).drop_duplicates()
        with engine.connect() as connection:
            df_matches.to_sql('match', connection, if_exists='replace', index=False)
        return len(df_matches)