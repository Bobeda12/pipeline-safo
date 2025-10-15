import pandas as pd
import sqlite3
import numpy as np
from sqlalchemy import create_engine
from sentence_transformers import SentenceTransformer

NOME_BANCO_DADOS = 'projeto_grande.db'

def preparar_banco_para_embeddings():
    """
    Adiciona uma coluna 'embedding' à tabela linha_ime se ela não existir.
    """
    print("Verificando e preparando o banco de dados...")
    conn = sqlite3.connect(NOME_BANCO_DADOS)
    cursor = conn.cursor()
    
    try:
        # Tenta adicionar a coluna. Se já existir, um erro ocorrerá.
        cursor.execute("ALTER TABLE linha_ime ADD COLUMN embedding BLOB;")
        print("Coluna 'embedding' adicionada à tabela 'linha_ime'.")
    except sqlite3.OperationalError as e:
        # Se o erro for "duplicate column name", a coluna já existe, o que é ok.
        if "duplicate column name" in str(e):
            print("Coluna 'embedding' já existe.")
        else:
            raise e # Lança outros erros
            
    conn.commit()
    conn.close()

def gerar_e_salvar_embeddings_ime():
    """
    Gera os embeddings para todas as linhas de pesquisa do IME e os salva no banco.
    """
    preparar_banco_para_embeddings()
    
    engine = create_engine(f'sqlite:///{NOME_BANCO_DADOS}')
    df_linhas = pd.read_sql_table('linha_ime', engine)

    # Verifica se já existem embeddings para não reprocessar desnecessariamente
    if 'embedding' in df_linhas.columns and df_linhas['embedding'].notna().all():
        print("Embeddings para todas as linhas do IME já parecem estar calculados. Encerrando.")
        return

    print("Carregando modelo de embedding... (pode demorar na primeira vez)")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    print("Gerando embeddings para as linhas de pesquisa do IME...")
    # Usamos a descrição para gerar o embedding
    textos_linhas = df_linhas['descricao'].tolist()
    embeddings_linhas = model.encode(textos_linhas, show_progress_bar=True)
    
    print("Salvando embeddings no banco de dados...")
    conn = sqlite3.connect(NOME_BANCO_DADOS)
    cursor = conn.cursor()
    
    for index, embedding in enumerate(embeddings_linhas):
        linha_id = df_linhas.iloc[index]['id']
        # Converte o array numpy para bytes (BLOB) para salvar no SQLite
        embedding_blob = embedding.astype(np.float32).tobytes()
        
        cursor.execute("UPDATE linha_ime SET embedding = ? WHERE id = ?", (embedding_blob, int(linha_id)))

    conn.commit()
    conn.close()
    print("Embeddings das linhas do IME salvos com sucesso!")

if __name__ == '__main__':
    # Você pode precisar rodar o script original uma vez para criar o banco de dados
    # ou garantir que ele exista antes de executar este.
    gerar_e_salvar_embeddings_ime()