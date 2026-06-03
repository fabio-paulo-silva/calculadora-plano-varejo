import datetime

import pandas as pd
import streamlit as st

from plano_acao import carregar_historico, gerar_pdf, salvar_historico
from transform_data import carregar_tudo

NOMES_MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

st.set_page_config(page_title="Calculadora de Metas", layout="wide", page_icon="🎯")


@st.cache_data(ttl=3600, show_spinner="Carregando dados...")
def load_data():
    return carregar_tudo()   # retorna: analise, hist_max, metas, base, dcentros


def formatar_moeda(valor):
    """Para st.metric — sem markdown, pode usar R$ normalmente."""
    if pd.isna(valor):
        return "—"
    return f"R$ {valor:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fm(valor):
    """Para textos markdown (st.info/success/warning) — escapa o $ para não virar LaTeX."""
    if pd.isna(valor):
        return "—"
    return f"R\\$ {valor:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_pct(valor):
    if pd.isna(valor):
        return "—"
    sinal = "+" if valor >= 0 else ""
    return f"{sinal}{valor * 100:.1f}%"


def formatar_numero(valor, decimais=1):
    if pd.isna(valor):
        return "—"
    return f"{valor:,.{decimais}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _safe(val):
    try:
        return None if pd.isna(val) else float(val)
    except Exception:
        return None


