# camara-pipeline

Pipeline de dados em três camadas (`raw`, `refined`, `marts`) com dados abertos da Câmara dos Deputados, feito como projeto final de um curso de engenharia de dados.

> Status: **etapa 1 de 7** — estrutura, download e inspeção do dado bruto. Os próximos passos estão listados no fim deste README.

## Fonte dos dados

- Portal: https://dadosabertos.camara.leg.br (seção de cotas: https://dadosabertos.camara.leg.br/cotas/)
- Despesas da cota parlamentar (CEAP), arquivo anual em massa:
  `https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip` (verificado em 2026-11-01)
- Formato: CSV com separador `;`, UTF-8 com BOM, valores decimais com ponto (`265.6`), datas em ISO (`2025-02-07T00:00:00`).

## Licença de uso

O portal de Dados Abertos da Câmara afirma, na página [Sobre os dados abertos](https://dadosabertos.camara.leg.br/howtouse/sobre-dados-abertos.html), que os dados são "livres de licenças": não estão sujeitos a regulações de direitos autorais, marcas, patentes ou segredo industrial, exceto dados que exigem sigilo e respeito à privacidade.

Não encontrei, até agora, o nome de uma licença específica (ex.: Creative Commons) nas páginas consultadas. **Pendente de confirmação** antes de publicar o repositório.

## Perguntas de negócio

1. Gasto médio por deputado, por partido e por UF, e como muda por ano.
2. Concentração do gasto nos 10 maiores fornecedores.
3. Categorias de despesa que mais crescem.
4. Relação entre gasto e participação em votações.
5. Despesas atípicas (valor muito acima da mediana da categoria, fim de semana, mesmo fornecedor repetido no mesmo dia).

## Camadas

| Camada | Pasta / schema | Conteúdo |
|---|---|---|
| `raw` | `data/raw/`, schema `raw` | Dado exatamente como veio da fonte. Nada alterado, tudo `VARCHAR`. |
| `refined` | `data/refined/`, schema `refined` | Dado limpo: valores numéricos, datas `DATE`, nomes normalizados, documento só com dígitos, CPF convertido em hash. |
| `marts` | `data/marts/`, schema `marts` | Tabelas de indicadores que respondem às perguntas de negócio. |

Os arquivos de dados (`data/*`) e o banco `.duckdb` ficam fora do git (ver `.gitignore`). Só código, SQL, testes e README são versionados.

## Dados pessoais

- **CPF de fornecedor** (`txtCNPJCPF` quando tem 11 dígitos): pessoa física. No refined, CNPJ fica em claro; CPF vira hash SHA-256 com salt vindo da variável de ambiente, nunca do repositório.
- **CPF do deputado** (coluna `cpf` do arquivo): não é necessário para nenhuma pergunta de negócio. Decisão prevista: não levar para o refined.

## Como rodar (etapa 1)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python -m src.download 2025     # baixa data/raw/Ano-2025.csv (use --forcar para baixar de novo)
```

## Inspeção do dado bruto (2025)

Arquivo: `Ano-2025.csv`, 209.081 linhas, 32 colunas.

| Aspecto | Observado |
|---|---|
| Separador | `;` |
| Encoding | UTF-8 com BOM (acentos corretos) |
| Decimal | ponto (`265.6`); nenhum valor com vírgula |
| Data `datEmissao` | ISO datetime; 8.675 linhas vazias |
| Documento do fornecedor | 207.233 CNPJ (14 dígitos) e 1.848 CPF (11 dígitos); nenhum vazio |
| UF | inclui `NA` (ex.: liderança do governo, sem UF) |
| Coluna `cpf` (deputado) | preenchida em 208.144 linhas |

## Decisões

- O download guarda o `.zip` e extrai o CSV sem alterar o conteúdo. A transformação começa só no refined.
- O download não baixa de novo se o CSV já existir (use `--forcar`).

## Próximas etapas

2. Carregar os CSVs no DuckDB (schema `raw`), tudo `VARCHAR`, re-executável.
3. Limpeza das despesas no refined, com testes pytest.
4. Deputados e votos; JOIN com despesas e taxa de linhas sem par.
5. Marts das perguntas 1 e 2.
6. Marts das perguntas 3, 4 e 5.
7. Runner único (`python -m src.run_pipeline`) e README final.
