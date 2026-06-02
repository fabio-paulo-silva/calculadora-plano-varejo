import pandas as pd
from load_data import load_data_url


def tratar_metas(metas: pd.DataFrame) -> pd.DataFrame:
    metas = metas.copy()
    metas['META'] = metas['META'].str.replace(",", ".").astype(float)
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
    df['Ano'] = df['DATA'].dt.year
    df['Mês'] = df['DATA'].dt.month
    return df


def agrupar_mensal(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(['CANAL', 'BCPS', 'Ano', 'Mês'], as_index=False)
        .agg({'FATURAMENTO': 'sum', 'BOLETOS': 'sum', 'QTD ITENS': 'sum'})
    )


def calcular_indicadores(base: pd.DataFrame) -> pd.DataFrame:
    base = base.copy()
    base['BM'] = base['FATURAMENTO'] / base['BOLETOS']
    # BM = PM * I/B, portanto:
    base['I/B'] = base['QTD ITENS'] / base['BOLETOS']
    base['PM'] = base['FATURAMENTO'] / base['QTD ITENS']  # fix: era QTD/FAT no código original
    return base


def construir_analise(base: pd.DataFrame, metas: pd.DataFrame) -> pd.DataFrame:
    base_2025 = base[base['Ano'] == 2025].copy()
    base_2026 = base[base['Ano'] == 2026].copy()

    df = base_2026.merge(
        base_2025[['CANAL', 'BCPS', 'Mês', 'FATURAMENTO', 'BOLETOS', 'QTD ITENS', 'BM', 'I/B', 'PM']].rename(
            columns={
                'FATURAMENTO': 'FAT_2025',
                'BOLETOS': 'BOL_2025',
                'QTD ITENS': 'QTD_2025',
                'BM': 'BM_2025',
                'I/B': 'IB_2025',
                'PM': 'PM_2025',
            }
        ),
        on=['CANAL', 'BCPS', 'Mês'],
        how='left',
    )

    df = df.sort_values(['CANAL', 'BCPS', 'Mês']).reset_index(drop=True)

    # Cumsum acumulado dentro do grupo (fix: shift() no groupby para não vazar entre grupos)
    df['CUM_26'] = df.groupby(['CANAL', 'BCPS'])['BOLETOS'].cumsum()
    df['CUM_25'] = df.groupby(['CANAL', 'BCPS'])['BOL_2025'].cumsum()
    df['CUM_26_ANT'] = df.groupby(['CANAL', 'BCPS'])['CUM_26'].shift(1)
    df['CUM_25_ANT'] = df.groupby(['CANAL', 'BCPS'])['CUM_25'].shift(1)

    df['VAR_BOL_MES'] = (df['BOLETOS'] / df['BOL_2025']) - 1
    df['VAR_MES_ANT'] = df.groupby(['CANAL', 'BCPS'])['VAR_BOL_MES'].shift(1)
    df['VAR_ACUM_ANT'] = (df['CUM_26_ANT'] / df['CUM_25_ANT']) - 1

    # Projeção de boletos: prioridade acumulada > mês anterior > base 2025
    df['BOLETOS_PROJ'] = (df['BOL_2025'] * (1 + df['VAR_ACUM_ANT'])).round(0)
    df['BOLETOS_PROJ'] = df['BOLETOS_PROJ'].fillna(
        (df['BOL_2025'] * (1 + df['VAR_MES_ANT'])).round(0)
    )
    df['BOLETOS_PROJ'] = df['BOLETOS_PROJ'].fillna(df['BOL_2025'])

    # Merge com metas — suporta planilha com ou sem coluna ANO
    if 'ANO' in metas.columns:
        metas_ano = metas[metas['ANO'] == 2026][['META', 'Mês', 'BCPS']]
    else:
        metas_ano = metas[['META', 'Mês', 'BCPS']]

    df = df.merge(metas_ano, on=['Mês', 'BCPS'], how='left')

    # Indicadores necessários para bater a meta com os boletos projetados
    df['BM_NECESSARIO']      = df['META'] / df['BOLETOS_PROJ']
    df['IB_NECESSARIO']      = df['BM_NECESSARIO'] / df['PM']    # mantendo PM atual
    df['PM_NECESSARIO']      = df['BM_NECESSARIO'] / df['I/B']   # mantendo I/B atual
    df['BOLETOS_NECESSARIOS'] = df['META'] / df['BM']            # mantendo BM atual

    # Variações necessárias em %
    df['VAR_BM']  = (df['BM_NECESSARIO']       / df['BM'])            - 1
    df['VAR_IB']  = (df['IB_NECESSARIO']        / df['I/B'])           - 1
    df['VAR_PM']  = (df['PM_NECESSARIO']        / df['PM'])            - 1
    df['VAR_BOL'] = (df['BOLETOS_NECESSARIOS']  / df['BOLETOS_PROJ'])  - 1

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


def carregar_tudo():
    metas_raw, raw_data, dcentros = load_data_url()
    metas = tratar_metas(metas_raw)
    df_varejo = tratar_dados_varejo(raw_data)
    base = agrupar_mensal(df_varejo)
    base = calcular_indicadores(base)
    analise = construir_analise(base, metas)
    hist_max = historico_max_por_bcps(base)
    return analise, hist_max, metas, base