def gerar_sugestao(row, hist_max_row):
    bm_nec  = _safe(row.get('BM_NECESSARIO'))
    ib_nec  = _safe(row.get('IB_NECESSARIO'))
    pm_nec  = _safe(row.get('PM_NECESSARIO'))
    bol_nec = _safe(row.get('BOLETOS_NECESSARIOS'))

    bm_at  = _safe(row.get('BM'))
    ib_at  = _safe(row.get('I/B'))
    pm_at  = _safe(row.get('PM'))
    bol_at = _safe(row.get('BOLETOS_PROJ'))

    var_ib  = _safe(row.get('VAR_IB'))
    var_pm  = _safe(row.get('VAR_PM'))
    var_bol = _safe(row.get('VAR_BOL'))

    if hist_max_row is None or bm_nec is None:
        return "warning", "Sem dados suficientes para gerar sugestão."

    max_bm  = _safe(hist_max_row.get('MAX_BM'))
    max_ib  = _safe(hist_max_row.get('MAX_IB'))
    max_pm  = _safe(hist_max_row.get('MAX_PM'))
    max_bol = _safe(hist_max_row.get('MAX_BOLETOS'))

    bm_ok  = max_bm  is not None and bm_nec  <= max_bm
    ib_ok  = max_ib  is not None and ib_nec  is not None and ib_nec  <= max_ib
    pm_ok  = max_pm  is not None and pm_nec  is not None and pm_nec  <= max_pm
    bol_ok = max_bol is not None and bol_nec is not None and bol_nec <= max_bol

    # ── Caso 1: BM já atingível ────────────────────────────────────────────────
    if bm_ok:
        return "success", (
            f"✅ **Meta factível — o BM de {fm(bm_nec)} já foi alcançado antes nesta loja** "
            f"(máx histórico: {fm(max_bm)}).\n\n"
            f"**Estratégia: garanta consistência nos dois vetores do BM:**\n"
            f"- 📦 Mantenha Itens por Boleto acima de **{formatar_numero(ib_nec)}** (atual: {formatar_numero(ib_at)})\n"
            f"- 💰 Mantenha Preço Médio acima de **{fm(pm_nec)}** (atual: {fm(pm_at)})\n"
            f"- 🏆 Reforce o desempenho da equipe com foco no mix de produtos de maior valor\n"
            f"- 📊 Acompanhe o BM diariamente para não perder ritmo no fim do mês"
        )

    # ── Caso 2: I/B e PM ambos factíveis — escolhe o menor esforço ────────────
    if ib_ok and pm_ok:
        if var_ib is not None and var_pm is not None and abs(var_ib) <= abs(var_pm):
            return "info", (
                f"📦 **Priorize Itens por Boleto** — menor esforço relativo "
                f"({formatar_pct(var_ib)} de aumento necessário).\n\n"
                f"Meta: **{formatar_numero(ib_nec)} It/Boleto** | Atual: {formatar_numero(ib_at)} | "
                f"Máx histórico: {formatar_numero(max_ib)}\n\n"
                f"**Ações sugeridas:**\n"
                f"- 🛍️ Treine a equipe em venda sugestiva: *\"Esse produto combina com...\"*\n"
                f"- 🎁 Monte kits e combos com produtos complementares (ex.: perfume + hidratante)\n"
                f"- 📍 Posicione itens de menor valor próximos ao produto principal\n"
                f"- 🏆 Desafio de equipe: meta de {formatar_numero(ib_nec, 0)} itens por boleto\n"
                f"- 📊 Monitore os Itens por Boleto diariamente por vendedora para correcao rapida"
            )
        else:
            return "info", (
                f"💰 **Priorize Preço Médio** — menor esforço relativo "
                f"({formatar_pct(var_pm)} de aumento necessário).\n\n"
                f"Meta: **{fm(pm_nec)} PM** | Atual: {fm(pm_at)} | "
                f"Máx histórico: {fm(max_pm)}\n\n"
                f"**Ações sugeridas:**\n"
                f"- 💎 Foque em lançamentos, edições especiais e mix premium\n"
                f"- 🚫 Reduza concessão de descontos em categorias de alto ticket\n"
                f"- 🎯 Direcione o atendimento para produtos de maior valor percebido\n"
                f"- 📦 Destaque presentes prontos e kits de maior valor no ponto de venda\n"
                f"- 📊 Acompanhe o PM por categoria e por vendedora"
            )

    # ── Caso 3: Só I/B é factível ─────────────────────────────────────────────
    if ib_ok:
        msg = (
            f"📦 **Foque em Itens por Boleto** — PM necessário ({fm(pm_nec)}) "
            f"está acima do histórico ({fm(max_pm)}), mas Itens por Boleto de **{formatar_numero(ib_nec)}** "
            f"e atingivel (max historico: {formatar_numero(max_ib)}).\n\n"
            f"**Acoes para aumentar Itens por Boleto ({formatar_pct(var_ib)} necessario):**\n"
            f"- 🛍️ Venda sugestiva ativa em todos os atendimentos\n"
            f"- 🎁 Kits e combos estratégicos com produtos complementares\n"
            f"- 📍 Visual merchandising estimulando compra de itens adicionais\n"
            f"- 🏆 Ranking diario da equipe por Itens por Boleto"
        )
        if bol_ok and var_bol is not None:
            msg += (
                f"\n\n💡 **Alternativa via volume:** Aumentar boletos em {formatar_pct(var_bol)} "
                f"(para {formatar_numero(bol_nec, 0)}) mantendo o BM atual — "
                f"já alcançado antes (máx: {formatar_numero(max_bol, 0)}).\n"
                f"Ative CRM, campanhas de tráfego e reativação de clientes inativos."
            )
        return "info", msg

    # ── Caso 4: Só PM é factível ──────────────────────────────────────────────
    if pm_ok:
        msg = (
            f"💰 **Foque em Preco Medio** — Itens por Boleto necessario ({formatar_numero(ib_nec)}) "
            f"está acima do histórico ({formatar_numero(max_ib)}), mas PM de **{fm(pm_nec)}** "
            f"é atingível (máx histórico: {fm(max_pm)}).\n\n"
            f"**Ações para aumentar PM ({formatar_pct(var_pm)} necessário):**\n"
            f"- 💎 Priorize lançamentos e produtos premium no atendimento\n"
            f"- 🚫 Discipline a política de descontos — preserve o ticket\n"
            f"- 🎯 Foque em presentes e kits de maior valor agregado\n"
            f"- 📊 Monitore o PM por turno e tome ação corretiva imediata"
        )
        if bol_ok and var_bol is not None:
            msg += (
                f"\n\n💡 **Alternativa via volume:** Aumentar boletos em {formatar_pct(var_bol)} "
                f"(para {formatar_numero(bol_nec, 0)}) mantendo o BM atual — "
                f"já alcançado antes (máx: {formatar_numero(max_bol, 0)}).\n"
                f"Ative CRM, campanhas de tráfego e reativação de clientes inativos."
            )
        return "info", msg

    # ── Caso 5: I/B e PM fora do histórico, mas boletos é factível ────────────
    if bol_ok and var_bol is not None:
        return "info", (
            f"🚀 **Estratégia de volume: aumente o fluxo de clientes.**\n\n"
            f"Os indicadores de qualidade (Itens por Boleto e PM) estao alem do historico desta loja. "
            f"A rota mais realista é aumentar a quantidade de boletos.\n\n"
            f"Meta de boletos: **{formatar_numero(bol_nec, 0)}** "
            f"({formatar_pct(var_bol)} acima da projeção atual de {formatar_numero(bol_at, 0)}) "
            f"— já alcançado antes (máx histórico: {formatar_numero(max_bol, 0)}).\n\n"
            f"**Ações para atrair mais clientes:**\n"
            f"- 📲 CRM ativo: contate clientes sem compra há 60+ dias com oferta personalizada\n"
            f"- 🎉 Promoção de tráfego: brinde ou condição especial para novos atendimentos\n"
            f"- 📱 Campanhas no WhatsApp e Instagram da loja para gerar agendamentos\n"
            f"- 🔔 Ativação do Clube Boti: notifique clientes com pontos próximos do vencimento\n"
            f"- 🤝 Parceria com negócios vizinhos para geração de indicações"
        )

    # ── Caso 6: Nenhuma alavanca isolada resolve — combinar tudo ──────────────
    bol_parcial = bol_at * 1.05 if bol_at else None
    sugestao_combo = ""
    if bol_parcial and row.get('META'):
        bm_reduzido = row.get('META') / bol_parcial
        if bm_reduzido:
            sugestao_combo = (
                f"\n\n💡 **Dica:** Com apenas **+5% de boletos** ({formatar_numero(bol_parcial, 0)}), "
                f"o BM necessário cai para {fm(bm_reduzido)} — reavalie se alguma alavanca de "
                f"qualidade passa a ser factível nesse cenário."
            )

    return "warning", (
        f"⚠️ **Meta muito desafiadora — combine todas as alavancas.**\n\n"
        f"Nenhum indicador isolado atinge a meta dentro do histórico desta loja. "
        f"É preciso evoluir em múltiplas frentes ao mesmo tempo.\n\n"
        f"**Plano combinado sugerido:**\n"
        f"- 📦 Itens por Boleto: {formatar_numero(ib_at)} -> **{formatar_numero(ib_nec)}** "
        f"({formatar_pct(var_ib)}) com venda sugestiva e kits\n"
        f"- 💰 PM: {fm(pm_at)} → **{fm(pm_nec)}** "
        f"({formatar_pct(var_pm)}) com foco em mix premium e redução de descontos\n"
        f"- 🚀 Boletos: {formatar_numero(bol_at, 0)} → **{formatar_numero(bol_nec, 0)}** "
        f"({formatar_pct(var_bol)}) com ações de tráfego, CRM e reativação"
        + sugestao_combo
    )


