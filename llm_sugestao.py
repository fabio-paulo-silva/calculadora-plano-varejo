"""
llm_sugestao.py
Integração com Groq (LLaMA 3.3 70B) para geração de planos de ação e chat estratégico.
Canal LOJA — Varejo Físico de Perfumaria e Cosméticos | IAF 2026.
"""

import os
import pathlib

import streamlit as st

_IAF_CONTEXT_PATH = pathlib.Path(__file__).parent / "iaf_context_loja.md"


@st.cache_data(show_spinner=False)
def _carregar_contexto_iaf() -> str:
    try:
        return _IAF_CONTEXT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _fmt_moeda(v) -> str:
    try:
        return f"R$ {float(v):,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "—"


def _fmt_num(v, dec=1) -> str:
    try:
        return f"{float(v):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "—"


def _fmt_pct(v) -> str:
    try:
        sinal = "+" if float(v) >= 0 else ""
        return f"{sinal}{float(v) * 100:.1f}%"
    except Exception:
        return "—"


def _fact(nec, mx) -> str:
    try:
        if nec is not None and mx is not None:
            if float(nec) <= float(mx):
                return "já atingido antes"
            pct = (float(nec) / float(mx) - 1) * 100
            return f"{pct:.0f}% acima do histórico"
    except Exception:
        pass
    return "sem histórico"


NOMES_MESES = {
    1:"Janeiro",2:"Fevereiro",3:"Março",4:"Abril",5:"Maio",6:"Junho",
    7:"Julho",8:"Agosto",9:"Setembro",10:"Outubro",11:"Novembro",12:"Dezembro",
}


def _bloco_dados(dados: dict) -> str:
    """Monta o bloco compacto de metas e indicadores necessários."""
    return f"""**Loja:** {dados.get('loja_nome','—')} (BCPS {dados.get('bcps','—')}) | **Mês:** {dados.get('mes_nome','—')} 2026 | **Regional:** {dados.get('regional','—')} | **Praça:** {dados.get('praca','—')} | **Tipo:** {dados.get('tipo_loja','Não informado')} | **Equipe:** {dados.get('tamanho_equipe','?')} consultores

| Indicador | 2025 | Necessário | Variação | Histórico máx |
|---|---|---|---|---|
| Meta | — | {_fmt_moeda(dados.get('meta'))} | — | — |
| Boletos | {_fmt_num(dados.get('bol_ref'),0)} | {_fmt_num(dados.get('bol_nec'),0)} | {_fmt_pct(dados.get('var_bol'))} | {_fact(dados.get('bol_nec'),dados.get('max_bol'))} |
| Boleto Médio | {_fmt_moeda(dados.get('bm_ref'))} | {_fmt_moeda(dados.get('bm_nec'))} | {_fmt_pct(dados.get('var_bm'))} | {_fact(dados.get('bm_nec'),dados.get('max_bm'))} |
| Itens/Boleto | {_fmt_num(dados.get('ib_ref'))} | {_fmt_num(dados.get('ib_nec'))} | {_fmt_pct(dados.get('var_ib'))} | {_fact(dados.get('ib_nec'),dados.get('max_ib'))} |
| Preço Médio | {_fmt_moeda(dados.get('pm_ref'))} | {_fmt_moeda(dados.get('pm_nec'))} | {_fmt_pct(dados.get('var_pm'))} | {_fact(dados.get('pm_nec'),dados.get('max_pm'))} |

**Principal desafio declarado pelo gestor:** {dados.get('desafio_principal','Não informado')}"""


def _bloco_tendencia(dados: dict) -> str:
    """Formata os últimos meses com dados reais para o prompt."""
    historico = dados.get('tendencia', [])
    if not historico:
        return "_Sem dados históricos recentes disponíveis._"

    linhas = ["| Mês | Fat. | Boletos | BM | I/B | PM | vs Meta |"]
    linhas.append("|---|---|---|---|---|---|---|")
    for m in historico:
        mes_nome = NOMES_MESES.get(m.get('MES', 0), str(m.get('MES', '')))
        fat  = _fmt_moeda(m.get('FATURAMENTO'))
        bol  = _fmt_num(m.get('BOLETOS'), 0)
        bm   = _fmt_moeda(m.get('BM'))
        ib   = _fmt_num(m.get('I/B'))
        pm   = _fmt_moeda(m.get('PM'))
        meta = m.get('META')
        fat_v = m.get('FATURAMENTO')
        vs_meta = (
            f"{(fat_v/meta*100):.0f}%" if meta and fat_v else "—"
        )
        linhas.append(f"| {mes_nome} | {fat} | {bol} | {bm} | {ib} | {pm} | {vs_meta} |")
    return "\n".join(linhas)


