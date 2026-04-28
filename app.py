from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime
from sqlalchemy import text, inspect
import os
import math
import json
import re
import ssl
import urllib.request
import urllib.parse

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cardapio.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB
app.secret_key = 'cardapio-chave-secreta-2025'

ADMIN_SENHA = '6284'  # troque para a senha que quiser

EXTENSOES_PERMITIDAS = {'png', 'jpg', 'jpeg', 'webp'}
FRETE_POR_KM = 3

db = SQLAlchemy(app)


# ── MODELOS ───────────────────────────────────────────────

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    preco = db.Column(db.String(20), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    imagem = db.Column(db.String(200), nullable=True)
    visivel = db.Column(db.Boolean, default=True)
    estoque = db.Column(db.Integer, nullable=True, default=None)


class Kit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    preco = db.Column(db.String(20), nullable=False)
    imagem = db.Column(db.String(200), nullable=True)
    visivel = db.Column(db.Boolean, default=True)
    itens = db.relationship('KitItem', backref='kit', cascade='all, delete-orphan')


class KitItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kit_id = db.Column(db.Integer, db.ForeignKey('kit.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    quantidade = db.Column(db.Integer, default=1)
    produto = db.relationship('Produto')


class Aviso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.Text, nullable=False, default='')
    ativo = db.Column(db.Boolean, default=True)


class Configuracao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    endereco_loja = db.Column(db.String(300), nullable=False, default='')


class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_cliente = db.Column(db.String(100), nullable=False)
    tipo_entrega = db.Column(db.String(20), nullable=False)
    endereco = db.Column(db.String(300), nullable=True)
    cep = db.Column(db.String(10), nullable=True)
    frete = db.Column(db.Float, default=0)
    total = db.Column(db.Float, nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    itens = db.relationship('PedidoItem', backref='pedido', cascade='all, delete-orphan')


class PedidoItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'), nullable=False)
    produto_id = db.Column(db.Integer, nullable=True)
    produto_nome = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    preco_unit = db.Column(db.Float, nullable=False)


def get_aviso():
    aviso = Aviso.query.first()
    if not aviso:
        aviso = Aviso(texto='', ativo=False)
        db.session.add(aviso)
        db.session.commit()
    return aviso


def get_configuracao():
    cfg = Configuracao.query.first()
    if not cfg:
        cfg = Configuracao(endereco_loja='')
        db.session.add(cfg)
        db.session.commit()
    return cfg


with app.app_context():
    db.create_all()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    get_aviso()
    get_configuracao()
    # Migração: adiciona coluna estoque se ainda não existir
    insp = inspect(db.engine)
    if 'estoque' not in [c['name'] for c in insp.get_columns('produto')]:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE produto ADD COLUMN estoque INTEGER'))
            conn.commit()


# ── HELPERS ───────────────────────────────────────────────

def login_necessario(f):
    @wraps(f)
    def verificar(*args, **kwargs):
        if not session.get('admin_logado'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return verificar


def arquivo_permitido(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in EXTENSOES_PERMITIDAS


def salvar_imagem(arquivo):
    if arquivo and arquivo.filename and arquivo_permitido(arquivo.filename):
        filename = secure_filename(arquivo.filename)
        arquivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    return None


def remover_imagem(nome_arquivo):
    if nome_arquivo:
        caminho = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
        if os.path.exists(caminho):
            os.remove(caminho)


_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def extrair_cep(texto):
    """Extrai o CEP (8 dígitos) de um texto."""
    m = re.search(r'(\d{5})-?(\d{3})', texto)
    return (m.group(1) + m.group(2)) if m else None


def get_coords_por_cep(cep):
    """Retorna (lat, lon) de um CEP. Usa Brasil API para obter o endereço e Nominatim para as coordenadas."""
    cep = re.sub(r'\D', '', cep)

    # Passo 1: Brasil API → endereço estruturado (+ tenta coordenadas direto)
    url = f'https://brasilapi.com.br/api/cep/v2/{cep}'
    req = urllib.request.Request(url, headers={'User-Agent': 'SiteCardapio/1.0'})
    street, city, state = '', '', ''
    try:
        with urllib.request.urlopen(req, timeout=8, context=_ssl_ctx) as resp:
            data = json.loads(resp.read())
            coords = data.get('location', {}).get('coordinates', {})
            lat = coords.get('latitude')
            lon = coords.get('longitude')
            if lat and lon:
                return float(lat), float(lon)
            street = data.get('street', '')
            city   = data.get('city', '')
            state  = data.get('state', '')
    except Exception:
        return None

    if not city:
        return None

    # Passo 2: Nominatim com busca estruturada
    params = urllib.parse.urlencode({k: v for k, v in {
        'street': street, 'city': city, 'state': state,
        'country': 'Brazil', 'format': 'json', 'limit': 1,
    }.items() if v})
    url2 = f'https://nominatim.openstreetmap.org/search?{params}'
    req2 = urllib.request.Request(url2, headers={'User-Agent': 'SiteCardapio/1.0'})
    try:
        with urllib.request.urlopen(req2, timeout=10, context=_ssl_ctx) as resp2:
            data2 = json.loads(resp2.read())
            if data2:
                return float(data2[0]['lat']), float(data2[0]['lon'])
    except Exception:
        pass
    return None


def haversine(lat1, lon1, lat2, lon2):
    """Distância em linha reta em km entre dois pontos."""
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def itens_do_form(produtos):
    """Lê as quantidades de produtos enviadas no form do kit."""
    selecionados = []
    for p in produtos:
        qtd = int(request.form.get(f'prod_{p.id}', 0) or 0)
        if qtd > 0:
            selecionados.append((p.id, qtd))
    return selecionados


# ── ROTAS PÚBLICAS ────────────────────────────────────────

@app.route('/')
def cardapio():
    produtos = Produto.query.filter_by(visivel=True).all()
    kits = Kit.query.filter_by(visivel=True).all()
    aviso = get_aviso()
    return render_template('cardapio.html', produtos=produtos, kits=kits, aviso=aviso)


@app.route('/montar-kit')
def montar_kit():
    produtos = Produto.query.filter_by(visivel=True).all()
    return render_template('montar_kit.html', produtos=produtos)


@app.route('/produto/<int:id>')
def produto(id):
    p = Produto.query.get_or_404(id)
    return render_template('produto.html', produto=p)


@app.route('/kit/<int:id>')
def kit_detalhe(id):
    kit = Kit.query.get_or_404(id)
    return render_template('kit.html', kit=kit)


@app.route('/carrinho')
def carrinho():
    return render_template('carrinho.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin_logado'):
        return redirect(url_for('admin'))
    erro = None
    if request.method == 'POST':
        if request.form['senha'] == ADMIN_SENHA:
            session['admin_logado'] = True
            return redirect(url_for('admin'))
        erro = 'Senha incorreta.'
    return render_template('login.html', erro=erro)


@app.route('/logout')
def logout():
    session.pop('admin_logado', None)
    return redirect(url_for('cardapio'))


# ── ROTAS ADMIN — PRODUTOS ────────────────────────────────

@app.route('/admin')
@login_necessario
def admin():
    produtos = Produto.query.all()
    kits = Kit.query.all()
    aviso = get_aviso()
    config = get_configuracao()
    pedidos = Pedido.query.order_by(Pedido.data.desc()).limit(10).all()
    return render_template('admin.html', produtos=produtos, kits=kits, aviso=aviso,
                           config=config, pedidos=pedidos)


@app.route('/admin/pedidos')
@login_necessario
def admin_pedidos():
    pedidos = Pedido.query.order_by(Pedido.data.desc()).all()
    return render_template('pedidos.html', pedidos=pedidos)


@app.route('/admin/produto/estoque/<int:id>', methods=['POST'])
@login_necessario
def atualizar_estoque(id):
    produto = Produto.query.get_or_404(id)
    val = request.form.get('estoque', '').strip()
    produto.estoque = int(val) if val.isdigit() else None
    db.session.commit()
    return redirect(url_for('admin'))


@app.route('/admin/configuracao', methods=['POST'])
@login_necessario
def salvar_configuracao():
    cfg = get_configuracao()
    cfg.endereco_loja = request.form.get('endereco_loja', '').strip()
    db.session.commit()
    return redirect(url_for('admin'))


@app.route('/api/calcular-frete', methods=['POST'])
def calcular_frete_api():
    data = request.get_json() or {}
    cep_cliente = re.sub(r'\D', '', data.get('cep', ''))

    if len(cep_cliente) != 8:
        return jsonify({'erro': 'CEP inválido. Informe os 8 dígitos.'}), 400

    cfg = get_configuracao()
    cep_loja = extrair_cep(cfg.endereco_loja or '')
    if not cep_loja:
        return jsonify({'erro': 'CEP da loja não configurado. Fale com o administrador.'}), 400

    coords_loja = get_coords_por_cep(cep_loja)
    if not coords_loja:
        return jsonify({'erro': 'Não foi possível localizar o CEP da loja.'}), 500

    coords_cliente = get_coords_por_cep(cep_cliente)
    if not coords_cliente:
        return jsonify({'erro': 'CEP não encontrado. Verifique e tente novamente.'}), 400

    dist_reta = haversine(*coords_loja, *coords_cliente)
    dist_km = round(dist_reta * 1.4, 1)
    frete = round(dist_km * FRETE_POR_KM, 2)

    return jsonify({'km': dist_km, 'frete': frete})


@app.route('/admin/aviso', methods=['POST'])
@login_necessario
def salvar_aviso():
    aviso = get_aviso()
    aviso.texto = request.form.get('texto', '').strip()
    aviso.ativo = 'ativo' in request.form
    db.session.commit()
    return redirect(url_for('admin'))


@app.route('/admin/criar', methods=['GET', 'POST'])
@login_necessario
def criar_produto():
    if request.method == 'POST':
        est = request.form.get('estoque', '').strip()
        produto = Produto(
            nome=request.form['nome'],
            descricao=request.form['descricao'],
            preco=request.form['preco'],
            categoria=request.form['categoria'],
            imagem=salvar_imagem(request.files.get('imagem')),
            visivel='visivel' in request.form,
            estoque=int(est) if est.isdigit() else None
        )
        db.session.add(produto)
        db.session.commit()
        return redirect(url_for('admin'))
    return render_template('criar_produto.html')


@app.route('/admin/editar/<int:id>', methods=['GET', 'POST'])
@login_necessario
def editar_produto(id):
    produto = Produto.query.get_or_404(id)
    if request.method == 'POST':
        produto.nome = request.form['nome']
        produto.descricao = request.form['descricao']
        produto.preco = request.form['preco']
        produto.categoria = request.form['categoria']
        produto.visivel = 'visivel' in request.form
        est = request.form.get('estoque', '').strip()
        produto.estoque = int(est) if est.isdigit() else None
        nova_imagem = salvar_imagem(request.files.get('imagem'))
        if nova_imagem:
            remover_imagem(produto.imagem)
            produto.imagem = nova_imagem
        db.session.commit()
        return redirect(url_for('admin'))
    return render_template('editar_produto.html', produto=produto)


@app.route('/admin/excluir/<int:id>', methods=['POST'])
@login_necessario
def excluir_produto(id):
    produto = Produto.query.get_or_404(id)
    remover_imagem(produto.imagem)
    db.session.delete(produto)
    db.session.commit()
    return redirect(url_for('admin'))


@app.route('/admin/visibilidade/<int:id>', methods=['POST'])
@login_necessario
def toggle_visibilidade(id):
    produto = Produto.query.get_or_404(id)
    produto.visivel = not produto.visivel
    db.session.commit()
    return redirect(url_for('admin'))


# ── ROTAS ADMIN — KITS ────────────────────────────────────

@app.route('/admin/kit/criar', methods=['GET', 'POST'])
@login_necessario
def criar_kit():
    produtos = Produto.query.all()
    if request.method == 'POST':
        kit = Kit(
            nome=request.form['nome'],
            descricao=request.form['descricao'],
            preco=request.form['preco'],
            imagem=salvar_imagem(request.files.get('imagem')),
            visivel='visivel' in request.form
        )
        db.session.add(kit)
        db.session.flush()

        for produto_id, qtd in itens_do_form(produtos):
            db.session.add(KitItem(kit_id=kit.id, produto_id=produto_id, quantidade=qtd))

        db.session.commit()
        return redirect(url_for('admin'))
    return render_template('criar_kit.html', produtos=produtos)


@app.route('/admin/kit/editar/<int:id>', methods=['GET', 'POST'])
@login_necessario
def editar_kit(id):
    kit = Kit.query.get_or_404(id)
    produtos = Produto.query.all()

    if request.method == 'POST':
        kit.nome = request.form['nome']
        kit.descricao = request.form['descricao']
        kit.preco = request.form['preco']
        kit.visivel = 'visivel' in request.form
        nova_imagem = salvar_imagem(request.files.get('imagem'))
        if nova_imagem:
            remover_imagem(kit.imagem)
            kit.imagem = nova_imagem

        # Recria os itens do kit
        KitItem.query.filter_by(kit_id=kit.id).delete()
        for produto_id, qtd in itens_do_form(produtos):
            db.session.add(KitItem(kit_id=kit.id, produto_id=produto_id, quantidade=qtd))

        db.session.commit()
        return redirect(url_for('admin'))

    # Monta dict {produto_id: quantidade} para pré-preencher o form
    qtds_atuais = {item.produto_id: item.quantidade for item in kit.itens}
    return render_template('editar_kit.html', kit=kit, produtos=produtos, qtds_atuais=qtds_atuais)


@app.route('/admin/kit/excluir/<int:id>', methods=['POST'])
@login_necessario
def excluir_kit(id):
    kit = Kit.query.get_or_404(id)
    remover_imagem(kit.imagem)
    db.session.delete(kit)
    db.session.commit()
    return redirect(url_for('admin'))


@app.route('/admin/kit/visibilidade/<int:id>', methods=['POST'])
@login_necessario
def toggle_visibilidade_kit(id):
    kit = Kit.query.get_or_404(id)
    kit.visivel = not kit.visivel
    db.session.commit()
    return redirect(url_for('admin'))


@app.route('/api/registrar-pedido', methods=['POST'])
def registrar_pedido():
    data     = request.get_json() or {}
    cart     = data.get('cart', [])
    nome     = data.get('nome', '').strip()
    tipo     = data.get('tipo', '')
    endereco = data.get('endereco', '')
    cep      = data.get('cep', '')
    frete    = float(data.get('frete', 0))

    if not cart or not nome or not tipo:
        return jsonify({'erro': 'Dados incompletos.'}), 400

    # Verifica estoque de todos os itens com ID numérico (produtos individuais)
    for item in cart:
        try:
            pid = int(item['id'])
        except (ValueError, TypeError):
            continue
        p = Produto.query.get(pid)
        if p and p.estoque is not None and p.estoque < item['quantidade']:
            disp = p.estoque
            return jsonify({
                'erro': f'Estoque insuficiente para "{p.nome}". '
                        f'Disponível: {disp} unidade{"s" if disp != 1 else ""}.'
            }), 400

    subtotal = sum(float(str(i['preco']).replace(',', '.')) * i['quantidade'] for i in cart)
    total    = subtotal + frete

    pedido = Pedido(nome_cliente=nome, tipo_entrega=tipo,
                    endereco=endereco, cep=cep, frete=frete, total=total)
    db.session.add(pedido)
    db.session.flush()

    for item in cart:
        preco_unit = float(str(item['preco']).replace(',', '.'))
        pi = PedidoItem(pedido_id=pedido.id, produto_nome=item['nome'],
                        quantidade=item['quantidade'], preco_unit=preco_unit)
        try:
            pid = int(item['id'])
            pi.produto_id = pid
            p = Produto.query.get(pid)
            if p and p.estoque is not None:
                p.estoque = max(0, p.estoque - item['quantidade'])
        except (ValueError, TypeError):
            pass
        db.session.add(pi)

    db.session.commit()
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(debug=True)
