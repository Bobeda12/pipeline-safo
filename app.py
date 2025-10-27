# app.py (Versão Local, com API login/register funcionais)
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session, abort
from dotenv import load_dotenv
from motor_ia import MotorDeCompatibilidade
from functools import wraps
import os
import datetime # Para conversão de data/hora
import traceback # Para log de erros

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "uma-chave-secreta-muito-forte-local")

print("Inicializando o motor de IA em modo local...")
# *** CORREÇÃO: Carregar o modelo de IA localmente (load_model=True) ***
motor = MotorDeCompatibilidade(load_model=True) 
if motor.model is None:
     print("AVISO: Modelo de IA não carregado. O cálculo de similaridade em tempo real não funcionará.")
else:
    print("Motor em modo local completo (modelo de IA carregado).")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Você precisa fazer login para acessar esta página.", "warning")
            return redirect(url_for('login')) 
        return f(*args, **kwargs)
    return decorated_function

# Rota Principal
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash("E-mail e senha são obrigatórios.", "danger")
            return render_template('login.html')

        user = motor.check_user(email, password) # motor.check_user agora verifica o hash

        if user:
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            flash(f"Login realizado com sucesso! Bem-vindo, {user['email']}.", "success")
            return redirect(url_for('home'))
        else:
            flash("E-mail ou senha inválidos.", "danger")
            return render_template('login.html')
    
    # Método GET
    return render_template('login.html')

# *** Rota de Registro RESTAURADA ***
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not email or not password or not confirm_password:
            flash("Todos os campos são obrigatórios.", "danger")
            return render_template('register.html')
        
        if password != confirm_password:
            flash("As senhas não coincidem.", "danger")
            return render_template('register.html')
        
        if len(password) <= 4:
             flash("Senha muito curta (precisa ter mais de 4 caracteres).", "danger")
             return render_template('register.html')

        success, message = motor.add_user(email, password) # motor.add_user salva o hash

        if success:
            flash("Conta criada com sucesso! Você já pode fazer login.", "success")
            return redirect(url_for('login'))
        else:
            flash(message, "danger") # Mensagem de erro (ex: "E-mail já cadastrado")
            return render_template('register.html')

    # Método GET
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("Você saiu do sistema.", "success")
    return redirect(url_for('home'))


# Rotas para Linhas de Pesquisa (Protegidas)
@app.route('/linhas')
@login_required
def listar_linhas():
    user_id = session['user_id']
    linhas = motor.get_linhas_by_user(user_id)
    return render_template('linhas.html', linhas=linhas)

@app.route('/linhas/nova', methods=['GET', 'POST'])
@login_required
def adicionar_linha():
    if request.method == 'POST':
        user_id = session['user_id']
        nova_linha_data = {
            "programa": request.form.get('programa', '').strip(),
            "linha": request.form.get('linha', '').strip(),
            "descricao": request.form.get('descricao', '').strip(),
            "emails_contato": request.form.get('emails_contato', '').strip()
        }
        if not nova_linha_data['programa'] or not nova_linha_data['linha'] or not nova_linha_data['descricao']:
             flash("Programa, Linha e Descrição são obrigatórios.", "danger")
             return render_template('linha_form.html', titulo="Adicionar Nova Linha de Pesquisa", linha=nova_linha_data)
        try:
            motor.add_linha(nova_linha_data, user_id)
            flash("Nova linha de pesquisa adicionada! O recálculo dos matches pode levar alguns minutos.", "success")
            return redirect(url_for('listar_linhas'))
        except Exception as e:
            flash(f"Erro ao adicionar linha: {e}", "danger")
            return render_template('linha_form.html', titulo="Adicionar Nova Linha de Pesquisa", linha=nova_linha_data)

    return render_template('linha_form.html', titulo="Adicionar Nova Linha de Pesquisa", linha=None)

@app.route('/linhas/editar/<int:linha_id>', methods=['GET', 'POST'])
@login_required
def editar_linha(linha_id):
    user_id = session['user_id']
    linha = motor.get_linha_by_id(linha_id, user_id)
    if linha is None:
        flash("Linha de pesquisa não encontrada ou você não tem permissão para editá-la.", "danger")
        return redirect(url_for('listar_linhas'))

    if request.method == 'POST':
        dados_atualizados = {
             "programa": request.form.get('programa', '').strip(),
             "linha": request.form.get('linha', '').strip(),
             "descricao": request.form.get('descricao', '').strip(),
             "emails_contato": request.form.get('emails_contato', '').strip()
        }
        if not dados_atualizados['programa'] or not dados_atualizados['linha'] or not dados_atualizados['descricao']:
             flash("Programa, Linha e Descrição são obrigatórios.", "danger")
             dados_atualizados['id'] = linha_id 
             return render_template('linha_form.html', titulo="Editar Linha de Pesquisa", linha=dados_atualizados)
        try:
            motor.update_linha(linha_id, dados_atualizados, user_id)
            flash("Linha de pesquisa atualizada! O recálculo dos matches pode levar alguns minutos.", "success")
            return redirect(url_for('listar_linhas'))
        except Exception as e:
             flash(f"Erro ao atualizar linha: {e}", "danger")
             dados_atualizados['id'] = linha_id
             return render_template('linha_form.html', titulo="Editar Linha de Pesquisa", linha=dados_atualizados)

    return render_template('linha_form.html', titulo="Editar Linha de Pesquisa", linha=linha)


