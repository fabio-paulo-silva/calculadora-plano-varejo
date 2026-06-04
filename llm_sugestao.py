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


def _bloco_dados(dados: dict) -> str:
    """Monta o bloco compacto de dados da loja para o prompt."""
    return f"""**Loja:** {dados.get('loja_nome', '—')} | **Mês:** {dados.get('mes_nome', '—')} 2026 | **Regional:** {dados.get('regional', '—')} | **Praça:** {dados.get('praca', '—')}

| Indicador | 2025 | Necessário | Variação | Histórico |
|---|---|---|---|---|
| Meta | — | {_fmt_moeda(dados.get('meta'))} | — | — |
| Boletos | {_fmt_num(dados.get('bol_ref'), 0)} | {_fmt_num(dados.get('bol_nec'), 0)} | {_fmt_pct(dados.get('var_bol'))} | {_fact(dados.get('bol_nec'), dados.get('max_bol'))} |
| Boleto Médio | {_fmt_moeda(dados.get('bm_ref'))} | {_fmt_moeda(dados.get('bm_nec'))} | {_fmt_pct(dados.get('var_bm'))} | {_fact(dados.get('bm_nec'), dados.get('max_bm'))} |
| Itens/Boleto | {_fmt_num(dados.get('ib_ref'))} | {_fmt_num(dados.get('ib_nec'))} | {_fmt_pct(dados.get('var_ib'))} | {_fact(dados.get('ib_nec'), dados.get('max_ib'))} |
| Preço Médio | {_fmt_moeda(dados.get('pm_ref'))} | {_fmt_moeda(dados.get('pm_nec'))} | {_fmt_pct(dados.get('var_pm'))} | {_fact(dados.get('pm_nec'), dados.get('max_pm'))} |"""


def _system_prompt(dados: dict) -> str:
    """Monta o system prompt completo com contexto IAF + dados da loja."""
    ctx = _carregar_contexto_iaf()
    return f"""Você é um consultor estratégico especializado em varejo físico de perfumaria e cosméticos, com profundo conhecimento do programa IAF do Grupo Boticário.

## REGRAS INEGOCIÁVEIS
- Respostas CURTAS e DIRETAS — máximo 5 bullets por seção, sem enrolação
- Nunca use numeração de indicadores (diga "Resgate Fidelidade", nunca "indicador 1.6")
- Se o gestor disser que uma ação não é viável, aceite SEM questionar e sugira alternativa imediatamente
- Priorize sempre o contexto IAF, mas pode sugerir ações fora dele quando fizer sentido
- Foco exclusivo no canal LOJA (PDV físico) — jamais mencione VD, revendedoras ou Eudora
- Português brasileiro, tom de gestor experiente em varejo

## CONTEXTO IAF 2026 — CANAL LOJA
{ctx}

## DADOS REAIS DA LOJA
{_bloco_dados(dados)}"""


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
    """Gera o plano de ação inicial enxuto com base nos dados da loja."""
    foco_map = {
        "combinado": "combinação das alavancas mais factíveis",
        "bm":        "Boleto Médio",
        "ib":        "Itens por Boleto",
        "pm":        "Preço Médio",
        "boletos":   "aumento de Boletos (fluxo)",
    }
    foco = foco_map.get(dados.get("foco", "combinado"), "combinação das alavancas mais factíveis")

    prompt_usuario = f"""Com base nos dados desta loja, gere um plano de ação com foco em **{foco}**.

Estrutura obrigatória (use exatamente estes títulos em markdown):

### Diagnóstico
2 frases: qual o gap principal e o caminho mais realista.

### Ação para Boleto Médio
3 ações práticas e específicas para esta loja. Mencione os indicadores IAF impactados pelo nome.

### Ação para Itens por Boleto
3 ações práticas. Inclua BT, BP ou Desafios quando relevante.

### Ação para Preço Médio
3 ações práticas. Foco em mix, categorias e disciplina de desconto.

### Ação para Boletos
3 ações para aumentar fluxo e captação. Inclua CRM e Loja Digital.

### O que monitorar
3 KPIs com frequência (ex: "BM diário por consultora").

### Impacto IAF
Quais indicadores IAF (pelo nome) serão mais beneficiados e quantos pontos estão em jogo.

Seja OBJETIVO. Máximo 250 palavras no total."""

    client = _get_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": _system_prompt(dados)},
            {"role": "user",   "content": prompt_usuario},
        ],
        temperature=0.3,
        max_tokens=900,
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

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.4,
        max_tokens=500,
    )
    return response.choices[0].message.content.strip()
