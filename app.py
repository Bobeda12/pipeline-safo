from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session
from dotenv import load_dotenv
from motor_ia import MotorDeCompatibilidade
from functools import wraps
import os

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "uma-chave-secreta-muito-forte")

print("Inicializando o servidor em modo de leitura (ultra-leve)...")
motor = MotorDeCompatibilidade(load_model=False)
print("Servidor pronto.")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Você precisa fazer login para acessar esta página.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = motor.check_user(email, password)
        if user:
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for('home'))
        else:
            flash("E-mail ou senha inválidos.", "danger")
    return render_template('login.html')

# ... (O resto das rotas, como home, logout, listar_linhas, etc., continuam iguais)

@app.route('/api/linhas-de-pesquisa')
def get_linhas_de_pesquisa():
    linhas = motor.obter_linhas_de_pesquisa_publico()
    return jsonify(linhas)

@app.route('/api/matches')
def get_matches():
    matches = motor.encontrar_matches_publico()
    return jsonify(matches)

@app.route('/api/edital/<int:edital_id>')
def get_edital_details(edital_id):
    detalhes = motor.get_edital_details(edital_id)
    if detalhes:
        return jsonify(detalhes)
    return jsonify({"error": "Edital not found"}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5001)

