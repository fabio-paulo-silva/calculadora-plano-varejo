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
- USE os dados reais de tendência e comparação para personalizar cada sugestão — nada genérico
- **NUNCA use termos estatísticos** como mediana, percentil, top 25%, benchmark, p50, p75. Use linguagem simples: "a maioria das lojas do mesmo tipo", "as melhores lojas", "abaixo do esperado para este formato"
- Foco exclusivo no canal LOJA (PDV físico) — jamais mencione VD, revendedoras ou Eudora
- Português brasileiro, tom de gestor experiente em varejo — linguagem direta e humana
- **NUNCA sugira "implementar Ação de Fluxo"** — ela já existe e já traz clientes. Foque sempre em CONVERTER os clientes que já vieram retirar o brinde: abordagem no momento do resgate, BT/BP no balcão, script do consultor

## CONTEXTO IAF 2026 — CANAL LOJA
{ctx}

## DADOS REAIS DA LOJA — MÊS ATUAL
{_bloco_dados(dados)}

## TENDÊNCIA — ÚLTIMOS MESES (2026)
{_bloco_tendencia(dados)}

## BENCHMARK — POSIÇÃO VS CLUSTER
{_bloco_benchmark(dados)}"""


def interpretar_tendencia(tendencia: list) -> list:
    """
    Gera conclusões diagnósticas em linguagem direta (tom: "Seu I/B caiu 3 meses seguidos").
    Foca em BM, I/B e PM. Boletos usado só para cruzamentos.
    """
    if len(tendencia) < 2:
        return []

    def _analisar(chave):
        vals = [m.get(chave) for m in tendencia if m.get(chave) is not None]
        if len(vals) < 2:
            return None
        # Conta meses consecutivos na mesma direção partindo do mais recente
        consec = 1
        for i in range(len(vals) - 1, 0, -1):
            if vals[i] < vals[i - 1]:   # caindo
                if vals[-1] < vals[-2]:
                    consec += 1
                else:
                    break
            else:                        # subindo
                if vals[-1] >= vals[-2]:
                    consec += 1
                else:
                    break
        delta = vals[-1] - vals[0]
        return {
            "vals":  vals,
            "dir":   "subindo" if delta >= 0 else "caindo",
            "consec": consec,
            "pct":   delta / vals[0] if vals[0] else 0,
            "primeiro": vals[0],
            "ultimo":   vals[-1],
        }

    bm  = _analisar("BM")
    ib  = _analisar("I/B")
    pm  = _analisar("PM")
    bol = _analisar("BOLETOS")

    conclusoes = []
    ja_citou_ib = False

    # ── Padrões cruzados (prioridade) ─────────────────────────────────────────

    # BM crescendo mas boletos caindo → fluxo é o gap
    if bm and bol and bm["dir"] == "subindo" and bol["dir"] == "caindo":
        n_bm  = bm["consec"]
        n_bol = bol["consec"]
        conclusoes.append(
            f"Você cresceu o BM por {n_bm} {'mês' if n_bm == 1 else 'meses'} seguidos "
            f"({_fmt_moeda(bm['primeiro'])} → {_fmt_moeda(bm['ultimo'])}) "
            f"mas perdeu boletos por {n_bol} {'mês' if n_bol == 1 else 'meses'} — "
            f"o fluxo é o gap real."
        )

    # I/B e PM caindo → equipe não está vendendo bem
    if ib and pm and ib["dir"] == "caindo" and pm["dir"] == "caindo":
        n_ib = ib["consec"]
        n_pm = pm["consec"]
        conclusoes.append(
            f"Seu I/B caiu {n_ib} {'mês' if n_ib == 1 else 'meses'} seguidos "
            f"({_fmt_num(ib['primeiro'], 1)} → {_fmt_num(ib['ultimo'], 1)}) "
            f"e seu PM caiu {n_pm} {'mês' if n_pm == 1 else 'meses'} "
            f"({_fmt_moeda(pm['primeiro'])} → {_fmt_moeda(pm['ultimo'])}) — "
            f"o problema não é meta, é execução: mix e venda sugestiva."
        )
        ja_citou_ib = True

    # ── Padrões por indicador ──────────────────────────────────────────────────

    # I/B caindo (se ainda não citado)
    if ib and ib["dir"] == "caindo" and ib["consec"] >= 2 and not ja_citou_ib:
        n = ib["consec"]
        conclusoes.append(
            f"Seu I/B caiu {n} meses seguidos "
            f"({_fmt_num(ib['primeiro'], 1)} → {_fmt_num(ib['ultimo'], 1)}) — "
            f"o problema não é meta, é processo: equipe não está executando BT/BP e venda sugestiva."
        )

    # BM caindo
    if bm and bm["dir"] == "caindo" and bm["consec"] >= 2:
        n = bm["consec"]
        conclusoes.append(
            f"Seu BM caiu {n} meses seguidos "
            f"({_fmt_moeda(bm['primeiro'])} → {_fmt_moeda(bm['ultimo'])}) — "
            f"mix de produtos perdendo valor ou desconto sendo mal aplicado."
        )

    # PM caindo sozinho
    if pm and pm["dir"] == "caindo" and pm["consec"] >= 2 and not any("PM caiu" in c for c in conclusoes):
        n = pm["consec"]
        conclusoes.append(
            f"Seu Preço Médio caiu {n} meses seguidos "
            f"({_fmt_moeda(pm['primeiro'])} → {_fmt_moeda(pm['ultimo'])}) — "
            f"categorias de menor valor ganhando espaço no mix."
        )

    # BM subindo consistente
    if bm and bm["dir"] == "subindo" and bm["consec"] >= 3 and not any("cresceu o BM" in c for c in conclusoes):
        n = bm["consec"]
        conclusoes.append(
            f"Você cresceu o BM por {n} meses consecutivos "
            f"({_fmt_moeda(bm['primeiro'])} → {_fmt_moeda(bm['ultimo'])}) — "
            f"ritmo positivo, manter execução de BT/BP e mix premium."
        )

    # I/B subindo
    if ib and ib["dir"] == "subindo" and ib["consec"] >= 3:
        n = ib["consec"]
        conclusoes.append(
            f"Seu I/B cresceu {n} meses seguidos "
            f"({_fmt_num(ib['primeiro'], 1)} → {_fmt_num(ib['ultimo'], 1)}) — "
            f"equipe executando bem a venda sugestiva."
        )

    # Sem padrão relevante
    if not conclusoes:
        partes = []
        for nome, d, fmt in [
            ("BM",  bm,  _fmt_moeda),
            ("I/B", ib,  lambda v: _fmt_num(v, 1)),
            ("PM",  pm,  _fmt_moeda),
        ]:
            if d and abs(d["pct"]) >= 0.03:
                partes.append(
                    f"{nome} {'subindo' if d['dir'] == 'subindo' else 'caindo'} "
                    f"{_fmt_pct(d['pct'])} ({fmt(d['primeiro'])} → {fmt(d['ultimo'])})"
                )
        if partes:
            conclusoes.append("Variações recentes: " + " | ".join(partes) + ".")

    return conclusoes


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
    """Gera o plano de ação inicial — usa tendência, benchmark, cluster, equipe e desafio."""

    # ── Sazonalidade do mês ────────────────────────────────────────────────────
    sazonalidade_map = {
        1:  "pós-festas — reativação de clientes, liquidação de estoque",
        2:  "Carnaval — perfumaria feminina, maquiagem para festas",
        3:  "Dia da Mulher (8/3) — gifting premium, kits de skincare",
        4:  "Páscoa — gifting, kits de presente, alto tráfego em shopping",
        5:  "Dia das Mães — maior data do varejo de cosméticos; gifting e perfumaria são prioridade",
        6:  "Dia dos Namorados (12/6) — perfumaria masculina e feminina, kits casal; BM historicamente alto",
        7:  "Férias escolares — queda de tráfego em alguns formatos; foco em fidelização e serviços",
        8:  "Dia dos Pais (2ª semana) — perfumaria masculina, kits presente",
        9:  "lançamentos coleção — boa janela para skincare e novas categorias",
        10: "Dia das Crianças (12/10) — gifting, alto tráfego em shopping",
        11: "Black Friday (última semana) — maior mês em volume de boletos; priorize I/B e conversão",
        12: "Natal + Ano Novo — gifting e perfumaria premium; segundo maior mês do ano",
    }
    mes_num  = dados.get('mes_num') or dados.get('mes_selecionado', 0)
    mes_nome = dados.get('mes_nome', '')
    sazonalidade = sazonalidade_map.get(int(mes_num), "")

    # ── Tendência: série + conclusões diagnósticas ────────────────────────────
    tendencia = dados.get('tendencia', [])
    insight_tendencia = "Sem histórico de meses anteriores disponível."

    if len(tendencia) >= 2:
        # Série numérica
        linhas_serie = []
        for ind, chave in [("BM", "BM"), ("I/B", "I/B"), ("PM", "PM"), ("Boletos", "BOLETOS")]:
            vals  = [m.get(chave) for m in tendencia if m.get(chave) is not None]
            meses = [NOMES_MESES.get(m.get('MES', 0), '')[:3] for m in tendencia if m.get(chave) is not None]
            if len(vals) < 2:
                continue
            fmt   = _fmt_moeda if ind in ("BM", "PM") else (lambda v: _fmt_num(v, 0)) if ind == "Boletos" else _fmt_num
            delta = vals[-1] - vals[0]
            pct   = delta / vals[0] if vals[0] else 0
            dir_  = "↑" if delta > 0 else "↓"
            serie = " → ".join(fmt(v) for v in vals)
            linhas_serie.append(f"- {ind}: {serie} [{', '.join(meses)}] {dir_} {_fmt_pct(pct)}")

        # Conclusões diagnósticas (mesma função usada na UI)
        conclusoes = interpretar_tendencia(tendencia)
        conclusoes_txt = "\n".join(conclusoes) if conclusoes else "Sem variação relevante identificada."
        serie_txt = "\n".join(linhas_serie)
        insight_tendencia = f"Série histórica desta loja:\n{serie_txt}\n\nDiagnóstico da tendência:\n{conclusoes_txt}"

    # ── Benchmark: posição vs cluster ─────────────────────────────────────────
    b = dados.get('benchmark', {})
    cluster_nome = b.get('cluster_nome', 'Geral')
    n_lojas      = b.get('n_lojas', 0)
    insight_bench = "Comparação não disponível."
    if n_lojas > 0:
        linhas_bench = []
        for ind, chave_loja, chave_p50, chave_p75 in [
            ("BM",      'bm_ref',  'p50_bm',  'p75_bm'),
            ("I/B",     'ib_ref',  'p50_ib',  'p75_ib'),
            ("PM",      'pm_ref',  'p50_pm',  'p75_pm'),
            ("Boletos", 'bol_ref', 'p50_bol', 'p75_bol'),
        ]:
            try:
                val  = float(dados.get(chave_loja))
                p50  = float(b.get(chave_p50))
                p75  = float(b.get(chave_p75))
                fmt  = _fmt_moeda if ind in ("BM", "PM") else (lambda v: _fmt_num(v, 0)) if ind == "Boletos" else _fmt_num
                # Linguagem simples — sem termos estatísticos
                if val >= p75:
                    pos = f"entre as melhores lojas {cluster_nome} ({fmt(val)} vs {fmt(p75)} das top)"
                elif val >= p50:
                    pos = f"acima da maioria das lojas {cluster_nome} ({fmt(val)} vs {fmt(p50)} da maioria)"
                else:
                    pct_gap = (p50 - val) / p50 * 100
                    pos = f"abaixo da maioria das lojas {cluster_nome} — gap de {pct_gap:.0f}% para alcançar a maioria ({fmt(val)} vs {fmt(p50)})"
                linhas_bench.append(f"- **{ind}:** {pos}")
            except Exception:
                pass
        if linhas_bench:
            insight_bench = f"Comparado com {n_lojas} lojas do tipo {cluster_nome}:\n" + "\n".join(linhas_bench)

    tipo_loja = dados.get('tipo_loja', 'Não informado')

    foco_key = dados.get("foco", "combinado")

    # Define quais seções de ação gerar conforme o foco
    secoes_acao = {
        "combinado": ["Boleto Médio", "Itens por Boleto", "Preço Médio", "Boletos"],
        "bm":        ["Boleto Médio"],
        "ib":        ["Itens por Boleto"],
        "pm":        ["Preço Médio"],
        "boletos":   ["Boletos"],
    }
    secoes = secoes_acao.get(foco_key, secoes_acao["combinado"])

    foco_map = {
        "combinado": "todos os indicadores",
        "bm":        "Boleto Médio",
        "ib":        "Itens por Boleto",
        "pm":        "Preço Médio",
        "boletos":   "Boletos",
    }
    foco = foco_map.get(foco_key, "todos os indicadores")

    def _fact_txt(nec, mx):
        try:
            return "✅ já atingido antes" if float(nec) <= float(mx) else f"🔴 {(float(nec)/float(mx)-1)*100:.0f}% acima do histórico"
        except Exception:
            return ""

    prompt_usuario = f"""## CONTEXTO DESTA LOJA

