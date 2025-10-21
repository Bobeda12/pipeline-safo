# motor_ia.py
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import os
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

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
        if self.db_type == "sqlite":
            return create_engine(f'sqlite:///{self.db_name}')
        raise ValueError("Tipo de banco de dados não suportado.")

    def _filtrar_por_elegibilidade(self, df: pd.DataFrame) -> pd.DataFrame:
        PALAVRAS_CHAVE_POSITIVAS = ['ict', 'instituição de ciência', 'instituições de pesquisa', 'universidade', 'pública']
        PALAVRAS_CHAVE_NEGATIVAS = ['exclusivo para empresas', 'somente mei', 'apenas para startups']
        
        # Filtra para manter apenas linhas com palavras-chave positivas
        df_positivo = df[df[self.coluna_elegibilidade].str.contains('|'.join(PALAVRAS_CHAVE_POSITIVAS), case=False, na=False)]
        # Do resultado, remove as linhas que contêm palavras-chave negativas
        df_final = df_positivo[~df_positivo[self.coluna_elegibilidade].str.contains('|'.join(PALAVRAS_CHAVE_NEGATIVAS), case=False, na=False)]
        return df_final
    
    def check_user(self, email, password):
        with self.engine.connect() as connection:
            query = text("SELECT * FROM users WHERE email = :email AND password = :password")
            result = connection.execute(query, {"email": email, "password": password}).fetchone()
            return result

    def get_linhas_by_user(self, user_id):
        return pd.read_sql(f"SELECT * FROM linha_ime WHERE user_id = {user_id}", self.engine).sort_values(by='linha')

    def get_linha_by_id(self, linha_id, user_id):
        df = pd.read_sql(f"SELECT * FROM linha_ime WHERE id = {linha_id} AND user_id = {user_id}", self.engine)
        return df.iloc[0].to_dict() if not df.empty else None

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

    def obter_linhas_de_pesquisa_publico(self) -> pd.DataFrame:
        return pd.read_sql_table('linha_ime', self.engine)[['id', 'linha', 'programa']].sort_values(by=['programa', 'linha'])

    def encontrar_matches_publico(self) -> pd.DataFrame:
        try:
            return pd.read_sql_table('match', self.engine)
        except ValueError:
            return pd.DataFrame()

    def encontrar_e_salvar_matches(self, top_n=5, limiar_minimo=0.6):
        if self.model is None:
            raise Exception("O motor de IA não foi carregado. Inicialize com load_model=True.")
        
        print(f"[DEBUG motor] Iniciando encontrar_e_salvar_matches com limiar={limiar_minimo}")
        
        df_editais = pd.read_sql_table('edital', self.engine)
        df_editais_abertos = df_editais[df_editais[self.coluna_status] == 'aberto'].copy()
        df_editais_elegiveis = self._filtrar_por_elegibilidade(df_editais_abertos)

        if df_editais_elegiveis.empty: 
            print("[DEBUG motor] Nenhum edital elegível encontrado após o filtro inicial.")
            return 0

        df_linhas = pd.read_sql_table('linha_ime', self.engine)
        if 'embedding' not in df_linhas.columns or df_linhas['embedding'].isnull().any():
             print("[DEBUG motor] ERRO: Embeddings não encontrados na tabela linha_ime.")
             raise Exception("Embeddings não foram pré-calculados.")
        
        print(f"[DEBUG motor] Encontrados {len(df_editais_elegiveis)} editais elegíveis e {len(df_linhas)} linhas de pesquisa com embeddings.")
        
        embeddings_linhas = np.array([np.frombuffer(blob, dtype=np.float32) for blob in df_linhas['embedding'].dropna()])
        
        textos_editais = (df_editais_elegiveis['titulo'] + '. ' + df_editais_elegiveis[self.coluna_elegibilidade]).tolist()
        embeddings_editais = self.model.encode(textos_editais, show_progress_bar=False)
        
        matriz_similaridade = cosine_similarity(embeddings_editais, embeddings_linhas)
        print(f"[DEBUG motor] Matriz de similaridade calculada com shape: {matriz_similaridade.shape}")

        lista_matches = []
        scores_maximos_por_linha = {} 

        for idx_linha, linha in df_linhas.iterrows():
            scores_para_esta_linha = matriz_similaridade[:, idx_linha]
            scores_maximos_por_linha[linha['id']] = scores_para_esta_linha.max() 
            
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
        
        print("\n[DEBUG motor] Scores máximos encontrados por linha (amostra dos 10 primeiros):")
        count = 0
        for linha_id, max_score in sorted(scores_maximos_por_linha.items(), key=lambda item: item[1], reverse=True):
             if count < 10:
                 print(f"  Linha ID {linha_id}: {max_score:.4f}")
                 count += 1
             else:
                 break

        if not lista_matches: 
            print(f"\n[DEBUG motor] Nenhum match encontrado com limiar {limiar_minimo}. Verifique os scores máximos acima.")
            with self.engine.connect() as connection:
                pd.DataFrame(columns=['edital_id', 'edital_titulo', 'linha_id', 'linha_nome', 'programa', 'score']).to_sql('match', connection, if_exists='replace', index=False)
            print("[DEBUG motor] Tabela 'match' criada vazia para evitar erros.")
            return 0
            
        df_matches = pd.DataFrame(lista_matches).drop_duplicates()
        print(f"\n[DEBUG motor] {len(df_matches)} matches encontrados acima do limiar. Salvando...")
        with self.engine.connect() as connection:
            df_matches.to_sql('match', connection, if_exists='replace', index=False)
        print("[DEBUG motor] Matches salvos na tabela 'match'.")
        return len(df_matches)

    def get_edital_details(self, edital_id):
        df = pd.read_sql(f"SELECT * FROM edital WHERE id = {edital_id}", self.engine)
        return df.iloc[0].to_dict() if not df.empty else None