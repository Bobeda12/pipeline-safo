import os
import sys
import time
import json
import requests
import io
import traceback
import subprocess # Para executar o Scrapy de forma robusta
import datetime
import sqlite3 # Importado para uso no seed
from dotenv import load_dotenv
from PyPDF2 import PdfReader # Para extrair texto do PDF
from motor_ia import MotorDeCompatibilidade
from werkzeug.security import generate_password_hash
from transformers import T5Tokenizer, T5ForConditionalGeneration
import torch

# --- NOVO IMPORT ---
from notificador import enviar_notificacao_match 

# Carrega variáveis de ambiente
load_dotenv()

# --- Configurações ---
# Arquivo JSON temporário para onde o Scrapy salvará os dados
JSON_OUTPUT_FILE = 'editais_finep.json'
# Palavras-chave para pré-filtragem de elegibilidade (exemplo)
PALAVRAS_CHAVE_ELEGIBILIDADE_IGNORAR = ["empresa", "startup", "exclusivo para"]

# --- NOVA CONFIGURAÇÃO ---
# Limiar de score para enviar notificação por e-mail (Ex: 0.35 = 35%)
# (Conforme doc Projeto IPE2)
LIMIAR_NOTIFICACAO = 0.35 

# Em run_update.py, abaixo das outras configurações globais
print("[Setup] Carregando modelo de sumarização (pode levar um tempo)...")
try:
    # Usamos um modelo T5 otimizado para sumarização em português
    MODEL_NAME = "recogna-nlp/ptt5-base-summ"
    tokenizer_sum = T5Tokenizer.from_pretrained(MODEL_NAME)
    model_sum = T5ForConditionalGeneration.from_pretrained(MODEL_NAME)
    print("[Setup] Modelo de sumarização carregado com sucesso.")
