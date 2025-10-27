import os
import time
import random
import pandas as pd
import numpy as np
import sqlite3 # Importa sqlite3 para manipulação direta
from faker import Faker
from sentence_transformers import SentenceTransformer
from motor_ia import MotorDeCompatibilidade # Importa a classe já configurada para SQLite
import traceback # Para log de erros
from dotenv import load_dotenv
import datetime # Importa datetime para conversão
from werkzeug.security import generate_password_hash # *** CORREÇÃO SEC-01: Importar hash ***

# Carrega variáveis de ambiente (pode ser útil para DB_NAME ou outras configs)
load_dotenv()

# --- CONFIGURAÇÕES UNIFICADAS ---
# Volta a usar o nome do arquivo SQLite local
DB_NAME = os.getenv("DB_NAME", "projeto_grande.db")
# Constrói o caminho absoluto para o DB na mesma pasta do script
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_NAME)

NUM_EDITAIS = 500
NUM_LINHAS_PESQUISA = 200
NUM_USUARIOS = 10

fake = Faker('pt_BR')

# --- Base de Conhecimento (Mantida igual) ---
AREAS_CONHECIMENTO = [
    {"area": "Inteligência Artificial", "programa": "PPGIA", "substantivos": ["algoritmos", "redes neurais", "aprendizado de máquina"], "verbos": ["otimizar", "desenvolver", "implementar"], "adjetivos": ["inteligente", "preditivo", "autônomo"]},
    {"area": "Computação Quântica", "programa": "PPGCQ", "substantivos": ["qubits", "algoritmos quânticos", "criptografia pós-quântica"], "verbos": ["projetar", "simular", "construir"], "adjetivos": ["quântico", "seguro", "robusto"]},
    {"area": "Energias Renováveis", "programa": "PPGER", "substantivos": ["energia solar", "energia eólica", "biomassa"], "verbos": ["gerar", "armazenar", "distribuir"], "adjetivos": ["sustentável", "limpa", "renovável"]}
]
FRASES_ELEGIBILIDADE = [
    "Este edital é aberto a toda instituição de ciência e tecnologia (ICT) do país.",
    "Universidades públicas e institutos de pesquisa são o público-alvo principal.",
    "Esta chamada é de uso exclusivo para empresas de base tecnlógica e startups."
]

# --- Funções de Geração (Mantidas iguais) ---
def gerar_linha_pesquisa(base):
    linha = f"Estudo de {random.choice(base['substantivos'])}"
    descricao = f"Análise e desenvolvimento de sistemas para {base['area']}, com foco em {random.choice(base['substantivos'])}."
    return linha, descricao

def gerar_edital(base):
    titulo = f"Chamada Pública nº {random.randint(1, 99)}/2025 - Fomento em {base['area']}"
    texto_base = f"O presente edital visa selecionar propostas para apoio financeiro a projetos em {base['area']}. "
    frase_elegibilidade = random.choice(FRASES_ELEGIBILIDADE)
    return titulo, texto_base + frase_elegibilidade

