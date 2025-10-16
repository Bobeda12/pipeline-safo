import pandas as pd
import sqlite3
import numpy as np
from sqlalchemy import create_engine
from sentence_transformers import SentenceTransformer
import os

NOME_BANCO_DADOS = os.getenv("DB_NAME", "projeto_grande.db")

def gerar_e_salvar_embeddings_ime():
    """
    Gera os embeddings para todas as linhas de pesquisa do IME e os salva no banco.
    """
    engine = create_engine(f'sqlite:///{NOME_BANCO_DADOS}')
    
    try:
        df_linhas = pd.read_sql_table('linha_ime', engine)
    except Exception as e:
        print(f"Erro ao ler a tabela 'linha_ime': {e}")
        print("Certifique-se de que o banco de dados foi criado corretamente com 'gerar_banco_grande.py'.")
        return

    if df_linhas.empty:
        print("A tabela 'linha_ime' está vazia. Nada para processar.")
        return

    print("Carregando modelo de embedding... (pode demorar na primeira vez)")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    print(f"Gerando embeddings para {len(df_linhas)} linhas de pesquisa do IME...")
    textos_linhas = df_linhas['descricao'].tolist()
    embeddings_linhas = model.encode(textos_linhas, show_progress_bar=True)
    
    print("Salvando embeddings no banco de dados...")
    conn = sqlite3.connect(NOME_BANCO_DADOS)
    cursor = conn.cursor()
    
    for index, embedding in enumerate(embeddings_linhas):
        linha_id = int(df_linhas.iloc[index]['id'])
        embedding_blob = embedding.astype(np.float32).tobytes()
        
        cursor.execute("UPDATE linha_ime SET embedding = ? WHERE id = ?", (embedding_blob, linha_id))

    conn.commit()
    conn.close()
    print("Embeddings das linhas do IME salvos com sucesso!")

if __name__ == '__main__':
    gerar_e_salvar_embeddings_ime()

