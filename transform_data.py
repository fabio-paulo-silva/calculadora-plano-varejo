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
        if cu_ascii in ('MS', 'MES', 'M S') or cu_ascii.startswith('M') and cu_ascii.endswith('S') and len(c) <= 4:
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

    df = base_2026.merge(
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

    # Merge com metas (usa coluna MES normalizada)
    if 'ANO' in metas.columns:
        metas_ano = metas[metas['ANO'] == 2026][['META', 'MES', 'BCPS']]
    else:
        metas_ano = metas[['META', 'MES', 'BCPS']]

    df = df.merge(metas_ano, on=['MES', 'BCPS'], how='left')

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
    col_praca = next((c for c in dcentros.columns if 'PRA' in c.upper()), None)
    col_gcvo  = next((c for c in dcentros.columns if 'GCVO' in c.upper()), None)

    colunas_map = {'BCPS': 'BCPS', 'LOJA': 'LOJA', 'GVO': 'GVO', 'GRVO': 'GRVO'}
    if col_praca:
        colunas_map[col_praca] = 'PRACA'
    if col_gcvo:
        colunas_map[col_gcvo] = 'GCVO'

    df = dcentros[[c for c in colunas_map if c in dcentros.columns]].copy()
    df = df.rename(columns=colunas_map)
    df['BCPS'] = pd.to_numeric(df['BCPS'], errors='coerce')
    return df.dropna(subset=['BCPS']).drop_duplicates(subset=['BCPS'])


def carregar_tudo():
    metas_raw, raw_data, dcentros_raw = load_data_url()
    metas     = tratar_metas(metas_raw)
    df_varejo = tratar_dados_varejo(raw_data)
    base      = agrupar_mensal(df_varejo)
    base      = calcular_indicadores(base)
    analise   = construir_analise(base, metas)
    hist_max  = historico_max_por_bcps(base)
    dcentros  = preparar_dcentros(dcentros_raw)

    analise = analise.merge(
        dcentros[['BCPS', 'LOJA', 'PRACA', 'GVO', 'GCVO', 'GRVO']],
        on='BCPS', how='left'
    )
    return analise, hist_max, metas, base, dcentros
