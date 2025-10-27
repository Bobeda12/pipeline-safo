# app.py (Versão Local, com API login/register funcionais)
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session, abort
from dotenv import load_dotenv
from motor_ia import MotorDeCompatibilidade
from functools import wraps
import os
import datetime # Para conversão de data/hora

# *** CORREÇÃO CORS: Importar o CORS ***
from flask_cors import CORS

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "uma-chave-secreta-muito-forte-local")

# *** CORREÇÃO PROBLEMA 2: Definir tempo de vida da sessão ***
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=7)

# *** CORREÇÃO CORS: Habilitar o CORS para a aplicação ***
CORS(app) 

# --- [DEBUG] ---
# Adiciona logs de inicialização
print("--- [DEBUG] APP: Servidor Flask inicializado ---")

# *** CORREÇÃO: Otimizado para modo local ***
# Carrega o modelo de IA na inicialização (modo local)
print("Inicializando o motor de IA em modo local...")
try:
    motor = MotorDeCompatibilidade(load_model=True) 
    if motor.model is None:
         print("AVISO: Modelo de IA não carregado. Cálculo de similaridade pode falhar.")
    else:
         print("Motor em modo local completo (modelo de IA carregado).")
except Exception as e:
    print(f"ERRO CRÍTICO ao carregar motor de IA: {e}")
    motor = None


# Decorator para exigir login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Você precisa fazer login para acessar esta página.", "warning")
            # Salva a página que o usuário tentou acessar
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

# Rota Principal
@app.route('/')
def home():
    return render_template('index.html')

# Rota para Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Se o usuário já está logado, manda ele para a home
    if 'user_id' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash("E-mail e senha são obrigatórios.", "danger")
            return render_template('login.html')

        # --- [DEBUG] ---
        print(f"--- [DEBUG] LOGIN: Tentativa de login para: {email}")

        # Verifica o usuário no banco de dados (o motor já usa hash)
        user = motor.check_user(email, password) 

        if user:
            # Usuário autenticado, armazena na sessão
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            
            # *** CORREÇÃO PROBLEMA 2: Torna a sessão permanente ***
            session.permanent = True
            
            # Pega a página de destino (se existir)
            next_page = request.args.get('next')
            
            # --- [DEBUG] ---
            print(f"--- [DEBUG] LOGIN: Usuário {email} logado com SUCESSO. Redirecionando para: {next_page or url_for('home')}")
            
            # Evita redirecionar para a própria página de login ou logout
            if next_page and next_page != url_for('login') and next_page != url_for('logout') and next_page != url_for('register'):
                 return redirect(next_page)
            return redirect(url_for('home'))
        else:
            # --- [DEBUG] ---
            print(f"--- [DEBUG] LOGIN: Usuário {email} falhou no login (senha ou email incorretos).")
            flash("E-mail ou senha inválidos.", "danger")
            return render_template('login.html')
    
    # GET request
    return render_template('login.html')

# Rota para Registro de Conta
@app.route('/register', methods=['GET', 'POST'])
def register():
    # Se o usuário já está logado, manda ele para a home
    if 'user_id' in session:
        return redirect(url_for('home'))

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

        # Tenta adicionar o usuário (motor.add_user salva o hash)
        success, message = motor.add_user(email, password)

        if success:
            # --- [DEBUG] ---
            print(f"--- [DEBUG] REGISTER: Usuário {email} criado com SUCESSO.")
            flash("Conta criada com sucesso! Por favor, faça o login.", "success")
            return redirect(url_for('login'))
        else:
            # --- [DEBUG] ---
            print(f"--- [DEBUG] REGISTER: Falha ao criar {email}. Motivo: {message}")
            # Retorna 409 (Conflict) se o email já existe, 500 para outros erros
            flash(message, "danger")
            return render_template('register.html')
            
    # GET request
    return render_template('register.html')

# Rota para Logout
@app.route('/logout')
def logout():
    user_email = session.get('user_email', 'Usuário desconhecido')
    session.clear()
    # --- [DEBUG] ---
    print(f"--- [DEBUG] LOGOUT: Usuário {user_email} deslogado.")
    flash("Você saiu da sua conta.", "success")
    return redirect(url_for('home'))


# Rotas para Linhas de Pesquisa (Protegidas)
@app.route('/linhas')
@login_required
def listar_linhas():
    # --- [DEBUG] ---
    print(f"--- [DEBUG] Rota /linhas acessada por user_id: {session.get('user_id')}")
    user_id = session['user_id']
    linhas = motor.get_linhas_by_user(user_id)
    return render_template('linhas.html', linhas=linhas)