# --- Rotas da API (Públicas ou chamadas via JS) ---

# Função auxiliar para converter tipos não serializáveis
def make_serializable(obj):
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return None 
    raise TypeError(f"Tipo {type(obj)} não é serializável em JSON")

@app.route('/api/linhas-de-pesquisa')
def get_linhas_de_pesquisa():
    # --- ADICIONADO DEBUG ---
    print("\n--- [DEBUG] API: Rota /api/linhas-de-pesquisa FOI CHAMADA ---")
    try:
        linhas = motor.obter_linhas_de_pesquisa_publico()
        print(f"--- [DEBUG] API: motor.obter_linhas_de_pesquisa_publico() retornou {len(linhas)} linhas.")
        
        if not linhas:
            print(f"--- [DEBUG] API: AVISO: Nenhuma linha encontrada.")
            print(f"--- [DEBUG] API: Verificando se o DB existe em: {motor.db_path}")
            if not os.path.exists(motor.db_path):
                print(f"--- [DEBUG] API: ERRO FATAL: O arquivo de banco de dados NÃO EXISTE em '{motor.db_path}'.")
                print(f"--- [DEBUG] API: POR FAVOR, RODE 'python run_update.py' PRIMEIRO E TENTE NOVAMENTE. ---")
            else:
                 print(f"--- [DEBUG] API: O DB existe. A tabela 'linha_ime' pode estar vazia ou 'run_update.py' falhou ao popular.")
        
        return jsonify(linhas)
    
    except Exception as e:
        print(f"--- [DEBUG] API: ERRO CRÍTICO em get_linhas_de_pesquisa: {e} ---")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    # --- FIM DEBUG ---

@app.route('/api/matches')
def get_matches():
    # --- ADICIONADO DEBUG ---
    print("\n--- [DEBUG] API: Rota /api/matches FOI CHAMADA ---")
    try:
        matches = motor.encontrar_matches_publico()
        print(f"--- [DEBUG] API: motor.encontrar_matches_publico() retornou {len(matches)} matches.")
        if not matches:
            print(f"--- [DEBUG] API: AVISO: Nenhum match encontrado. Verifique se 'run_update.py' completou a 'Etapa 4'.")

         # Converte datas/outros tipos se necessário antes de retornar JSON
        serializable_matches = []
        for match in matches:
             match['score'] = float(match['score']) if match.get('score') is not None else 0.0
             match['notificado'] = bool(match['notificado']) if match.get('notificado') is not None else False
             serializable_matches.append(match)
        return jsonify(serializable_matches)
    
    except Exception as e:
         print(f"--- [DEBUG] API: ERRO CRÍTICO em get_matches: {e} ---")
         traceback.print_exc()
         return jsonify({"error": "Erro ao processar dados de matches"}), 500
    # --- FIM DEBUG ---


@app.route('/api/edital/<int:edital_id>')
def get_edital_details_api(edital_id):
    # --- ADICIONADO DEBUG ---
    print(f"\n--- [DEBUG] API: Rota /api/edital/{edital_id} FOI CHAMADA ---")
    try:
        detalhes = motor.get_edital_details(edital_id)
        if detalhes:
            print(f"--- [DEBUG] API: Encontrado edital ID {edital_id}: {detalhes.get('titulo')}")
            # Tenta serializar, convertendo datas/bytes que o jsonify padrão não lida
            serializable_details = {}
            for k, v in detalhes.items():
                if isinstance(v, (datetime.datetime, datetime.date)):
                    serializable_details[k] = v.isoformat()
                elif isinstance(v, bytes):
                    serializable_details[k] = None # Ignora bytes (ex: embeddings)
                else:
                    serializable_details[k] = v
            return jsonify(serializable_details)
        else:
            print(f"--- [DEBUG] API: ERRO: Edital ID {edital_id} NÃO ENCONTRADO.")
            abort(404, description="Edital não encontrado") # Retorna 404
            
    except Exception as e:
         print(f"--- [DEBUG] API: ERRO CRÍTICO em get_edital_details_api (ID: {edital_id}): {e} ---")
         traceback.print_exc()
         return jsonify({"error": f"Erro ao processar detalhes do edital: {e}"}), 500
    # --- FIM DEBUG ---


if __name__ == '__main__':
    # Roda localmente na porta 5001, acessível na rede local, com debug ativado
    app.run(host="0.0.0.0", debug=True, port=5001)

