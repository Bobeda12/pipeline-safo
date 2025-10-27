import os
import sys
import time
import json
import requests
import io
import traceback
import subprocess # Para executar o Scrapy de forma robusta
import datetime
from dotenv import load_dotenv
from PyPDF2 import PdfReader # Para extrair texto do PDF
from motor_ia import MotorDeCompatibilidade
from werkzeug.security import generate_password_hash

# Carrega variáveis de ambiente
load_dotenv()

# --- Configurações ---
# Arquivo JSON temporário para onde o Scrapy salvará os dados
JSON_OUTPUT_FILE = 'editais_finep.json'
# Palavras-chave para pré-filtragem de elegibilidade (exemplo)
PALAVRAS_CHAVE_ELEGIBILIDADE_IGNORAR = ["empresa", "startup", "exclusivo para"]

# --- Funções Auxiliares ---

def extrair_texto_pdf(pdf_url):
    """
    Baixa um PDF de uma URL, extrai seu texto e o retorna como uma string.
    """
    print(f"  Baixando PDF de: {pdf_url[:50]}...")
    try:
        response = requests.get(pdf_url, timeout=30) # Timeout de 30s
        response.raise_for_status() # Lança erro se o request falhar
        
        # Usa BytesIO para ler o conteúdo em memória sem salvar em disco
        with io.BytesIO(response.content) as f:
            reader = PdfReader(f)
            texto_completo = ""
            for page in reader.pages:
                texto_completo += page.extract_text() + "\n"
        
        print(f"  PDF extraído com sucesso ({len(texto_completo)} caracteres).")
        return texto_completo
    except requests.exceptions.RequestException as e:
        print(f"  ERRO: Falha ao baixar o PDF {pdf_url}. Erro: {e}")
    except Exception as e:
        print(f"  ERRO: Falha ao processar o PDF {pdf_url}. Erro: {e}")
    return None # Retorna None em caso de falha

def parse_prazo(prazo_str):
    """
    Converte uma string de data 'DD/MM/AAAA' para um objeto datetime.date.
    """
    if not prazo_str or prazo_str == 'Prazo não encontrado':
        return None
    try:
        return datetime.datetime.strptime(prazo_str.strip(), '%d/%m/%Y').date()
    except ValueError:
        print(f"  AVISO: Não foi possível parsear a data '{prazo_str}'.")
        return None

# --- NOVA FUNÇÃO ---
def parse_data_publicacao(data_str):
    """
    Converte uma string de data 'DD/MM/AAAA' para um objeto datetime.date.
    """
    if not data_str or data_str == 'Não encontrada':
        return None
    try:
        return datetime.datetime.strptime(data_str.strip(), '%d/%m/%Y').date()
    except ValueError:
        print(f"  AVISO: Não foi possível parsear a data de publicação '{data_str}'.")
        return None

def seed_initial_data(motor):
    """
    Popula o banco com um usuário admin e linhas de pesquisa de exemplo
    APENAS SE o banco estiver vazio.
    """
    conn = motor._get_db_conn()
    if not conn: return
    try:
        cursor = conn.cursor()
        
        # 1. Adicionar usuário admin se não existir
        cursor.execute("SELECT COUNT(*) as count FROM users")
        if cursor.fetchone()['count'] == 0:
            print("[Seed Data] Banco de usuários vazio. Adicionando 'admin@ime.br'...")
            hashed_password_admin = generate_password_hash('admin')
            cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", ('admin@ime.br', hashed_password_admin))
            conn.commit()
        else:
            print("[Seed Data] Usuários já existem.")

        # 2. Adicionar linhas de pesquisa de exemplo se não existirem
        cursor.execute("SELECT COUNT(*) as count FROM linha_ime")
        if cursor.fetchone()['count'] == 0:
            print("[Seed Data] Tabela 'linha_ime' vazia. Adicionando dados de exemplo...")
            # Dados de exemplo (você pode expandir isso)
            linhas_data = [
                ('PPGIA', 'Aprendizado de Máquina', 'Pesquisa em algoritmos de aprendizado supervisionado e não supervisionado.', 'admin@ime.br', None, 1),
                ('PPGIA', 'Processamento de Linguagem Natural', 'Modelos para compreensão e geração de texto.', 'admin@ime.br', None, 1),
                ('PPGCQ', 'Algoritmos Quânticos', 'Desenvolvimento de algoritmos para computadores quânticos.', 'admin@ime.br', None, 1)
            ]
            cursor.executemany("""
                INSERT INTO linha_ime (programa, linha, descricao, emails_contato, embedding, user_id)
                VALUES (?, ?, ?, ?, ?, ?);
            """, linhas_data)
            conn.commit()
        else:
            print("[Seed Data] Linhas de pesquisa já existem.")

    except sqlite3.Error as e:
        print(f"Erro durante o seeding de dados: {e}")
        conn.rollback()
    finally:
        conn.close()


