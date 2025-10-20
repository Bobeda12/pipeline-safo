from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session
from dotenv import load_dotenv
from motor_ia import MotorDeCompatibilidade
from functools import wraps
import os
import pandas as pd

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "uma-chave-secreta-muito-forte")

print("Inicializando o servidor em modo de leitura (leve)...")
# Inicializa o motor em modo leve, sem carregar o modelo de IA pesado
motor = MotorDeCompatibilidade(load_model=False)
print("Servidor pronto para receber requisições.")


# --- DECORATOR DE AUTENTICAÇÃO ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Você precisa fazer login para acessar esta página.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROTAS DE AUTENTICAÇÃO E GERENCIAMENTO (sem alterações na lógica) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    # ... (código da função login)
    pass # Este bloco foi omitido para brevidade, mantenha seu código original aqui

@app.route('/logout')
def logout():
    # ... (código da função logout)
    pass # Este bloco foi omitido para brevidade, mantenha seu código original aqui

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/linhas')
@login_required
def listar_linhas():
    # ... (código da função listar_linhas)
    pass # Este bloco foi omitido para brevidade, mantenha seu código original aqui

@app.route('/linhas/nova', methods=['GET', 'POST'])
@login_required
def adicionar_linha():
    # ... (código da função adicionar_linha)
    pass # Este bloco foi omitido para brevidade, mantenha seu código original aqui

@app.route('/linhas/editar/<int:linha_id>', methods=['GET', 'POST'])
@login_required
def editar_linha(linha_id):
    # ... (código da função editar_linha)
    pass # Este bloco foi omitido para brevidade, mantenha seu código original aqui


# --- ROTAS DE API (MODIFICADAS PARA SEREM LEVES) ---

@app.route('/api/linhas-de-pesquisa')
def get_linhas_de_pesquisa():
    """Busca a lista de linhas de pesquisa diretamente do banco."""
    df_linhas = motor.obter_linhas_de_pesquisa()
    return jsonify(df_linhas.to_dict(orient='records'))

@app.route('/api/matches')
def get_matches():
    """
    Busca os resultados de compatibilidade PRÉ-CALCULADOS da tabela 'match'.
    Esta rota não executa a IA, por isso é muito rápida e leve.
    """
    try:
        # Consulta SQL para juntar as tabelas e obter os dados formatados
        query = """
            SELECT 
                m.score,
                m.edital_id,
                m.linha_id,
                e.titulo as edital_titulo,
                l.linha as linha_nome,
                l.programa
            FROM match m
            JOIN edital e ON m.edital_id = e.id
            JOIN linha_ime l ON m.linha_id = l.id;
        """
        df_matches = pd.read_sql(query, motor.engine)
        return jsonify(df_matches.to_dict(orient='records'))
    except Exception as e:
        print(f"Erro ao buscar matches pré-calculados: {e}")
        # Retorna uma lista vazia em caso de erro (ex: tabela 'match' ainda não existe)
        return jsonify([])

if __name__ == '__main__':
    app.run(debug=True, port=5001)