except Exception as e:
    print(f"AVISO: Falha ao carregar modelo de sumarização: {e}. Resumos não serão gerados.")
    model_sum = None
    tokenizer_sum = None

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
            hashed_password_admin = generate_password_hash('admin') # Senha 'admin' como padrão
            cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", ('admin@ime.br', hashed_password_admin))
            conn.commit()
            print("[Seed Data] Usuário 'admin@ime.br' (senha: 'admin') criado.")
        else:
            print("[Seed Data] Usuários já existem.")

        # 2. Adicionar linhas de pesquisa de exemplo se não existirem
        cursor.execute("SELECT COUNT(*) as count FROM linha_ime")
        if cursor.fetchone()['count'] == 0:
            print("[Seed Data] Tabela 'linha_ime' vazia. Adicionando dados reais do IME...")
             # --- ATUALIZADO: Dados reais extraídos do .docx ---
             # (programa, linha, descricao, emails_contato, embedding, user_id)
             # Assumindo user_id=1 para 'admin@ime.br'
            linhas_data = [
                ('Engenharia Cartográfica', 'Imageamento Digital',
                 """A linha de pesquisa de Imageamento Digital tem por objetivos específicos o processamento, a análise de imagens digitais e a compreensão de cenas, com base nos dados provenientes de sensores ativos e passivos, em todos os seus níveis de aquisição. Destaca-se, nesta linha, a correção de distorções radiométricas e geométricas em imagens digitais por meio de técnicas de fotogrametria, o emprego de sensores hiperespectrais e de imagens multitemporais multisensores para a melhor compreensão da dinâmica de uso e cobertura da terra. O desenvolvimento de técnicas e conhecimentos baseados em abordagens avançadas para a detecção de alvos e reconhecimento de feições cartográficas é feito com o uso de abordagens como a neurocomputação e de análises de imagens baseadas em objetos georreferenciados (OBIA). O uso do imageamento orbital permite a obtenção contínua de informações de toda a superfície do País com intervalos regulares de poucos dias ou até de horas, tornando importante o domínio dos métodos de obtenção de informações georreferenciadas a partir de um imenso volume de dados espaciais amplamente disponíveis atualmente, devido à crescente tecnologia de satélites e das plataformas baseadas em drone (VARP ou VANT).""",
                 'admin@ime.br', None, 1),

                ('Engenharia Cartográfica', 'Modelagem e Representação Terrestre',
                 """A linha de pesquisa de Modelagem e Representação Terrestres tem por objetivos específicos o desenvolvimento de diversos métodos e técnicas de coleta, tratamento e processamento de dados geodésicos provenientes de modernos sistemas de navegação, associados aos contextos de sistemas e de redes geodésicas, referente às suas componentes planimétricas e altimétricas. Nas áreas de Cartografia, destaca-se o uso de Sistemas de Informações Geográficas e a execução de análises espaciais com o emprego de técnicas cartográficas, matemáticas e estatísticas, bem como a realização de pesquisas em cartografia colaborativa, tátil e histórica, generalização cartográfica, visualização cartográfica em ambiente tridimensional e geração de protótipos com fins militares.""",
                 'admin@ime.br', None, 1),

                ('Engenharia de Defesa', 'Comunicações, Computação, Cibernética e Inteligência',
                 """Grande parte dos sistemas de defesa modernos dependem de subsistemas de comunicações, computação, cibernética e de tratamento da informação. Por exemplo, mísseis podem ter seu guiamento apoiado por recepção de sinais de GPS, o que envolve o uso de rádios e de funcionalidades de processamento de informações de localização geográfica. Sistemas de Comando e Controle, por sua vez, são fortemente dependentes de redes de dados e sistemas de comunicações, necessitando de diversas ferramentas de processamento e armazenamento da informação. O desenvolvimento e a operação desses Sistemas de Defesa exigem cada vez mais a integração de conhecimentos multidisciplinares, mormente das grandes áreas de Engenharias e Ciências Exatas e da Terra. Nesta linha de pesquisa, em particular, são tratados temas que envolvem as subáreas de Engenharia Elétrica, Ciências da Computação e Sistemas de dados, com foco em projetos de emprego integrado desses conhecimentos em Sistemas de Defesa. Esta Linha de Pesquisa (LP) engloba, portanto, projetos ligados a comunicações militares e aspectos científicos e tecnológicos na obtenção, análise, processamento e emprego de dados para geração de subsídios às ações de inteligência dos órgãos ou agentes de defesa. Ainda no escopo da linha se enquadram os aspectos de integração das soluções que envolvem eletrônica (em especial voltada para comunicações) e tratamento da informação nos sistemas de armas e outros sistemas de defesa. Parte das pesquisas aqui desenvolvidas se apóia em estudos de modelagem de problemas ou dispositivos complexos, bem como em simulações numéricas de desempenho e funciona­mento de sistemas. Dentre os temas de pesquisas no escopo desta LP destacam-se: modernização de rádios HF para comunicações militares, tecnologias ópticas (confinadas e de espaço livre) para redes estratégicas, ferra­mentas computacionais e infra-estrutura de redes de telecomunicações para apoio a ações de C3I (Comando, Controle, Comunicações e Inteligência), dispositivos e técnicas para Guerra Eletrônica e processamento de sinais de voz com foco em Segurança da Informação.""",
                 'admin@ime.br', None, 1),

                ('Engenharia de Defesa', 'Infraestrutura, Logística, Meio Ambiente, Geoinformação e Energia',
                 """Esta Linha de Pesquisa tem abordagem interdisciplinar vinculada à Engenharia de Defesa, com vertentes em Infraestrutura, Logística, Meio Ambiente, Geoinformação e Energia. Os objetivos desta LP são: (Infraestrutura) estudar e desenvolver materiais e técnicas a serem empregadas no projeto, construção, manutenção e gerenciamento de obras de infraestrutura e também estudar e desenvolver processos e tecnologias integradas a serem empregadas em benefício da criação, utilização e atualização de modelos digitais de uma construção, de forma colaborativa, para aplicação direta à gerência do ciclo de vida do ambiente construído, seja ele relativo a obras verticais ou de infraestrutura; (Logística) estudar e desenvolver modelos e técnicas de planejamento logístico relacionados a previsão da demanda, com o uso e a ocupação do solo, e com a integração dos diferentes modos de transporte; (Meio Ambiente) analisar os impactos das mudanças climáticas e impactos ambientais associados a ações de engenharia, visando à sustentabilidade e preocupando-se com a preservação do meio ambiente; (Geoinformação)  ampliar a compreensão acerca dos diferentes fenômenos que ocorrem no espaço geográfico bem como a modelagem e representação da superfície terrestre utilizando geotecnologia, a qual engloba as áreas de Sensoriamento Remoto, Sistemas de Informações Geográficas, Cartografia Digital, Sistemas de Posicionamento Global e áreas correlatas; (Energia) desenvolver tecnologias, metodologias e algoritmos aplicados a sistemas de energia, com o objetivo de ampliar a capacidade, a confiabilidade, a disponibilidade e a qualidade no fornecimento e na geração de energia de distintas fontes, otimizando sua utilização. Nesta LP são desenvolvidos projetos e pesquisas prioritariamente nas áreas das engenharias civil, cartográfica, elétrica, química, nuclear, ambiental e computação.""",
                 'admin@ime.br', None, 1),

                ('Engenharia de Defesa', 'Mecatrônica, Matéria Condensada e Sistemas de Armas',
                 """Um dos elementos fundamentais dos sistemas de defesa são os sistemas de armas. A concepção, o projeto, a fabricação e o emprego tático dos sistemas de armas necessitam de uma visão global dos sistemas de defesa, tanto no que diz respeito ao fluxo de informações, quanto às características do teatro de operações que determinarão seu modo de emprego. O desenvolvimento de sistemas de armas modernos requer o conhecimento multidisciplinar e concorrente de diversos conhecimentos, especialmente de sistemas mecânicos e eletrônicos, daí a denominação Mecatrônica, além de outros, como por exemplo a química, no que se refere às reações altamente exotérmicas e escoamento altamente energéticos envolvidos em processos de propulsão de mísseis e foguetes. As diversas etapas da concepção de um sistema de armas são contempladas nas pesquisas desta Linha, sejam nos aspectos mais abrangentes, sejam naqueles mais específicos como o controle de um veículo aéreo não-tripulado (VANT) ou o planejamento de sua missão. Vários aspectos desenvolvidos nas demais linhas de pesquisa são importantes para integrar esses equipamentos em um Sistema de Defesa típico. Neste contexto, podem ser citados, por exemplo, os projetos de reconhecimento das características específicas do terreno do teatro de operações, de comunicações e de fluxo de informações com o centro de Comando e Controle da missão. Nesta LP são desenvolvidos projetos e pesquisas nas áreas de armamento, mecânica estrutural, sistemas de controle automático, navegação geodésica global e inercial, guiamento, dinâmica de sistemas, instrumentação, processamento de sinais, filtragem, propulsão, balística e demais assuntos correlatos, o que naturalmente envolverá profissionais de várias áreas de engenharia como mecânica, eletrônica, computação, cartografia, química e outras.""",
                 'admin@ime.br', None, 1),

                ('Engenharia Elétrica', 'Automação, Controle e Operação de Sistemas',
                 """Essa linha trata da pesquisa, do estudo e da validação (por meio de simulações ou a partir de implementações práticas) de sínteses de controle nos domínios do tempo e da frequência. Envolve estudos em controle robusto, ótimo, adaptativo, não-linear e de técnicas inteligentes de controle, bem como o controle de sistemas lineares variantes no tempo. Realizam-se ainda, estudos na área de identificação e otimização de sistemas físicos, modelagem e aplicações de técnicas de controle clássico e moderno, assim como pesquisas relacionadas ao controle e verificação de Sistemas a Eventos Discretos e Sistemas Híbridos, com aplicações voltadas para sistemas eletrônicos de defesa. O foco em sistemas elétricos de potência ocorre por meio de pesquisas que englobam, mas não se restringem à modelagem, análise, planejamento da operação, proteção e qualidade de energia elétrica. Tem por objetivo principal a formação de recursos humanos e a geração de conhecimento nos temas descritos a seguir: \na) Controle Supervisório de Sistemas a Eventos Discretos (SEDs): Sistemas de Controle Hierárquico; Controle de SEDs Temporizados; Controle Tolerante a Falhas; Model Checking; Aplicações na Indústria 4.0: Smart Factories, Sistemas Ciberfísicos, Internet das Coisas e Segurança Cibernética.\nb) Modelagem, Identificação e Otimização de Sistemas Dinâmicos: Modelagem de Sistemas visando a aplicação de Técnicas de Controle Moderno; Identificação de Sistemas por Métodos no Domínio da Frequência; Identificação de Sistemas por Métodos no Domínio do Tempo; Métodos de Redução de Ordem de Modelos; Simulação de Sistemas Dinâmicos.\nc) Controle Ótimo e Moderno: Controle Ótimo; Controle Robusto a Incertezas Estruturadas e Não-Estruturadas; Controle Robusto Paramétrico com Base na Qualidade da Identificação Bayesiana; Controle Linear a Parâmetros Variáveis; Integral Quadratic Constraints (IQC) - teoria e aplicações.\nd)  Modelagem, Análise e Controle de Sistemas Elétricos de Potência: Modelagem e Identificação de Sistemas; Análise e Controle a Pequenos Sinais; Estabilidade de Tensão; Detecção de Distúrbios Causados por Ataques Cibernéticos; Operação em Tempo Real e Planejamento da Operação; Dinâmica, Proteção e Controle; Qualidade de Energia Elétrica; Desempenho de equipamentos.""",
                 'admin@ime.br', None, 1),

                ('Engenharia Elétrica', 'Processamento de Sinais e Sistemas Robóticos e Autônomos',
                 """a)  Processamento de Sinais Acústicos: Métodos de realce de sinais robustos a ruídos acústicos urbanos;  Máscaras acústicas para aprimoramento de inteligibilidade auditiva; Processamento de interferências acústicas (reverberação, ruído); Ambientes acusticamente sensíveis; Audição Robótica; Tratamento acústico de ego-interferências: robôs e drones; Inteligibilidade acústica; Seleção de sensores acústicos para aprimoramento de audição assistida; Auto Localização e Mapeamento (SLAM) com sensores acústicos; Classificação de ambientes acústicos urbanos com aprendizados (​com IA/Redes Neurais​); Identificação e autenticação de indivíduos pelo sinal de voz (patente concedida); Localização de fontes sonoras em espaço urbano robusto a ruídos; Filtros tempo-frequência adaptativos para representação auditiva; Identificação acústica de estados emocionais; Classificação​ com aprendizado​ estocástico e não supervisionado de ​sinais ​acústicos​ e imagens​ (áudio visual).\nb) Processamento Digital de Imagem: Processamento de Imagens; Streaming de Vídeo.\nc) Processamento Digital de Sinais, Teoria e Aplicações: Filtragem adaptativa; Processamento de sinais em arranjo de sensores; Processamento de sinais em sub-bandas; Processamento de sinais em grafos.\nd) Processamento de nuvens de pontos 3D: Registro de nuvens de pontos LiDAR; Mapeamento indoor usando dados RGB-D; Aprendizado não supervisionado em nuvens de pontos 3D.\ne) Processamento de sinais GNSS: Posicionamento por Ponto Preciso em Tempo Real (Real Time Precise Point Positioning); Filtragem de Kalman para navegação por GNSS; Modelos Estocásticos para mitigação de erros nos sinais; Modelagem de efeitos atmosféricos (Ionosfera e Troposfera) em sinais; Análise de séries temporais de coordenadas de estações GNSS.\nf) Reconhecimento de padrões em imagens e sinais acústicos: Métodos de aprendizado profundo para detecção de objetos, segmentação semântica e segmentação de instâncias em imagens; Redes neurais convolucionais para reconhecimento de padrões em sinais acústicos; Aprendizado não supervisionado em imagens e sinais acústicos; Processamento e análise de imagens hiperespectrais;\ng) Sistemas Autônomos e Inteligentes de Robótica: Framework multiagentes para um enxame de drones heterogêneos; Aprendizado profundo para um sistema de robôs móveis em tarefas competitivas (Futebol de robôs); Sistemas embarcados críticos para soluções de problemas em tempo real; Técnicas de SLAM (Auto localização e Mapeamento Simultâneos) para a navegação autônoma em plataformas terrestres móveis; Prototipagem/desenvolvimento de veículos aéreos não tripulados; Aprendizado de máquina para a caminhada de robôs humanoides; Algoritmos meta-heurísticos para aplicações de enxames de drones para cidades inteligentes; Desenvolvimento de Flying Ad-hoc Networks (FANETs) para a comunicação em um enxame de drones; Aprendizado profundo para a reconstrução 3D com imagens de múltiplos drones.""",
                 'admin@ime.br', None, 1),

                ('Engenharia Elétrica', 'Sistemas de Comunicações',
                 """a)  Dispositivos e Sistemas Ópticos: Análise de Dispositivos para Comunicações e Sensores Ópticos; Dispositivos Ópticos Integrados; Modelagem, Simulação e Desenvolvimento de Sistemas com Óptica no Espaço Livre (FSO); Modelagem, Simulação e Desenvolvimento de Sensores Ópticos; Projeto e Caracterização de Sensores Ópticos.\nb) Sistemas Radar: Modelagem e simulação de transmissores e receptores radar; Avaliação de desempenho de algoritmos de detecção e estimação de características de objetos refletores; Caracterização de seção reta radar de alvos distribuídos; Caracterização de assinaturas; Microdoppler de alvos distribuídos; Análise de técnicas de interceptação e de despistamento de formas de onda radar;  Projeto de sistemas radar phased array; Radares passivos; Projeto e análise de formas de onda radar; Joint Communication and Sensing;\nc) Sistemas e Técnicas de Transmissão Digital: Avaliação de desempenho de sistemas de comunicações; Modelagem e simulação de canais em nível físico e de enlace;  Modulação e equalização para canais com desvanecimento; Transmissão multi-portadora: OFDM e variantes; Sistemas rádio cognitivos.\nd) Teoria Eletromagnética, Micro-ondas, Propagação de Ondas, Antenas e Sistemas de Telecomunicações: Antenas e canal de radiopropagação; Circuitos de RF e micro-ondas; Compatibilidade eletromagnética; Dimensionamento de sistemas de rádio; Medidas de propriedades dielétricas de materiais.""",
                 'admin@ime.br', None, 1),

                ('Engenharia Mecânica', 'Dinâmica de Veículos Militares',
                 """A linha de pesquisa em Dinâmica de Veículos Militares é dedicada à modelagem matemática e simulação do comportamento do veículo em terrenos firmes e/ou irregulares, envolvendo trafegabilidade e mobilidade, conforto, influência na precisão do disparo de armas. Os temas de interesse são:\n- Dinâmica de Multicorpos Rígidos e Flexíveis;\n- Dinâmica de Veículos Terrestres;\n- Veículos Autônomos;\n- Métodos Numéricos;\n- Ensaios de Veículos;\n- Robótica de Manipuladores;\n- Vibrações; e\n- Resistência dos Materiais.\nTais temas são aplicados a Veículos Militares e Material de Emprego Militar.""",
                 'admin@ime.br', None, 1),

                ('Engenharia Mecânica', 'Fenômenos Balísticos',
                 """Fenômenos Balísticos é a linha de pesquisa da área de concentração em Armamento, dedicada a modelagem matemática e experimental, a simulação e a análise de fenômenos termofluidodinâmicos, sistemas térmicos e de estruturas, cujos temas de interesse são:\n- Transferência de calor;\n- Combustão;\n- Métodos Analíticos e Numéricos;\n- Termofluidodinâmica;\n- Resistência e Seleção de Materiais;\n- Aerodinâmica;\n- Transferência de Calor e Massa;\n- Dinâmica dos Fluidos Computacional; e\n- Turbulência\nTemas aplicados a Sistemas de Armas e a Material de Emprego Militar. Adicionalmente esta Linha de Pesquisa contempla temas relacionados a vibrações dos sistemas de armas e dinâmica e controle de suas munições em voo.""",
                 'admin@ime.br', None, 1),

                ('Engenharia Nuclear', 'Reatores Nucleares',
                 """Esta linha de pesquisa abrange o estudo de diversos tipos de reatores nucleares, com ênfase na análise do núcleo do reator, na transferência de calor, nos materiais empregados e na blindagem. As atividades de ensino e pesquisa nessa área estão principalmente relacionadas à Física de Reatores e à Engenharia de Reatores.\nFísica de Reatores: análise de incertezas e sensibilidade, cinética espacial, desenvolvimento e aplicação de códigos computacionais nucleares, parametrização de dados nucleares e estudo do comportamento da seção de choque macroscópica em reatores.\nEngenharia de Reatores: transferência de calor, segurança de reatores e extensão da vida útil de centrais nucleares.\nMateriais Nucleares: enriquecimento, armazenamento e reprocessamento de combustíveis nucleares, além do estudo dos materiais empregados na cadeia produtiva dos reatores.\nTecnologia de Reatores Avançados e Inovadores: desenvolvimento e análise de reatores modulares de pequeno porte, reatores rápidos, reatores térmicos e reatores refrigerados a gás de alta temperatura (HTGR).""",
                 'admin@ime.br', None, 1),

                ('Engenharia Nuclear', 'Defesa Radiológica e Nuclear',
                 """Na área de Defesa Radiológica e Nuclear, desenvolvem-se estudos relacionados à Física Nuclear Aplicada e ao controle das radiações em diferentes meios e cenários, com ênfase na avaliação dos impactos no ser humano e no meio ambiente. O foco principal recai sobre materiais e sistemas de uso dual, que atendam às necessidades do Exército Brasileiro e contribuam para o desenvolvimento da sociedade.\nAs dissertações desenvolvidas nessa linha de pesquisa abordam os seguintes temas:\nSAFETY:  \nMétodos e técnicas para a determinação de indicadores de condições preexistentes e avaliação do impacto ambiental decorrente de modificações antropogênicas em diferentes meios.\nTécnicas e métodos de detecção, monitoração e controle de radiações provenientes de fontes naturais e artificiais, bem como suas aplicações.\nRadioproteção, dosimetria e blindagem radiológica, com foco na segurança de indivíduos expostos a diferentes tipos de radiação ionizante. Estudo de materiais para blindagens simples ou multilaminadas.\nAplicações industriais da radiação ionizante, incluindo radiotraçadores, radiografia industrial, gamagrafia e medidores de nível.\nIrradiação de materiais e seus efeitos.\nDesenvolvimento de programas computacionais aplicados a medidores e identificadores radiológicos para uso em ações de Defesa Química, Biológica, Radiológica e Nuclear (DQBRN).\nAplicação de Inteligência Artificial, Robótica e AutomaÇÃO no desenvolvimento de instrumentos operacionais para DQBRN.\nSimulação computacional para predição dos efeitos do espalhamento de materiais radioativos e nucleares em incidentes ou acidentes.\nDesenvolvimento de protocolos e procedimentos técnicos para a melhoria da qualidade metrológica de laboratórios de calibração de medidores de radiação.\nMétodos e técnicas para o emprego de radiofármacos, radioterapia e radiodiagnóstico em diferentes aplicações da medicina nuclear.\nSECURITY\nSegurança Nuclear, incluindo análise de acidentes, segurança física (proteção e controle de materiais nucleares, defesa cibernética nuclear), segurança da informação e segurança no transporte de materiais radioativos.\nTerrorismo Nuclear e estudo de sistemas de defesa nuclear.""",
                 'admin@ime.br', None, 1),

                # --- NOMES PADRONIZADOS A PARTIR DAQUI ---
                ('Engenharia de Transportes', 'Planejamento e Operação dos Sistemas de Transportes',
                 """Desenvolvimento de modelos e técnicas de planejamento dos transportes relacionados com a previsão da demanda, com o uso e a ocupação do solo, e com a integração dos diferentes modos de transporte e os aspectos econômicos envolvidos, a análise dos impactos ambientais provocados pela instalação e operação de projetos de transportes, legislação pertinente, métodos para avaliação e medidas mitigadoras das componentes do passivo ambiental criado.""",
                 'admin@ime.br', None, 1),

                ('Engenharia de Transportes', 'Logística',
                 """Desenvolvimento e aplicação de métodos e técnicas de modelagem matemática, utilizando-se de métodos exatos, heurísticos, meta-heurísticos e de simulação para avaliação de sistemas logísticos integrados e para o planejamento dos mesmos, como aplicações de roteirização e programação de veículos, localização de facilidades, empacotamento, desenho de redes logísticas, programação da manutenção de veículos e alocação de fluxos em redes.""",
                 'admin@ime.br', None, 1),

                ('Engenharia de Transportes', 'Infraestrutura dos Sistemas de Transportes',
                 """Estudo e desenvolvimento de materiais e técnicas a serem empregadas em projetos de construção, manutenção e gerenciamento de estradas, ferrovias, hidrovias, dutovias, portos e aeroportos. Estudar e projetar estruturas, hidráulica fluvial, obras hidroviárias, obras rodoviárias, obras ferroviárias e obras portuárias, além de estudar viabilidades técnica, econômica e ambiental.""",
                 'admin@ime.br', None, 1),

                ('Engenharia de Transportes', 'Materiais e Estruturas para Transportes',
                 """Estudo e desenvolvimento de materiais e técnicas a serem empregadas em projetos de construção, manutenção e gerenciamento de estradas, ferrovias, hidrovias, dutovias, portos e aeroportos. Estudar e projetar estruturas, hidráulica fluvial, obras hidroviárias, obras rodoviárias, obras ferroviárias e obras portuárias, além de estudar viabilidades técnica, econômica e ambiental.""",
                 'admin@ime.br', None, 1),
                # --- FIM ENGENHARIA DE TRANSPORTES ---

                ('Ciência e Engenharia de Materiais', 'Materiais Cerâmicos',
                 """Esta Linha de Pesquisa tem por objetivo a síntese, processamento e caracterização de materiais cerâmicos, bem como o estudo das propriedades mecânicas desses materiais. Projetos nessa linha envolvem materiais cerâmicos avançados, biomateriais cerâmicos e materiais compósitos de matriz cerâmica""",
                 'admin@ime.br', None, 1),

                ('Ciência e Engenharia de Materiais', 'Materiais Eletrônicos',
                 """Esta Linha de Pesquisa tem por objetivo produzir materiais para aplicação em dispositivos eletrônicos e correlacionar as propriedades elétricas, ópticas e magnéticas desses materiais com a sua microestrutura. Projetos nessa linha vêm sendo desenvolvidos nas áreas de filmes finos para células solares, filmes finos para filtros ópticos e nanopartículas magnéticas para aplicações biomédicas e de engenharia.""",
                 'admin@ime.br', None, 1),

                ('Ciência e Engenharia de Materiais', 'Materiais Metálicos',
                 """Esta Linha de Pesquisa tem por objetivo estudar a microestrutura de metais e ligas metálicas e sua influência nas propriedades mecânicas desses materiais. Projetos nessa linha envolvem a influência da textura cristalográfica no comportamento anisotrópico de materiais metálicos, biomateriais metálicos, materiais de alta resistência mecânica e elevada condutividade elétrica e materiais compósitos de matriz metálica.""",
                 'admin@ime.br', None, 1),

                ('Ciência e Engenharia de Materiais', 'Materiais Poliméricos',
                 """Esta Linha de Pesquisa tem por objetivo estudar as propriedades físico-químicas e mecânicas de materiais poliméricos. Projetos nessa linha envolvem novas matrizes poliméricas em materiais compósitos, aproveitamento de rejeitos industriais, blindagens balísticas baseadas em polímeros, uso de polímeros para contenção de resíduos tóxicos e radioativos, degradação de polímeros, biomateriais poliméricos e materiais poliméricos reforçados por fibras naturais.""",
                 'admin@ime.br', None, 1),

                ('Engenharia Química', 'Química de Materiais e Materiais Energéticos',
                 """Nos últimos anos, a pesquisa na área de materiais tornou-se prioritária para a sociedade e para as Forças Armadas. Fruto desta motivação, esta linha de pesquisa se concentra na compreensão dos fenômenos químicos ligados aos novos materiais e no aprimoramento de materiais conhecidos, realizando atividades de pesquisa básica, desenvolvimento, e avaliação, sempre buscando pela inovação. \nNo contexto dos materiais de interesse destacam-se os materiais energéticos, reconhecidos pelo amplo uso em tecnologias militares, bem como em aplicações industriais específicas, tais como: a indústria do petróleo, de mineração, da construção civil e aeroespacial. Os materiais energéticos abrangem os explosivos, propelentes e pirotécnicos na forma de compostos individuais ou misturas e que são caracterizados pela elevada velocidade de liberação de seu conteúdo energético. A intensidade e as condições termodinâmicas dos fenômenos típicos dos materiais energéticos estabelecem um campo do saber bastante específico que não é muito explorado na literatura da área de química e, portanto, aumentando o interesse para as pesquisas desenvolvidas no programa.""",
                 'admin@ime.br', None, 1),

                ('Engenharia Química', 'Química Medicinal, Defesa Química e Substâncias Bioativas',
                 """Substâncias bioativas são aquelas que apresentam qualquer atividade em meios biológicos, podendo ser sintetizadas ou encontradas em fontes naturais, como em plantas, algas, esponjas e micro-organismos. Também estão presentes nos resíduos da agroindústria, onde seu aproveitamento viabiliza a sustentabilidade dos processos industriais e incrementa a Bioeconomia. Em substâncias que já são consumidas como alimentos ou plantas medicinais, a toxicidade costuma ser baixa, viabilizando o desenvolvimento mais direto de bioprodutos como cosméticos, perfumes, suplementos alimentares, aditivos industriais diversos ou mesmo medicamentos. Nesse último caso, as pesquisas realizadas no IME estão focadas no desenvolvimento de novas substâncias bioativas tanto para a ação em doenças importantes de grande impacto social, como as doenças negligenciadas e o câncer, como também para a ação em antídotos contra armas químicas e biológicas, na área denominada Defesa Química.\nAs pesquisas nessa linha são realizadas por métodos químicos tradicionais, como a síntese orgânica e a fitoquímica (que emprega métodos cromatográficos e espectroscópicos em busca de bioativos em extratos naturais), bioquímicos (com enzimas ou nos próprios meios biológicos,  in vitro  e  in   vivo ) e físico-químicos (com ensaios computacionais que simulam as condições biológicas,  in silico ). O IME possui a expertise para atuar nessas áreas com estudos realizados tanto nos seus laboratórios como em outros centros de pesquisa de instituições militares localizadas no próprio Rio de Janeiro e em outros parceiros nacionais e internacionais.""",
                 'admin@ime.br', None, 1),

                ('Engenharia Química', 'Energia, Catálise e Tecnologias Sustentáveis',
                 """O uso intensivo de energia caracteriza a sociedade moderna. A demanda energética não para de crescer e o impacto ambiental produzido pela geração de energia necessária para atender a esta demanda é importante, com destaque para a grande emissão de gases de efeito estufa e o consequente aquecimento global. Neste contexto, o estudo de novas formas de geração, de novos combustíveis e de tecnologias sustentáveis de menor impacto ambiental é crítico. Assim, as universidades e empresas vem investindo pesadamente em pesquisas em áreas como reciclagem de materiais, combustíveis alternativos derivados de biomassa, inclusive hidrogênio, produtos químicos obtidos por rotas verdes, novos materiais e novos projetos de baterias e supercapacitores, entre outras. São pesquisas multidisciplinares, onde quase sempre o uso de catalisadores é parte importante para o desenvolvimento da aplicação.\nAs principais pesquisas nessa linha envolvem a reciclagem de plásticos e rejeitos industriais e domésticos, a geração de combustíveis líquidos e hidrogênio a partir de biomassa usando diferentes tecnologias, a síntese de novos catalisadores com ênfase em reações de hidrogenação e em sistemas bifuncionais, a síntese de adsorventes para remoção de poluentes orgânicos e inorgânicos, o preparo de novos materiais com propriedades eletrônicas e eletroquímicas otimizadas para aplicação em dispositivos de conversão e armazenamento de energia.""",
                 'admin@ime.br', None, 1),

                # --- NOMES PADRONIZADOS A PARTIR DAQUI ---
                ('Sistemas e Computação', 'Engenharia de Sistemas e Informação',
                 """Esta linha tem como objetivo o desenvolvimento de conceitos, modelos, técnicas e processos para o desenvolvimento de tecnologias e de sistemas de informação. Temas de interesse desta linha de pesquisa incluem: Banco de Dados, Bioinformática, Educação à Distância, Engenharia de Software, Inteligência Artificial, Mineração de Dados e de Texto e Modelagem Conceitual.""",
                 'admin@ime.br', None, 1),

                ('Sistemas e Computação', 'Metodologia da Computação',
                 """Esta linha tem como objetivo o desenvolvimento de modelos de sistemas computacionais, bem como técnicas para tratar e analisar esses modelos, abordando assuntos relacionados com Teoria da Computação e Matemática da Computação. Temas de interesse desta linha de pesquisa incluem: Lógica, Linguagens Formais e Autômatos, Computabilidade, Análise de Algoritmos, Algoritmos em Grafos, Teoria Espectral de Grafos e Otimização combinatória.""",
                 'admin@ime.br', None, 1),

                ('Sistemas e Computação', 'Sistemas de Computação',
                 """Esta linha tem como objetivo investigar técnicas, modelos e metodologias para a construção de sistemas computacionais que se caracterizam por aspectos de distribuição, automação, simulação, visualização e segurança. Temas de interesse desta linha de pesquisa incluem: Computação de Alto Desempenho, Computação Gráfica, Processamento de Imagens e Interação, Inteligência Computacional, Interação Homem-Computador, Processamento Paralelo e Distribuído, Redes de Computadores, Robótica e Automação, Segurança da Informação (Defesa Cibernética), Sistemas de Telecomunicações e Visualização""",
                 'admin@ime.br', None, 1)
                # --- FIM SISTEMAS E COMPUTAÇÃO ---
            ]
            # --- FIM DA ATUALIZAÇÃO ---

            cursor.executemany("""
                INSERT INTO linha_ime (programa, linha, descricao, emails_contato, embedding, user_id)
                VALUES (?, ?, ?, ?, ?, ?);
            """, linhas_data)
            conn.commit()
            print(f"[Seed Data] {len(linhas_data)} linhas de pesquisa reais inseridas com sucesso.")
        else:
            print("[Seed Data] Linhas de pesquisa já existem.")

    except sqlite3.Error as e:
        print(f"Erro durante o seeding de dados: {e}")
        conn.rollback()
    finally:
        conn.close()