def run_finep_crawler(motor):
    """
    Executa o crawler Scrapy, processa os resultados com pré-filtragem
    e insere os editais válidos e novos no banco de dados.
    """
    print(f"\n[ETAPA 2] Executando Crawler da FINEP...")
    
    # Limpa o arquivo de saída anterior, se existir
    if os.path.exists(JSON_OUTPUT_FILE):
        os.remove(JSON_OUTPUT_FILE)
        
    # Executa o Scrapy como um subprocesso. Esta é a forma mais robusta
    # de rodar Scrapy de dentro de outro script, evitando problemas com o 'reactor' do Twisted.
    try:
        # Usamos sys.executable para garantir que estamos usando o mesmo python
        # -m scrapy: executa o scrapy como módulo
        # -L INFO: Reduz o log para não poluir
        comando = [
            sys.executable, "-m", "scrapy", "runspider", 
            "finep_spider.py", "-o", JSON_OUTPUT_FILE, "-L", "INFO"
        ]
        subprocess.run(comando, check=True, capture_output=True, text=True)
        print(f"Crawler executado. Resultados salvos em {JSON_OUTPUT_FILE}.")
    except FileNotFoundError:
        print("\n" + "="*50)
        print("ERRO CRÍTICO: Comando 'scrapy' não encontrado.")
        print("Você instalou as dependências do 'requirements.txt'?")
        print(f"Tente: pip install -r requirements.txt")
        print("="*50 + "\n")
        return
    except subprocess.CalledProcessError as e:
        print(f"ERRO: Falha ao executar o crawler Scrapy.")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return
    except Exception as e:
        print(f"ERRO inesperado ao executar o crawler: {e}")
        return

    # Processar o arquivo JSON de resultados
    if not os.path.exists(JSON_OUTPUT_FILE):
        print("ERRO: O crawler foi executado, mas o arquivo de saída JSON não foi criado.")
        return

    try:
        with open(JSON_OUTPUT_FILE, 'r', encoding='utf-8') as f:
            crawler_results = json.load(f)
    except json.JSONDecodeError:
        print("ERRO: Falha ao ler o arquivo JSON de resultados. Pode estar vazio ou corrompido.")
        return
    finally:
        # Limpa o arquivo temporário
        if os.path.exists(JSON_OUTPUT_FILE):
            os.remove(JSON_OUTPUT_FILE)

    print(f"Crawler encontrou {len(crawler_results)} editais. Processando e filtrando...")
    
    editais_novos_count = 0
    editais_ignorados_count = 0
    # --- MUDANÇA: Definindo o limite de 1 ano atrás ---
    data_limite_antigo = datetime.date.today() - datetime.timedelta(days=365)
    
    for item in crawler_results:
        link_pagina = item.get('url')
        if not link_pagina:
            print("  AVISO: Item sem URL encontrado, ignorando.")
            continue
            
        print(f"\nProcessando: {item.get('Título', 'Sem Título')}")

        # --- FILTRO 1: Duplicata (Conforme sua sugestão) ---
        if motor.check_edital_exists(link_pagina):
            print("  Filtro (Duplicata): Edital já existe no banco. Ignorando.")
            editais_ignorados_count += 1
            continue

        # --- FILTRO 2: Prazo Expirado (Conforme sua sugestão) ---
        # --- MUDANÇA: Capturando a string original do prazo ---
        prazo_str = item.get('Prazo Final', 'Prazo não encontrado')
        prazo_date = parse_prazo(prazo_str)
        if prazo_date and prazo_date < datetime.date.today():
            print(f"  Filtro (Prazo): Prazo expirado em {prazo_date}. Ignorando.")
            editais_ignorados_count += 1
            continue
            
        # --- FILTRO 3: Elegibilidade (Conforme sua sugestão) ---
        # --- MUDANÇA: Capturando a string original do público-alvo ---
        publico_alvo_str = item.get('Público-alvo', 'Não especificado')
        publico_alvo_lower = publico_alvo_str.lower()
        if any(palavra in publico_alvo_lower for palavra in PALAVRAS_CHAVE_ELEGIBILIDADE_IGNORAR):
            print(f"  Filtro (Elegibilidade): Público-alvo parece ser para 'empresa'. Ignorando.")
            editais_ignorados_count += 1
            continue
            
        # --- NOVO FILTRO 4: Editais Antigos Sem Prazo (Sua sugestão) ---
        # Verifica se o prazo E o público-alvo estão ausentes
        sem_prazo = (prazo_str == 'Prazo não encontrado' or prazo_str == '')
        sem_publico = (publico_alvo_str == 'Não especificado' or publico_alvo_str == '')
        
        if sem_prazo and sem_publico:
            data_pub_str = item.get('Data de Publicação', 'Não encontrada')
            data_pub_date = parse_data_publicacao(data_pub_str)
            
            if data_pub_date and data_pub_date < data_limite_antigo:
                print(f"  Filtro (Antigo): Edital sem prazo/público, publicado em {data_pub_date} (mais de 1 ano). Ignorando.")
                editais_ignorados_count += 1
                continue
            elif data_pub_date is None:
                 # Se não tiver prazo, nem público, nem data de publicação, melhor ignorar.
                 print(f"  Filtro (Dados Insuficientes): Edital sem prazo, público ou data de publicação. Ignorando.")
                 editais_ignorados_count += 1
                 continue
            # Se for recente (menos de 1 ano), ele passa e é processado.

        print("  Status: Edital NOVO e passou nos pré-filtros. Processando PDF...")

        # --- ETAPA CARA: Processamento do PDF ---
        link_pdf = item.get('Link PDF')
        if not link_pdf:
            print("  AVISO: Edital sem link de PDF. Será inserido sem 'texto_pdf'.")
            texto_pdf = ""
        else:
            texto_pdf = extrair_texto_pdf(link_pdf)
            if texto_pdf is None:
                print("  AVISO: Falha na extração do PDF. Será inserido sem 'texto_pdf'.")
                texto_pdf = ""

        # --- Preparação dos dados para o DB ---
        edital_data = {
            'titulo': item.get('Título'),
            'orgao': 'FINEP',
            'link_pagina': link_pagina,
            'texto_pdf': texto_pdf,
            'status': 'aberto', # Sabemos que está aberto pela URL do crawler
            'modalidade': None, # Nosso crawler não captura
            'prazo_submissao': prazo_date,
            'valor_estimado': None, # Nosso crawler não captura
            'elegibilidade': item.get('Público-alvo'),
            'areas_tema': ", ".join(item.get('Tema', [])), # Converte lista em string
            'data_captura': datetime.datetime.now()
        }
        
        # --- Inserção no Banco de Dados ---
        if motor.insert_edital(edital_data):
            print(f"  SUCESSO: Edital '{item.get('Título')}' inserido no banco.")
            editais_novos_count += 1
        else:
            print(f"  ERRO: Falha ao inserir edital '{item.get('Título')}' no banco.")

    print("\n--- Resumo da Coleta ---")
    print(f"Editais novos inseridos: {editais_novos_count}")
    print(f"Editais ignorados (duplicados/filtrados): {editais_ignorados_count}")
    print(f"Total de editais encontrados pelo crawler: {len(crawler_results)}")