# ── Layout ────────────────────────────────────────────────────────────────────

st.title("🎯 Calculadora de Indicadores Comerciais")

# Inicializa session_state para persistir o PDF entre reruns
if "pdf_bytes" not in st.session_state:
    st.session_state["pdf_bytes"] = None
if "pdf_nome" not in st.session_state:
    st.session_state["pdf_nome"] = None
if "pdf_chave" not in st.session_state:
    st.session_state["pdf_chave"] = None   # identifica loja+mês do PDF gerado

try:
    analise, hist_max, metas, base, dcentros = load_data()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Filtros")

    # ── Filtros de hierarquia (cascata) ───────────────────────────────────────
    def _opcoes(col, df):
        return ["Todos"] + sorted(df[col].dropna().unique().tolist())

    dc = dcentros.copy()

    grvo_sel = st.selectbox("Regional (GRVO)", _opcoes('GRVO', dc), key="f_grvo")
    if grvo_sel != "Todos":
        dc = dc[dc['GRVO'] == grvo_sel]

    gcvo_sel = st.selectbox("Coordenador (GCVO)", _opcoes('GCVO', dc), key="f_gcvo")
    if gcvo_sel != "Todos":
        dc = dc[dc['GCVO'] == gcvo_sel]

    gvo_sel = st.selectbox("Gestor (GVO)", _opcoes('GVO', dc), key="f_gvo")
    if gvo_sel != "Todos":
        dc = dc[dc['GVO'] == gvo_sel]

    praca_sel = st.selectbox("Praça", _opcoes('PRACA', dc), key="f_praca")
    if praca_sel != "Todos":
        dc = dc[dc['PRACA'] == praca_sel]

    # Filtra BCPS disponíveis pelo que sobrou na hierarquia
    bcps_hierarquia = set(dc['BCPS'].astype(int).tolist())
    lojas_disponiveis = sorted([
        b for b in analise['BCPS'].dropna().unique().astype(int).tolist()
        if b in bcps_hierarquia
    ])

    if not lojas_disponiveis:
        st.warning("Nenhuma loja encontrada para essa combinação de filtros.")
        st.stop()

    # Formata label da loja com nome se disponível
    loja_map = dcentros.set_index('BCPS')['LOJA'].to_dict()
    def _label_loja(bcps):
        nome = loja_map.get(int(bcps), "")
        return f"{int(bcps)} — {nome}" if nome else f"Loja {int(bcps)}"

    bcps_selecionado = st.selectbox(
        "Loja (BCPS)",
        options=lojas_disponiveis,
        format_func=_label_loja,
        key="f_bcps",
    )

    meses_disponiveis = sorted(analise[analise['BCPS'] == bcps_selecionado]['MES'].unique().tolist())
    mes_selecionado = st.selectbox(
        "Mês de Análise",
        options=meses_disponiveis,
        index=len(meses_disponiveis) - 1,
        format_func=lambda x: NOMES_MESES.get(x, str(x)),
    )

    canais_disponiveis = analise[
        (analise['BCPS'] == bcps_selecionado) & (analise['MES'] == mes_selecionado)
    ]['CANAL'].unique().tolist()

    if len(canais_disponiveis) > 1:
        canal_selecionado = st.selectbox("Canal", options=["Todos"] + canais_disponiveis)
    else:
        canal_selecionado = canais_disponiveis[0] if canais_disponiveis else "Todos"

    # Info da loja selecionada
    loja_info = dcentros[dcentros['BCPS'] == int(bcps_selecionado)]
    if not loja_info.empty:
        li = loja_info.iloc[0]
        st.markdown("---")
        st.caption(f"**{li.get('LOJA','')}**")
        st.caption(f"Praça: {li.get('PRACA','')}  |  GVO: {li.get('GVO','')}")
        st.caption(f"GCVO: {li.get('GCVO','')}  |  GRVO: {li.get('GRVO','')}")

    st.markdown("---")
    if st.button("🔄 Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Filtrar linha de análise ──────────────────────────────────────────────────

mask = (analise['BCPS'] == bcps_selecionado) & (analise['MES'] == mes_selecionado)
if canal_selecionado != "Todos":
    mask = mask & (analise['CANAL'] == canal_selecionado)

df_linha = analise[mask]

if df_linha.empty:
    st.warning("Nenhum dado encontrado para a seleção.")
    st.stop()

# Agrega se houver múltiplos canais
if len(df_linha) > 1:
    row = {
        'BCPS': bcps_selecionado,
        'MES': mes_selecionado,
        'FATURAMENTO': df_linha['FATURAMENTO'].sum(),
        'BOLETOS': df_linha['BOLETOS'].sum(),
        'QTD ITENS': df_linha['QTD ITENS'].sum(),
        'FAT_2025': df_linha['FAT_2025'].sum(),
        'BOL_2025': df_linha['BOL_2025'].sum(),
        'QTD_2025': df_linha['QTD_2025'].sum(),
        'META': df_linha['META'].sum(),
        'BOLETOS_PROJ': df_linha['BOLETOS_PROJ'].sum(),
    }
    row['BM'] = row['FATURAMENTO'] / row['BOLETOS'] if row['BOLETOS'] else float('nan')
    row['I/B'] = row['QTD ITENS'] / row['BOLETOS'] if row['BOLETOS'] else float('nan')
    row['PM'] = row['FATURAMENTO'] / row['QTD ITENS'] if row['QTD ITENS'] else float('nan')
    row['BM_2025'] = row['FAT_2025'] / row['BOL_2025'] if row['BOL_2025'] else float('nan')
    row['IB_2025'] = row['QTD_2025'] / row['BOL_2025'] if row['BOL_2025'] else float('nan')
    row['PM_2025'] = row['FAT_2025'] / row['QTD_2025'] if row['QTD_2025'] else float('nan')
    row['BM_NECESSARIO'] = row['META'] / row['BOLETOS_PROJ'] if row['BOLETOS_PROJ'] else float('nan')
    row['IB_NECESSARIO'] = row['BM_NECESSARIO'] / row['PM'] if row['PM'] else float('nan')
    row['PM_NECESSARIO'] = row['BM_NECESSARIO'] / row['I/B'] if row['I/B'] else float('nan')
    row['VAR_BM'] = (row['BM_NECESSARIO'] / row['BM']) - 1 if row['BM'] else float('nan')
    row['VAR_IB'] = (row['IB_NECESSARIO'] / row['I/B']) - 1 if row['I/B'] else float('nan')
    row['VAR_PM'] = (row['PM_NECESSARIO'] / row['PM']) - 1 if row['PM'] else float('nan')
    row = pd.Series(row)
else:
    row = df_linha.iloc[0]

hist_row_df = hist_max[hist_max['BCPS'] == bcps_selecionado]
hist_row = hist_row_df.iloc[0] if not hist_row_df.empty else None

# ── Cabeçalho ─────────────────────────────────────────────────────────────────

nome_loja = loja_map.get(int(bcps_selecionado), "")
titulo_loja = f"{int(bcps_selecionado)} — {nome_loja}" if nome_loja else f"Loja {int(bcps_selecionado)}"
st.subheader(f"{titulo_loja}  ·  {NOMES_MESES.get(mes_selecionado, mes_selecionado)} 2026")

# ── Seção 1: Planejamento da Meta ────────────────────────────────────────────

meta      = _safe(row.get('META'))
bol_proj  = _safe(row.get('BOLETOS_PROJ'))
bm_nec    = _safe(row.get('BM_NECESSARIO'))
ib_nec    = _safe(row.get('IB_NECESSARIO'))
pm_nec    = _safe(row.get('PM_NECESSARIO'))
bol_nec   = _safe(row.get('BOLETOS_NECESSARIOS'))
bm_ref    = _safe(row.get('BM_2025'))
ib_ref    = _safe(row.get('IB_2025'))
pm_ref    = _safe(row.get('PM_2025'))
bol_ref   = _safe(row.get('BOL_2025'))

st.markdown("#### 🎯 Planejamento da Meta")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Meta do Mês", formatar_moeda(meta))
with col2:
    st.metric(
        "Boletos Projetados",
        formatar_numero(bol_proj, 0),
        delta=f"{formatar_pct((bol_proj/bol_ref)-1)} vs 2025" if bol_ref and bol_proj else None,
        help="Projeção baseada na variação acumulada vs mesmo período 2025",
    )
with col3:
    st.metric(
        "Boleto Médio Necessário",
        formatar_moeda(bm_nec),
        delta=f"{formatar_pct((bm_nec/bm_ref)-1)} vs 2025" if bm_ref and bm_nec else None,
        delta_color="inverse",
        help="Meta / Boletos Projetados",
    )

st.divider()

# ── Seção 2: Caminhos para atingir a meta ─────────────────────────────────────

def _delta_inv(nec, ref):
    if nec is None or ref is None or ref == 0:
        return None
    return formatar_pct((nec / ref) - 1) + " vs 2025"

def _badge(nec, max_val):
    """Retorna emoji + texto de factibilidade baseado no histórico máximo."""
    if nec is None or max_val is None:
        return ""
    if nec <= max_val:
        return "✅ Já foi alcançado antes"
    pct_acima = (nec / max_val - 1) * 100
    if pct_acima <= 15:
        return "🟡 Levemente acima do histórico"
    return "🔴 Acima do histórico"

max_ib  = _safe(hist_row.get('MAX_IB'))  if hist_row is not None else None
max_pm  = _safe(hist_row.get('MAX_PM'))  if hist_row is not None else None
max_bol = _safe(hist_row.get('MAX_BOLETOS')) if hist_row is not None else None
max_bm  = _safe(hist_row.get('MAX_BM'))  if hist_row is not None else None

st.markdown("#### 📊 Caminhos para Atingir a Meta")

# Destaque do BM como objetivo central
bm_delta_str = f"{formatar_pct((bm_nec/bm_ref)-1)} vs 2025" if bm_ref and bm_nec else ""
badge_bm = _badge(bm_nec, max_bm)
st.info(
    f"**Boleto Médio necessário: {fm(bm_nec)}** "
    f"{'(' + bm_delta_str + ')' if bm_delta_str else ''}  {badge_bm}\n\n"
    f"Com **{formatar_numero(bol_proj, 0)} boletos projetados**, você precisa de um BM de "
    f"**{fm(bm_nec)}** para atingir a meta de **{fm(meta)}**. "
    f"Referência 2025: {fm(bm_ref)}."
)

st.caption("Escolha um caminho — ou combine-os no Simulador abaixo:")

col1, col2, col3 = st.columns(3)

with col1:
    badge = _badge(ib_nec, max_ib)
    esforco = _delta_inv(ib_nec, ib_ref)
    st.markdown(f"**📦 Caminho 1 — Itens por Boleto**")
    st.metric(
        "Meta de Itens por Boleto",
        formatar_numero(ib_nec),
        delta=esforco,
        delta_color="inverse",
        help="Mantendo o Preço Médio de 2025",
    )
    st.caption(f"2025: {formatar_numero(ib_ref)}  |  Máx histórico: {formatar_numero(max_ib)}")
    st.markdown(badge)

with col2:
    badge = _badge(pm_nec, max_pm)
    esforco = _delta_inv(pm_nec, pm_ref)
    st.markdown(f"**💰 Caminho 2 — Preço Médio**")
    st.metric(
        "Meta de Preço Médio",
        formatar_moeda(pm_nec),
        delta=esforco,
        delta_color="inverse",
        help="Mantendo os Itens por Boleto de 2025",
    )
    st.caption(f"2025: {fm(pm_ref)}  |  Máx histórico: {fm(max_pm)}")
    st.markdown(badge)

with col3:
    badge = _badge(bol_nec, max_bol)
    esforco = _delta_inv(bol_nec, bol_ref)
    st.markdown(f"**🚀 Caminho 3 — Aumentar Boletos**")
    st.metric(
        "Meta de Boletos",
        formatar_numero(bol_nec, 0),
        delta=esforco,
        delta_color="inverse",
        help="Mantendo o BM de 2025 — atrair mais clientes",
    )
    st.caption(f"2025: {formatar_numero(bol_ref, 0)}  |  Máx histórico: {formatar_numero(max_bol, 0)}")
    st.markdown(badge)

st.divider()

# ── Seção 3: Simulador combinado ──────────────────────────────────────────────

st.markdown("#### 🔢 Simulador de Cenários")
st.caption(
    "Ajuste qualquer combinação de indicadores e veja o faturamento projetado. "
    "**Faturamento = Boletos × Itens por Boleto × Preço Médio**"
)

sc1, sc2, sc3, sc4 = st.columns(4)

with sc1:
    sim_bol = st.number_input(
        f"Boletos  (padrão: boletos projetados = {formatar_numero(bol_proj, 0)})",
        min_value=1,
        value=int(bol_proj or bol_ref or 100),
        step=5,
        key="sim_bol",
    )
with sc2:
    sim_ib = st.number_input(
        f"Itens por Boleto  (padrão: realizado em {NOMES_MESES.get(mes_selecionado,'')} 2025 = {formatar_numero(ib_ref)})",
        min_value=0.1,
        value=round(float(ib_ref or 2.0), 1),
        step=0.1,
        format="%.1f",
        key="sim_ib",
    )
with sc3:
    sim_pm = st.number_input(
        f"Preço Médio  (padrão: realizado em {NOMES_MESES.get(mes_selecionado,'')} 2025 = {formatar_moeda(pm_ref)})",
        min_value=1.0,
        value=round(float(pm_ref or 50.0), 0),
        step=1.0,
        format="%.0f",
        key="sim_pm",
    )
with sc4:
    # BM é derivado: Itens por Boleto × Preço Médio
    sim_bm_calc = sim_ib * sim_pm
    st.metric(
        "Boleto Médio resultante",
        formatar_moeda(sim_bm_calc),
        delta=_delta_inv(sim_bm_calc, bm_ref),
        delta_color="normal",
        help="Calculado automaticamente: Itens por Boleto × Preço Médio",
    )

# Resultado do cenário
sim_fat = sim_bol * sim_bm_calc
pct_sim = (sim_fat / meta * 100) if meta else 0
gap_sim = sim_fat - meta if meta else 0

if pct_sim >= 100:
    cor = "success"
    icone = "✅"
elif pct_sim >= 90:
    cor = "warning"
    icone = "🟡"
else:
    cor = "error"
    icone = "🔴"

getattr(st, cor)(
    f"{icone} **Faturamento projetado: {fm(sim_fat)}** "
    f"— {pct_sim:.1f}% da meta "
    f"({'sobra ' if gap_sim >= 0 else 'faltam '}{fm(abs(gap_sim))})"
)

# Mini-tabela comparando cenário vs necessário
comp = pd.DataFrame({
    "Indicador":        ["Boletos", "Itens por Boleto", "Preço Médio", "Boleto Médio", "Faturamento"],
    "Referência 2025":  [formatar_numero(bol_ref, 0),   formatar_numero(ib_ref),  formatar_moeda(pm_ref),  formatar_moeda(bm_ref),  "—"],
    "Necessário p/ meta": [formatar_numero(bol_nec, 0), formatar_numero(ib_nec),  formatar_moeda(pm_nec),  formatar_moeda(bm_nec),  formatar_moeda(meta)],
    "Seu Cenário":      [formatar_numero(sim_bol, 0),   formatar_numero(sim_ib),  formatar_moeda(sim_pm),  formatar_moeda(sim_bm_calc), formatar_moeda(sim_fat)],
})
st.dataframe(comp, use_container_width=True, hide_index=True)

st.divider()

# ── Seção 4: Sugestão Inteligente ─────────────────────────────────────────────

st.markdown("#### 💡 Sugestão Inteligente")

tipo, mensagem = gerar_sugestao(row, hist_row)

if tipo == "success":
    st.success(mensagem)
elif tipo == "info":
    st.info(mensagem)
else:
    st.warning(mensagem)

# Tabela comparativa com máximos históricos
if hist_row is not None:
    st.markdown("**Comparativo com máximo histórico da loja:**")
    def _fact(nec_key, max_key, fmt="moeda"):
        nec = _safe(row.get(nec_key))
        mx  = _safe(hist_row.get(max_key))
        if nec is None or mx is None:
            return "—"
        return "✅ Factível" if nec <= mx else "⚠️ Acima do histórico"

    tabela = pd.DataFrame({
        "Indicador": ["BM (Boleto Médio)", "Itens por Boleto", "PM (Preço Médio)", "Boletos"],
        "Atual": [
            formatar_moeda(row.get('BM')),
            formatar_numero(row.get('I/B')),
            formatar_moeda(row.get('PM')),
            formatar_numero(row.get('BOLETOS_PROJ'), 0),
        ],
        "Necessário para meta": [
            formatar_moeda(row.get('BM_NECESSARIO')),
            formatar_numero(row.get('IB_NECESSARIO')),
            formatar_moeda(row.get('PM_NECESSARIO')),
            formatar_numero(row.get('BOLETOS_NECESSARIOS'), 0),
        ],
        "Máx histórico": [
            formatar_moeda(hist_row.get('MAX_BM')),
            formatar_numero(hist_row.get('MAX_IB')),
            formatar_moeda(hist_row.get('MAX_PM')),
            formatar_numero(hist_row.get('MAX_BOLETOS'), 0),
        ],
        "Factível?": [
            _fact('BM_NECESSARIO',       'MAX_BM'),
            _fact('IB_NECESSARIO',       'MAX_IB'),
            _fact('PM_NECESSARIO',       'MAX_PM'),
            _fact('BOLETOS_NECESSARIOS', 'MAX_BOLETOS'),
        ],
    })
    st.dataframe(tabela, use_container_width=True, hide_index=True)

st.divider()

# ── Seção 5: Evolução mensal (tabela auxiliar) ────────────────────────────────

with st.expander("📊 Ver evolução mensal da loja em 2026"):
    mask_loja = analise['BCPS'] == bcps_selecionado
    if canal_selecionado != "Todos":
        mask_loja = mask_loja & (analise['CANAL'] == canal_selecionado)

    df_evolucao = analise[mask_loja].copy()
    df_evolucao['MES_NOME'] = df_evolucao['MES'].map(NOMES_MESES)

    cols_exibir = ['MES_NOME', 'FATURAMENTO', 'BOLETOS', 'BM', 'I/B', 'PM',
                   'META', 'BOLETOS_PROJ', 'BM_NECESSARIO']
    cols_existentes = [c for c in cols_exibir if c in df_evolucao.columns]

    df_show = df_evolucao[cols_existentes].copy()
    df_show = df_show.rename(columns={
        'MES_NOME': 'Mes', 'FATURAMENTO': 'Faturamento', 'BOLETOS': 'Boletos',
        'META': 'Meta', 'BOLETOS_PROJ': 'Bol. Proj.', 'BM_NECESSARIO': 'BM Nec.',
    })

    for col in ['Faturamento', 'BM', 'PM', 'Meta', 'BM Nec.']:
        if col in df_show.columns:
            df_show[col] = df_show[col].apply(formatar_moeda)
    for col in ['I/B']:
        if col in df_show.columns:
            df_show[col] = df_show[col].apply(lambda x: formatar_numero(x, 1))
    for col in ['Boletos', 'Bol. Proj.']:
        if col in df_show.columns:
            df_show[col] = df_show[col].apply(lambda x: formatar_numero(x, 0))

    st.dataframe(df_show, use_container_width=True, hide_index=True)

st.divider()

# ── Seção 6: Plano de Ação ────────────────────────────────────────────────────

st.markdown("#### 📋 Plano de Ação")

nome_gestor = st.text_input(
    "Seu nome (Gestor)",
    placeholder="Ex: João Silva",
    key="nome_gestor",
)

st.markdown("**Descreva as ações que serão tomadas para cada indicador:**")
col_pa1, col_pa2, col_pa3 = st.columns(3)

with col_pa1:
    acao_bm = st.text_area(
        "Ação para Boleto Médio (BM)",
        placeholder="Ex: Trabalhar mix de produtos de maior valor...",
        height=120,
        key="acao_bm",
    )
with col_pa2:
    acao_ib = st.text_area(
        "Ação para Itens por Boleto",
        placeholder="Ex: Oferecer combo/sugestão de item complementar...",
        height=120,
        key="acao_ib",
    )
with col_pa3:
    acao_pm = st.text_area(
        "Ação para Preço Médio (PM)",
        placeholder="Ex: Focar em categorias premium, reduzir descontos...",
        height=120,
        key="acao_pm",
    )

acao_boletos = st.text_area(
    "🚀 Ação para aumentar Boletos (captação de clientes)",
    placeholder="Ex: Contato ativo via CRM com inativos, campanha WhatsApp, parceria com loja vizinha...",
    height=90,
    key="acao_boletos",
)

observacoes = st.text_area(
    "Observações adicionais",
    placeholder="Contexto da loja, dificuldades, oportunidades identificadas...",
    height=80,
    key="observacoes",
)

col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])

