# IA Safo Avançada - Matcher de Editais e Linhas de Pesquisa

Este projeto é um sistema web desenvolvido em **Python (Flask)** que utiliza Inteligência Artificial para analisar e calcular o *match* (compatibilidade) entre linhas de pesquisa cadastradas por pesquisadores e editais (como os da Finep). 

## 🚀 Funcionalidades

- **Autenticação de Usuários**: Sistema completo de login e registro para pesquisadores.
- **Gerenciamento de Linhas de Pesquisa**: CRUD para cadastrar, editar e visualizar linhas de pesquisa de interesse.
- **Motor de IA (Embeddings)**: Utiliza IA para processar textos das linhas de pesquisa e dos editais, calculando a similaridade semântica entre eles.
- **Web Scraping/Coleta de Editais**: Conta com um spider (scraper) para coletar dados de editais automaticamente (`finep_spider.py`).
- **Sistema de Notificação**: Disparo de e-mails para os pesquisadores quando um edital de alta compatibilidade é encontrado (`notificador.py`).
- **API REST**: Rotas públicas para obter linhas de pesquisa, matches e detalhes de editais.

## 🛠️ Tecnologias Utilizadas

- **Backend**: Python, Flask, Flask-CORS
- **Banco de Dados**: SQLite
- **Inteligência Artificial**: Processamento de Linguagem Natural e embeddings para cálculo de similaridade (Motor IA).
- **Web Scraping**: BeautifulSoup/Requests (via `finep_spider.py`)
- **Automação**: Agendamento de atualizações (`run_update.py`)

## ⚙️ Como executar o projeto localmente

1. **Clone o repositório**
   ```bash
   git clone <URL_DO_SEU_REPOSITORIO>
   cd "ia safo avançada"
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
   - Crie um arquivo `.env` na raiz do projeto baseado no `.env.example`:
     ```bash
     cp .env.example .env
     ```
   - Preencha as informações necessárias no `.env` (credenciais de e-mail).

5. **Inicialize o Banco de Dados e os Modelos**
   - Execute o script de atualização para criar o banco e preenchê-lo com os dados iniciavales:
     ```bash
     python run_update.py
     ```

6. **Inicie o servidor Flask**
   ```bash
   python app.py
   ```
   Acesse a aplicação em: `http://localhost:5001/`

## 🔒 Segurança e Boas Práticas (Portfólio)
- Credenciais sensíveis e o banco de dados local (`*.db`) estão ignorados no controle de versão (`.gitignore`).
- As senhas dos usuários devem ser armazenadas com hashing (verifique a implementação no motor).
- O arquivo `.env.example` serve como template para as chaves necessárias.

---
Desenvolvido por **[Seu Nome/Contato]**
