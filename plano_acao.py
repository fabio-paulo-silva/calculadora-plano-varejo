from pathlib import Path
from io import BytesIO

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
    "meta", "realizado", "boletos_proj",
    "bm_atual", "ib_atual", "pm_atual",
    "bm_necessario", "ib_necessario", "pm_necessario", "boletos_necessarios",
    "sugestao", "acao_bm", "acao_ib", "acao_pm", "acao_boletos", "observacoes",
]


# ── Histórico ─────────────────────────────────────────────────────────────────

def salvar_historico(registro: dict) -> None:
    novo = pd.DataFrame([{col: registro.get(col) for col in COLUNAS_HISTORICO}])

    if HISTORICO_PATH.exists():
        df = pd.read_excel(HISTORICO_PATH)
        # Garante que todas as colunas existam (migração suave)
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


def carregar_historico(gestor: str | None = None) -> pd.DataFrame:
    if not HISTORICO_PATH.exists():
        return pd.DataFrame(columns=COLUNAS_HISTORICO)
    df = pd.read_excel(HISTORICO_PATH)
    if gestor:
        df = df[df["gestor"].str.strip().str.lower() == gestor.strip().lower()]
    return df.sort_values("data_registro", ascending=False).reset_index(drop=True)


# ── PDF ───────────────────────────────────────────────────────────────────────

def _moeda(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "-"
    return f"R$ {float(valor):,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _num(valor, dec=1) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "-"
    return f"{float(valor):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _factivel(necessario, maximo) -> str:
    if necessario is None or maximo is None:
        return "-"
    if pd.isna(necessario) or pd.isna(maximo):
        return "-"
    return "Sim" if float(necessario) <= float(maximo) else "Nao"


def _linha_tabela(pdf: FPDF, cols: list, larguras: list, altura=7, borda=1):
    for texto, larg in zip(cols, larguras):
        pdf.cell(larg, altura, str(texto), border=borda)
    pdf.ln()


def gerar_pdf(dados: dict) -> bytes:
    pdf = FPDF()
    pdf.set_margins(left=15, top=15, right=15)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ── Cabeçalho ──────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 10, "PLANO DE ACAO COMERCIAL", ln=True, align="C")

    pdf.set_font("Helvetica", "", 10)
    mes_nome = NOMES_MESES.get(dados.get("mes"), str(dados.get("mes", "")))
    pdf.cell(0, 6, f"Loja: {dados.get('bcps')}  |  Mes: {mes_nome} {dados.get('ano', 2026)}  |  Data: {dados.get('data', '')}", ln=True, align="C")
    pdf.cell(0, 6, f"Gestor: {dados.get('gestor', '')}", ln=True, align="C")
    pdf.ln(4)

    # ── Linha separadora ───────────────────────────────────────────────────────
    pdf.set_draw_color(180, 180, 180)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(4)

    # ── Situação da Meta ───────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Situacao da Meta", ln=True)
    pdf.set_font("Helvetica", "", 10)

    larguras_meta = [60, 60, 60]
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(60, 7, "Meta", border=1, fill=True, align="C")
    pdf.cell(60, 7, "Realizado", border=1, fill=True, align="C")
    pdf.cell(60, 7, "BM Necessario", border=1, fill=True, align="C")
    pdf.ln()
    pdf.cell(60, 7, _moeda(dados.get("meta")), border=1, align="C")
    pdf.cell(60, 7, _moeda(dados.get("realizado")), border=1, align="C")
    pdf.cell(60, 7, _moeda(dados.get("bm_necessario")), border=1, align="C")
    pdf.ln(10)

    # ── Indicadores ────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Indicadores Necessarios para a Meta", ln=True)

    larg = [42, 32, 32, 42, 32]
    cabecalhos = ["Indicador", "Atual", "Necessario", "Max. Historico", "Factivel?"]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(220, 230, 240)
    for texto, l in zip(cabecalhos, larg):
        pdf.cell(l, 7, texto, border=1, fill=True, align="C")
    pdf.ln()

    hist = dados.get("historico_max", {})
    indicadores = [
        ("Boleto Medio (BM)",
         _moeda(dados.get("bm_atual")),
         _moeda(dados.get("bm_necessario")),
         _moeda(hist.get("MAX_BM")),
         _factivel(dados.get("bm_necessario"), hist.get("MAX_BM"))),
        ("Itens por Boleto (I/B)",
         _num(dados.get("ib_atual")),
         _num(dados.get("ib_necessario")),
         _num(hist.get("MAX_IB")),
         _factivel(dados.get("ib_necessario"), hist.get("MAX_IB"))),
        ("Preco Medio (PM)",
         _moeda(dados.get("pm_atual")),
         _moeda(dados.get("pm_necessario")),
         _moeda(hist.get("MAX_PM")),
         _factivel(dados.get("pm_necessario"), hist.get("MAX_PM"))),
    ]

    pdf.set_font("Helvetica", "", 9)
    for linha in indicadores:
        for texto, l in zip(linha, larg):
            pdf.cell(l, 7, texto, border=1, align="C")
        pdf.ln()
    pdf.ln(6)

    # ── Sugestão ───────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Sugestao Inteligente", ln=True)
    pdf.set_font("Helvetica", "", 10)
    sugestao = dados.get("sugestao", "").replace("**", "")
    pdf.multi_cell(0, 6, sugestao)
    pdf.ln(4)

    # ── Plano de Ação ──────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Plano de Acao", ln=True)

    acoes = [
        ("Boleto Medio (BM)",       dados.get("acao_bm", "")),
        ("Itens por Boleto (I/B)",  dados.get("acao_ib", "")),
        ("Preco Medio (PM)",        dados.get("acao_pm", "")),
        ("Captacao de Boletos",     dados.get("acao_boletos", "")),
    ]
    acoes_preenchidas = [(ind, acao) for ind, acao in acoes if acao and str(acao).strip()]

    if acoes_preenchidas:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(220, 230, 240)
        pdf.cell(55, 7, "Indicador", border=1, fill=True)
        pdf.cell(125, 7, "Acao Planejada", border=1, fill=True, ln=True)

        pdf.set_font("Helvetica", "", 9)
        for indicador, acao in acoes_preenchidas:
            # Salva posição para multi-cell da ação
            x_ind = pdf.get_x()
            y_antes = pdf.get_y()
            pdf.cell(55, 7, indicador, border=1)
            x_acao = pdf.get_x()

            # Calcula altura necessária para o texto da ação
            linhas = pdf.multi_cell(125, 7, str(acao), border=1, split_only=True)
            altura_linha = max(7, len(linhas) * 7)

            # Redesenha: primeiro a célula do indicador com altura correta
            pdf.set_xy(x_ind, y_antes)
            pdf.cell(55, altura_linha, indicador, border=1)
            pdf.set_xy(x_acao, y_antes)
            pdf.multi_cell(125, 7, str(acao), border=1)
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 7, "Nenhuma acao registrada.", ln=True)

    pdf.ln(4)

    # ── Observações ────────────────────────────────────────────────────────────
    obs = dados.get("observacoes", "")
    if obs and str(obs).strip():
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Observacoes", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, str(obs))
        pdf.ln(4)

    # ── Assinatura ─────────────────────────────────────────────────────────────
    pdf.ln(8)
    pdf.set_draw_color(100, 100, 100)
    pdf.line(15, pdf.get_y(), 90, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Assinatura: {dados.get('gestor', '')}", ln=True)

    # ── Rodapé ─────────────────────────────────────────────────────────────────
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, f"Gerado em {dados.get('data', '')} | Calculadora de Indicadores Comerciais", align="C")

    return bytes(pdf.output())
