import unicodedata
from pathlib import Path

import pandas as pd
from fpdf import FPDF

HISTORICO_PATH = Path(__file__).parent / "historico_planos.xlsx"

NOMES_MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Marco", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

COLUNAS_HISTORICO = [
    "data_registro", "gestor", "bcps", "mes", "ano",
    "meta", "boletos_proj",
    "bm_ref", "ib_ref", "pm_ref", "bol_ref",
    "bm_necessario", "ib_necessario", "pm_necessario", "boletos_necessarios",
    "sim_bol", "sim_ib", "sim_pm", "sim_bm", "sim_fat",
    "sugestao", "acao_ib", "acao_pm", "acao_bm", "acao_boletos", "observacoes",
]


# ── Helpers de texto ──────────────────────────────────────────────────────────

def _ascii(texto) -> str:
    """Remove acentos/diacríticos para compatibilidade com fonte Helvetica no PDF."""
    if texto is None:
        return ""
    s = str(texto)
    nfd = unicodedata.normalize("NFD", s)
    sem_acento = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    # Remove emojis e caracteres fora do Latin-1
    return sem_acento.encode("latin-1", errors="replace").decode("latin-1")


def _moeda(valor) -> str:
    if valor is None:
        return "-"
    try:
        v = float(valor)
        if pd.isna(v):
            return "-"
        return f"R$ {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def _num(valor, dec=1) -> str:
    if valor is None:
        return "-"
    try:
        v = float(valor)
        if pd.isna(v):
            return "-"
        return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def _pct(valor) -> str:
    if valor is None:
        return "-"
    try:
        v = float(valor)
        if pd.isna(v):
            return "-"
        sinal = "+" if v >= 0 else ""
        return f"{sinal}{v * 100:.1f}%"
    except Exception:
        return "-"


# ── Histórico ─────────────────────────────────────────────────────────────────

def salvar_historico(registro: dict) -> None:
    novo = pd.DataFrame([{col: registro.get(col) for col in COLUNAS_HISTORICO}])

    if HISTORICO_PATH.exists():
        df = pd.read_excel(HISTORICO_PATH)
        for col in COLUNAS_HISTORICO:
            if col not in df.columns:
                df[col] = None

        mask = (
            (df["bcps"].astype(str) == str(registro["bcps"])) &
            (df["mes"] == registro["mes"]) &
            (df["ano"] == registro["ano"]) &
            (df["gestor"].str.strip().str.lower() == str(registro["gestor"]).strip().lower())
        )

        if mask.any():
            df.loc[mask, COLUNAS_HISTORICO] = novo[COLUNAS_HISTORICO].values
        else:
            df = pd.concat([df, novo], ignore_index=True)
    else:
        df = novo

    df.to_excel(HISTORICO_PATH, index=False)


def carregar_historico(gestor=None) -> pd.DataFrame:
    if not HISTORICO_PATH.exists():
        return pd.DataFrame(columns=COLUNAS_HISTORICO)
    df = pd.read_excel(HISTORICO_PATH)
    if gestor:
        df = df[df["gestor"].str.strip().str.lower() == gestor.strip().lower()]
    return df.sort_values("data_registro", ascending=False).reset_index(drop=True)


# ── PDF ───────────────────────────────────────────────────────────────────────

def _cabecalho_tabela(pdf: FPDF, colunas: list, larguras: list):
    pdf.set_fill_color(220, 230, 245)
    pdf.set_font("Helvetica", "B", 9)
    for texto, larg in zip(colunas, larguras):
        pdf.cell(larg, 7, _ascii(texto), border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)


def _linha_tabela(pdf: FPDF, valores: list, larguras: list, altura=7):
    for texto, larg in zip(valores, larguras):
        pdf.cell(larg, altura, _ascii(str(texto)), border=1, align="C")
    pdf.ln()


def _secao(pdf: FPDF, titulo: str):
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(50, 90, 160)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, f"  {_ascii(titulo)}", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(2)


