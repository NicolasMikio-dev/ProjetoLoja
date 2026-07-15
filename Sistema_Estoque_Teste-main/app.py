from flask import Flask, render_template, request, redirect, url_for 
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask import flash
import os
from datetime import datetime
import pandas as pdd 
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
    produtos = db.relationship('Produto', backref='dono', lazy=True)
    vendas = db.relationship('Venda', backref='dono', lazy='True')
    fiados = db.relationship('Venda', backref='dono', lazy='True')

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Float, nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
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
    return Usuario.query.get(int(user_id))

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
        novo_usuario = Usuario(username=username, senha=request.form['senha'])
        db.session.add(novo_usuario)
        db.session.commit()

        flash('Usuário registrado com sucesso!', 'success')
        return redirect(url_for('login'))
    return render_template('registrar.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = Usuario.query.filter_by(username=request.form['username']).first()

        if usuario and usuario.senha == request.form['senha']:
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
    produto = Produto.query.get_or_404(id)
    if request.method == 'POST':
        produto.nome = request.form['nome']
        produto.preco = request.form['preco']
        produto.quantidade = request.form['quantidade']
        try:
            db.session.commit()
            return redirect('/')
        except:
            return 'Houve um erro ao atualizar o produto'
    return render_template('editar.html', produto=produto)

@app.route('/registrarVendas.html', methods=['GET', 'POST'])
@login_required 
def registrarVendas():
    if request.method == 'POST':
        nome_produto = request.form['nome']
        preco = float(request.form['preco'])
        quantidade = int(request.form['quantidade'])
        pagamento = request.form['pagamento']
        cliente = request.form.get('cliente', '').strip()
        
        valor_total = preco * quantidade

        # Registra a venda no histórico geral
        nova_venda = Venda(
            produto_nome=nome_produto,
            quantidade=quantidade,
            valor_total=valor_total,
            pagamento=pagamento,
            usuario_id=current_user.id
        )
        db.session.add(nova_venda)

        # Se for fiado, registra também na tabela de devedores
        if pagamento == 'Fiado' and cliente:
            novo_fiado = Fiado(
                cliente=cliente,
                produto_nome=nome_produto,
                valor_fiado=valor_total,
                usuario_id=current_user.id
            )
            db.session.add(novo_fiado)

        # Opcional: Abater automaticamente do estoque de produtos
        produto_estoque = Produto.query.filter_by(nome=nome_produto, usuario_id=current_user.id).first()
        if produto_estoque and produto_estoque.quantidade >= quantidade:
            produto_estoque.quantidade -= quantidade

        db.session.commit()
        flash('Venda registrada com sucesso!', 'success')
        return redirect(url_for('registrarVendas'))

    vendas = Venda.query.filter_by(usuario_id=current_user.id).order_by(Venda.data_venda.desc()).all()
    return render_template('registrarVendas.html', vendas=vendas)



if __name__ == '__main__':
    app.run(debug=True)