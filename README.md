# Sinapse - Sistema de Notificação e Análise para Seleção de Editais

Projeto desenvolvido na disciplina de Introdução a Projetos de Engenharia 2 (IPE 2) do Instituto Militar de Engenharia (IME) - 2025.

## Visão Geral

O Sinapse é uma solução de engenharia de software voltada para a otimização do processo de captação de recursos para pesquisa. O sistema automatiza o monitoramento de editais de fomento, utilizando Inteligência Artificial para analisar a compatibilidade semântica entre as chamadas públicas e as linhas de pesquisa da instituição.

O objetivo do projeto é mitigar a perda de oportunidades de financiamento decorrente da dispersão de informações, centralizando a busca e oferecendo uma análise preliminar de aderência técnica.

## Arquitetura do Sistema

O projeto opera através de um pipeline de dados contínuo, estruturado em três módulos principais:

1. **Coleta de Dados (Web Scraping)**: Um crawler monitora periodicamente o portal da FINEP, extraindo metadados e textos dos editais.
2. **Processamento e IA**:
   - Extração de texto dos documentos.
   - Vetorização (Embeddings) utilizando o modelo de linguagem `paraphrase-multilingual-MiniLM-L12-v2` (Sentence Transformers).
   - Cálculo de similaridade de cosseno para determinar o grau de pertinência (score) entre o edital e as linhas de pesquisa cadastradas.
3. **Interface e Notificação**: Aplicação Web em Flask que permite o gerenciamento de linhas de pesquisa e visualização dos resultados, acoplada a um módulo de notificação por e-mail para alertas de alta relevância.

## Tecnologias Utilizadas

- **Linguagem**: Python 3.10+
- **Backend**: Flask e Flask-CORS
- **Banco de Dados**: SQLite
- **Crawler**: BeautifulSoup/Requests (`finep_spider.py`)
- **Inteligência Artificial**: Sentence-Transformers e Scikit-learn
- **Frontend**: HTML5 e Bootstrap 5

## Estrutura do Repositório

- `app.py`: Aplicação principal e rotas do servidor web.
- `finep_spider.py`: Módulo de extração de dados (crawler).
- `motor_ia.py`: Lógica de carregamento do modelo de NLP e operações vetoriais.
- `run_update.py`: Script de orquestração que executa a coleta e atualização dos scores.
- `notificador.py`: Módulo de envio automático de e-mails.

## ⚙️ Instruções de Execução

1. **Clone o repositório**
   ```bash
   git clone https://github.com/Bobeda12/Sinapse.git
   cd Sinapse
   ```

2. **Crie e ative o ambiente virtual**
   ```bash
   python -m venv venv
   # No Windows:
   venv\Scripts\activate
   # No Linux/Mac:
   source venv/bin/activate
   ```

3. **Instale as dependências**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure as Variáveis de Ambiente**
   - Crie um arquivo `.env` na raiz do projeto baseado no template:
     ```bash
     cp .env.example .env
     ```
   - Preencha as informações necessárias no `.env` (credenciais de e-mail SMTP para envio de notificações).

5. **Inicialize o Banco de Dados e os Modelos**
   - Execute o script de atualização para coletar os editais e processar a inteligência artificial pela primeira vez:
     ```bash
     python run_update.py
     ```

6. **Inicie o servidor Flask**
   ```bash
   python app.py
   ```
   Acesse a aplicação em: `http://localhost:5001/`

## 🔒 Segurança (Portfólio)
- Credenciais sensíveis e o banco de dados local (`*.db`) estão ignorados no controle de versão (`.gitignore`).
- O arquivo `.env.example` serve como template para as chaves necessárias, mantendo a segurança da aplicação.

## Autor

Breno Bobeda - Engenharia de Computação (IME)
