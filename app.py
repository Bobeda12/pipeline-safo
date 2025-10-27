# app.py (Versão Local, com API login/register funcionais)
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash, session, abort
from dotenv import load_dotenv
from motor_ia import MotorDeCompatibilidade
from functools import wraps
import os
import datetime # Para conversão de data/hora

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "uma-chave-secreta-muito-forte-local")

print("Inicializando o motor de IA em modo local...")
motor = MotorDeCompatibilidade(load_model=True) # Carrega o modelo localmente
if motor.model is None:
     print("AVISO: Modelo de IA não carregado. Cálculo de similaridade pode falhar se não pré-calculado.")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Você precisa fazer login para acessar esta página.", "warning")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# Rota Principal
@app.route('/')
def home():
    return render_template('index.html')

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
            flash("Nova linha de pesquisa adicionada! Pode levar um tempo para os embeddings serem calculados.", "success")
             # Idealmente, aqui você dispararia um recálculo de embeddings/matches
             # Para simplificar, o usuário terá que rodar run_update.py manualmente
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
             # Passa os dados *não salvos* de volta para o formulário
             dados_atualizados['id'] = linha_id # Mantém o ID
             return render_template('linha_form.html', titulo="Editar Linha de Pesquisa", linha=dados_atualizados)
        try:
            motor.update_linha(linha_id, dados_atualizados, user_id)
            flash("Linha de pesquisa atualizada! Pode levar um tempo para os embeddings serem recalculados.", "success")
             # Idealmente, aqui você dispararia um recálculo de embeddings/matches
            return redirect(url_for('listar_linhas'))
        except Exception as e:
             flash(f"Erro ao atualizar linha: {e}", "danger")
             # Passa os dados *não salvos* de volta para o formulário
             dados_atualizados['id'] = linha_id # Mantém o ID
             return render_template('linha_form.html', titulo="Editar Linha de Pesquisa", linha=dados_atualizados)

    # GET request: apenas exibe o formulário com os dados existentes
    return render_template('linha_form.html', titulo="Editar Linha de Pesquisa", linha=linha)


# --- Rotas da API (Públicas ou chamadas via JS) ---

# API para Login (usada pelo modal via Fetch)
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"success": False, "message": "E-mail e senha são obrigatórios."}), 400

    user = motor.check_user(email, password) # motor.check_user agora verifica o hash

    if user:
        session['user_id'] = user['id']
        session['user_email'] = user['email']
        return jsonify({
            "success": True,
            "message": "Login realizado com sucesso!",
            "user_email": user['email']
        })
    else:
        return jsonify({"success": False, "message": "E-mail ou senha inválidos."}), 401

# API para Cadastro (usada pelo modal via Fetch)
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"success": False, "message": "E-mail e senha são obrigatórios para cadastro."}), 400

    # Adicionar validações extras se necessário (formato do email, força da senha)
    if len(password) <= 4:
         return jsonify({"success": False, "message": "Senha muito curta (precisa ter mais de 4 caracteres)."}), 400

    success, message = motor.add_user(email, password) # motor.add_user salva o hash

    if success:
        return jsonify({"success": True, "message": message})
    else:
        # Retorna 409 (Conflict) se o email já existe, 500 para outros erros
        status_code = 409 if "já está cadastrado" in message else 500
        return jsonify({"success": False, "message": message}), status_code

# Rota para Logout
@app.route('/logout')
def logout():
    session.clear()
    # Retorna JSON para a chamada Fetch do JavaScript
    return jsonify({"success": True, "message": "Logout realizado com sucesso."})


# --- Rotas API para dados do Dashboard ---

# Função auxiliar para converter tipos não serializáveis
def make_serializable(obj):
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    # Adicione outras conversões se necessário (ex: BLOB para string base64 se for enviar embeddings)
    # No caso de BLOB de embedding, provavelmente NÃO queremos enviá-lo via API
    if isinstance(obj, bytes):
        return None # Ou alguma representação, mas geralmente não é útil
    raise TypeError(f"Tipo {type(obj)} não é serializável em JSON")

@app.route('/api/linhas-de-pesquisa')
def get_linhas_de_pesquisa():
    linhas = motor.obter_linhas_de_pesquisa_publico()
    # Retorna diretamente, pois os dados (id, linha, programa) são serializáveis
    return jsonify(linhas)

@app.route('/api/matches')
def get_matches():
    matches = motor.encontrar_matches_publico()
     # Converte datas/outros tipos se necessário antes de retornar JSON
    try:
        serializable_matches = []
        for match in matches:
             # Converte score para float padrão (se não for)
             match['score'] = float(match['score']) if match.get('score') is not None else 0.0
             # Converte notificado para boolean (se não for)
             match['notificado'] = bool(match['notificado']) if match.get('notificado') is not None else False
             # Adicione conversões de data se a tabela match tiver colunas de data
             serializable_matches.append(match)
        return jsonify(serializable_matches)
    except Exception as e:
         print(f"Erro ao serializar matches: {e}")
         traceback.print_exc()
         return jsonify({"error": "Erro ao processar dados de matches"}), 500


@app.route('/api/edital/<int:edital_id>')
def get_edital_details_api(edital_id):
    detalhes = motor.get_edital_details(edital_id)
    if detalhes:
        # Usa a função auxiliar para garantir que datas sejam convertidas para string ISO
        try:
            # Não é mais necessário iterar e converter manualmente aqui se o motor já retorna dict
            # Precisamos garantir que _dict_factory ou a conversão no motor funcione bem com datas
            # A função get_edital_details já tenta converter para datetime, jsonify vai converter para ISO
            return jsonify(detalhes)
        except TypeError as e:
             print(f"Erro ao serializar detalhes do edital {edital_id}: {e}")
             # Tenta serializar manualmente como fallback
             try:
                 serializable_details = {k: make_serializable(v) if isinstance(v, (datetime.datetime, bytes)) else v for k, v in detalhes.items()}
                 return jsonify(serializable_details)
             except Exception as inner_e:
                  print(f"Erro na serialização manual do edital {edital_id}: {inner_e}")
                  return jsonify({"error": f"Erro ao processar detalhes do edital: {inner_e}"}), 500
    else:
        abort(404, description="Edital não encontrado") # Retorna 404


if __name__ == '__main__':
    # Roda localmente na porta 5001, acessível na rede local, com debug ativado
    app.run(host="0.0.0.0", debug=True, port=5001)

