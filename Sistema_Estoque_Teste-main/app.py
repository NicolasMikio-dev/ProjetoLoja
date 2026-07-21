from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask import flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
import pandas as pd
import io
 
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///produtos.db'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-padrao-apenas-para-desenvolvimento')
db = SQLAlchemy(app)
 
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
 
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    senha = db.Column(db.String(50), nullable=False)
    produtos = db.relationship('Produto', backref='dono', lazy='select')
    vendas = db.relationship('Venda', backref='dono', lazy='select')
    fiados = db.relationship('Fiado', backref='dono', lazy='select')
 
class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Float, nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class Prateleira(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Float, nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
 
class Prateleira_gato(db.Model):
    id_gatos = db.Column(db.Integer, primary_key=True)
    nome_gatos = db.Column(db.String(100), nullable=False)
    preco_gatos = db.Column(db.Float, nullable=False)
    quantidade_gatos = db.Column(db.Integer, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class Venda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_nome = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    valor_total = db.Column(db.Float, nullable=False)
    pagamento = db.Column(db.String(50), nullable=False)
    data_venda = db.Column(db.DateTime, default=datetime.now)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
 
class Fiado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(100), nullable=False)
    produto_nome = db.Column(db.String(100), nullable=False)
    valor_fiado = db.Column(db.Float, nullable=False)
    data_venda = db.Column(db.DateTime, default=datetime.now)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False) 
 
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))
 
with app.app_context():
    db.create_all()
 
 
@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
 
    if request.method == 'POST':
        username = request.form['username']
 
        usuario_existente = Usuario.query.filter_by(username=username).first()
        
        if usuario_existente:
            flash('Este nome de usuário já está em uso. Escolha outro.', 'danger')
            return redirect(url_for('registrar'))
 
        senha_hash = generate_password_hash(request.form['senha'])
        novo_usuario = Usuario(username=username, senha=senha_hash)
        db.session.add(novo_usuario)
        db.session.commit()
 
        flash('Usuário registrado com sucesso!', 'success')
        return redirect(url_for('login'))
    return render_template('registrar.html')
 
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = Usuario.query.filter_by(username=request.form['username']).first()
 
        if usuario and check_password_hash(usuario.senha, request.form['senha']):
            login_user(usuario)
            return redirect(url_for('index'))
        
        else:
            flash('Usuário ou senha incorretos. Tente novamente.', 'danger')
    return render_template('login.html')
 
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))
 
 
@app.route('/', methods=['GET', 'POST'])
@login_required 
def index():
    if request.method == 'POST':
        nome_produto = request.form['nome']
        preco_produto = request.form['preco']
        quantidade_produto = request.form['quantidade']
 
        novo_produto = Produto(
            nome=nome_produto, 
            preco=float(preco_produto),
            quantidade=int(quantidade_produto),
            usuario_id=current_user.id
        )
        db.session.add(novo_produto)
        db.session.commit()
        return redirect('/')
    
    busca = request.args.get('busca') 
 
    query_base = Produto.query.filter_by(usuario_id=current_user.id)
 
    if busca:
        produtos = query_base.filter(Produto.nome.contains(busca)).all()
    else:
        produtos = query_base.all()
 
    return render_template('index.html', produtos=produtos)
 
 
@app.route('/deletar/<int:id>')
@login_required
def delete(id):
    produto = Produto.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    db.session.delete(produto)
    db.session.commit()
    return redirect('/')
 
@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    produto = Produto.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    if request.method == 'POST':
        produto.nome = request.form['nome']
        produto.preco = float(request.form['preco'])
        produto.quantidade = int(request.form['quantidade'])
        try:
            db.session.commit()
            return redirect('/')
        except Exception as e:
            return f'Houve um erro ao atualizar o produto: {e}'
    return render_template('editar.html', produto=produto)

