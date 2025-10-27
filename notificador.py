# notificador.py
import smtplib
import ssl
import os
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Carrega variáveis de ambiente (EMAIL_SENDER, etc.)
load_dotenv()

def enviar_notificacao_match(match_info, lista_destinatarios):
    """
    Envia um e-mail de notificação sobre um novo match.
    
    :param match_info: Um dicionário (linha do DB) contendo todos os detalhes
                       (edital_titulo, linha_nome, score, link_pagina, etc.)
    :param lista_destinatarios: Uma lista de strings de e-mail.
    """
    
    # Configurações do E-mail (lidas do .env)
    SMTP_SERVER = os.getenv("SMTP_SERVER")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    EMAIL_SENDER = os.getenv("EMAIL_SENDER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

    if not all([SMTP_SERVER, SMTP_PORT, EMAIL_SENDER, EMAIL_PASSWORD]):
        print("  ERRO (Notificador): Configurações de SMTP não encontradas no .env.")
        return False

    # Extrai informações para o template
    try:
        titulo_edital = match_info['edital_titulo']
        linha_nome = match_info['linha_nome']
        programa = match_info['programa']
        score_percentual = round(match_info['score'] * 100, 1)
        link_pagina = match_info['link_pagina']
        
        prazo_str = 'Não informado'
        if match_info.get('prazo_submissao'):
             try:
                 # Converte data YYYY-MM-DD para DD/MM/YYYY
                 prazo_dt = match_info['prazo_submissao']
                 if isinstance(prazo_dt, str):
                     prazo_dt = prazo_dt.split(' ')[0] # Remove hora se houver
                     prazo_str = f"{prazo_dt[8:10]}/{prazo_dt[5:7]}/{prazo_dt[0:4]}"
                 elif hasattr(prazo_dt, 'strftime'):
                     prazo_str = prazo_dt.strftime('%d/%m/%Y')
             except Exception:
                 pass # Mantém 'Não informado'

    except KeyError as e:
        print(f"  ERRO (Notificador): 'match_info' incompleto. Faltando chave: {e}")
        return False

    # Cria a mensagem
    assunto = f"SINAPSE: Novo Edital Aderente à sua Linha de Pesquisa '{linha_nome}'"
    
    message = MIMEMultipart("alternative")
    message["Subject"] = assunto
    message["From"] = f"Sinapse Notificações <{EMAIL_SENDER}>"
    # Juntamos os destinatários para o cabeçalho 'To'
    message["To"] = ", ".join(lista_destinatarios)

    # [cite_start]Corpo do e-mail em texto puro e HTML (conforme Projeto IPE2 [cite: 70])
    text = f"""
    Olá, Pesquisador(a) do programa {programa},

    O sistema SINAPSE identificou um novo edital com alta aderência à sua linha de pesquisa:
    Linha de Pesquisa: {linha_nome}
    
    Edital: {titulo_edital}
    Prazo de Submissão: {prazo_str}
    Aderência (Score IA): {score_percentual}%

    Acesse o edital na página oficial:
    {link_pagina}

    Atenciosamente,
    Equipe Sinapse
    """
    
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6;">
        <p>Olá, Pesquisador(a) do programa <strong>{programa}</strong>,</p>
        <p>O sistema SINAPSE identificou um novo edital com alta aderência à sua linha de pesquisa:</p>
        
        <table style="width: 90%; margin: 20px 0; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 8px; width: 180px;"><strong>Linha de Pesquisa:</strong></td>
                <td style="padding: 8px;">{linha_nome}</td>
            </tr>
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 8px;"><strong>Edital:</strong></td>
                <td style="padding: 8px;">{titulo_edital}</td>
            </tr>
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 8px;"><strong>Prazo de Submissão:</strong></td>
                <td style="padding: 8px;">{prazo_str}</td>
            </tr>
            <tr style="background-color: #f9f9f9; border-bottom: 1px solid #ddd;">
                <td style="padding: 8px;"><strong>Aderência (Score IA):</strong></td>
                <td style="padding: 8px; font-weight: bold; font-size: 1.1em;">{score_percentual}%</td>
            </tr>
        </table>

        <p>Acesse o edital na página oficial:</p>
        <p style="margin: 25px 0;">
            <a href="{link_pagina}" style="background-color: #003366; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                Ver Edital
            </a>
        </p>
        
        <p style="font-size: 0.9em; color: #777;">Atenciosamente,<br>Equipe Sinapse</p>
      </body>
    </html>
    """

    # Anexa as partes text/plain e text/html à mensagem
    message.attach(MIMEText(text, "plain"))
    message.attach(MIMEText(html, "html"))

    # Conexão e Envio
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            # Envia o e-mail para a LISTA de destinatários
            server.sendmail(EMAIL_SENDER, lista_destinatarios, message.as_string())
        return True
    except Exception as e:
        print(f"  ERRO (Notificador): Falha ao enviar e-mail para {', '.join(lista_destinatarios)}.")
        print(f"  Erro SMTP: {e}")
        traceback.print_exc()
        return False