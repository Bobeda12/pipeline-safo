import sqlite3
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

NOME_BANCO_DADOS = 'projeto_grande.db'
ID_LINHA_PARA_TESTAR = 15 # Vamos testar com a linha de pesquisa de ID = 15 (você pode mudar esse número)
TOP_N_RESULTADOS = 10 # Quantos dos melhores resultados queremos ver

def teste_focado():
    """
    Simula o caso de uso real: encontra os melhores editais para UMA linha de pesquisa.
    """
    print("--- Iniciando Teste Focado ---")
    engine = create_engine(f'sqlite:///{NOME_BANCO_DADOS}')
    
    # 1. Carregar a linha de pesquisa específica e seu embedding
    print(f"Carregando a linha de pesquisa com ID={ID_LINHA_PARA_TESTAR}...")
    df_linha_unica = pd.read_sql(f"SELECT * FROM linha_ime WHERE id = {ID_LINHA_PARA_TESTAR}", engine)
    
    if df_linha_unica.empty:
        print(f"ERRO: Linha de pesquisa com ID {ID_LINHA_PARA_TESTAR} não encontrada.")
        return
        
    linha_especifica = df_linha_unica.iloc[0]
    embedding_linha = np.frombuffer(linha_especifica['embedding'], dtype=np.float32).reshape(1, -1)
    
    print(f"Linha selecionada: '{linha_especifica['linha']}'")
    print(f"Descrição: '{linha_especifica['descricao']}'\n")

    # 2. Carregar TODOS os editais
    print("Carregando todos os editais...")
    df_editais = pd.read_sql_table('edital', engine)

    # 3. Gerar embeddings para todos os editais
    print("Carregando modelo de embedding...")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    print(f"Gerando embeddings para os {len(df_editais)} editais...")
    textos_editais = (df_editais['titulo'] + '. ' + df_editais['texto_pdf']).tolist()
    embeddings_editais = model.encode(textos_editais, show_progress_bar=True)

    # 4. Calcular similaridade entre a LINHA ÚNICA e TODOS os editais
    print("Calculando similaridade...")
    scores = cosine_similarity(embedding_linha, embeddings_editais)

    # 5. Organizar e mostrar os melhores resultados
    df_editais['score'] = scores[0] # scores[0] porque só temos uma linha na matriz de similaridade
    
    # Ordena o DataFrame pelo score, do maior para o menor
    df_resultados = df_editais.sort_values(by='score', ascending=False)
    
    print(f"\n--- TOP {TOP_N_RESULTADOS} EDITAIS MAIS ADERENTES À LINHA DE PESQUISA '{linha_especifica['linha']}' ---")
    
    # Exibe os melhores N resultados formatados
    for index, row in df_resultados.head(TOP_N_RESULTADOS).iterrows():
        print(f"  - Score: {row['score']:.4f} | Título do Edital: {row['titulo']}")

if __name__ == '__main__':
    teste_focado()