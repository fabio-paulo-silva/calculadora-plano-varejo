import re

import pandas as pd

from load_data import load_data_url


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_numero(s) -> float:
    """Converte strings numéricas de vários formatos para float.
    Suporta: 'R$ 147.086,40' | '147,086.40' | '147.086.40' | '147086,40'
    """
    if s is None:
        return float('nan')
    s = re.sub(r'[R$\s]', '', str(s)).strip()
    if not s:
        return float('nan')
    n_dots   = s.count('.')
    n_commas = s.count(',')
    if n_commas == 1 and n_dots >= 1:          # BR: 147.086,40
        s = s.replace('.', '').replace(',', '.')
    elif n_commas >= 1 and n_dots == 1:        # US: 147,086.40
        s = s.replace(',', '')
    elif n_dots > 1:                           # 147.086.40 → último ponto = decimal
        partes = s.rsplit('.', 1)
        s = partes[0].replace('.', '') + '.' + partes[1]
    elif n_commas == 1 and n_dots == 0:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return float('nan')


def _detectar_col_mes(df: pd.DataFrame) -> str:
    """Encontra o nome real da coluna de mês (MÊS/Mês/MES etc.) no DataFrame."""
    for c in df.columns:
        cu = c.upper()
        # Normaliza para ASCII para comparar
        cu_ascii = cu.encode('ascii', errors='replace').decode('ascii').replace('?', '')
        if cu_ascii in ('MS', 'MES', 'M S',"Mês") or cu_ascii.startswith('M') and cu_ascii.endswith('S') and len(c) <= 4:
            return c
    # Fallback: coluna com valores inteiros 1-12
    for c in df.columns:
        try:
            vals = pd.to_numeric(df[c], errors='coerce').dropna()
            if len(vals) > 0 and vals.between(1, 12).all() and vals.nunique() <= 12:
                return c
        except Exception:
            pass
    return None


# ── Tratamento ────────────────────────────────────────────────────────────────

def tratar_metas(metas: pd.DataFrame) -> pd.DataFrame:
    metas = metas.copy()
    metas['META'] = metas['META'].apply(_parse_numero)

    # Normaliza coluna de mês → 'MES'
    col_mes = _detectar_col_mes(metas)
    if col_mes and col_mes != 'MES':
        metas = metas.rename(columns={col_mes: 'MES'})

    # Normaliza ANO → 'ANO' (já está assim, mas garante)
    if 'ANO' not in metas.columns:
        col_ano = next((c for c in metas.columns if 'ANO' in c.upper()), None)
        if col_ano:
            metas = metas.rename(columns={col_ano: 'ANO'})

    metas['BCPS'] = (
        metas['BCPS'].astype(str)
        .str.replace("-", "", regex=False)
        .str.strip()
    )
    metas['BCPS'] = pd.to_numeric(metas['BCPS'], errors='coerce')
    return metas


def tratar_dados_varejo(raw_data: pd.DataFrame) -> pd.DataFrame:
    df = raw_data.drop(columns=['fonte', 'id_dcentros'], errors='ignore').copy()
    df['FATURAMENTO'] = (
        df['FATURAMENTO'].astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )
    df['DATA'] = pd.to_datetime(df['DATA'])
    df['ANO'] = df['DATA'].dt.year   # ASCII: sem acento
    df['MES'] = df['DATA'].dt.month  # ASCII: sem acento
    return df


def agrupar_mensal(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(['CANAL', 'BCPS', 'ANO', 'MES'], as_index=False)
        .agg({'FATURAMENTO': 'sum', 'BOLETOS': 'sum', 'QTD ITENS': 'sum'})
    )


def calcular_indicadores(base: pd.DataFrame) -> pd.DataFrame:
    base = base.copy()
    base['BM']  = base['FATURAMENTO'] / base['BOLETOS']
    base['I/B'] = base['QTD ITENS']   / base['BOLETOS']
    base['PM']  = base['FATURAMENTO'] / base['QTD ITENS']
    return base


