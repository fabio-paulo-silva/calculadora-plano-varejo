"""
llm_sugestao.py
Integração com Groq (LLaMA 3.1 70B) para geração de sugestões e planos de ação
baseados no contexto IAF 2026 — Canal LOJA.
"""

import os
import pathlib

import streamlit as st

# ── Carrega o contexto IAF uma única vez ──────────────────────────────────────

_IAF_CONTEXT_PATH = pathlib.Path(__file__).parent / "iaf_context_loja.md"

@st.cache_data(show_spinner=False)
def _carregar_contexto_iaf() -> str:
    """Lê o arquivo iaf_context_loja.md e retorna como string."""
    try:
        return _IAF_CONTEXT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


# ── Helpers de formatação para o prompt ──────────────────────────────────────

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


# ── Montagem do prompt ────────────────────────────────────────────────────────

def montar_prompt(dados: dict) -> str:
    """
    Monta o prompt completo enviado ao LLM com os dados da loja e o pedido de ação.

    Parâmetros esperados em `dados`:
        loja_nome, bcps, mes_nome, regional (GRVO), praca
        meta, bol_proj, bm_nec, ib_nec, pm_nec, bol_nec
        bm_ref, ib_ref, pm_ref, bol_ref  (referência 2025)
        max_bm, max_ib, max_pm, max_bol  (máximo histórico)
        var_bm, var_ib, var_pm, var_bol  (variações necessárias)
        sugestao_deterministica           (texto do gerar_sugestao() atual)
        foco                             ("bm"|"ib"|"pm"|"boletos"|"combinado")
    """

    ctx = _carregar_contexto_iaf()

    # Decodifica o foco para texto natural
    foco_map = {
        "bm":       "Boleto Médio (BM)",
        "ib":       "Itens por Boleto (I/B)",
        "pm":       "Preço Médio (PM)",
        "boletos":  "Aumento de Boletos (fluxo de clientes)",
        "combinado": "combinação de todas as alavancas",
    }
    foco_texto = foco_map.get(dados.get("foco", "combinado"), "combinação de todas as alavancas")

    # Factibilidade de cada indicador
    def _fact(nec_key, max_key):
        nec = dados.get(nec_key)
        mx  = dados.get(max_key)
        try:
            if nec is not None and mx is not None:
                pct_acima = (float(nec) / float(mx) - 1) * 100
                if float(nec) <= float(mx):
                    return "✅ já foi atingido antes nesta loja"
                elif pct_acima <= 15:
                    return f"🟡 levemente acima do máximo histórico ({_fmt_pct(pct_acima/100)} acima)"
                else:
                    return f"🔴 acima do máximo histórico ({_fmt_pct(pct_acima/100)} acima)"
        except Exception:
            pass
        return "—"

    fact_bm  = _fact("bm_nec",  "max_bm")
    fact_ib  = _fact("ib_nec",  "max_ib")
    fact_pm  = _fact("pm_nec",  "max_pm")
    fact_bol = _fact("bol_nec", "max_bol")

    prompt = f"""Você é um consultor especialista em gestão de lojas franqueadas O Boticário.
Seu objetivo é gerar um plano de ação comercial OBJETIVO e ACIONÁVEL para o gestor da loja,
com foco no canal LOJA (PDV físico). Use a terminologia do Grupo Boticário (BT, BP, BM, I/B, PM, IAF).

---

## CONTEXTO IAF 2026 — CANAL LOJA

{ctx}

---

## DADOS DA LOJA

- **Loja:** {dados.get('loja_nome', '—')} (BCPS {dados.get('bcps', '—')})
- **Mês de análise:** {dados.get('mes_nome', '—')} 2026
- **Regional (GRVO):** {dados.get('regional', '—')}
- **Praça:** {dados.get('praca', '—')}

## SITUAÇÃO ATUAL vs META

| Indicador | Referência 2025 | Necessário p/ meta | Variação necessária | Factível? |
|---|---|---|---|---|
| Meta do mês | — | {_fmt_moeda(dados.get('meta'))} | — | — |
| Boletos projetados | {_fmt_num(dados.get('bol_ref'), 0)} | {_fmt_num(dados.get('bol_nec'), 0)} | {_fmt_pct(dados.get('var_bol'))} | {fact_bol} |
| Boleto Médio (BM) | {_fmt_moeda(dados.get('bm_ref'))} | {_fmt_moeda(dados.get('bm_nec'))} | {_fmt_pct(dados.get('var_bm'))} | {fact_bm} |
| Itens por Boleto (I/B) | {_fmt_num(dados.get('ib_ref'))} | {_fmt_num(dados.get('ib_nec'))} | {_fmt_pct(dados.get('var_ib'))} | {fact_ib} |
| Preço Médio (PM) | {_fmt_moeda(dados.get('pm_ref'))} | {_fmt_moeda(dados.get('pm_nec'))} | {_fmt_pct(dados.get('var_pm'))} | {fact_pm} |

**Máximos históricos desta loja:**
- BM máximo: {_fmt_moeda(dados.get('max_bm'))}
- I/B máximo: {_fmt_num(dados.get('max_ib'))}
- PM máximo: {_fmt_moeda(dados.get('max_pm'))}
- Boletos máximo: {_fmt_num(dados.get('max_bol'), 0)}

## DIAGNÓSTICO INICIAL (gerado automaticamente)

{dados.get('sugestao_deterministica', '—')}

---

## TAREFA

Gere um plano de ação detalhado com foco em **{foco_texto}**.

O plano deve conter EXATAMENTE as seguintes seções, separadas por título em markdown:

### Diagnóstico
Explique em 2-3 frases a situação da loja, o gap principal e o que precisa acontecer para atingir a meta.

### Ação para Boleto Médio (BM)
Liste 3 a 5 ações práticas e específicas para aumentar o BM nesta loja.
Mencione quais indicadores IAF são impactados (ex: IAF 6.7, 6.8, 6.9, 1.6).

### Ação para Itens por Boleto (I/B)
Liste 3 a 5 ações práticas e específicas para aumentar o I/B.
Inclua ações de venda sugestiva, BT, BP e Desafios Beautybox.

### Ação para Preço Médio (PM)
Liste 3 a 5 ações práticas e específicas para aumentar o PM.
Inclua foco em mix, disciplina de descontos e categorias estratégicas.

### Ação para Boletos (captação de clientes)
Liste 3 a 5 ações práticas para aumentar o fluxo de clientes e número de boletos.
Inclua CRM, Ação de Fluxo, Loja Digital, redes sociais.

### Indicadores de Acompanhamento
Liste 3 a 5 KPIs que o gestor deve monitorar diariamente, com frequência sugerida.

### Conexão IAF
Liste quais indicadores IAF 2026 serão impactados por este plano e a estimativa de pontos em jogo.

---

IMPORTANTE:
- Seja direto e objetivo. Sem introduções longas.
- Use linguagem de gestor de loja, não de consultor acadêmico.
- Cada ação deve ser executável pelo consultor no PDV, não apenas pelo gestor.
- NÃO mencione indicadores de VD, revendedoras ou Eudora.
- Máximo de 600 palavras no total.
"""
    return prompt


# ── Chamada à API Groq ────────────────────────────────────────────────────────

def gerar_sugestao_llm(dados: dict) -> str:
    """
    Chama a API Groq (LLaMA 3.3 70B) e retorna o texto do plano de ação gerado.
    A chave é lida de st.secrets["GROQ_API_KEY"] ou da variável de ambiente GROQ_API_KEY.

    Retorna o texto gerado ou lança exceção em caso de erro.
    """
    # Importação lazy — groq só é necessário quando chamado
    try:
        from groq import Groq  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Pacote 'groq' não instalado. Adicione 'groq' ao requirements.txt."
        ) from exc

    # Recupera a chave
    api_key = None
    try:
        api_key = st.secrets["GROQ_API_KEY"]
    except Exception:
        pass
    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "Chave GROQ_API_KEY não encontrada. "
            "Configure em .streamlit/secrets.toml ou como variável de ambiente."
        )

    client = Groq(api_key=api_key)
    prompt = montar_prompt(dados)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "Você é um consultor especialista em gestão comercial de franquias O Boticário. "
                    "Gera planos de ação objetivos, práticos e baseados em dados reais da loja. "
                    "Responde sempre em português brasileiro."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=1200,
    )

    return response.choices[0].message.content.strip()