# ── Botão Salvar no Histórico ─────────────────────────────────────────────────

with col_btn1:
    if st.button("💾 Salvar no Histórico", use_container_width=True):
        if not nome_gestor.strip():
            st.error("Informe seu nome antes de salvar.")
        else:
            registro = {
                "data_registro": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                "gestor": nome_gestor.strip(),
                "bcps": int(bcps_selecionado),
                "mes": mes_selecionado,
                "ano": 2026,
                "meta": row.get("META"),
                "realizado": row.get("FATURAMENTO"),
                "boletos_proj": row.get("BOLETOS_PROJ"),
                "bm_atual": row.get("BM"),
                "ib_atual": row.get("I/B"),
                "pm_atual": row.get("PM"),
                "bm_necessario": row.get("BM_NECESSARIO"),
                "ib_necessario": row.get("IB_NECESSARIO"),
                "pm_necessario": row.get("PM_NECESSARIO"),
                "boletos_necessarios": row.get("BOLETOS_NECESSARIOS"),
                "sugestao": mensagem,
                "acao_bm": acao_bm.strip(),
                "acao_ib": acao_ib.strip(),
                "acao_pm": acao_pm.strip(),
                "acao_boletos": acao_boletos.strip(),
                "observacoes": observacoes.strip(),
            }
            salvar_historico(registro)
            st.success(f"Plano salvo com sucesso para {nome_gestor.strip()}!")

