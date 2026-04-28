const CART_KEY = 'cardapio_carrinho';
const WHATSAPP_NUM = '5511949737460';

function getCart() {
    return JSON.parse(localStorage.getItem(CART_KEY) || '[]');
}

function saveCart(cart) {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
    atualizarBadge();
}

function addToCart(id, nome, preco, imagem, quantidade) {
    quantidade = quantidade || 1;
    const cart = getCart();
    const item = cart.find(i => i.id === id);
    if (item) {
        item.quantidade += quantidade;
    } else {
        cart.push({ id, nome, preco, imagem, quantidade });
    }
    saveCart(cart);
    mostrarToast(nome);
}

// ── Controles de quantidade nos cards ─────────
function incrementarCard(btn) {
    const el = btn.closest('.qtd-ctrl-card').querySelector('.qtd-num');
    if (el) el.textContent = parseInt(el.textContent) + 1;
}

function decrementarCard(btn) {
    const el = btn.closest('.qtd-ctrl-card').querySelector('.qtd-num');
    if (el && parseInt(el.textContent) > 1) el.textContent = parseInt(el.textContent) - 1;
}

function addToCartFromCard(btn) {
    const el = btn.closest('.card-acoes').querySelector('.qtd-num');
    const qtd = el ? parseInt(el.textContent) : 1;
    addToCart(parseInt(btn.dataset.id), btn.dataset.nome, btn.dataset.preco, btn.dataset.imagem, qtd);
    if (el) el.textContent = '1';
}

// ── Controles de quantidade na página de detalhe
function incrementarDetalhe() {
    const el = document.getElementById('qtd-detalhe');
    if (el) el.textContent = parseInt(el.textContent) + 1;
}

function decrementarDetalhe() {
    const el = document.getElementById('qtd-detalhe');
    if (el && parseInt(el.textContent) > 1) el.textContent = parseInt(el.textContent) - 1;
}

function addToCartDetalhe(btn) {
    const el = document.getElementById('qtd-detalhe');
    const qtd = el ? parseInt(el.textContent) : 1;
    addToCart(
        parseInt(btn.dataset.id),
        btn.dataset.nome,
        btn.dataset.preco,
        btn.dataset.imagem,
        qtd
    );
    if (el) el.textContent = '1';
}

function removerItem(id) {
    saveCart(getCart().filter(i => i.id !== id));
    renderCarrinho();
}

function alterarQtd(id, delta) {
    const cart = getCart();
    const item = cart.find(i => i.id === id);
    if (!item) return;
    item.quantidade += delta;
    if (item.quantidade <= 0) {
        saveCart(cart.filter(i => i.id !== id));
    } else {
        saveCart(cart);
    }
    renderCarrinho();
}

function limparCarrinho() {
    localStorage.removeItem(CART_KEY);
    atualizarBadge();
}

// ── Badge no header ───────────────────────────
function atualizarBadge() {
    const cart = getCart();
    const total = cart.reduce((s, i) => s + i.quantidade, 0);
    document.querySelectorAll('.cart-badge').forEach(el => {
        el.textContent = total;
        el.style.display = total > 0 ? 'inline-flex' : 'none';
    });
}

// ── Toast "adicionado" ────────────────────────
function mostrarToast(nome) {
    let toast = document.getElementById('cart-toast');
    if (!toast) return;
    toast.textContent = `"${nome}" adicionado ao carrinho!`;
    toast.classList.add('visivel');
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove('visivel'), 2500);
}

// ── Helpers de preço ──────────────────────────
function parsePreco(str) {
    return parseFloat(String(str).replace(',', '.')) || 0;
}

function formatPreco(val) {
    return val.toFixed(2).replace('.', ',');
}

// ── Renderiza página do carrinho ──────────────
function renderCarrinho() {
    const lista = document.getElementById('carrinho-lista');
    const rodape = document.getElementById('carrinho-rodape');
    const vazio = document.getElementById('carrinho-vazio');
    if (!lista) return;

    const cart = getCart();

    if (cart.length === 0) {
        lista.innerHTML = '';
        rodape.style.display = 'none';
        vazio.style.display = 'block';
        return;
    }

    vazio.style.display = 'none';
    rodape.style.display = 'block';

    lista.innerHTML = cart.map(item => {
        const subtotal = parsePreco(item.preco) * item.quantidade;
        const imgHtml = item.imagem
            ? `<img src="/static/uploads/${item.imagem}" alt="${item.nome}" class="cart-thumb">`
            : `<div class="cart-sem-img">Sem foto</div>`;

        return `
        <div class="cart-item" data-id="${item.id}">
            ${imgHtml}
            <div class="cart-info">
                <strong>${item.nome}</strong>
                <span class="cart-preco-unit">R$ ${item.preco} cada</span>
            </div>
            <div class="cart-controles">
                <button class="qtd-btn" onclick="alterarQtd(${item.id}, -1)">−</button>
                <span class="qtd-num">${item.quantidade}</span>
                <button class="qtd-btn" onclick="alterarQtd(${item.id}, +1)">+</button>
            </div>
            <div class="cart-subtotal">R$ ${formatPreco(subtotal)}</div>
            <button class="btn-remover" onclick="removerItem(${item.id})" title="Remover">✕</button>
        </div>`;
    }).join('');

    const totalGeral = cart.reduce((s, i) => s + parsePreco(i.preco) * i.quantidade, 0);
    document.getElementById('total-valor').textContent = `R$ ${formatPreco(totalGeral)}`;
}