@app.route('/linhas/nova', methods=['GET', 'POST'])
@login_required
def adicionar_linha():
    user_id = session['user_id']
    if request.method == 'POST':
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
            flash("Nova linha de pesquisa adicionada! Pode levar um tempo para os embeddings serem calculados.", "success")
            # TODO: Disparar recálculo de embeddings/matches
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
            flash("Linha de pesquisa atualizada! Pode levar um tempo para os embeddings serem recalculados.", "success")
            # TODO: Disparar recálculo de embeddings/matches
            return redirect(url_for('listar_linhas'))
        except Exception as e:
             flash(f"Erro ao atualizar linha: {e}", "danger")
             dados_atualizados['id'] = linha_id
             return render_template('linha_form.html', titulo="Editar Linha de Pesquisa", linha=dados_atualizados)

    return render_template('linha_form.html', titulo="Editar Linha de Pesquisa", linha=linha)


# --- Rotas da API (Públicas) ---

# Função auxiliar para converter tipos não serializáveis (como datetime)
def make_serializable(obj):
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return None # Não enviar blobs de embedding
    raise TypeError(f"Tipo {type(obj)} não é serializável em JSON")

@app.route('/api/linhas-de-pesquisa')
def get_linhas_de_pesquisa():
    # --- [DEBUG] ---
    print(f"--- [DEBUG] API: Rota /api/linhas-de-pesquisa FOI CHAMADA ---")
    
    if motor is None:
        print(f"--- [DEBUG] API: ERRO: Motor de IA não foi carregado.")
        return jsonify({"error": "Motor de IA não inicializado"}), 500

    linhas = motor.obter_linhas_de_pesquisa_publico()
    
    # --- [DEBUG] ---
    if not linhas:
        print(f"--- [DEBUG] API: motor.obter_linhas_de_pesquisa_publico() retornou 0 linhas.")
        # Verifica se o DB existe para dar uma dica ao usuário
        db_path = motor.db_path
        print(f"--- [DEBUG] API: Verificando se o DB existe em: {db_path}")
        if not os.path.exists(db_path):
            print(f"--- [DEBUG] API: ERRO FATAL: O arquivo de banco de dados NÃO EXISTE em '{db_path}'.")
            print(f"--- [DEBUG] API: POR FAVOR, RODE 'python run_update.py' PRIMEIRO E TENTE NOVAMENTE. ---")
        else:
             print(f"--- [DEBUG] API: AVISO: Nenhuma linha encontrada, mas o DB existe. O DB pode estar vazio.")
    else:
        print(f"--- [DEBUG] API: motor.obter_linhas_de_pesquisa_publico() retornou {len(linhas)} linhas.")

    return jsonify(linhas)


@app.route('/api/matches')
def get_matches():
    # --- [DEBUG] ---
    print(f"--- [DEBUG] API: Rota /api/matches FOI CHAMADA ---")

    if motor is None:
        print(f"--- [DEBUG] API: ERRO: Motor de IA não foi carregado.")
        return jsonify({"error": "Motor de IA não inicializado"}), 500

    matches = motor.encontrar_matches_publico()
    
    try:
        # Garante que os tipos estão corretos para JSON
        serializable_matches = []
        for match in matches:
             match['score'] = float(match.get('score', 0.0))
             match['notificado'] = bool(match.get('notificado', False))
             serializable_matches.append(match)
        
        # --- [DEBUG] ---
        print(f"--- [DEBUG] API: motor.encontrar_matches_publico() retornou {len(serializable_matches)} matches.")

        return jsonify(serializable_matches)
    except Exception as e:
         print(f"--- [DEBUG] API: Erro ao serializar matches: {e}")
         return jsonify({"error": "Erro ao processar dados de matches"}), 500


@app.route('/api/edital/<int:edital_id>')
def get_edital_details_api(edital_id):
     # --- [DEBUG] ---
    print(f"--- [DEBUG] API: Rota /api/edital/{edital_id} FOI CHAMADA ---")

    if motor is None:
        print(f"--- [DEBUG] API: ERRO: Motor de IA não foi carregado.")
        return jsonify({"error": "Motor de IA não inicializado"}), 500

    detalhes = motor.get_edital_details(edital_id)
    if detalhes:
        try:
            # jsonify lida com objetos datetime automaticamente
            return jsonify(detalhes)
        except TypeError as e:
             print(f"--- [DEBUG] API: Erro ao serializar edital {edital_id}: {e}")
             # Tenta serializar manualmente como fallback
             try:
                 serializable_details = {k: make_serializable(v) if isinstance(v, (datetime.datetime, bytes)) else v for k, v in detalhes.items()}
                 return jsonify(serializable_details)
             except Exception as inner_e:
                  print(f"--- [DEBUG] API: Erro na serialização manual do edital {edital_id}: {inner_e}")
                  return jsonify({"error": f"Erro ao processar detalhes do edital: {inner_e}"}), 500
    else:
        print(f"--- [DEBUG] API: Edital {edital_id} NÃO ENCONTRADO.")
        abort(404, description="Edital não encontrado") # Retorna 404


if __name__ == '__main__':
    # Roda localmente na porta 5001, acessível na rede local, com debug ativado
    print("--- [DEBUG] APP: Iniciando servidor Flask... ---")
    app.run(host="0.0.0.0", debug=True, port=5001)

