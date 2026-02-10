# Sinapse - Sistema de Notificação e Análise para Seleção de Editais

Projeto desenvolvido na disciplina de Introdução a Projetos de Engenharia 2 (IPE 2) do Instituto Militar de Engenharia (IME) - 2025.

## Visão Geral

O Sinapse é uma solução de engenharia de software voltada para a otimização do processo de captação de recursos para pesquisa. O sistema automatiza o monitoramento de editais de fomento, utilizando Inteligência Artificial para analisar a compatibilidade semântica entre as chamadas públicas e as linhas de pesquisa da instituição.

O objetivo do projeto é mitigar a perda de oportunidades de financiamento decorrente da dispersão de informações, centralizando a busca e oferecendo uma análise preliminar de aderência técnica.

## Arquitetura do Sistema

O projeto opera através de um pipeline de dados contínuo, estruturado em três módulos principais:

1. Coleta de Dados (Web Scraping): Um crawler desenvolvido com o framework Scrapy monitora periodicamente o portal da FINEP, extraindo metadados e arquivos PDF dos editais.
2. Processamento e IA:
   - Extração de texto dos documentos PDF.
   - Vetorização (Embeddings) utilizando o modelo de linguagem "paraphrase-multilingual-MiniLM-L12-v2" (Sentence Transformers).
   - Cálculo de similaridade de cosseno para determinar o grau de pertinência (score) entre o edital e as linhas de pesquisa cadastradas.
3. Interface e Notificação: Aplicação Web em Flask que permite o gerenciamento de linhas de pesquisa e visualização dos resultados, acoplada a um módulo de notificação por e-mail para alertas de alta relevância.

## Tecnologias Utilizadas

- Linguagem: Python 3.10+
- Backend: Flask
- Banco de Dados: SQLite
- Crawler: Scrapy e PyPDF2
- Inteligência Artificial: Sentence-Transformers e Scikit-learn
- Frontend: HTML5 e Bootstrap 5

## Estrutura do Repositório

- app.py: Aplicação principal e rotas do servidor web.
- finep_spider.py: Módulo de extração de dados (crawler).
- motor_ia.py: Lógica de carregamento do modelo de NLP e operações vetoriais.
- run_update.py: Script de orquestração que executa a coleta e atualização dos scores.
- notificador.py: Módulo de envio automático de e-mails.

## Instruções de Execução

1. Instale as dependências listadas no arquivo requirements.txt.
2. Configure as variáveis de ambiente para o envio de e-mails (SMTP).
3. Execute o script "run_update.py" para realizar a primeira carga de dados e processamento vetorial.
4. Inicie o servidor web através do arquivo "app.py".

## Autor

Breno Bobeda - Engenharia de Computação (IME)