const FRETE_POR_KM = 3;
let freteAtual = 0;

// ── Modal de confirmação ──────────────────────
function abrirModal() {
    if (getCart().length === 0) return;
    freteAtual = 0;
    document.getElementById('modal-confirmacao').style.display = 'flex';
    document.getElementById('modal-erro').style.display = 'none';
    document.getElementById('modal-resumo').style.display = 'none';
    document.querySelectorAll('input[name="tipo_entrega"]').forEach(r => r.checked = false);
    document.getElementById('campos-entrega').style.display = 'none';
    document.getElementById('aviso-retirada').style.display = 'none';
    document.getElementById('frete-preview').style.display = 'none';
    document.getElementById('frete-status').style.display = 'none';
    document.querySelectorAll('.tipo-opcao').forEach(el => el.classList.remove('tipo-opcao-ativa'));
    setTimeout(() => document.getElementById('pedido-nome').focus(), 100);
}

function fecharModal() {
    document.getElementById('modal-confirmacao').style.display = 'none';
}

function alterarTipoEntrega() {
    const tipo = document.querySelector('input[name="tipo_entrega"]:checked')?.value;

    freteAtual = 0;
    document.getElementById('campos-entrega').style.display  = tipo === 'entrega'  ? 'block' : 'none';
    document.getElementById('aviso-retirada').style.display  = tipo === 'retirada' ? 'flex'  : 'none';
    document.getElementById('modal-resumo').style.display    = 'none';
    document.getElementById('frete-preview').style.display   = 'none';
    document.getElementById('frete-status').style.display    = 'none';

    document.querySelectorAll('.tipo-opcao').forEach(el => el.classList.remove('tipo-opcao-ativa'));
    if (tipo === 'entrega')  document.getElementById('opcao-entrega').classList.add('tipo-opcao-ativa');
    if (tipo === 'retirada') document.getElementById('opcao-retirada').classList.add('tipo-opcao-ativa');

    if (tipo === 'retirada') atualizarResumo(0);
}

function formatarCep(input) {
    let v = input.value.replace(/\D/g, '');
    if (v.length > 5) v = v.slice(0, 5) + '-' + v.slice(5, 8);
    input.value = v;
}

function calcularFreteAuto() {
    const cep = document.getElementById('pedido-cep').value.replace(/\D/g, '');
    const endereco = document.getElementById('pedido-endereco').value.trim();
    const erro = document.getElementById('modal-erro');
    erro.style.display = 'none';

    if (!endereco) {
        erro.textContent = 'Preencha o endereço de entrega.';
        erro.style.display = 'block';
        return;
    }
    if (cep.length !== 8) {
        erro.textContent = 'Preencha o CEP completo (8 dígitos).';
        erro.style.display = 'block';
        return;
    }

    const status = document.getElementById('frete-status');
    const preview = document.getElementById('frete-preview');
    const btn = document.getElementById('btn-calc-frete');

    status.textContent = '⏳ Calculando distância...';
    status.style.display = 'block';
    preview.style.display = 'none';
    document.getElementById('modal-resumo').style.display = 'none';
    btn.disabled = true;

    fetch('/api/calcular-frete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cep })
    })
    .then(r => r.json())
    .then(data => {
        btn.disabled = false;
        if (data.erro) {
            status.textContent = '❌ ' + data.erro;
            freteAtual = 0;
            return;
        }
        freteAtual = data.frete;
        status.style.display = 'none';
        document.getElementById('frete-valor').textContent = `R$ ${formatPreco(data.frete)}`;
        document.getElementById('frete-detalhe').textContent = `(~${data.km} km estimado)`;
        preview.style.display = 'flex';
        atualizarResumo(data.frete);
    })
    .catch(() => {
        btn.disabled = false;
        status.textContent = '❌ Erro ao calcular frete. Tente novamente.';
        freteAtual = 0;
    });
}

