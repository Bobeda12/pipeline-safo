import sqlite3
import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class MotorDeCompatibilidade:
    def __init__(self, load_model=False):
        self.db_name = os.getenv("DB_NAME", "projeto_grande.db")
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.db_name)
        self.model = None

        if load_model:
            print("Carregando modelo de IA (modo worker)...")
            self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            print("Modelo de IA carregado.")
        else:
            print("Motor de IA em modo de leitura (ultra-leve).")

    def _get_db_conn(self):
        """Retorna uma conexão sqlite3 direta."""
        return sqlite3.connect(self.db_path)

    def _dict_factory(self, cursor, row):
        """Converte uma linha do banco de dados em um dicionário."""
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
        except sqlite3.OperationalError:
            conn.close()
            return []

    def get_edital_details(self, edital_id):
        conn = self._get_db_conn()
        conn.row_factory = self._dict_factory
        cursor = conn.cursor()
        detalhes = cursor.execute("SELECT * FROM edital WHERE id = ?", (edital_id,)).fetchone()
        conn.close()
        return detalhes

    # Este método pesado continua a usar Pandas, pois só é chamado pelo worker
    def encontrar_e_salvar_matches(self, top_n=5, limiar_minimo=0.60):
        if self.model is None:
            raise Exception("Motor de IA não carregado.")
        
        engine = create_engine(f'sqlite:///{self.db_path}')
        df_editais = pd.read_sql_table('edital', engine)
        df_linhas = pd.read_sql_table('linha_ime', engine)

        # A lógica de filtro e cálculo de similaridade com Pandas continua aqui...
        # ...
        
        # Exemplo simplificado para manter o código completo
        # Substitua este bloco pelo código completo de encontrar_e_salvar_matches que já tínhamos
        print("Lógica de encontrar e salvar matches executada (simulado).")
        return 0