**Loja:** {dados.get('loja_nome','—')} | **Cluster:** {tipo_loja} | **Mês:** {mes_nome} 2026
**Sazonalidade de {mes_nome}:** {sazonalidade}

## METAS DO MÊS
- Meta: **{_fmt_moeda(dados.get('meta'))}**
- BM necessário: **{_fmt_moeda(dados.get('bm_nec'))}** (ref. 2025: {_fmt_moeda(dados.get('bm_ref'))}, var. {_fmt_pct(dados.get('var_bm'))}) — {_fact_txt(dados.get('bm_nec'), dados.get('max_bm'))}
- I/B necessário: **{_fmt_num(dados.get('ib_nec'))}** (ref. 2025: {_fmt_num(dados.get('ib_ref'))}, var. {_fmt_pct(dados.get('var_ib'))}) — {_fact_txt(dados.get('ib_nec'), dados.get('max_ib'))}
- PM necessário: **{_fmt_moeda(dados.get('pm_nec'))}** (ref. 2025: {_fmt_moeda(dados.get('pm_ref'))}, var. {_fmt_pct(dados.get('var_pm'))}) — {_fact_txt(dados.get('pm_nec'), dados.get('max_pm'))}
- Boletos necessários: **{_fmt_num(dados.get('bol_nec'),0)}** (ref. 2025: {_fmt_num(dados.get('bol_ref'),0)}, var. {_fmt_pct(dados.get('var_bol'))}) — {_fact_txt(dados.get('bol_nec'), dados.get('max_bol'))}