function atualizarResumo(frete) {
    const cart     = getCart();
    const subtotal = cart.reduce((s, i) => s + parsePreco(i.preco) * i.quantidade, 0);
    const total    = subtotal + frete;

    document.getElementById('resumo-subtotal').textContent = `R$ ${formatPreco(subtotal)}`;
    document.getElementById('resumo-frete').textContent    = frete > 0 ? `R$ ${formatPreco(frete)}` : 'Grátis';
    document.getElementById('resumo-total').textContent    = `R$ ${formatPreco(total)}`;
    document.getElementById('modal-resumo').style.display  = 'block';
}

function confirmarPedido() {
    const cart = getCart();
    if (cart.length === 0) return;

    const nome = document.getElementById('pedido-nome').value.trim();
    const tipo = document.querySelector('input[name="tipo_entrega"]:checked')?.value;
    const erro = document.getElementById('modal-erro');

    if (!nome) {
        erro.textContent = 'Por favor, preencha seu nome.';
        erro.style.display = 'block'; return;
    }
    if (!tipo) {
        erro.textContent = 'Escolha entre Entrega ou Retirada.';
        erro.style.display = 'block'; return;
    }

    let endereco = '';
    let frete    = 0;

    if (tipo === 'entrega') {
        endereco = document.getElementById('pedido-endereco').value.trim();
        if (!endereco) {
            erro.textContent = 'Por favor, preencha o endereço de entrega.';
            erro.style.display = 'block'; return;
        }
        if (freteAtual <= 0) {
            erro.textContent = 'Clique em "Calcular Frete" antes de finalizar o pedido.';
            erro.style.display = 'block'; return;
        }
        frete = freteAtual;
    }

    erro.style.display = 'none';

    const cepCliente = document.getElementById('pedido-cep')?.value || '';
    const subtotal   = cart.reduce((s, i) => s + parsePreco(i.preco) * i.quantidade, 0);
    const total      = subtotal + frete;

    const linhas = cart.map(i => {
        const sub = formatPreco(parsePreco(i.preco) * i.quantidade);
        return `• ${i.quantidade}x ${i.nome} — R$ ${sub}`;
    }).join('\n');

    let entregaInfo = '';
    if (tipo === 'entrega') {
        entregaInfo =
            `*Tipo:* 🛵 Entrega\n` +
            `*Endereço:* ${endereco}\n` +
            (cepCliente ? `*CEP:* ${cepCliente}\n` : '') +
            `*Frete:* R$ ${formatPreco(frete)}\n`;
    } else {
        entregaInfo = `*Tipo:* 🏪 Retirada pelo cliente\n`;
    }

    const msg =
        `Olá! Gostaria de fazer um pedido:\n\n` +
        `*Nome:* ${nome}\n` +
        entregaInfo +
        `\n*Itens do pedido:*\n${linhas}\n\n` +
        `*Subtotal:* R$ ${formatPreco(subtotal)}\n` +
        (frete > 0 ? `*Frete:* R$ ${formatPreco(frete)}\n` : '') +
        `*Total: R$ ${formatPreco(total)}*`;

    const btn = document.getElementById('btn-confirmar');
    btn.disabled = true;
    btn.textContent = 'Enviando...';

    const waWindow = window.open('', '_blank');

    fetch('/api/registrar-pedido', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cart, nome, tipo, endereco, cep: cepCliente, frete })
    })
    .then(r => r.json())
    .then(data => {
        btn.disabled = false;
        btn.textContent = 'Enviar pelo WhatsApp';
        if (data.erro) {
            waWindow.close();
            erro.textContent = data.erro;
            erro.style.display = 'block';
            return;
        }
        limparCarrinho();
        fecharModal();
        renderCarrinho();
        document.getElementById('pedido-nome').value = '';
        if (document.getElementById('pedido-endereco')) document.getElementById('pedido-endereco').value = '';
        if (document.getElementById('pedido-cep')) document.getElementById('pedido-cep').value = '';
        waWindow.location.href = `https://wa.me/${WHATSAPP_NUM}?text=${encodeURIComponent(msg)}`;
    })
    .catch(() => {
        waWindow.close();
        btn.disabled = false;
        btn.textContent = 'Enviar pelo WhatsApp';
        erro.textContent = 'Erro de conexão. Tente novamente.';
        erro.style.display = 'block';
    });
}

// Fecha modal clicando fora
document.addEventListener('click', e => {
    const modal = document.getElementById('modal-confirmacao');
    if (modal && e.target === modal) fecharModal();
});

document.addEventListener('DOMContentLoaded', () => {
    atualizarBadge();
    renderCarrinho();
});