def construir_analise(base: pd.DataFrame, metas: pd.DataFrame) -> pd.DataFrame:
    base_2025 = base[base['ANO'] == 2025].copy()
    base_2026 = base[base['ANO'] == 2026].copy()

    # Metas 2026 — ponto de partida (inclui meses futuros sem dados ainda)
    if 'ANO' in metas.columns:
        metas_2026 = metas[metas['ANO'] == 2026][['META', 'MES', 'BCPS']].copy()
    else:
        metas_2026 = metas[['META', 'MES', 'BCPS']].copy()

    # Canais por BCPS (extraído do histórico 2025)
    canais_bcps = base_2025[['CANAL', 'BCPS']].drop_duplicates()

    # Scaffold: todos os BCPS×MES das metas × canais disponíveis
    scaffold = (
        metas_2026[['BCPS', 'MES']].drop_duplicates()
        .merge(canais_bcps, on='BCPS', how='left')
    )
    scaffold['ANO'] = 2026

    # Junta dados reais 2026 quando existirem (meses passados)
    df = scaffold.merge(
        base_2026[['CANAL', 'BCPS', 'MES', 'FATURAMENTO', 'BOLETOS', 'QTD ITENS']],
        on=['CANAL', 'BCPS', 'MES'],
        how='left',
    )

    # Calcula indicadores reais (NaN para meses sem dados)
    df['BM']  = df['FATURAMENTO'] / df['BOLETOS']
    df['I/B'] = df['QTD ITENS']   / df['BOLETOS']
    df['PM']  = df['FATURAMENTO'] / df['QTD ITENS']

    # Referência 2025
    df = df.merge(
        base_2025[['CANAL', 'BCPS', 'MES', 'FATURAMENTO', 'BOLETOS', 'QTD ITENS', 'BM', 'I/B', 'PM']].rename(
            columns={
                'FATURAMENTO': 'FAT_2025', 'BOLETOS': 'BOL_2025',
                'QTD ITENS': 'QTD_2025',  'BM': 'BM_2025',
                'I/B': 'IB_2025',          'PM': 'PM_2025',
            }
        ),
        on=['CANAL', 'BCPS', 'MES'],
        how='left',
    )

    df = df.sort_values(['CANAL', 'BCPS', 'MES']).reset_index(drop=True)

    df['CUM_26']     = df.groupby(['CANAL', 'BCPS'])['BOLETOS'].cumsum()
    df['CUM_25']     = df.groupby(['CANAL', 'BCPS'])['BOL_2025'].cumsum()
    df['CUM_26_ANT'] = df.groupby(['CANAL', 'BCPS'])['CUM_26'].shift(1)
    df['CUM_25_ANT'] = df.groupby(['CANAL', 'BCPS'])['CUM_25'].shift(1)

    df['VAR_BOL_MES'] = (df['BOLETOS'] / df['BOL_2025']) - 1
    df['VAR_MES_ANT'] = df.groupby(['CANAL', 'BCPS'])['VAR_BOL_MES'].shift(1)
    df['VAR_ACUM_ANT'] = (df['CUM_26_ANT'] / df['CUM_25_ANT']) - 1

    df['BOLETOS_PROJ'] = (df['BOL_2025'] * (1 + df['VAR_ACUM_ANT'])).round(0)
    df['BOLETOS_PROJ'] = df['BOLETOS_PROJ'].fillna(
        (df['BOL_2025'] * (1 + df['VAR_MES_ANT'])).round(0)
    )
    df['BOLETOS_PROJ'] = df['BOLETOS_PROJ'].fillna(df['BOL_2025'])

    # Junta META (já filtrada para 2026 no scaffold, agora adiciona o valor)
    df = df.merge(metas_2026, on=['MES', 'BCPS'], how='left')

    df['BM_NECESSARIO']       = df['META'] / df['BOLETOS_PROJ']
    df['IB_NECESSARIO']       = df['BM_NECESSARIO'] / df['PM']
    df['PM_NECESSARIO']       = df['BM_NECESSARIO'] / df['I/B']
    df['BOLETOS_NECESSARIOS'] = df['META'] / df['BM']

    df['VAR_BM']  = (df['BM_NECESSARIO']      / df['BM'])           - 1
    df['VAR_IB']  = (df['IB_NECESSARIO']       / df['I/B'])          - 1
    df['VAR_PM']  = (df['PM_NECESSARIO']       / df['PM'])           - 1
    df['VAR_BOL'] = (df['BOLETOS_NECESSARIOS'] / df['BOLETOS_PROJ']) - 1

    return df


def historico_max_por_bcps(base: pd.DataFrame) -> pd.DataFrame:
    return (
        base.groupby('BCPS')
        .agg(
            MAX_BM=('BM', 'max'),
            MAX_IB=('I/B', 'max'),
            MAX_PM=('PM', 'max'),
            MAX_BOLETOS=('BOLETOS', 'max'),
        )
        .reset_index()
    )


