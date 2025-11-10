# simular_notificacao.py (VERSÃO 2)
import sqlite3
import datetime
import os
import traceback

DB_NAME = "projeto_grande.db"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_NAME)

# --- CONFIGURAÇÃO DO TESTE ---
# ID da linha "Comunicações, Computação, Cibernética e Inteligência"
LINHA_ID_ALVO = 3

def injetar_edital_e_match_falsos():
    print(f"Conectando ao banco de dados em: {DB_PATH}...")
    
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        # Habilita o row_factory para ler como dicionário
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()

        # 1. Busca os dados REAIS da Linha de Pesquisa Alvo
        print(f"Buscando dados da Linha de Pesquisa ID: {LINHA_ID_ALVO}...")
        cursor.execute("SELECT linha, programa, descricao FROM linha_ime WHERE id = ?", (LINHA_ID_ALVO,))
        linha_info = cursor.fetchone()
        
        if not linha_info:
            print(f"ERRO: Linha de Pesquisa com ID {LINHA_ID_ALVO} não encontrada.")
            conn.rollback()
            return

        linha_nome = linha_info['linha']
        programa_nome = linha_info['programa']
        descricao_real = linha_info['descricao'] # <-- A CHAVE PARA O TESTE!
        
        print(f"Linha alvo encontrada: '{linha_nome}'")

        # 2. Prepara o Edital Falso usando o texto real
        prazo_futuro = (datetime.date.today() + datetime.timedelta(days=1))
        
        edital_falso = (
            'Edital de Teste (Específico de Computação)',
            'SINAPSE-TESTE',
            'http://www.exemplo.com/teste-notificacao-v2', # Link único
            descricao_real, # <-- Usa a descrição real como texto do PDF
            descricao_real[:500] + "...", # Usa parte da descrição como resumo
            'aberto', # Status crucial
            None,
            prazo_futuro,
            'R$ 5.000.000,00',
            'ICTs, Institutos de Pesquisa',
            'Inteligência Artificial, Defesa, Cibernética',
            datetime.datetime.now()
        )

        # 3. Insere o Edital Falso
        print("Inserindo edital de teste 'aberto' com texto específico...")
        cursor.execute("""
        INSERT INTO edital (
            titulo, orgao, link_pagina, texto_pdf, resumo_pdf, status, modalidade,
            prazo_submissao, valor_estimado, elegibilidade, areas_tema, data_captura
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, edital_falso)
        
        novo_edital_id = cursor.lastrowid
        print(f"Edital de teste inserido com ID: {novo_edital_id}")

        # 4. Dados do Match Falso (para o teste IMEDIATO do notificador)
        match_falso = (
            novo_edital_id,
            'Edital de Teste (Específico de Computação)',
            LINHA_ID_ALVO,
            linha_nome,
            programa_nome,
            0.99,  # Score de 99% (garante passar no limiar)
            False  # Crucial: notificado = FALSE
        )

        # 5. Insere o Match Falso
        print("Inserindo match falso (99% score, não notificado)...")
        cursor.execute("""
        INSERT INTO match (
            edital_id, edital_titulo, linha_id, linha_nome, programa, score, notificado
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, match_falso)

        conn.commit()
        print("\nSUCESSO!")
        print(f"Edital {novo_edital_id} e Match (para Linha {LINHA_ID_ALVO}) foram injetados no banco.")
        
    except sqlite3.IntegrityError:
        print("\nERRO: O edital de teste (link_pagina) já existe no banco.")
        print("Delete o 'Edital de Teste' da tabela 'edital' (verifique o link_pagina) antes de rodar de novo.")
        if conn:
            conn.rollback()
    except sqlite3.Error as e:
        print(f"\nERRO de SQLite: {e}")
        traceback.print_exc()
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    injetar_edital_e_match_falsos()