# =======================================================================
# CORREÇÃO: a rota da prateleira de produtos "normais" agora também busca
# os produtos da prateleira de gatos e envia os DOIS para o template, já
# que "prateleira.html" mostra as duas tabelas na mesma página.
# =======================================================================
@app.route('/prateleira', methods=['GET', 'POST'])
@login_required
def prateleira():
    if request.method == 'POST':
        nome_produto = request.form['nome']
        preco_produto = request.form['preco']
        quantidade_produto = request.form['quantidade']
 
        novo_produto_prateleira = Prateleira(
            nome=nome_produto, 
            preco=float(preco_produto),
            quantidade=int(quantidade_produto),
            usuario_id=current_user.id
        )
        db.session.add(novo_produto_prateleira)
        db.session.commit()
        return redirect(url_for('prateleira'))
    
    busca = request.args.get('busca') 
 
    query_base = Prateleira.query.filter_by(usuario_id=current_user.id)
 
    if busca:
        produtos = query_base.filter(Prateleira.nome.contains(busca)).all()
    else:
        produtos = query_base.all()

    # CORREÇÃO: antes essa variável nunca era criada nem enviada ao template,
    # por isso o Jinja2 acusava 'produto_gatos' is undefined.
    produtos_gatos = Prateleira_gato.query.filter_by(usuario_id=current_user.id).all()
 
    return render_template('prateleira.html', produtos=produtos, produtos_gatos=produtos_gatos)

@app.route('/deletar_prateleira/<int:id>')
@login_required
def deletar_prateleira(id):
    produto = Prateleira.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    db.session.delete(produto)
    db.session.commit()
    return redirect(url_for('prateleira'))
 