# ── Botão Gerar PDF ───────────────────────────────────────────────────────────

with col_btn2:
    if st.button("📄 Gerar PDF", use_container_width=True):
        if not nome_gestor.strip():
            st.error("Informe seu nome para gerar o PDF.")
        else:
            with st.spinner("Gerando PDF..."):
                mes_nome_pdf = NOMES_MESES.get(mes_selecionado, str(mes_selecionado))
                dados_pdf = {
                    "gestor":      nome_gestor.strip(),
                    "bcps":        int(bcps_selecionado),
                    "mes":         mes_selecionado,
                    "ano":         2026,
                    "data":        datetime.datetime.now().strftime("%d/%m/%Y"),
                    # Meta e projeção
                    "meta":        meta,
                    "boletos_proj": bol_proj,
                    # Referência 2025
                    "bm_ref":      bm_ref,
                    "ib_ref":      ib_ref,
                    "pm_ref":      pm_ref,
                    "bol_ref":     bol_ref,
                    # Necessários
                    "bm_necessario":       bm_nec,
                    "ib_necessario":       ib_nec,
                    "pm_necessario":       pm_nec,
                    "boletos_necessarios": bol_nec,
                    # Cenário do simulador
                    "sim_bol": float(st.session_state.get("sim_bol", bol_proj or 0)),
                    "sim_ib":  float(st.session_state.get("sim_ib",  ib_ref  or 0)),
                    "sim_pm":  float(st.session_state.get("sim_pm",  pm_ref  or 0)),
                    "sim_bm":  float(st.session_state.get("sim_ib",  ib_ref  or 0)) *
                               float(st.session_state.get("sim_pm",  pm_ref  or 0)),
                    "sim_fat": float(st.session_state.get("sim_bol", bol_proj or 0)) *
                               float(st.session_state.get("sim_ib",  ib_ref  or 0)) *
                               float(st.session_state.get("sim_pm",  pm_ref  or 0)),
                    # Sugestão e ações
                    "sugestao":     mensagem,
                    "acao_bm":      acao_bm.strip(),
                    "acao_ib":      acao_ib.strip(),
                    "acao_pm":      acao_pm.strip(),
                    "acao_boletos": acao_boletos.strip(),
                    "observacoes":  observacoes.strip(),
                }
                try:
                    st.session_state["pdf_bytes"] = gerar_pdf(dados_pdf)
                    st.session_state["pdf_nome"]  = f"plano_acao_loja{int(bcps_selecionado)}_{mes_nome_pdf}_2026.pdf"
                    st.session_state["pdf_chave"] = f"{bcps_selecionado}_{mes_selecionado}"
                except Exception as e:
                    st.error(f"Erro ao gerar PDF: {e}")