## TENDÊNCIA DOS ÚLTIMOS MESES (2026)
{insight_tendencia}

## BENCHMARK VS CLUSTER {cluster_nome.upper()}
{insight_bench}

---

Com base EXCLUSIVAMENTE nos dados acima, gere um plano focado em **{foco}**.

**REGRAS:**
- Diagnóstico: use as frases da conclusão da tendência com os números reais
- Cada ação: cita o valor-alvo e um número da tendência ou comparação com lojas {tipo_loja}
- Sazonalidade de {mes_nome}: mencione na ação mais relevante
- PROIBIDO: mediana, percentil, p50, top 25% — use "maioria das lojas {tipo_loja}", "lojas parecidas"

Use EXATAMENTE estes títulos markdown (sem adicionar outros):

### Diagnóstico
2 frases:
- Frase 1: tendência com números reais (ex: "Seu I/B caiu 3 meses seguidos, de 2,4 para 2,0 — o problema não é meta, é processo")
- Frase 2: comparação com lojas {tipo_loja} com número concreto

{secoes_prompt}

### O que monitorar
{n_kpis} KPIs diários — focados em {foco}. Formato: "indicador — frequência".

Máximo {max_words} palavras. Sem introdução. Sem conclusão. Cada ação começa com um verbo."""

    # ── Monta seções de ação conforme o foco ─────────────────────────────────
    metas_por_secao = {
        "Boleto Médio":     f"atingir {_fmt_moeda(dados.get('bm_nec'))} de BM. Use BT/BP e mix premium. Cite o indicador IAF impactado pelo nome.",
        "Itens por Boleto": f"chegar em {_fmt_num(dados.get('ib_nec'))} I/B. Use BT/BP e conversão da Ação de Fluxo (brinde → compra paga).",
        "Preço Médio":      f"atingir {_fmt_moeda(dados.get('pm_nec'))} de PM. Mix premium e sazonalidade de {mes_nome}.",
        "Boletos":          f"alcançar {_fmt_num(dados.get('bol_nec'), 0)} boletos. CRM, Loja Digital, conversão da Ação de Fluxo.",
    }
    n_acoes = 3 if len(secoes) == 1 else 2
    max_words = 160 if len(secoes) == 1 else 260
    n_kpis = 3

    secoes_linhas = [
        f"### Ação para {s}\n{n_acoes} ações práticas para {metas_por_secao[s]}"
        for s in secoes
    ]
    secoes_prompt_str = "\n\n".join(secoes_linhas)

    prompt_usuario = prompt_usuario.format(
        foco=foco,
        tipo_loja=tipo_loja,
        mes_nome=mes_nome,
        secoes_prompt=secoes_prompt_str,
        n_kpis=n_kpis,
        max_words=max_words,
    )

    client = _get_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": _system_prompt(dados)},
            {"role": "user",   "content": prompt_usuario},
        ],
        temperature=0.2,
        max_tokens=800,
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