# Em run_update.py, pode ser antes de 'run_finep_crawler'

def gerar_resumo(texto_completo, max_input_length=1024, num_sentences_fallback=5):
    """
    Gera um resumo abstrativo do texto completo usando o modelo T5.
    """
    if not model_sum or not tokenizer_sum:
        print("  AVISO: Modelo de sumarização não carregado. Usando fallback (primeiras frases).")
        try:
            sentences = texto_completo.split('.')
            fallback_summary = '. '.join(sentences[:num_sentences_fallback]).strip()
            return fallback_summary + "..." if len(sentences) > num_sentences_fallback else fallback_summary
        except Exception:
            return "Resumo não disponível."

    if not texto_completo or not texto_completo.strip():
        return "Nenhuma informação textual para resumir."

    try:
        # O T5 espera um prefixo para a tarefa de sumarização
        input_text = "resumir: " + texto_completo

        # Trunca o input para o limite do modelo (ex: 1024 tokens)
        inputs = tokenizer_sum(input_text, 
                               max_length=max_input_length, 
                               truncation=True, 
                               return_tensors="pt")

        # Gera o resumo
        summary_ids = model_sum.generate(inputs["input_ids"], 
                                       num_beams=4, 
                                       max_length=150,  # Comprimento máximo do resumo
                                       min_length=30,   # Comprimento mínimo
                                       early_stopping=True)

        resumo = tokenizer_sum.decode(summary_ids[0], skip_special_tokens=True)
        print(f"  Resumo gerado com sucesso ({len(resumo)} caracteres).")
        return resumo

    except Exception as e:
        print(f"  ERRO ao gerar resumo com IA: {e}. Usando fallback.")
        sentences = texto_completo.split('.')
        fallback_summary = '. '.join(sentences[:num_sentences_fallback]).strip()
        return fallback_summary + "..." if len(sentences) > num_sentences_fallback else fallback_summary

