import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import os

class MotorDeCompatibilidade:
    def __init__(self):
        self.db_type = os.getenv("DB_TYPE", "sqlite")
        self.db_name = os.getenv("DB_NAME", "projeto_grande.db")
        self.coluna_elegibilidade = os.getenv("COLUNA_EDITAL_ELEGIBILIDADE", "texto_pdf")
        self.coluna_status = os.getenv("COLUNA_EDITAL_STATUS", "status")
        self.engine = self._get_database_engine()
        print("Carregando modelo de IA na memória...")
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        print("Modelo de IA carregado.")

    def _get_database_engine(self):
        if self.db_type == "sqlite":
            return create_engine(f'sqlite:///{self.db_name}')
        raise ValueError("Tipo de banco de dados não suportado.")

    def _filtrar_por_elegibilidade(self, df: pd.DataFrame) -> pd.DataFrame:
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

    def check_user(self, email, password):
        with self.engine.connect() as connection:
            query = text("SELECT id, email FROM users WHERE email = :email AND password = :password")
            result = connection.execute(query, {"email": email, "password": password}).fetchone()
            return result

    def get_linhas_by_user(self, user_id):
        df = pd.read_sql(f"SELECT * FROM linha_ime WHERE user_id = {user_id}", self.engine)
        return df.sort_values(by=['programa', 'linha'])

    def get_linha_by_id(self, linha_id, user_id):
        """
        CORREÇÃO: Busca uma linha e retorna como um dicionário Python simples,
        garantindo que ela pertence ao usuário logado.
        """
        with self.engine.connect() as connection:
            query = text("SELECT * FROM linha_ime WHERE id = :id AND user_id = :user_id")
            result = connection.execute(query, {"id": linha_id, "user_id": user_id}).mappings().first()
            return result # Retorna um dicionário ou None

    def add_linha(self, data, user_id):
        data['user_id'] = user_id
        with self.engine.connect() as connection:
            query = text("INSERT INTO linha_ime (programa, linha, descricao, emails_contato, user_id) VALUES (:programa, :linha, :descricao, :emails_contato, :user_id)")
            connection.execute(query, data)
            connection.commit()
        print("Nova linha adicionada. Lembre-se de recalcular os embeddings.")

    def update_linha(self, linha_id, data, user_id):
        data['id'] = linha_id
        data['user_id'] = user_id
        with self.engine.connect() as connection:
            query = text("UPDATE linha_ime SET programa = :programa, linha = :linha, descricao = :descricao, emails_contato = :emails_contato WHERE id = :id AND user_id = :user_id")
            result = connection.execute(query, data)
            connection.commit()
            # Verifica se alguma linha foi de fato alterada (segurança extra)
            if result.rowcount == 0:
                raise Exception("Update falhou: ou a linha não existe ou o usuário não tem permissão.")
        print("Linha atualizada.")

    def get_edital_details(self, edital_id):
        df = pd.read_sql(f"SELECT * FROM edital WHERE id = {edital_id}", self.engine)
        return df.iloc[0] if not df.empty else None
    
    def obter_linhas_de_pesquisa(self) -> pd.DataFrame:
        df_linhas = pd.read_sql_table('linha_ime', self.engine)
        return df_linhas[['id', 'linha', 'programa']].sort_values(by=['programa', 'linha'])

    def encontrar_matches(self, top_n=5, limiar_minimo=0.68) -> pd.DataFrame:
        df_editais = pd.read_sql_table('edital', self.engine)
        df_editais_abertos = df_editais[df_editais[self.coluna_status] == 'aberto'].copy()
        df_editais_elegiveis = self._filtrar_por_elegibilidade(df_editais_abertos)

        if df_editais_elegiveis.empty: return pd.DataFrame()

        df_linhas = pd.read_sql_table('linha_ime', self.engine)
        if 'embedding' not in df_linhas.columns or df_linhas['embedding'].isnull().all():
             print("AVISO: Embeddings não foram pré-calculados para nenhuma linha. A busca de matches não retornará resultados.")
             return pd.DataFrame()
        
        df_linhas_com_embedding = df_linhas.dropna(subset=['embedding']).reset_index(drop=True)
        if df_linhas_com_embedding.empty:
            return pd.DataFrame()
            
        embeddings_linhas_precalculados = np.array([np.frombuffer(blob, dtype=np.float32) for blob in df_linhas_com_embedding['embedding']])
        
        textos_editais = (df_editais_elegiveis['titulo'] + '. ' + df_editais_elegiveis[self.coluna_elegibilidade]).tolist()
        embeddings_editais = self.model.encode(textos_editais, show_progress_bar=False)
        
        matriz_similaridade = cosine_similarity(embeddings_editais, embeddings_linhas_precalculados)

        lista_matches = []
        for idx_linha, linha in df_linhas_com_embedding.iterrows():
            scores_para_esta_linha = matriz_similaridade[:, idx_linha]
            indices_top_n_editais = scores_para_esta_linha.argsort()[-top_n:][::-1]
            for idx_edital_na_matriz in indices_top_n_editais:
                score = scores_para_esta_linha[idx_edital_na_matriz]
                if score >= limiar_minimo:
                    edital = df_editais_elegiveis.iloc[idx_edital_na_matriz]
                    match = { 'edital_id': int(edital['id']), 'edital_titulo': edital['titulo'], 'linha_id': int(linha['id']), 'linha_nome': linha['linha'], 'programa': linha['programa'], 'score': round(float(score), 4) }
                    lista_matches.append(match)
        
        if not lista_matches: return pd.DataFrame()
        return pd.DataFrame(lista_matches).drop_duplicates()

