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
    mes_num = dados.get('mes_num') or dados.get('mes_selecionado', 0)
    sazonalidade = sazonalidade_map.get(int(mes_num), "")

    # ── Tendência: série + conclusão diagnóstica automática ───────────────────
    tendencia = dados.get('tendencia', [])
    insight_tendencia = "Sem histórico de meses anteriores disponível (primeira análise ou dados insuficientes)."
    conclusoes_tendencia = []   # frases prontas de diagnóstico para o LLM usar

    if len(tendencia) >= 2:
        linhas_serie = []
        tendencias_ind = {}  # ind → (vals, pct, n_meses_consecutivos, direcao)

        for ind, chave in [("BM", "BM"), ("I/B", "I/B"), ("PM", "PM"), ("Boletos", "BOLETOS")]:
            vals  = [m.get(chave) for m in tendencia if m.get(chave) is not None]
            meses = [NOMES_MESES.get(m.get('MES', 0), '')[:3] for m in tendencia if m.get(chave) is not None]
            if len(vals) < 2:
                continue

            fmt = _fmt_moeda if ind in ("BM", "PM") else (lambda v: _fmt_num(v, 0)) if ind == "Boletos" else _fmt_num
            serie = " → ".join(fmt(v) for v in vals)
            delta = vals[-1] - vals[0]
            pct   = delta / vals[0] if vals[0] else 0
            dir_  = "subindo" if delta > 0 else "caindo"

            # Conta meses consecutivos na mesma direção (do mais recente para o mais antigo)
            consecutivos = 1
            for i in range(len(vals) - 1, 0, -1):
                if (vals[i] > vals[i-1]) == (delta > 0):
                    consecutivos += 1
                else:
                    break

            tendencias_ind[ind] = {"vals": vals, "pct": pct, "dir": dir_, "consec": consecutivos, "meses": meses}
            linhas_serie.append(f"- **{ind}:** {serie} [{', '.join(meses)}] → {dir_} {_fmt_pct(pct)}")

        # Gera conclusões diagnósticas automáticas
        bm  = tendencias_ind.get("BM", {})
        ib  = tendencias_ind.get("I/B", {})
        pm  = tendencias_ind.get("PM", {})
        bol = tendencias_ind.get("Boletos", {})

        if ib.get("dir") == "caindo" and ib.get("consec", 0) >= 2:
            n = ib["consec"]
            conclusoes_tendencia.append(
                f"🔴 I/B caindo há {n} {'meses seguidos' if n > 1 else 'mês'} ({ib['meses'][0]} a {ib['meses'][-1]}) — "
                f"isso não é problema de meta, é problema de PROCESSO: a equipe não está executando venda sugestiva e BT/BP."
            )
        if bm.get("dir") == "subindo" and bol.get("dir") == "caindo":
            conclusoes_tendencia.append(
                f"⚠️ BM crescendo mas Boletos caindo — a equipe vende bem para quem entra, mas o FLUXO está diminuindo. "
                f"O foco deve ser trazer mais clientes (CRM, Loja Digital, conversão da Ação de Fluxo)."
            )
        if bm.get("dir") == "caindo" and pm.get("dir") == "caindo":
            conclusoes_tendencia.append(
                f"🔴 BM e PM caindo juntos — mix de produtos migrando para itens de menor valor. "
                f"Avaliar disciplina de desconto e direcionamento de categorias premium."
            )
        if bm.get("dir") == "subindo" and ib.get("dir") == "subindo" and bol.get("dir") == "subindo":
            conclusoes_tendencia.append(
                f"🟢 Loja em crescimento consistente nos 3 indicadores — manter ritmo e focar em não perder o que está funcionando."
            )
        if bol.get("dir") == "caindo" and ib.get("dir") == "caindo":
            conclusoes_tendencia.append(
                f"🔴 Boletos E I/B caindo ao mesmo tempo — queda dupla: menos clientes e menos produtividade por atendimento. "
                f"Ação urgente em fluxo (CRM, Ação de Fluxo) e em processo de venda (BT/BP)."
            )

        if not conclusoes_tendencia and linhas_serie:
            # Sem padrão claro, apenas mostra direção
            for ind, dados_ind in tendencias_ind.items():
                if abs(dados_ind["pct"]) > 0.05:  # só cita se variação > 5%
                    conclusoes_tendencia.append(
                        f"{ind} {dados_ind['dir']} {_fmt_pct(dados_ind['pct'])} nos últimos meses."
                    )

        serie_txt = "\n".join(linhas_serie) if linhas_serie else "Dados disponíveis mas sem variação significativa."
        conclusoes_txt = "\n".join(conclusoes_tendencia) if conclusoes_tendencia else "Sem padrão claro de tendência."
        insight_tendencia = f"**Série histórica:**\n{serie_txt}\n\n**Conclusão diagnóstica:**\n{conclusoes_txt}"

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

    # ── Contexto da equipe e desafio ──────────────────────────────────────────
    equipe   = dados.get('tamanho_equipe', '?')
    desafio  = dados.get('desafio_principal', 'Não informado')
    tipo_loja = dados.get('tipo_loja', 'Não informado')

    foco_map = {
        "combinado": "alavancas mais factíveis baseadas nos dados reais",
        "bm":        "Boleto Médio",
        "ib":        "Itens por Boleto",
        "pm":        "Preço Médio",
        "boletos":   "aumento de Boletos",
    }
    foco = foco_map.get(dados.get("foco", "combinado"), "alavancas mais factíveis")

    def _fact_txt(nec, mx):
        try:
            return "✅ já atingido antes" if float(nec) <= float(mx) else f"🔴 {(float(nec)/float(mx)-1)*100:.0f}% acima do histórico"
        except Exception:
            return ""

    prompt_usuario = f"""## CONTEXTO DESTA LOJA

**Loja:** {dados.get('loja_nome','—')} | **Cluster:** {tipo_loja} | **Mês:** {dados.get('mes_nome','')} 2026
**Equipe:** {equipe} consultores | **Principal desafio declarado:** {desafio}
**Sazonalidade de {dados.get('mes_nome','')}:** {sazonalidade}

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

**REGRAS OBRIGATÓRIAS:**
- O Diagnóstico DEVE reproduzir a conclusão diagnóstica da tendência acima — é a frase mais importante do plano
- Cada ação deve citar um número real (da série histórica ou da comparação com outras lojas)
- Usar a sazonalidade de {dados.get('mes_nome','')} para priorizar categoria
- PROIBIDO: mediana, percentil, benchmark, p50, top 25% — use "maioria das lojas", "lojas parecidas", "o esperado para este tipo de loja"

Use EXATAMENTE estes títulos markdown:

### Diagnóstico
2 frases diretas baseadas na conclusão diagnóstica acima:
- Frase 1: copie e adapte a conclusão diagnóstica da tendência (ex: se diz "I/B caindo há 3 meses", diga "Seu I/B caiu de X para Y nos últimos 3 meses — isso é problema de processo, não de meta")
- Frase 2: comparação com outras lojas em linguagem simples (ex: "Lojas {tipo_loja} parecidas vendem em média X a mais por boleto")

### Ação para Boleto Médio
2 ações para atingir {_fmt_moeda(dados.get('bm_nec'))} — calibradas para {equipe} consultores e cluster {tipo_loja}. Cite o indicador IAF impactado pelo nome.

### Ação para Itens por Boleto
2 ações para chegar em {_fmt_num(dados.get('ib_nec'))} I/B — use BT/BP e Conversão da Ação de Fluxo (converter resgate de brinde em compra paga).

### Ação para Preço Médio
2 ações para atingir {_fmt_moeda(dados.get('pm_nec'))} de PM — conecte à sazonalidade de {dados.get('mes_nome','')} e ao cluster {tipo_loja}.

### Ação para Boletos
2 ações para alcançar {_fmt_num(dados.get('bol_nec'),0)} boletos — considere o desafio "{desafio}" e CRM/Loja Digital.

### O que monitorar
3 KPIs diários com frequência definida, relevantes para {equipe} consultores.

Máximo 220 palavras. Sem introdução. Sem conclusão. Cada ação deve ter UM verbo de ação claro."""

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