def gerar_pdf(dados: dict) -> bytes:
    pdf = FPDF()
    pdf.set_margins(left=12, top=12, right=12)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    meta     = dados.get("meta")
    bol_ref  = dados.get("bol_ref")
    bm_ref   = dados.get("bm_ref")
    ib_ref   = dados.get("ib_ref")
    pm_ref   = dados.get("pm_ref")
    fat_ref  = (bol_ref * bm_ref) if (bol_ref and bm_ref) else None

    sim_bol  = dados.get("sim_bol")
    sim_ib   = dados.get("sim_ib")
    sim_pm   = dados.get("sim_pm")
    sim_bm   = dados.get("sim_bm")
    sim_fat  = dados.get("sim_fat")

    mes_nome = NOMES_MESES.get(dados.get("mes"), str(dados.get("mes", "")))

    # ── Cabeçalho ──────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "PLANO DE ACAO COMERCIAL", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Loja: {dados.get('bcps')}  |  Mes: {mes_nome} {dados.get('ano', 2026)}  |  Data: {dados.get('data', '')}", ln=True, align="C")
    pdf.cell(0, 6, f"Gestor: {_ascii(dados.get('gestor', ''))}", ln=True, align="C")
    pdf.ln(3)
    pdf.set_draw_color(50, 90, 160)
    pdf.set_line_width(0.8)
    pdf.line(12, pdf.get_y(), 198, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.set_draw_color(0, 0, 0)
    pdf.ln(4)

    # ── 1. Cenário Planejado (Simulador) ───────────────────────────────────────
    _secao(pdf, "1. Cenario Planejado para o Mes")

    larg_cen = [52, 38, 38, 38, 20]
    _cabecalho_tabela(pdf, ["Indicador", "Planejado", "Ref. 2025", "Meta/Nec.", "Cresc."], larg_cen)

    def _cresc(novo, ref):
        if novo is None or ref is None or ref == 0:
            return "-"
        try:
            return _pct((float(novo) / float(ref)) - 1)
        except Exception:
            return "-"

    linhas_cenario = [
        ("Boletos",          _num(sim_bol, 0),  _num(bol_ref, 0),        _num(dados.get("boletos_proj"), 0), _cresc(sim_bol, bol_ref)),
        ("Itens por Boleto", _num(sim_ib),       _num(ib_ref),            _num(dados.get("ib_necessario")),   _cresc(sim_ib, ib_ref)),
        ("Preco Medio",      _moeda(sim_pm),     _moeda(pm_ref),          _moeda(dados.get("pm_necessario")), _cresc(sim_pm, pm_ref)),
        ("Boleto Medio",     _moeda(sim_bm),     _moeda(bm_ref),          _moeda(dados.get("bm_necessario")), _cresc(sim_bm, bm_ref)),
        ("Faturamento",      _moeda(sim_fat),    _moeda(fat_ref),         _moeda(meta),                       _cresc(sim_fat, fat_ref)),
    ]
    for linha in linhas_cenario:
        _linha_tabela(pdf, linha, larg_cen)

    # Resultado vs Meta
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    pct_meta = (float(sim_fat) / float(meta) * 100) if (sim_fat and meta) else None
    gap = (float(sim_fat) - float(meta)) if (sim_fat and meta) else None
    resultado_txt = ""
    if pct_meta is not None:
        sinal = "sobra" if gap >= 0 else "faltam"
        resultado_txt = f"Faturamento planejado: {_moeda(sim_fat)} = {pct_meta:.1f}% da meta | {sinal} {_moeda(abs(gap))}"
    if resultado_txt:
        pdf.cell(0, 7, _ascii(resultado_txt), ln=True)
    pdf.ln(4)

    # ── 2. Plano de Ação por Indicador ─────────────────────────────────────────
    _secao(pdf, "2. Plano de Acao por Indicador")

    acoes = [
        ("Itens por Boleto", sim_ib,  ib_ref,  dados.get("acao_ib",      "")),
        ("Preco Medio",      sim_pm,  pm_ref,  dados.get("acao_pm",      "")),
        ("Boleto Medio",     sim_bm,  bm_ref,  dados.get("acao_bm",      "")),
        ("Captacao Boletos", sim_bol, bol_ref, dados.get("acao_boletos", "")),
    ]
    acoes_preenchidas = [(ind, novo, ref, acao) for ind, novo, ref, acao in acoes
                         if acao and str(acao).strip()]

    if acoes_preenchidas:
        for indicador, novo, ref, acao in acoes_preenchidas:
            cresc = _cresc(novo, ref)
            # Linha do indicador com crescimento
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(235, 242, 255)
            pdf.cell(0, 7, f"  {_ascii(indicador)}  |  Crescimento planejado: {cresc} vs 2025", border=1, fill=True, ln=True)
            # Texto da ação
            pdf.set_font("Helvetica", "", 9)
            pdf.set_x(12)
            pdf.multi_cell(0, 6, _ascii(str(acao)), border="LRB")
            pdf.ln(2)
    else:
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 7, "Nenhuma acao registrada.", ln=True)

    pdf.ln(3)

    # ── 3. Sugestão Inteligente ────────────────────────────────────────────────
    _secao(pdf, "3. Sugestao Inteligente")
    pdf.set_font("Helvetica", "", 9)
    sugestao = dados.get("sugestao", "")
    # Remove marcadores markdown e emojis
    import re
    sugestao_limpa = re.sub(r"\*\*|#{1,4} ?", "", str(sugestao))
    sugestao_limpa = re.sub(r"[^\x00-\x7F\xC0-\xFF]+", " ", sugestao_limpa)  # remove emojis
    pdf.multi_cell(0, 6, _ascii(sugestao_limpa))
    pdf.ln(3)

    # ── 4. Observações ─────────────────────────────────────────────────────────
    obs = dados.get("observacoes", "")
    if obs and str(obs).strip():
        _secao(pdf, "4. Observacoes")
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 6, _ascii(str(obs)))
        pdf.ln(3)

    # ── Assinatura ─────────────────────────────────────────────────────────────
    pdf.ln(6)
    pdf.set_draw_color(100, 100, 100)
    pdf.line(12, pdf.get_y(), 100, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Assinatura: {_ascii(dados.get('gestor', ''))}", ln=True)

    # ── Rodapé ─────────────────────────────────────────────────────────────────
    pdf.set_y(-18)
    pdf.set_draw_color(50, 90, 160)
    pdf.set_line_width(0.5)
    pdf.line(12, pdf.get_y(), 198, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(130, 130, 130)
    pdf.cell(0, 4, f"Gerado em {dados.get('data', '')} | Calculadora de Indicadores Comerciais | Loja {dados.get('bcps')}", align="C")

    return bytes(pdf.output())
