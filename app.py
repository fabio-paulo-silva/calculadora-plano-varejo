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
    return carregar_tudo()


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
            f"- 📦 Mantenha I/B acima de **{formatar_numero(ib_nec)}** (atual: {formatar_numero(ib_at)})\n"
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
                f"Meta: **{formatar_numero(ib_nec)} I/B** | Atual: {formatar_numero(ib_at)} | "
                f"Máx histórico: {formatar_numero(max_ib)}\n\n"
                f"**Ações sugeridas:**\n"
                f"- 🛍️ Treine a equipe em venda sugestiva: *\"Esse produto combina com...\"*\n"
                f"- 🎁 Monte kits e combos com produtos complementares (ex.: perfume + hidratante)\n"
                f"- 📍 Posicione itens de menor valor próximos ao produto principal\n"
                f"- 🏆 Desafio de equipe: meta de {formatar_numero(ib_nec, 0)} itens por boleto\n"
                f"- 📊 Monitore o I/B diariamente por vendedora para correção rápida"
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
            f"está acima do histórico ({fm(max_pm)}), mas I/B de **{formatar_numero(ib_nec)}** "
            f"é atingível (máx histórico: {formatar_numero(max_ib)}).\n\n"
            f"**Ações para aumentar I/B ({formatar_pct(var_ib)} necessário):**\n"
            f"- 🛍️ Venda sugestiva ativa em todos os atendimentos\n"
            f"- 🎁 Kits e combos estratégicos com produtos complementares\n"
            f"- 📍 Visual merchandising estimulando compra de itens adicionais\n"
            f"- 🏆 Ranking diário da equipe por I/B"
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
            f"💰 **Foque em Preço Médio** — I/B necessário ({formatar_numero(ib_nec)}) "
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
            f"Os indicadores de qualidade (I/B e PM) estão além do histórico desta loja. "
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
        f"- 📦 I/B: {formatar_numero(ib_at)} → **{formatar_numero(ib_nec)}** "
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
    analise, hist_max, metas, base = load_data()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Filtros")

    lojas_disponiveis = sorted(analise['BCPS'].dropna().unique().astype(int).tolist())
    bcps_selecionado = st.selectbox(
        "Loja (BCPS)",
        options=lojas_disponiveis,
        format_func=lambda x: f"Loja {int(x)}",
    )

    meses_disponiveis = sorted(analise[analise['BCPS'] == bcps_selecionado]['Mês'].unique().tolist())
    mes_selecionado = st.selectbox(
        "Mês de Análise",
        options=meses_disponiveis,
        index=len(meses_disponiveis) - 1,
        format_func=lambda x: NOMES_MESES.get(x, str(x)),
    )

    canais_disponiveis = analise[
        (analise['BCPS'] == bcps_selecionado) & (analise['Mês'] == mes_selecionado)
    ]['CANAL'].unique().tolist()

    if len(canais_disponiveis) > 1:
        canal_selecionado = st.selectbox("Canal", options=["Todos"] + canais_disponiveis)
    else:
        canal_selecionado = canais_disponiveis[0] if canais_disponiveis else "Todos"

    if st.button("🔄 Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Filtrar linha de análise ──────────────────────────────────────────────────

mask = (analise['BCPS'] == bcps_selecionado) & (analise['Mês'] == mes_selecionado)
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
        'Mês': mes_selecionado,
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

st.subheader(f"Loja {int(bcps_selecionado)} — {NOMES_MESES.get(mes_selecionado, mes_selecionado)} 2026")

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

# ── Seção 2: Indicadores necessários vs referência 2025 ──────────────────────

st.markdown("#### 📊 Indicadores Necessários para Atingir a Meta")
st.caption("Referência: mesmo mês de 2025. Cada coluna mostra o que precisa ser feito e o esforço relativo.")

col1, col2, col3, col4 = st.columns(4)

def _delta_inv(nec, ref):
    if nec is None or ref is None or ref == 0:
        return None
    return formatar_pct((nec / ref) - 1) + " vs 2025"

with col1:
    st.metric(
        "Boleto Médio",
        formatar_moeda(bm_nec),
        delta=_delta_inv(bm_nec, bm_ref),
        delta_color="inverse",
        help="Meta ÷ Boletos Projetados",
    )
    if bm_ref:
        st.caption(f"Referência 2025: {formatar_moeda(bm_ref)}")
with col2:
    st.metric(
        "Itens por Boleto",
        formatar_numero(ib_nec),
        delta=_delta_inv(ib_nec, ib_ref),
        delta_color="inverse",
        help="BM Necessário ÷ Preço Médio 2025 (mantendo PM de referência)",
    )
    if ib_ref:
        st.caption(f"Referência 2025: {formatar_numero(ib_ref)}")
with col3:
    st.metric(
        "Preço Médio",
        formatar_moeda(pm_nec),
        delta=_delta_inv(pm_nec, pm_ref),
        delta_color="inverse",
        help="BM Necessário ÷ Itens por Boleto 2025 (mantendo I/B de referência)",
    )
    if pm_ref:
        st.caption(f"Referência 2025: {formatar_moeda(pm_ref)}")
with col4:
    st.metric(
        "Boletos (se BM = 2025)",
        formatar_numero(bol_nec, 0),
        delta=_delta_inv(bol_nec, bol_ref),
        delta_color="inverse",
        help="Meta ÷ BM de 2025 — boletos necessários mantendo o BM do ano passado",
    )
    if bol_ref:
        st.caption(f"Referência 2025: {formatar_numero(bol_ref, 0)}")

st.divider()

# ── Seção 3: Simulador what-if ────────────────────────────────────────────────

st.markdown("#### 🔢 Simulador — E se eu melhorar um indicador?")
st.caption("Defina o valor que você pretende alcançar em um indicador e veja o que os outros precisam ser.")

sim_col1, sim_col2, sim_col3 = st.columns([1, 1, 2])

with sim_col1:
    indicador_fixo = st.selectbox(
        "Indicador que você vai definir",
        ["Itens por Boleto", "Preço Médio", "Boleto Médio", "Boletos"],
        key="sim_indicador",
    )

with sim_col2:
    if indicador_fixo == "Itens por Boleto":
        val_ref = ib_ref or 0.0
        sim_val = st.number_input("Meta de Itens por Boleto", min_value=0.0,
                                  value=round(float(val_ref), 1), step=0.1, format="%.1f")
    elif indicador_fixo == "Preço Médio":
        val_ref = pm_ref or 0.0
        sim_val = st.number_input("Meta de Preço Médio (R$)", min_value=0.0,
                                  value=round(float(val_ref), 0), step=1.0, format="%.0f")
    elif indicador_fixo == "Boleto Médio":
        val_ref = bm_ref or 0.0
        sim_val = st.number_input("Meta de Boleto Médio (R$)", min_value=0.0,
                                  value=round(float(val_ref), 0), step=1.0, format="%.0f")
    else:
        val_ref = bol_ref or 0.0
        sim_val = st.number_input("Meta de Boletos", min_value=0,
                                  value=int(val_ref), step=10)

with sim_col3:
    if meta and sim_val and sim_val > 0:
        if indicador_fixo == "Itens por Boleto":
            sim_bm  = meta / bol_proj if bol_proj else None
            sim_pm  = sim_bm / sim_val if sim_bm else None
            sim_bol = bol_proj
            label   = f"Com **{formatar_numero(sim_val)} Itens por Boleto**:"
            r1 = ("Boleto Médio necessário",  formatar_moeda(sim_bm),  _delta_inv(sim_bm, bm_ref))
            r2 = ("Preço Médio necessário",   formatar_moeda(sim_pm),  _delta_inv(sim_pm, pm_ref))
            r3 = ("Boletos projetados",       formatar_numero(sim_bol, 0), None)

        elif indicador_fixo == "Preço Médio":
            sim_bm  = meta / bol_proj if bol_proj else None
            sim_ib  = sim_bm / sim_val if sim_bm else None
            sim_bol = bol_proj
            label   = f"Com **{formatar_moeda(sim_val)} de Preço Médio**:"
            r1 = ("Boleto Médio necessário",       formatar_moeda(sim_bm),  _delta_inv(sim_bm, bm_ref))
            r2 = ("Itens por Boleto necessário",   formatar_numero(sim_ib), _delta_inv(sim_ib, ib_ref))
            r3 = ("Boletos projetados",            formatar_numero(sim_bol, 0), None)

        elif indicador_fixo == "Boleto Médio":
            sim_ib  = sim_val / pm_ref if pm_ref else None
            sim_pm  = sim_val / ib_ref if ib_ref else None
            sim_bol = meta / sim_val
            label   = f"Com **{formatar_moeda(sim_val)} de Boleto Médio**:"
            r1 = ("Itens por Boleto necessário",  formatar_numero(sim_ib), _delta_inv(sim_ib, ib_ref))
            r2 = ("Preço Médio necessário",        formatar_moeda(sim_pm),  _delta_inv(sim_pm, pm_ref))
            r3 = ("Boletos necessários",           formatar_numero(sim_bol, 0), _delta_inv(sim_bol, bol_ref))

        else:  # Boletos
            sim_bm  = meta / sim_val
            sim_ib  = sim_bm / pm_ref if pm_ref else None
            sim_pm  = sim_bm / ib_ref if ib_ref else None
            label   = f"Com **{formatar_numero(sim_val, 0)} Boletos**:"
            r1 = ("Boleto Médio necessário",      formatar_moeda(sim_bm),  _delta_inv(sim_bm, bm_ref))
            r2 = ("Itens por Boleto necessário",  formatar_numero(sim_ib), _delta_inv(sim_ib, ib_ref))
            r3 = ("Preço Médio necessário",        formatar_moeda(sim_pm),  _delta_inv(sim_pm, pm_ref))

        st.markdown(label)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(r1[0], r1[1], delta=r1[2], delta_color="inverse")
        with c2:
            st.metric(r2[0], r2[1], delta=r2[2], delta_color="inverse")
        with c3:
            st.metric(r3[0], r3[1], delta=r3[2], delta_color="inverse" if r3[2] else "normal")

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
        "Indicador": ["BM (Boleto Médio)", "I/B (Itens/Boleto)", "PM (Preço Médio)", "Boletos"],
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
    df_evolucao['Mês Nome'] = df_evolucao['Mês'].map(NOMES_MESES)

    cols_exibir = ['Mês Nome', 'FATURAMENTO', 'BOLETOS', 'BM', 'I/B', 'PM',
                   'META', 'BOLETOS_PROJ', 'BM_NECESSARIO']
    cols_existentes = [c for c in cols_exibir if c in df_evolucao.columns]

    df_show = df_evolucao[cols_existentes].copy()
    df_show = df_show.rename(columns={
        'Mês Nome': 'Mês', 'FATURAMENTO': 'Faturamento', 'BOLETOS': 'Boletos',
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
        "Ação para Itens por Boleto (I/B)",
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
                dados_pdf = {
                    "gestor": nome_gestor.strip(),
                    "bcps": int(bcps_selecionado),
                    "mes": mes_selecionado,
                    "ano": 2026,
                    "data": datetime.datetime.now().strftime("%d/%m/%Y"),
                    "meta": row.get("META"),
                    "realizado": row.get("FATURAMENTO"),
                    "boletos_proj": row.get("BOLETOS_PROJ"),
                    "bm_atual": row.get("BM"),
                    "ib_atual": row.get("I/B"),
                    "pm_atual": row.get("PM"),
                    "bm_necessario": row.get("BM_NECESSARIO"),
                    "ib_necessario": row.get("IB_NECESSARIO"),
                    "pm_necessario": row.get("PM_NECESSARIO"),
                    "sugestao": mensagem,
                    "acao_bm": acao_bm.strip(),
                    "acao_ib": acao_ib.strip(),
                    "acao_pm": acao_pm.strip(),
                    "acao_boletos": acao_boletos.strip(),
                    "observacoes": observacoes.strip(),
                    "historico_max": {
                        "MAX_BM":      hist_row["MAX_BM"]      if hist_row is not None else None,
                        "MAX_IB":      hist_row["MAX_IB"]      if hist_row is not None else None,
                        "MAX_PM":      hist_row["MAX_PM"]      if hist_row is not None else None,
                        "MAX_BOLETOS": hist_row["MAX_BOLETOS"] if hist_row is not None else None,
                    },
                }
                mes_nome_pdf = NOMES_MESES.get(mes_selecionado, str(mes_selecionado))
                # Guarda no session_state para o botão de download persistir após o rerun
                st.session_state["pdf_bytes"] = gerar_pdf(dados_pdf)
                st.session_state["pdf_nome"]  = f"plano_acao_loja{int(bcps_selecionado)}_{mes_nome_pdf}_2026.pdf"
                st.session_state["pdf_chave"] = f"{bcps_selecionado}_{mes_selecionado}"

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