def run_complete_update():
    """
    Executa todo o pipeline LOCALMENTE: cria/recria o DB SQLite, popula,
    calcula embeddings e encontra matches.
    """
    print(f"--- INICIANDO TAREFA DE ATUALIZAÇÃO LOCAL (SQLite: {DB_PATH}) ---")
    start_time = time.time()
    conn = None # Inicializa conn fora do try para garantir que ele exista no finally

    # ETAPA 1: (Re)Criar DB e tabelas
    # Remove o banco antigo para garantir um estado limpo a cada execução
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print(f"Banco de dados '{DB_NAME}' existente removido.")
        except OSError as e:
            print(f"Erro ao remover banco de dados antigo: {e}. Tentando continuar...")

    try:
        conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES) # Adicionado detect_types
        
        # Habilitar suporte para tipos datetime (opcional, mas bom ter)
        # sqlite3.register_adapter(datetime.datetime, lambda val: val.isoformat())
        # sqlite3.register_converter("DATETIME", lambda val: datetime.datetime.fromisoformat(val.decode()))

        cursor = conn.cursor()

        print("[ETAPA 1] Criando tabelas...")
        # Criação das tabelas (com as colunas adicionais para edital e match)
        cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL);")
        cursor.execute("""
            CREATE TABLE edital (
                id INTEGER PRIMARY KEY,
                titulo TEXT,
                orgao TEXT,
                link_pagina TEXT,
                texto_pdf TEXT,
                status TEXT,
                modalidade TEXT,
                prazo_submissao DATETIME, -- Usar DATETIME
                valor_estimado TEXT,
                elegibilidade TEXT,
                areas_tema TEXT,
                data_captura DATETIME DEFAULT CURRENT_TIMESTAMP -- Usar DATETIME
            );
        """)
        cursor.execute("""
            CREATE TABLE linha_ime (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                programa TEXT,
                linha TEXT,
                descricao TEXT,
                emails_contato TEXT,
                embedding BLOB,
                user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        """)
        # Adicionada coluna 'notificado' e 'data_calculo' (opcional)
        cursor.execute("""
            CREATE TABLE match (
                edital_id INTEGER,
                edital_titulo TEXT,
                linha_id INTEGER,
                linha_nome TEXT,
                programa TEXT,
                score REAL,
                notificado BOOLEAN DEFAULT FALSE,
                data_calculo DATETIME DEFAULT CURRENT_TIMESTAMP, -- Usar DATETIME
                FOREIGN KEY (edital_id) REFERENCES edital (id),
                FOREIGN KEY (linha_id) REFERENCES linha_ime (id)
            );
        """)
        print("Tabelas criadas com sucesso.")

        # ETAPA 2: Popular com dados de teste
        print("[ETAPA 2] Gerando e inserindo dados simulados...")
        
        # *** CORREÇÃO SEC-01: Gerar hash para senhas ***
        hashed_password_admin = generate_password_hash('admin')
        hashed_password_user = generate_password_hash('123')
        
        users = [('admin@ime.br', hashed_password_admin)] + \
                [(f'user{i}@ime.br', hashed_password_user) for i in range(2, NUM_USUARIOS + 1)]
        
        cursor.executemany("INSERT INTO users (email, password) VALUES (?, ?);", users)
        actual_user_ids = list(range(1, NUM_USUARIOS + 1))
        print(f"{len(users)} usuários inseridos (com senhas hasheadas). IDs assumidos: {actual_user_ids}")

        linhas_data = []
        for _ in range(NUM_LINHAS_PESQUISA):
            base = random.choice(AREAS_CONHECIMENTO)
            linha, desc = gerar_linha_pesquisa(base)
            user_id = random.choice(actual_user_ids) # Usa os IDs assumidos/reais
            # Embedding é NULL inicialmente
            linhas_data.append((base['programa'], linha, desc, fake.email(), None, user_id))
        cursor.executemany("""
            INSERT INTO linha_ime (programa, linha, descricao, emails_contato, embedding, user_id)
            VALUES (?, ?, ?, ?, ?, ?);
        """, linhas_data)

        editais_data = []
        for i in range(1, NUM_EDITAIS + 1):
            base = random.choice(AREAS_CONHECIMENTO)
            titulo, texto_pdf = gerar_edital(base)
            prazo = fake.future_datetime(end_date='+60d')
            # *** CORREÇÃO: Converter Timestamp para objeto datetime padrão ***
            data_captura_dt = pd.Timestamp.now(tz='UTC').to_pydatetime()
            
            # *** CORREÇÃO BUG-01: Garantir que a URL seja absoluta ***
            link_pagina = f"http://www.{fake.domain_name()}/{fake.slug()}"

            editais_data.append((
                i, titulo, "FINEP", link_pagina, texto_pdf, "aberto",
                random.choice(["Nacional", "Regional"]), prazo, f"R$ {random.randint(50, 500)} mil",
                random.choice(FRASES_ELEGIBILIDADE), base['area'],
                data_captura_dt # Passar o objeto datetime padrão
            ))

            # DEBUG: Verificar alguns dados antes de inserir
        print(f"Verificando os primeiros 3 editais gerados para inserção:")
        for k in range(min(3, len(editais_data))):
            print(f"  Edital {k+1} - Status: '{editais_data[k][5]}', Link: '{editais_data[k][3]}'") # [5] é status, [3] é link

        # Inserção (código existente)
        cursor.executemany("""
            INSERT INTO edital (id, titulo, orgao, link_pagina, texto_pdf, status, modalidade, prazo_submissao, valor_estimado, elegibilidade, areas_tema, data_captura)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, editais_data)

        conn.commit() # Salva as inserções
        print(f"{len(linhas_data)} linhas e {len(editais_data)} editais inseridos.")

        # ETAPA 3: Calcular e salvar embeddings
        print("[ETAPA 3] Pré-calculando e salvando embeddings...")
        df_linhas = pd.read_sql_query("SELECT id, descricao FROM linha_ime WHERE descricao IS NOT NULL AND descricao != ''", conn)
        if df_linhas.empty:
            print("Nenhuma linha de pesquisa encontrada para calcular embeddings.")
        else:
            print(f"Calculando embeddings para {len(df_linhas)} linhas...")
            model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            embeddings = model.encode(df_linhas['descricao'].tolist(), show_progress_bar=True)

            print("Salvando embeddings no banco de dados SQLite...")
            embeddings_saved_count = 0
            
            # *** Otimização: Usar executemany para salvar embeddings ***
            update_data = []
            for index, embedding in enumerate(embeddings):
                linha_id = int(df_linhas.iloc[index]['id'])
                embedding_blob = embedding.astype(np.float32).tobytes()
                update_data.append((embedding_blob, linha_id))

            try:
                # Usar a mesma conexão, mas com um novo cursor para o executemany
                update_cursor = conn.cursor()
                update_cursor.executemany("UPDATE linha_ime SET embedding = ? WHERE id = ?", update_data)
                conn.commit()
                embeddings_saved_count = len(update_data)
            except sqlite3.Error as update_err:
                 print(f"Erro ao salvar embeddings em lote: {update_err}")

            print(f"{embeddings_saved_count}/{len(df_linhas)} Embeddings salvos.")

        # Fecha a conexão principal que foi usada pelo Pandas
        conn.close()
        conn = None # Marca como fechada

    except sqlite3.Error as e:
        print(f"Erro CRÍTICO durante a configuração/população do banco SQLite: {e}")
        traceback.print_exc()
        # Não precisa fechar conn aqui, o finally cuidará disso
        if conn: conn.close() # Garante fechamento em caso de erro
        exit(1)
    except ImportError:
         print("Erro: Verifique se Pandas e SentenceTransformers estão instalados ('pip install pandas sentence-transformers')")
         if conn: conn.close()
         exit(1)
    except Exception as e:
        print(f"Erro inesperado durante a Etapa 1, 2 ou 3: {e}")
        traceback.print_exc()
        if conn: conn.close()
        exit(1)
    finally:
        # Garante que a conexão seja fechada mesmo se ocorrer um erro
        if conn:
            conn.close()
            print("Conexão SQLite principal fechada.")


    # ETAPA 4: Encontrar e salvar matches (Usa a classe MotorDeCompatibilidade que agora usa SQLite)
    print("[ETAPA 4] Encontrando e salvando matches...")
    try:
        # Instancia o motor (agora configurado para SQLite e carregando o modelo)
        motor = MotorDeCompatibilidade(load_model=True)
        if motor.model:
            num_matches = motor.encontrar_e_salvar_matches()
            print(f"Processo de matches concluído. {num_matches} matches processados e salvos em '{DB_NAME}'.")
        else:
            print("Modelo de IA não carregado na instância do motor, pulando cálculo de matches.")
    except Exception as e:
        print(f"Erro ao instanciar ou rodar MotorDeCompatibilidade para matches: {e}")
        traceback.print_exc()

    end_time = time.time()
    print(f"--- ATUALIZAÇÃO LOCAL (SQLite) CONCLUÍDA EM {end_time - start_time:.2f} SEGUNDOS ---")

if __name__ == "__main__":
    run_complete_update()

