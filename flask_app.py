from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session
from dotenv import load_dotenv
from motor_ia import MotorDeCompatibilidade
from functools import wraps
import os

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "uma-chave-secreta-muito-forte-para-producao")

print("Inicializando o servidor e carregando o modelo de IA...")
motor = MotorDeCompatibilidade()
print("Servidor pronto para receber requisições.")

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
            session['user_id'] = user.id
            session['user_email'] = user.email
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for('home'))
        else:
            flash("E-mail ou senha inválidos.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Você foi desconectado.", "info")
    return redirect(url_for('home'))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/linhas')
@login_required
def listar_linhas():
    user_id = session['user_id']
    df_linhas = motor.get_linhas_by_user(user_id)
    return render_template('linhas.html', linhas=df_linhas.to_dict(orient='records'))

@app.route('/linhas/nova', methods=['GET', 'POST'])
@login_required
def adicionar_linha():
    if request.method == 'POST':
        nova_linha_data = { "programa": request.form['programa'], "linha": request.form['linha'], "descricao": request.form['descricao'], "emails_contato": request.form['emails_contato'] }
        user_id = session['user_id']
        motor.add_linha(nova_linha_data, user_id)
        flash("Nova linha de pesquisa adicionada com sucesso!", "success")
        return redirect(url_for('listar_linhas'))
    return render_template('linha_form.html', titulo="Adicionar Nova Linha de Pesquisa", linha=None)

@app.route('/linhas/editar/<int:linha_id>', methods=['GET', 'POST'])
@login_required
def editar_linha(linha_id):
    user_id = session['user_id']
    # Busca a linha para garantir que o usuário tem permissão
    linha = motor.get_linha_by_id(linha_id, user_id)
    
    if linha is None:
        flash("Linha de pesquisa não encontrada ou você não tem permissão para editá-la.", "danger")
        return redirect(url_for('listar_linhas'))

    if request.method == 'POST':
        dados_atualizados = { "programa": request.form['programa'], "linha": request.form['linha'], "descricao": request.form['descricao'], "emails_contato": request.form['emails_contato'] }
        motor.update_linha(linha_id, dados_atualizados, user_id)
        flash("Linha de pesquisa atualizada com sucesso!", "success")
        return redirect(url_for('listar_linhas'))
    
    # Para a requisição GET, renderiza o formulário com os dados da linha
    return render_template('linha_form.html', titulo="Editar Linha de Pesquisa", linha=linha)

@app.route('/api/linhas-de-pesquisa')
def get_linhas_de_pesquisa():
    df_linhas = motor.obter_linhas_de_pesquisa()
    return jsonify(df_linhas.to_dict(orient='records'))

@app.route('/api/matches')
def get_matches():
    df_matches = motor.encontrar_matches()
    return jsonify(df_matches.to_dict(orient='records'))

@app.route('/api/edital/<int:edital_id>')
def get_edital_details(edital_id):
    details = motor.get_edital_details(edital_id)
    if details is not None:
        return jsonify(details.to_dict())
    return jsonify({"error": "Edital not found"}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5001)