# Mostra o botão de download enquanto os bytes estiverem no session_state
# (some automaticamente se trocar de loja/mês)
chave_atual = f"{bcps_selecionado}_{mes_selecionado}"
if st.session_state.get("pdf_chave") != chave_atual:
    st.session_state["pdf_bytes"] = None   # limpa PDF de outra loja/mês

if st.session_state.get("pdf_bytes"):
    with col_btn3:
        st.download_button(
            label="⬇️ Baixar PDF",
            data=st.session_state["pdf_bytes"],
            file_name=st.session_state["pdf_nome"],
            mime="application/pdf",
            use_container_width=True,
            key="download_pdf_btn",
        )

st.divider()

# ── Seção 7: Histórico de Planos ──────────────────────────────────────────────

with st.expander("📁 Ver histórico de planos salvos"):
    busca_gestor = st.text_input("Filtrar por gestor (deixe em branco para ver todos)", key="busca_gestor")
    df_hist = carregar_historico(busca_gestor.strip() if busca_gestor.strip() else None)

    if df_hist.empty:
        st.info("Nenhum plano salvo ainda.")
    else:
        cols_hist = ["data_registro", "gestor", "bcps", "mes", "bm_necessario", "acao_bm", "acao_ib", "acao_pm"]
        cols_hist_existentes = [c for c in cols_hist if c in df_hist.columns]
        df_hist_show = df_hist[cols_hist_existentes].copy()
        df_hist_show.columns = [c.replace("_", " ").title() for c in df_hist_show.columns]
        st.dataframe(df_hist_show, use_container_width=True, hide_index=True)
