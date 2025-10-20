import os
from motor_ia import MotorDeCompatibilidade
# Importe aqui as funções dos seus crawlers (Equipas A e B)
# Exemplo: from crawler_finep import rodar_crawler_finep
# Exemplo: from crawler_ime import rodar_crawler_ime

def executar_atualizacao_completa():
    """
    Este script é executado pelo GitHub Actions.
    Ele coordena todo o processo de atualização de dados.
    """
    print("--- INICIANDO TAREFA DE ATUALIZAÇÃO AUTOMÁTICA ---")

    # ETAPA 1: Executar os crawlers para buscar novos dados
    # Esta parte dependerá dos scripts das outras equipas.
    # Por agora, vamos assumir que os dados já existem no DB.
    print("[ETAPA 1] Crawlers (simulado). Usando dados existentes.")
    # rodar_crawler_finep()
    # rodar_crawler_ime()

    # ETAPA 2: Pré-calcular os embeddings para as linhas do IME
    # O ideal é que este script seja inteligente e só calcule para novas linhas.
    print("[ETAPA 2] Pré-calculando embeddings...")
    os.system("python pre_calcular_embeddings_ime.py")
    print("Cálculo de embeddings concluído.")

    # ETAPA 3: Executar o motor de IA para encontrar e salvar os matches
    print("[ETAPA 3] Executando o motor de compatibilidade...")
    # Inicializamos o motor em modo pesado para esta tarefa
    motor = MotorDeCompatibilidade(load_model=True)
    num_matches = motor.encontrar_e_salvar_matches()
    print(f"Motor de compatibilidade concluído. {num_matches} matches salvos.")

    print("--- TAREFA DE ATUALIZAÇÃO AUTOMÁTICA CONCLUÍDA ---")

if __name__ == "__main__":
    executar_atualizacao_completa()