def _bloco_benchmark(dados: dict) -> str:
    """Formata o benchmark do cluster/geral para o prompt."""
    b = dados.get('benchmark', {})
    if not b or b.get('n_lojas', 0) == 0:
        return "_Benchmark não disponível._"

    cluster = b.get('cluster_nome', 'Geral')
    n       = b.get('n_lojas', 0)
    loja_bm  = dados.get('bm_ref')
    loja_ib  = dados.get('ib_ref')
    loja_pm  = dados.get('pm_ref')
    loja_bol = dados.get('bol_ref')

    def _pos(val, p50, p75):
        try:
            if float(val) >= float(p75): return "🟢 Top 25%"
            if float(val) >= float(p50): return "🟡 Acima da mediana"
            return "🔴 Abaixo da mediana"
        except Exception:
            return "—"

    return f"""**Cluster de referência:** {cluster} ({n} lojas) — comparativo com {NOMES_MESES.get(dados.get('mes_num',0),'2025')} 2025

| Indicador | Esta loja | Mediana cluster | Top 25% cluster | Posição |
|---|---|---|---|---|
| Boleto Médio | {_fmt_moeda(loja_bm)} | {_fmt_moeda(b.get('p50_bm'))} | {_fmt_moeda(b.get('p75_bm'))} | {_pos(loja_bm, b.get('p50_bm'), b.get('p75_bm'))} |
| Itens/Boleto | {_fmt_num(loja_ib)} | {_fmt_num(b.get('p50_ib'))} | {_fmt_num(b.get('p75_ib'))} | {_pos(loja_ib, b.get('p50_ib'), b.get('p75_ib'))} |
| Preço Médio | {_fmt_moeda(loja_pm)} | {_fmt_moeda(b.get('p50_pm'))} | {_fmt_moeda(b.get('p75_pm'))} | {_pos(loja_pm, b.get('p50_pm'), b.get('p75_pm'))} |
| Boletos | {_fmt_num(loja_bol,0)} | {_fmt_num(b.get('p50_bol'),0)} | {_fmt_num(b.get('p75_bol'),0)} | {_pos(loja_bol, b.get('p50_bol'), b.get('p75_bol'))} |"""


def _system_prompt(dados: dict) -> str:
    """Monta o system prompt completo com contexto IAF + dados + tendência + benchmark."""
    ctx = _carregar_contexto_iaf()
    return f"""Você é um consultor estratégico especializado em varejo físico de perfumaria e cosméticos, com profundo conhecimento do programa IAF do Grupo Boticário.

## REGRAS INEGOCIÁVEIS
- Respostas CURTAS e DIRETAS — máximo 5 bullets por seção, sem enrolação
- Nunca use numeração de indicadores (diga "Resgate Fidelidade", nunca "indicador 1.6")
- Se o gestor disser que uma ação não é viável, aceite SEM questionar e sugira alternativa imediatamente
- USE os dados reais de tendência e benchmark para personalizar cada sugestão — nada genérico
- Foco exclusivo no canal LOJA (PDV físico) — jamais mencione VD, revendedoras ou Eudora
- Português brasileiro, tom de gestor experiente em varejo

## CONTEXTO IAF 2026 — CANAL LOJA
{ctx}

## DADOS REAIS DA LOJA — MÊS ATUAL
{_bloco_dados(dados)}

## TENDÊNCIA — ÚLTIMOS MESES (2026)
{_bloco_tendencia(dados)}

## BENCHMARK — POSIÇÃO VS CLUSTER
{_bloco_benchmark(dados)}"""


def _get_client():
    """Retorna cliente Groq autenticado."""
    try:
        from groq import Groq  # type: ignore
    except ImportError as exc:
        raise ImportError("Pacote 'groq' não instalado. Adicione 'groq' ao requirements.txt.") from exc

    api_key = None
    try:
        api_key = st.secrets["GROQ_API_KEY"]
    except Exception:
        pass
    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY não encontrada. Configure em .streamlit/secrets.toml.")

    from groq import Groq  # type: ignore
    return Groq(api_key=api_key)


# ── Geração do plano inicial ──────────────────────────────────────────────────

