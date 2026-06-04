# Calculadora de Indicadores Comerciais — O Boticário

## Visão Geral

Ferramenta de **planejamento comercial para gestores de lojas franqueadas O Boticário**, usada no início de cada mês. O objetivo é mostrar o que o gestor precisa fazer em termos de indicadores comerciais para atingir a meta de faturamento e estruturar um plano de ação.

**Deploy:** Streamlit Community Cloud  
**Repositório:** https://github.com/fabio-paulo-silva/calculadora-plano-varejo  
**Stack:** Python 3.13, Streamlit, Pandas, fpdf2, openpyxl

---

## Estrutura de Arquivos

```
app.py               # Interface Streamlit (UI completa)
transform_data.py    # Pipeline de dados (ETL + cálculos)
load_data.py         # Carrega planilhas do Google Sheets
plano_acao.py        # Geração de PDF + histórico Excel
requirements.txt     # streamlit, pandas, openpyxl, fpdf2
historico_planos.xlsx  # Histórico de planos salvos (local, não vai pro GitHub)
```

---

## Fontes de Dados (Google Sheets via URL CSV)

Definidas em `load_data.py`:

| Variável | Conteúdo |
|---|---|
| `url_dados_varejo` | Histórico de vendas diárias: CANAL, BCPS, DATA, FATURAMENTO, QTD ITENS, BOLETOS |
| `url_metas` | Meta de faturamento por BCPS + MÊS + ANO |
| `url_dcentros` | Hierarquia comercial: BCPS, LOJA, PRAÇA, GVO, GCVO, GRVO |

**Período dos dados:** Janeiro 2025 a Maio/Junho 2026

---

## Pipeline de Dados (`transform_data.py`)

Funções principais:

- `_parse_numero(s)` — converte strings monetárias de qualquer formato (`R$ 147.086,40`, `147,086.40`, etc.) para float
- `_detectar_col_mes(df)` — detecta coluna de mês independente de encoding (MÊS/Mês/MES)
- `tratar_metas(df)` — normaliza META (R$ → float), renomeia coluna mês → `MES`, BCPS → numeric
- `tratar_dados_varejo(df)` — converte FATURAMENTO, DATA → datetime, cria `ANO` e `MES`
- `agrupar_mensal(df)` — groupby CANAL/BCPS/ANO/MES → soma FATURAMENTO, BOLETOS, QTD ITENS
- `calcular_indicadores(df)` — calcula BM, I/B, PM por linha
- `construir_analise(base, metas)` — **função central**: parte das metas 2026 (scaffold), cruza com dados reais 2026 e referência 2025, projeta boletos, calcula indicadores necessários
- `historico_max_por_bcps(base)` — MAX_BM, MAX_IB, MAX_PM, MAX_BOLETOS por loja
- `preparar_dcentros(df)` — normaliza colunas com encoding especial (PRAÇA → PRACA, GCVO/GPVO → GCVO)
- `carregar_tudo()` — orquestra tudo, retorna `(analise, hist_max, metas, base, dcentros)`

### Lógica de Projeção de Boletos

```
VAR_ACUM = (boletos acumulados 2026 até mês anterior) / (boletos acumulados 2025 até mês anterior) - 1
BOLETOS_PROJ = BOL_2025 × (1 + VAR_ACUM)
Fallback 1: variação do mês anterior
Fallback 2: base 2025 direta
```

### Indicadores Calculados (todos em `analise`)

```
BM_NECESSARIO       = META / BOLETOS_PROJ
IB_NECESSARIO       = BM_NECESSARIO / PM_2025   (mantendo PM de referência)
PM_NECESSARIO       = BM_NECESSARIO / IB_2025   (mantendo I/B de referência)
BOLETOS_NECESSARIOS = META / BM_2025            (mantendo BM de referência)
VAR_BM/IB/PM/BOL    = variações % necessárias vs atual
```

### Colunas de referência 2025 no DataFrame `analise`

`FAT_2025`, `BOL_2025`, `QTD_2025`, `BM_2025`, `IB_2025`, `PM_2025`

### Colunas de hierarquia (do merge com dcentros)

`LOJA`, `PRACA`, `GVO`, `GCVO`, `GRVO`

### Nomes de colunas normalizados (ASCII, sem acento)

- Mês → `MES`
- Ano → `ANO`
- PRAÇA → `PRACA`
- GCVO/GPVO → `GCVO`

---

## Interface (`app.py`)

### Sidebar — Filtros cascata

Ordem: **GRVO → GCVO → GVO → Praça → Loja (BCPS)**  
Cada filtro restringe as opções do próximo. Dropdown de loja mostra `BCPS — NOME DA LOJA`.  
Card informativo mostra Praça/GVO/GCVO/GRVO da loja selecionada.

### Seções da página

