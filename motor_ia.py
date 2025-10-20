# motor_ia.py
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import os

class MotorDeCompatibilidade:
    def __init__(self, load_model=False):
        self.db_type = os.getenv("DB_TYPE", "sqlite")
        self.db_name = os.getenv("DB_NAME", "projeto_grande.db")
        self.coluna_elegibilidade = os.getenv("COLUNA_EDITAL_ELEGIBILIDADE", "texto_pdf")
        self.coluna_status = os.getenv("COLUNA_EDITAL_STATUS", "status")
        self.engine = self._get_database_engine()
        self.model = None
        if load_model:
            print("Carregando modelo de IA (modo worker)...")
            self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            print("Modelo de IA carregado.")
        else:
            print("Motor de IA em modo de leitura (sem modelo).")

    def _get_database_engine(self):
        # ... (código desta função permanece o mesmo)
        if self.db_type == "sqlite":
             return create_engine(f'sqlite:///{self.db_name}')
        # Adicionar outras lógicas de conexão aqui se necessário
        raise ValueError("Tipo de banco de dados não suportado.")

    def _filtrar_por_elegibilidade(self, df: pd.DataFrame) -> pd.DataFrame:
        # ... (código desta função permanece o mesmo)
        PALAVRAS_CHAVE_POSITIVAS = ['ict', 'instituição de ciência', 'instituições de pesquisa', 'universidade', 'pública']
        PALAVRAS_CHAVE_NEGATIVAS = ['exclusivo para empresas', 'somente mei', 'apenas para startups']
        indices_para_manter = []
        for index, row in df.iterrows():
            texto = str(row[self.coluna_elegibilidade]).lower()
            if any(palavra in texto for palavra in PALAVRAS_CHAVE_NEGATIVAS):
                continue
            if any(palavra in texto for palavra in PALAVRAS_CHAVE_POSITIVAS):
                indices_para_manter.append(index)
        return df.loc[indices_para_manter]
    
    # --- MÉTODOS DE GERENCIAMENTO CORRIGIDOS ---
    def check_user(self, email, password):
        with self.engine.connect() as connection:
            query = text("SELECT * FROM users WHERE email = :email AND password = :password")
            result = connection.execute(query, {"email": email, "password": password}).fetchone()
            return result

    def get_linhas_by_user(self, user_id):
        df = pd.read_sql(f"SELECT * FROM linha_ime WHERE user_id = {user_id}", self.engine)
        return df.sort_values(by=['programa', 'linha'])

    def get_linha_by_id(self, linha_id, user_id):
        df = pd.read_sql(f"SELECT * FROM linha_ime WHERE id = {linha_id} AND user_id = {user_id}", self.engine)
        return df.iloc[0] if not df.empty else None

    def add_linha(self, data, user_id):
        data['user_id'] = user_id
        with self.engine.connect() as connection:
            query = text("""INSERT INTO linha_ime (programa, linha, descricao, emails_contato, user_id) VALUES (:programa, :linha, :descricao, :emails_contato, :user_id)""")
            connection.execute(query, data)
            connection.commit()

    def update_linha(self, linha_id, data, user_id):
        data['id'] = linha_id
        data['user_id'] = user_id
        with self.engine.connect() as connection:
            query = text("""UPDATE linha_ime SET programa = :programa, linha = :linha, descricao = :descricao, emails_contato = :emails_contato WHERE id = :id AND user_id = :user_id""")
            connection.execute(query, data)
            connection.commit()

    # --- MÉTODOS DE BUSCA PÚBLICOS ---
    def obter_linhas_de_pesquisa_publico(self) -> pd.DataFrame:
        """Busca TODAS as linhas de pesquisa para o dashboard público."""
        df_linhas = pd.read_sql_table('linha_ime', self.engine)
        return df_linhas[['id', 'linha', 'programa']].sort_values(by=['programa', 'linha'])

    def encontrar_matches_publico(self) -> pd.DataFrame:
        """Busca TODOS os matches, que serão depois filtrados no frontend."""
        # Este método agora lê os matches da tabela 'match', que foi pré-calculada
        try:
            df_matches = pd.read_sql_table('match', self.engine)
            return df_matches
        except ValueError: # Tabela 'match' pode não existir ainda
            return pd.DataFrame()

    # --- MÉTODO PARA O WORKER ---
    def encontrar_e_salvar_matches(self, top_n=5, limiar_minimo=0.68):
        # ... (código desta função permanece o mesmo)
        # Este método deve ler os editais e linhas, e no final salvar na tabela 'match'
        # ...
        # No final, retorna o número de matches salvos
        # return len(df_matches)
        pass # Placeholder