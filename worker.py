from dotenv import load_dotenv
from motor_ia import MotorDeCompatibilidade
import traceback

def run_worker():
    """
    Função principal do robô (Cron Job).
    1. Inicializa o motor de IA em modo pesado.
    2. Executa o pipeline de cálculo de compatibilidade.
    3. Salva os resultados no banco de dados.
    """
    print("Iniciando o worker para cálculo de compatibilidade...")
    
    # Carrega as variáveis de ambiente (como DATABASE_URL)
    load_dotenv()
    
    try:
        # Inicializa o motor no modo completo, carregando o modelo de IA pesado
        motor = MotorDeCompatibilidade(load_model=True)
        
        # O método 'encontrar_e_salvar_matches' faz todo o trabalho pesado
        num_matches = motor.encontrar_e_salvar_matches()
        
        print(f"Worker concluído. {num_matches} matches foram processados e salvos.")
        
    except Exception as e:
        print("!!!!!! OCORREU UM ERRO DURANTE A EXECUÇÃO DO WORKER !!!!!!")
        # Imprime o erro detalhado no log do Render para podermos depurar
        traceback.print_exc()

if __name__ == '__main__':
    run_worker()