def gerar_plano_inicial(dados: dict) -> str:
    """Gera o plano de ação inicial personalizado e enxuto para a loja."""

    foco_map = {
        "combinado": "alavancas mais factíveis para esta loja",
        "bm":        "Boleto Médio",
        "ib":        "Itens por Boleto",
        "pm":        "Preço Médio",
        "boletos":   "aumento de Boletos",
    }
    foco = foco_map.get(dados.get("foco", "combinado"), "alavancas mais factíveis")

    # Monta bloco de metas específicas da loja para o prompt
    def _fact_txt(nec, mx):
        try:
            return "✅ já atingido antes" if float(nec) <= float(mx) else f"🔴 {(float(nec)/float(mx)-1)*100:.0f}% acima do histórico"
        except Exception:
            return ""

    metas_loja = f"""**Metas específicas desta loja para {dados.get('mes_nome','')}/{dados.get('bcps','')}:**
- Boleto Médio necessário: **{_fmt_moeda(dados.get('bm_nec'))}** (ref. 2025: {_fmt_moeda(dados.get('bm_ref'))}, var. {_fmt_pct(dados.get('var_bm'))}) — {_fact_txt(dados.get('bm_nec'), dados.get('max_bm'))}
- Itens por Boleto necessário: **{_fmt_num(dados.get('ib_nec'))}** (ref. 2025: {_fmt_num(dados.get('ib_ref'))}, var. {_fmt_pct(dados.get('var_ib'))}) — {_fact_txt(dados.get('ib_nec'), dados.get('max_ib'))}
- Preço Médio necessário: **{_fmt_moeda(dados.get('pm_nec'))}** (ref. 2025: {_fmt_moeda(dados.get('pm_ref'))}, var. {_fmt_pct(dados.get('var_pm'))}) — {_fact_txt(dados.get('pm_nec'), dados.get('max_pm'))}
- Boletos necessários: **{_fmt_num(dados.get('bol_nec'),0)}** (ref. 2025: {_fmt_num(dados.get('bol_ref'),0)}, var. {_fmt_pct(dados.get('var_bol'))}) — {_fact_txt(dados.get('bol_nec'), dados.get('max_bol'))}
- Meta do mês: **{_fmt_moeda(dados.get('meta'))}**"""

    # Deriva insight de tendência para o prompt
    tendencia = dados.get('tendencia', [])
    insight_tendencia = ""
    if len(tendencia) >= 2:
        bm_vals = [m.get('BM') for m in tendencia if m.get('BM')]
        ib_vals = [m.get('I/B') for m in tendencia if m.get('I/B')]
        if len(bm_vals) >= 2:
            delta_bm = bm_vals[-1] - bm_vals[0]
            tendencia_txt = "em alta" if delta_bm > 0 else "em queda"
            insight_tendencia = f"Tendência de BM nos últimos meses: **{tendencia_txt}** ({_fmt_pct(delta_bm / bm_vals[0] if bm_vals[0] else 0)})."

    # Deriva insight de benchmark
    b = dados.get('benchmark', {})
    insight_bench = ""
    if b.get('n_lojas', 0) > 0:
        loja_bm = dados.get('bm_ref')
        p50_bm  = b.get('p50_bm')
        p75_bm  = b.get('p75_bm')
        try:
            if float(loja_bm) >= float(p75_bm):
                insight_bench = f"BM acima do Top 25% do cluster ({b.get('cluster_nome','')}) — oportunidade está em I/B ou boletos."
            elif float(loja_bm) < float(p50_bm):
                insight_bench = f"BM abaixo da mediana do cluster ({b.get('cluster_nome','')}) — há espaço real de captura via mix e BT/BP."
            else:
                insight_bench = f"BM entre mediana e Top 25% do cluster ({b.get('cluster_nome','')}) — potencial de subir uma faixa com foco em PM."
        except Exception:
            pass

    prompt_usuario = f"""{metas_loja}

{insight_tendencia}
{insight_bench}

Gere um plano PERSONALIZADO para esta loja de **{dados.get('tipo_loja','varejo')}**, focado em **{foco}**.
Considere: tipo de loja, sazonalidade do mês, tendência recente e posição no benchmark do cluster.

Use EXATAMENTE estes títulos markdown:

### Diagnóstico
1 frase precisa: qual indicador é o gargalo real, baseado na tendência e no benchmark.

### Ação para Boleto Médio
2 ações específicas para esta loja atingir {_fmt_moeda(dados.get('bm_nec'))}. Conecte ao IAF pelo nome.

### Ação para Itens por Boleto
2 ações para chegar em {_fmt_num(dados.get('ib_nec'))} I/B. Use BT/BP se pertinente ao cluster.

### Ação para Preço Médio
2 ações para atingir {_fmt_moeda(dados.get('pm_nec'))} de PM. Adeque ao perfil {dados.get('tipo_loja','da loja')}.

### Ação para Boletos
2 ações para alcançar {_fmt_num(dados.get('bol_nec'),0)} boletos. CRM, Loja Digital, Ação de Fluxo.

### O que monitorar
3 KPIs com frequência (ex: "BM diário por consultora").

Máximo 200 palavras. Sem introdução. Sem conclusão. Direto ao ponto."""

    client = _get_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": _system_prompt(dados)},
            {"role": "user",   "content": prompt_usuario},
        ],
        temperature=0.25,
        max_tokens=700,
    )
    return response.choices[0].message.content.strip()


# ── Chat estratégico ──────────────────────────────────────────────────────────

def chat_estrategico(historico: list, mensagem_gestor: str, dados: dict) -> str:
    """
    Continua a conversa estratégica com o gestor.

    historico: lista de dicts {role: 'user'|'assistant', content: str}
    mensagem_gestor: nova mensagem do gestor
    dados: dados da loja (mesmo dict usado no plano inicial)
    """
    client = _get_client()

    messages = [{"role": "system", "content": _system_prompt(dados)}]
    messages.extend(historico)
    messages.append({"role": "user", "content": mensagem_gestor})

    # Injeta lembrete de brevidade na última mensagem do usuário
    messages[-1]["content"] = (
        messages[-1]["content"]
        + "\n\n(Responda em no máximo 120 palavras. Seja direto e estratégico.)"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.4,
        max_tokens=350,
    )
    return response.choices[0].message.content.strip()