1. **🎯 Planejamento da Meta** — Meta, Boletos Projetados, BM Necessário (3 métricas)
2. **📊 Caminhos para Atingir a Meta** — bloco info com BM necessário + 3 caminhos (I/B, PM, Boletos) com fórmula de cálculo visível, referência 2025, máximo histórico e badge de factibilidade
3. **💡 Sugestão** — lógica determinística com 6 casos baseados no histórico máximo da loja
4. **🔢 Simulador de Cenários** — 3 inputs livres (Boletos, I/B, PM), BM calculado automaticamente, resultado colorido vs meta, tabela comparativa
5. **📊 Evolução mensal** (expander)
6. **📋 Plano de Ação** — nome gestor, 4 campos de ação (I/B, PM, BM, Boletos), observações, botões Salvar + Gerar PDF
7. **📁 Histórico de planos** (expander)

### Defaults do simulador

- Boletos → `BOLETOS_PROJ`
- Itens por Boleto → `IB_2025` (mesmo mês 2025)
- Preço Médio → `PM_2025` (mesmo mês 2025)
- BM → calculado (I/B × PM)

### Funções de formatação

- `formatar_moeda(valor)` — para `st.metric` (sem markdown): `R$ 1.234`
- `fm(valor)` — para `st.info/warning/success/caption` (markdown): `R\$ 1.234` (escapa $ para não virar LaTeX)
- `formatar_numero(valor, decimais)` — para números sem moeda
- `formatar_pct(valor)` — `+12,5%`
- `_safe(val)` — converte para float ou None se NaN

### Regra crítica sobre R$

Streamlit renderiza `$texto$` como LaTeX em `st.info`, `st.warning`, `st.success`, `st.caption`, `st.markdown`.  
**Sempre usar `fm()` nesses contextos. Apenas `st.metric` pode usar `formatar_moeda()`.**

### Session state

```python
st.session_state["pdf_bytes"]  # bytes do PDF gerado
st.session_state["pdf_nome"]   # nome do arquivo
st.session_state["pdf_chave"]  # f"{bcps}_{mes}" — invalida PDF ao trocar loja/mês
```

---

## Geração de PDF (`plano_acao.py`)

### Problema de encoding

fpdf2 com fonte Helvetica não suporta Unicode. **Solução:** função `_ascii(texto)` usa `unicodedata.normalize("NFD")` para remover diacríticos antes de passar ao PDF.

### Estrutura do PDF

1. Cabeçalho (loja, mês, gestor, data)
2. **Cenário Planejado** (do simulador): tabela com Boletos, I/B, PM, BM, Faturamento vs 2025 e crescimento %
3. **Plano de Ação por Indicador**: para cada ação preenchida, mostra crescimento planejado vs 2025 + texto
4. **Sugestão** (texto limpo, sem markdown/emojis)
5. Observações + assinatura + rodapé

### Histórico (`historico_planos.xlsx`)

- 1 registro por gestor + BCPS + mês + ano
- Se existir, atualiza; se não, adiciona
- **Não persiste no Streamlit Cloud** (disco efêmero) — migração para Google Sheets está no backlog

---

## Lógica da Sugestão Inteligente (6 casos)

```python
# Compara indicadores necessários com MAX histórico da loja
bm_ok  = bm_nec  <= MAX_BM
ib_ok  = ib_nec  <= MAX_IB
pm_ok  = pm_nec  <= MAX_PM
bol_ok = bol_nec <= MAX_BOLETOS

Caso 1: bm_ok              → ✅ Meta factível
Caso 2: ib_ok and pm_ok    → sugere menor esforço relativo (menor VAR_IB ou VAR_PM)
Caso 3: só ib_ok           → foca I/B + alternativa boletos se bol_ok
Caso 4: só pm_ok           → foca PM + alternativa boletos se bol_ok
Caso 5: só bol_ok          → estratégia de volume (CRM, tráfego)
Caso 6: nenhum             → plano combinado com cálculo de combo mínimo
```

---

## Bugs Corrigidos / Decisões Técnicas

| Problema | Solução |
|---|---|
| `cumsum().shift()` vazava entre grupos | Dois passos: `groupby().cumsum()` depois `groupby().shift()` |
| Preço Médio calculado invertido | Corrigido para `FATURAMENTO / QTD_ITENS` |
| `FPDFUnicodeEncodingException` no PDF | Função `_ascii()` com `unicodedata.normalize` |
| `split_only=True` removido no fpdf2 2.8 | Substituído por abordagem sem cálculo de altura |
| R$ virava LaTeX no Streamlit | Função `fm()` usa `R\$` nos contextos markdown |
| PDF sumia ao clicar Baixar | `st.session_state` persiste bytes entre reruns |
| Coluna `Mês` com encoding diferente | `_detectar_col_mes()` + normalização para `MES` |
| META com formato `R$ 147.086,40` | `_parse_numero()` remove prefixo R$ e detecta formato |
| Junho sem dados não aparecia | `construir_analise` parte das metas (scaffold), não dos dados reais |
| `top-level code` executava no import | Tudo em funções, ponto de entrada em `carregar_tudo()` |

---

## Backlog (não implementado)

- Persistência do histórico em nuvem (Google Sheets ou Supabase)
- Autenticação por gestor/loja
- Envio do PDF por e-mail para gestor superior
- Gráfico de evolução dos indicadores
- Benchmarking entre lojas da rede
- Análise de tendência mais sofisticada para projeção de boletos