def run_complete_update():
    """
    Executa todo o pipeline de atualização:
    1. Garante que o DB e as tabelas existam.
    2. Popula dados iniciais (usuários, linhas) se o DB for novo.
    3. Executa o crawler da FINEP para buscar e inserir novos editais (com filtros).
    4. Calcula embeddings para linhas de pesquisa que ainda não possuem.
    5. Calcula e salva os matches (similaridade) entre editais e linhas.
    """
    print(f"--- INICIANDO TAREFA DE ATUALIZAÇÃO COMPLETA ({datetime.datetime.now()}) ---")
    start_time = time.time()
    
    # Instancia o motor. load_model=True é essencial para as etapas 4 e 5.
    motor = MotorDeCompatibilidade(load_model=True)
    if motor.model is None:
        print("="*50)
        print("ERRO CRÍTICO: Modelo de IA (SentenceTransformer) não foi carregado.")
        print("Verifique sua conexão com a internet (para baixar o modelo) ou a instalação.")
        print("As etapas de embedding e matching serão puladas.")
        print("="*50)
    
    # ETAPA 1: Garantir que o DB e as tabelas existam
    print("\n[ETAPA 1] Verificando estrutura do banco de dados...")
    motor.create_tables_if_not_exist()
    
    # ETAPA 1.5: Popular dados iniciais se for a primeira execução
    seed_initial_data(motor)
    
    # ETAPA 2: Executar o Crawler da FINEP (com lógica de filtro e upsert)
    run_finep_crawler(motor)
    
    if motor.model:
        # ETAPA 3: Calcular embeddings pendentes (para linhas novas)
        print("\n[ETAPA 3] Calculando embeddings para linhas de pesquisa pendentes...")
        motor.calcular_embeddings_pendentes()
        
        # ETAPA 4: Encontrar e salvar matches
        print("\n[ETAPA 4] Encontrando e salvando matches de similaridade...")
        num_matches = motor.encontrar_e_salvar_matches()
        print(f"Processo de matches concluído. {num_matches} matches processados.")
    else:
        print("\n[ETAPA 3 e 4] Pulando cálculo de embeddings e matches (Modelo de IA não carregado).")

    end_time = time.time()
    print(f"--- ATUALIZAÇÃO CONCLUÍDA EM {end_time - start_time:.2f} SEGUNDOS ---")

if __name__ == "__main__":
    run_complete_update()