@app.route('/editar_prateleira/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_prateleira(id):
    produto = Prateleira.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    if request.method == 'POST':
        produto.nome = request.form['nome']
        produto.preco = float(request.form['preco'])
        produto.quantidade = int(request.form['quantidade'])
        try:
            db.session.commit()
            return redirect(url_for('prateleira'))
        except Exception as e:
            return f'Houve um erro ao atualizar o produto: {e}'
    return render_template('editar_prateleira.html', produto=produto)


# AQUI È DOS GATOS DAQUI PRA BAIXO

# =======================================================================
# CORREÇÃO PRINCIPAL: essa rota tinha a MESMA URL '/prateleira' da rota
# 'prateleira()' acima. Duas rotas com a mesma URL fazem o Flask/Werkzeug
# nunca conseguir chamar a segunda (o cadastro de produtos de gatos nunca
# rodava de verdade). Agora a URL é '/prateleira_gatos', exclusiva dela.
#
# Também trocamos "Prateleira(...)" por "Prateleira_gato(...)": o código
# original tentava criar um Prateleira com campos nome_gatos/preco_gatos/
# quantidade_gatos, que não existem nessa classe (só existem na classe
# Prateleira_gato) — isso geraria um TypeError.
# =======================================================================
@app.route('/prateleira_gatos', methods=['GET', 'POST'])
@login_required
def prateleira_gatos():
    if request.method == 'POST':
        nome_produto_gatos = request.form['nome_gatos']
        preco_produto_gatos = request.form['preco_gatos']
        quantidade_produto_gatos = request.form['quantidade_gatos']
 
        novo_produto_prateleira_gato = Prateleira_gato(
            nome_gatos=nome_produto_gatos, 
            preco_gatos=float(preco_produto_gatos),
            quantidade_gatos=int(quantidade_produto_gatos),
            usuario_id=current_user.id
        )
        db.session.add(novo_produto_prateleira_gato)
        db.session.commit()

    # a listagem de gatos é sempre exibida junto na página /prateleira
    return redirect(url_for('prateleira'))

@app.route('/deletar_prateleira_gatos/<int:id_gatos>')
@login_required
def deletar_prateleira_gatos(id_gatos):
    # CORREÇÃO: estava consultando o model errado (Prateleira em vez de
    # Prateleira_gato) e usando id=id_gatos, mas a chave primária dessa
    # tabela se chama id_gatos, não id.
    produto_gatos = Prateleira_gato.query.filter_by(id_gatos=id_gatos, usuario_id=current_user.id).first_or_404()
    db.session.delete(produto_gatos)
    db.session.commit()
    return redirect(url_for('prateleira'))
 
@app.route('/editar_prateleira_gatos/<int:id_gatos>', methods=['GET', 'POST'])
@login_required
def editar_prateleira_gatos(id_gatos):
    # CORREÇÃO: mesmo problema acima — precisa ser Prateleira_gato e
    # filtrar por id_gatos.
    produto_gatos = Prateleira_gato.query.filter_by(id_gatos=id_gatos, usuario_id=current_user.id).first_or_404()
    if request.method == 'POST':
        produto_gatos.nome_gatos = request.form['nome_gatos']
        produto_gatos.preco_gatos = float(request.form['preco_gatos'])
        produto_gatos.quantidade_gatos = int(request.form['quantidade_gatos'])
        try:
            db.session.commit()
            return redirect(url_for('prateleira'))
        except Exception as e:
            return f'Houve um erro ao atualizar o produto: {e}'
    return render_template('editar_prateleira_gatos.html', produto_gatos=produto_gatos)

 
@app.route('/registrarVendas', methods=['GET', 'POST'])
@login_required 
def registrarVendas():
    if request.method == 'POST':
        nome_produto = request.form['nome']
        preco = float(request.form['preco'])
        quantidade = int(request.form['quantidade'])
        pagamento = request.form['pagamento']
        cliente = request.form.get('cliente', '').strip()
        
        valor_total = preco * quantidade
 
        nova_venda = Venda(
            produto_nome=nome_produto,
            quantidade=quantidade,
            valor_total=valor_total,
            pagamento=pagamento,
            usuario_id=current_user.id
        )
        db.session.add(nova_venda)
 
        if pagamento == 'Fiado' and cliente:
            novo_fiado = Fiado(
                cliente=cliente,
                produto_nome=nome_produto,
                valor_fiado=valor_total,
                usuario_id=current_user.id
            )
            db.session.add(novo_fiado)
 
        produto_estoque = Produto.query.filter_by(nome=nome_produto, usuario_id=current_user.id).first()
        if produto_estoque and produto_estoque.quantidade >= quantidade:
            produto_estoque.quantidade -= quantidade
 
        db.session.commit()
        flash('Venda registrada com sucesso!', 'success')
        return redirect(url_for('registrarVendas'))
 
    vendas = Venda.query.filter_by(usuario_id=current_user.id).order_by(Venda.data_venda.desc()).all()
    return render_template('registrarVendas.html', vendas=vendas)
 
@app.route('/deletar_venda/<int:id>')
@login_required
def deletar_venda(id):
    venda = Venda.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    db.session.delete(venda)
    db.session.commit()
    return redirect(url_for('registrarVendas'))
 
@app.route('/fiados', methods=['GET', 'POST'])
@login_required
def fiados():
    if request.method == 'POST':
        cliente = request.form['cliente'].strip()
        produto_nome = request.form['produto_nome'].strip()
        valor_fiado = float(request.form['valor_fiado'])
 
        novo_fiado = Fiado(
            cliente=cliente,
            produto_nome=produto_nome,
            valor_fiado=valor_fiado,
            usuario_id=current_user.id
        )
        db.session.add(novo_fiado)
        db.session.commit()
        flash('Fiado registrado com sucesso!', 'success')
        return redirect(url_for('fiados'))
 
    lista_fiados = Fiado.query.filter_by(usuario_id=current_user.id).order_by(Fiado.data_venda.desc()).all()
    return render_template('fiados.html', fiados=lista_fiados)
 
@app.route('/editar_fiado/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_fiado(id):
    fiado = Fiado.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    if request.method == 'POST':
        fiado.cliente = request.form['cliente']
        fiado.produto_nome = request.form['produto_nome']
        fiado.valor_fiado = float(request.form['valor_fiado'])
        db.session.commit()
        flash('Registro de fiado atualizado!', 'success')
        return redirect(url_for('fiados'))
    return render_template('editar_fiado.html', fiado=fiado)
 
@app.route('/deletar_fiado/<int:id>')
@login_required
def deletar_fiado(id):
    fiado = Fiado.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    db.session.delete(fiado)
    db.session.commit()
    flash('Devedor removido com sucesso!', 'success')
    return redirect(url_for('fiados'))
 
@app.route('/exportar_excel')
@login_required
def exportar_excel():
    vendas = Venda.query.filter_by(usuario_id=current_user.id).all()
    
    data = []
    total_vendas = 0
    for v in vendas:
        total_vendas += v.valor_total
        data.append({
            'Data/Horário': v.data_venda.strftime('%d/%m/%Y %H:%M:%S'),
            'Produto': v.produto_nome,
            'Quantidade': v.quantidade,
            'Valor Total (R$)': v.valor_total,
            'Forma de Pagamento': v.pagamento
        })
    
    df = pd.DataFrame(data)
    
    df_resumo = pd.DataFrame([{
        'Data/Horário': 'TOTAL DO DIA / PERÍODO',
        'Produto': '-',
        'Quantidade': '-',
        'Valor Total (R$)': total_vendas,
        'Forma de Pagamento': '-'
    }])
    df_final = pd.concat([df, df_resumo], ignore_index=True)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False, sheet_name='Relatório de Vendas')
    
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f"relatorio_vendas_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    )

if __name__ == '__main__':
    app.run(debug=True)