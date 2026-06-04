import pandas as pd


# ── URL da planilha de clusters (opcional) ────────────────────────────────────
# Crie uma aba no Google Sheets com colunas: BCPS | CLUSTER
# Valores de CLUSTER: Shopping | Rua | Outlet | Quiosque | Aeroporto
# Deixe vazio ("") para desabilitar — o sistema usará benchmark geral.
URL_CLUSTERS = ""


def load_data_url():
    url_dados_varejo = "https://docs.google.com/spreadsheets/d/1AcFjOoiGQbSJXOpuSxbjxbgVnpOJUeqW/export?format=csv"
    url_dcentros     = "https://docs.google.com/spreadsheets/d/16QETixI-5L6OI49ome84xTe2kqyfnsm0/export?format=csv&gid=469045108"
    url_metas        = "https://docs.google.com/spreadsheets/d/1wMZvvU5Efr_GJMH9Yt3Z8gC02bUu--Nu/export?format=csv"

    metas    = pd.read_csv(url_metas).dropna()
    raw_data = pd.read_csv(url_dados_varejo)
    dcentros = pd.read_csv(url_dcentros)

    # Clusters — carrega se URL configurada, senão retorna DataFrame vazio
    clusters = pd.DataFrame(columns=["BCPS", "CLUSTER"])
    if URL_CLUSTERS:
        try:
            clusters = pd.read_csv(URL_CLUSTERS)
            clusters["BCPS"] = pd.to_numeric(clusters["BCPS"], errors="coerce")
            clusters = clusters.dropna(subset=["BCPS"])
        except Exception:
            pass

    return metas, raw_data, dcentros, clusters