def preparar_dcentros(dcentros: pd.DataFrame) -> pd.DataFrame:
    col_praca   = next((c for c in dcentros.columns if 'PRA' in c.upper()), None)
    col_gcvo    = next((c for c in dcentros.columns if 'GCVO' in c.upper()), None)
    col_cluster = next((c for c in dcentros.columns if 'CLUSTER' in c.upper()), None)

    colunas_map = {'BCPS': 'BCPS', 'LOJA': 'LOJA', 'GVO': 'GVO', 'GRVO': 'GRVO'}
    if col_praca:
        colunas_map[col_praca] = 'PRACA'
    if col_gcvo:
        colunas_map[col_gcvo] = 'GCVO'
    if col_cluster:
        colunas_map[col_cluster] = 'CLUSTER'

    df = dcentros[[c for c in colunas_map if c in dcentros.columns]].copy()
    df = df.rename(columns=colunas_map)
    df['BCPS'] = pd.to_numeric(df['BCPS'], errors='coerce')
    if 'CLUSTER' not in df.columns:
        df['CLUSTER'] = None
    return df.dropna(subset=['BCPS']).drop_duplicates(subset=['BCPS'])


def tendencia_loja(analise: pd.DataFrame, bcps: int, mes_atual: int, n_meses: int = 3) -> list:
    """
    Retorna os últimos n_meses com dados reais 2026 anteriores ao mês atual.
    Cada item: dict com MES, BM, I/B, PM, BOLETOS, META, FATURAMENTO e refs 2025.
    """
    df = analise[
        (analise['BCPS'] == bcps) &
        (analise['MES'] < mes_atual) &
        (analise['FATURAMENTO'].notna())
    ].sort_values('MES').tail(n_meses)

    cols = ['MES', 'FATURAMENTO', 'BOLETOS', 'BM', 'I/B', 'PM',
            'META', 'BM_2025', 'IB_2025', 'PM_2025', 'BOL_2025']
    cols_ok = [c for c in cols if c in df.columns]
    return df[cols_ok].to_dict('records')


def benchmark_cluster(
    analise: pd.DataFrame,
    mes: int,
    dcentros: pd.DataFrame,
    bcps: int,
) -> dict:
    """
    Calcula benchmarks (mediana e P75) para o mês, usando a coluna CLUSTER do dcentros.

    - Se CLUSTER disponível, filtra pelo cluster do BCPS informado.
    - Fallback: usa todas as lojas do mesmo mês (benchmark geral).
    """
    cluster_nome = "Geral"
    df_bench = analise[analise['MES'] == mes].drop_duplicates(subset=['BCPS'])

    if 'CLUSTER' in dcentros.columns:
        loja_row = dcentros[dcentros['BCPS'] == bcps]
        if not loja_row.empty and pd.notna(loja_row.iloc[0].get('CLUSTER')):
            cluster_nome = str(loja_row.iloc[0]['CLUSTER']).strip()
            bcps_cluster = dcentros.loc[
                dcentros['CLUSTER'].astype(str).str.strip() == cluster_nome, 'BCPS'
            ].tolist()
            df_filtrado = df_bench[df_bench['BCPS'].isin(bcps_cluster)]
            if len(df_filtrado) >= 3:
                df_bench = df_filtrado

    cols_ref = ['BM_2025', 'IB_2025', 'PM_2025', 'BOL_2025']
    df_bench = df_bench[[c for c in cols_ref if c in df_bench.columns]].dropna()

    if df_bench.empty:
        return {"cluster_nome": cluster_nome, "n_lojas": 0}

    return {
        "cluster_nome": cluster_nome,
        "n_lojas":  len(df_bench),
        "p50_bm":   round(df_bench['BM_2025'].median(), 2),
        "p75_bm":   round(df_bench['BM_2025'].quantile(0.75), 2),
        "p50_ib":   round(df_bench['IB_2025'].median(), 2),
        "p75_ib":   round(df_bench['IB_2025'].quantile(0.75), 2),
        "p50_pm":   round(df_bench['PM_2025'].median(), 2),
        "p75_pm":   round(df_bench['PM_2025'].quantile(0.75), 2),
        "p50_bol":  round(df_bench['BOL_2025'].median(), 0),
        "p75_bol":  round(df_bench['BOL_2025'].quantile(0.75), 0),
    }


def carregar_tudo():
    metas_raw, raw_data, dcentros_raw = load_data_url()
    metas     = tratar_metas(metas_raw)
    df_varejo = tratar_dados_varejo(raw_data)
    base      = agrupar_mensal(df_varejo)
    base      = calcular_indicadores(base)
    analise   = construir_analise(base, metas)
    hist_max  = historico_max_por_bcps(base)
    dcentros  = preparar_dcentros(dcentros_raw)   # já inclui coluna CLUSTER

    cols_merge = [c for c in ['BCPS', 'LOJA', 'PRACA', 'GVO', 'GCVO', 'GRVO', 'CLUSTER']
                  if c in dcentros.columns]
    analise = analise.merge(dcentros[cols_merge], on='BCPS', how='left')

    return analise, hist_max, metas, base, dcentros
