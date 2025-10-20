import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import os

# --- IMPORTS MOVIMENTADOS PARA O TOPO DO FICHEIRO ---
# Estas bibliotecas precisam de estar sempre disponíveis
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

class MotorDeCompatibilidade:
    """
    Encapsula toda a lógica de filtragem, cálculo de similaridade por IA e
    ranking de compatibilidade entre editais e linhas de pesquisa.
    """
    def __init__(self, load_model=False):
        """
        Construtor da classe. Pode ser inicializado em modo leve (para o site)
        ou modo pesado (para o worker que calcula a IA).
        """
        # Carrega as configurações do .env ou usa valores padrão
        self.db_type = os.getenv("DB_TYPE")
        self.database_url = os.getenv("DATABASE_URL")
        self.coluna_elegibilidade = os.getenv("COLUNA_EDITAL_ELEGIBILIDADE", "texto_pdf")
        self.coluna_status = os.getenv("COLUNA_EDITAL_STATUS", "status")

        self.engine = self._get_database_engine()
        self.model = None  # O modelo de IA começa como nulo

        if load_model:
            print("Carregando modelo de IA na memória (modo worker)...")
            # A inicialização do modelo pesado acontece apenas aqui
            self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            print("Modelo de IA carregado com sucesso.")
        else:
            print("Motor de IA inicializado em modo de leitura (sem carregar o modelo).")

    def _get_database_engine(self):
        """Método auxiliar para criar a conexão com o banco de dados."""
        if self.database_url:
            # Usa a URL de conexão do Render (PostgreSQL)
            return create_engine(self.database_url)
        elif self.db_type == "sqlite":
            # Usa um arquivo SQLite local para desenvolvimento
            return create_engine(f'sqlite:///{os.getenv("DB_NAME", "projeto.db")}')
        raise ValueError("Configuração de banco de dados não encontrada no .env")

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

    def obter_linhas_de_pesquisa(self) -> pd.DataFrame:
        """Busca todas as linhas de pesquisa do banco para popular a interface."""
        df_linhas = pd.read_sql_table('linha_ime', self.engine)
        return df_linhas[['id', 'linha', 'programa']].sort_values(by=['programa', 'linha'])

    def encontrar_e_salvar_matches(self, top_n=5, limiar_minimo=0.68):
        """
        Método pesado, a ser executado pelo worker. Ele faz todo o pipeline de IA
        e salva os resultados na tabela 'match'.
        """
        if not self.model:
            raise Exception("O modelo de IA não foi carregado. Inicialize o motor com load_model=True.")

        print("Iniciando busca por matches para salvar no banco...")
        df_editais = pd.read_sql_table('edital', self.engine)
        df_editais_abertos = df_editais[df_editais[self.coluna_status] == 'aberto'].copy()
        df_editais_elegiveis = self._filtrar_por_elegibilidade(df_editais_abertos)

        if df_editais_elegiveis.empty:
            print("Nenhum edital elegível encontrado. Nenhum match para calcular.")
            return 0

        df_linhas = pd.read_sql_table('linha_ime', self.engine)
        if 'embedding' not in df_linhas.columns or df_linhas['embedding'].isnull().any():
            raise Exception("Embeddings não foram pré-calculados na tabela 'linha_ime'.")
        
        embeddings_linhas_precalculados = np.array([np.frombuffer(blob, dtype=np.float32) for blob in df_linhas['embedding']])
        textos_editais = (df_editais_elegiveis['titulo'] + '. ' + df_editais_elegiveis[self.coluna_elegibilidade]).tolist()
        embeddings_editais = self.model.encode(textos_editais, show_progress_bar=True)
        
        # A função cosine_similarity agora está sempre disponível
        matriz_similaridade = cosine_similarity(embeddings_editais, embeddings_linhas_precalculados)

        lista_matches = []
        for idx_linha, linha in df_linhas.iterrows():
            scores_para_esta_linha = matriz_similaridade[:, idx_linha]
            indices_top_n_editais = scores_para_esta_linha.argsort()[-top_n:][::-1]
            for idx_edital_na_matriz in indices_top_n_editais:
                score = scores_para_esta_linha[idx_edital_na_matriz]
                if score >= limiar_minimo:
                    edital = df_editais_elegiveis.iloc[idx_edital_na_matriz]
                    match = {
                        'edital_id': int(edital['id']),
                        'linha_id': int(linha['id']),
                        'score': round(float(score), 4),
                        'data_calculo': pd.Timestamp.now()
                    }
                    lista_matches.append(match)
        
        if not lista_matches:
            print("Nenhum match encontrado com os critérios atuais.")
            return 0
            
        df_matches = pd.DataFrame(lista_matches).drop_duplicates()
        
        print(f"Encontrados {len(df_matches)} matches. Salvando no banco de dados...")
        with self.engine.connect() as connection:
            # Apaga os matches antigos e insere os novos.
            # a tabela 'match' precisa existir no banco de dados.
            df_matches.to_sql('match', connection, if_exists='replace', index=False)
        
        return len(df_matches)

