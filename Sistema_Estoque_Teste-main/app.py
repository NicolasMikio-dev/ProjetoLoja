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
    # CORREÇÃO: Usuario.query.get() está depreciado no SQLAlchemy 2.0 (aviso no console)
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

        # CORREÇÃO: senha agora é armazenada com hash, nunca em texto puro
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

        # CORREÇÃO: comparação de senha agora usa check_password_hash (compatível com o hash salvo)
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
    # CORREÇÃO: agora filtra também por usuario_id, senão qualquer usuário logado
    # conseguia editar produtos de outras pessoas só sabendo o id
    produto = Produto.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    if request.method == 'POST':
        produto.nome = request.form['nome']
        # CORREÇÃO: preco e quantidade agora são convertidos para float/int,
        # antes eram salvos como string vinda do formulário
        produto.preco = float(request.form['preco'])
        produto.quantidade = int(request.form['quantidade'])
        try:
            db.session.commit()
            return redirect('/')
        except Exception as e:
            # CORREÇÃO: except genérico agora mostra o erro real, facilita debug
            return f'Houve um erro ao atualizar o produto: {e}'
    return render_template('editar.html', produto=produto)

# CORREÇÃO PRINCIPAL: rota renomeada de '/registrarVendas.html' para '/registrarVendas'.
# Era esse o motivo do erro 404: a página (GET) respondia em '/registrarVendas.html',
# mas o formulário enviava o POST para 'S' (sem .html), URL que não existia.
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

@app.route('/deletar_venda/<int:id>')
@login_required
def deletar_venda(id):
    venda = Venda.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    db.session.delete(venda)
    db.session.commit()
    return redirect(url_for('registrarVendas'))

@app.route('/fiados')
@login_required
def fiados():
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
    # Coleta as vendas do usuário logado
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
    
    # Adiciona uma linha de resumo ao final do Excel
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