import pandas as pd



def load_data_url():


    url_dados_varejo = 'https://docs.google.com/spreadsheets/d/1AcFjOoiGQbSJXOpuSxbjxbgVnpOJUeqW/export?format=csv'

    url_dcentros = 'https://docs.google.com/spreadsheets/d/16QETixI-5L6OI49ome84xTe2kqyfnsm0/export?format=csv&gid=469045108'

    url_metas  = 'https://docs.google.com/spreadsheets/d/1wMZvvU5Efr_GJMH9Yt3Z8gC02bUu--Nu/export?format=csv'

    metas = pd.read_csv(url_metas).dropna()
    raw_data = pd.read_csv(url_dados_varejo)
    
    dcentros = pd.read_csv(url_dcentros)

    return metas, raw_data, dcentros