def run_finep_crawler(motor):
    """
    Executa o crawler Scrapy, processa os resultados com pré-filtragem
    e insere os editais válidos e novos no banco de dados.
    """
    print(f"\n[ETAPA 2] Executando Crawler da FINEP...")
    
    # Limpa o arquivo de saída anterior, se existir
    if os.path.exists(JSON_OUTPUT_FILE):
        os.remove(JSON_OUTPUT_FILE)
        
    # Executa o Scrapy como um subprocesso.
    try:
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
        prazo_str = item.get('Prazo Final', 'Prazo não encontrado')
        prazo_date = parse_prazo(prazo_str)
        # --- MODIFICADO PARA DEMONSTRAÇÃO ---
        # Filtro de prazo desativado para permitir editais encerrados
        # if prazo_date and prazo_date < datetime.date.today():
        #     print(f"  Filtro (Prazo): Prazo expirado em {prazo_date}. Ignorando.")
        #     editais_ignorados_count += 1
        #     continue
            
        # --- FILTRO 3: Elegibilidade (Conforme sua sugestão) ---
        publico_alvo_str = item.get('Público-alvo', 'Não especificado')
        publico_alvo_lower = publico_alvo_str.lower()
        if any(palavra in publico_alvo_lower for palavra in PALAVRAS_CHAVE_ELEGIBILIDADE_IGNORAR):
            print(f"  Filtro (Elegibilidade): Público-alvo parece ser para 'empresa'. Ignorando.")
            editais_ignorados_count += 1
            continue
            
        # --- NOVO FILTRO 4: Editais Antigos Sem Prazo (Sua sugestão) ---
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
                print(f"  Filtro (Dados Insuficientes): Edital sem prazo, público ou data de publicação. Ignorando.")
                editais_ignorados_count += 1
                continue
            # Se for recente (menos de 1 ano), ele passa e é processado.

        print("  Status: Edital NOVO e passou nos pré-filtros. Processando PDF...")

        # --- ETAPA CARA: Processamento do PDF ---
        link_pdf = item.get('Link PDF')
        texto_pdf = "" # Garante que a variável exista
        if not link_pdf:
            print("  AVISO: Edital sem link de PDF. Será inserido sem 'texto_pdf'.")
            texto_pdf = ""
        else:
            texto_pdf_extraido = extrair_texto_pdf(link_pdf)
            if texto_pdf_extraido is None:
                print("  AVISO: Falha na extração do PDF. Será inserido sem 'texto_pdf'.")
                texto_pdf = ""
            else:
                texto_pdf = texto_pdf_extraido
        
        # ===================================================================
        # INÍCIO DO BLOCO CORRIGIDO (INDENTADO PARA DENTRO DO LOOP 'for')
        # ===================================================================

        # --- GERAÇÃO DO RESUMO ---
        print("  Gerando resumo do texto do PDF...")
        resumo_pdf = gerar_resumo(texto_pdf)
        # --- FIM DA GERAÇÃO ---

        # --- Preparação dos dados para o DB ---
        edital_data = {
            'titulo': item.get('Título'),
            'orgao': 'FINEP',
            'link_pagina': link_pagina,
            'texto_pdf': texto_pdf,
            'resumo_pdf': resumo_pdf, # <-- PASSE O RESUMO AQUI
            'status': 'aberto', 
            'modalidade': None, 
            'prazo_submissao': prazo_date,
            'valor_estimado': None, 
            'elegibilidade': item.get('Público-alvo'),
            'areas_tema': ", ".join(item.get('Tema', [])),
            'data_captura': datetime.datetime.now()
        }
            
        # --- Inserção no Banco de Dados ---
        if motor.insert_edital(edital_data):
            print(f"  SUCESSO: Edital '{item.get('Título')}' inserido no banco.")
            editais_novos_count += 1
        else:
            print(f"  ERRO: Falha ao inserir edital '{item.get('Título')}' no banco.")
            
        # ===================================================================
        # FIM DO BLOCO CORRIGIDO
        # ===================================================================

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
    6. Verifica e envia notificações por e-mail para novos matches.
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

        # --- NOVA ETAPA 5: Enviar Notificações ---
        print("\n[ETAPA 5] Verificando e enviando notificações por e-mail...")
        if not os.getenv("EMAIL_SENDER"):
            print("  AVISO: Variáveis de ambiente de E-MAIL (EMAIL_SENDER, etc) não configuradas no .env.")
            print("  Etapa de notificação será pulada.")
        else:
            try:
                novos_matches = motor.get_novos_matches_para_notificar(LIMIAR_NOTIFICACAO)
                if not novos_matches:
                    print("  Nenhum match novo acima do limiar encontrado para notificar.")
                else:
                    print(f"  Encontrados {len(novos_matches)} matches para notificar (score >= {LIMIAR_NOTIFICACAO})...")
                    sucessos_keys = [] # Lista de (edital_id, linha_id)
                    
                    for match in novos_matches:
                        # Parsear emails_contato da linha
                        emails_para_enviar = [email.strip() for email in match['emails_contato'].split(',') if email.strip()]
                        
                        if not emails_para_enviar:
                            print(f"  AVISO: Match para linha '{match['linha_nome']}' (Score: {match['score']:.2f}) não possui e-mails de contato. Pulando.")
                            # Marcar como notificado mesmo assim para não tentar de novo
                            sucessos_keys.append((match['edital_id'], match['linha_id']))
                            continue
                        
                        print(f"  -> Enviando notificação sobre '{match['edital_titulo'][:40]}...' para a linha '{match['linha_nome']}'...")
                        
                        sucesso = enviar_notificacao_match(match, emails_para_enviar)
                        
                        if sucesso:
                            print(f"     ... Sucesso.")
                            # Adiciona a chave composta (edital_id, linha_id) à lista
                            sucessos_keys.append((match['edital_id'], match['linha_id']))
                        else:
                            print(f"     ... FALHA ao enviar e-mail. Não será marcado como notificado.")
                    
                    # Marcar todos que tiveram sucesso (ou que foram pulados)
                    if sucessos_keys:
                        motor.marcar_matches_como_notificados(sucessos_keys)
                        
            except Exception as e:
                print(f"  ERRO CRÍTICO durante o processo de notificação: {e}")
                traceback.print_exc()

    else:
        print("\n[ETAPA 3, 4 e 5] Pulando cálculo de embeddings, matches e notificações (Modelo de IA não carregado).")

    end_time = time.time()
    print(f"\n--- ATUALIZAÇÃO CONCLUÍDA EM {end_time - start_time:.2f} SEGUNDOS ---")

if __name__ == "__main__":
    run_complete_update()