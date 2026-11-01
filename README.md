# camara-pipeline

Pipeline de dados em três camadas (`raw`, `refined`, `marts`) com dados abertos da Câmara dos Deputados, feito como projeto final de um curso de engenharia de dados.

> Status: **etapas 1, 2 e 3 de 7 concluídas** (estrutura, download, carga do raw e limpeza das despesas). **Etapa 4 em andamento**: deputados, votos e ponte feitos; a definição de participação em votações aguarda aprovação. Os próximos passos estão listados no fim deste README.

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
- **CPF do deputado** (coluna `cpf` do arquivo): não é necessário para nenhuma pergunta de negócio. **Não vai para o refined.** Fica só no raw local, que está fora do git.
- **Nome de passageiro** (`txtPassageiro`): pessoa física. **Não vai para o refined.** Só o booleano `tem_passageiro` é mantido.
- **Nome de fornecedor pessoa física** (`txtFornecedor` quando o documento é CPF): é dado pessoal. No refined, o nome é trocado pelo rótulo fixo `PESSOA FISICA`. O identificador fica só o hash do CPF.

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python -m src.download 2023 2024   # baixa data/raw/Ano-{ano}.csv (use --forcar para baixar de novo)
python -m src.load_raw             # carrega data/raw/*.csv em data/camara.duckdb, schema raw

python -m src.download camara      # cadastro de deputados e votações/votos 2023-2025
python -m src.load_raw             # carrega também os arquivos de deputados e votos
```

Depois da carga do raw, a limpeza:

```powershell
$env:CAMARA_SALT = "<valor>"
python -m src.clean                # refined.despesas
python -m src.clean_camara         # refined.deputados, refined.votos, refined.ponte_deputado_ceap
python -m pytest
```

O ano de 2026 não é baixado: o arquivo ainda está incompleto. O `load_raw` é re-executável e recria as tabelas em vez de acumular linhas.

### Salt do hash de CPF

A limpeza (`src/clean.py`) exige a variável `CAMARA_SALT`. Sem ela, o comando falha com erro claro.

```powershell
# Gerar um valor longo e aleatório (uma vez; guarde-o fora do repositório):
python -c "import secrets; print(secrets.token_hex(32))"

# Definir na sessão antes de rodar a limpeza:
$env:CAMARA_SALT = "<valor gerado>"
```

- Nunca grave o salt em arquivo versionado nem o cole em issue, PR ou log.
- Trocar o salt muda todos os hashes de CPF. Para reproduzir os mesmos hashes, use sempre o mesmo valor.
- Os testes não leem o salt do ambiente: ele é definido por `monkeypatch`.

### Limpeza (refined)

```powershell
$env:CAMARA_SALT = "<valor>"
python -m src.clean      # recria refined.despesas a partir de raw.ceap_2023, _2024 e _2025
python -m pytest         # testes com dados inventados, sem abrir data/camara.duckdb
```

A regra fica em `sql/refined/despesas.sql`. O `src/clean.py` executa esse SQL e confere que nenhuma conversão perdeu valor: se um valor ou data não-vazio virou `NULL`, a carga falha.

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
- No raw, campo vazio fica como `''`, não vira `NULL`. O refined trata isso com `NULLIF(TRIM(col), '')`.
- A carga confere se a contagem da tabela bate com a do próprio CSV lido pelo DuckDB, e falha se houver `NULL` no raw.

## Limpeza (refined): decisões

Tabela `refined.despesas`: os três anos empilhados com `UNION ALL BY NAME`, uma coluna `ano_arquivo` indica a origem. 674.753 linhas (232.754 + 232.918 + 209.081), igual ao raw. Nenhuma conversão perdeu valor.

| Tema | Decisão |
|---|---|
| Vazio | `''` vira `NULL` com `NULLIF(TRIM(col), '')`. |
| Valores | Separador decimal é ponto (confirmado: nenhum valor com vírgula, no máximo 2 casas). Convertidos para `DECIMAL(18,2)`. |
| Datas | `datEmissao` e `datPagamentoRestituicao` viram `DATE`. Ano antes de 2015 ou data futura gera `data_*_suspeita = TRUE`, sem descartar. Há 1 data suspeita (2002). |
| Fornecedor | Nome em maiúsculas, sem acento, espaços colapsados. Documento só com dígitos. `tipo_documento_fornecedor` = `CNPJ` (14), `CPF` (11) ou `OUTRO`. |
| CPF de fornecedor | Hash SHA-256 de `CAMARA_SALT|cpf`. CNPJ fica em claro. |
| Nome de pessoa física | Se o fornecedor é CPF, `fornecedor_nome` = `PESSOA FISICA`. O nome original não vai para o refined. |
| Estorno | Valores negativos ficam. `eh_estorno = TRUE` se o documento ou o líquido for negativo: 29.899 linhas. |
| Líquido | `liquido_diverge = TRUE` quando `vlrLiquido ≠ vlrDocumento − vlrGlosa` (glosa vazia conta como zero): 3.370 linhas. Ver abaixo. |
| Id do documento | `ideDocumento = '0'` é sentinela (28.294 linhas) e vira `NULL`. O id não é chave única: há repetições legítimas, então não serve como chave. |
| Chave do deputado | `nu_deputado_id`. É consistente nos três anos: nenhum `nuDeputadoId` tem dois `ideCadastro`. `ide_cadastro` fica vazio nas lideranças. |
| Pessoais | `cpf` do deputado e `txtPassageiro` não entram. Fica `tem_passageiro`. |

Divergência de líquido (3.370 linhas), dois casos:
- **2.440 linhas** com glosa vazia e `vlrLiquido = −vlrDocumento`. Quase todas são "COMPLEMENTAÇÃO DO AUXÍLIO-MORADIA" de 2025. É convenção de sinal da fonte; `eh_estorno` já as marca.
- **930 linhas** com líquido menor que o documento e glosa zero ou preenchida (ex.: 238,24 → 195,34). A glosa não explica essa diferença. Ficam sinalizadas, não corrigidas.

## Deputados e votos (etapa 4)

Fontes (arquivos em massa do portal, HTTP 200 sem User-Agent especial; não foi preciso a API v2):

- `https://dadosabertos.camara.leg.br/arquivos/deputados/csv/deputados.csv`
- `https://dadosabertos.camara.leg.br/arquivos/votacoes/csv/votacoes-{2023,2024,2025}.csv`
- `https://dadosabertos.camara.leg.br/arquivos/votacoesVotos/csv/votacoesVotos-{2023,2024,2025}.csv`

Raw: `raw.deputados`, `raw.votacoes_{ano}`, `raw.votacoes_votos_{ano}`. Mesma regra do CEAP: tudo `VARCHAR`, vazio como `''`, contagem conferida com o próprio DuckDB.

| Tabela refined | Conteúdo | Decisão |
|---|---|---|
| `refined.deputados` | id da API, nome parlamentar, legislatura inicial e final, partido e UF atuais | Partido e UF vêm do voto mais recente em 2023–2025 (o cadastro em massa não traz). `NULL` para quem não votou no período. |
| `refined.votos` | id da votação, id do deputado, tipo de voto, data da votação | Só votações de 2023–2025. `tipo_voto` vazio vira `NULL`. |
| `refined.ponte_deputado_ceap` | id CEAP → id da API, com o método usado | Ver abaixo. |

Colunas do cadastro e o que foi mantido: `uri` (vira `id_deputado`), `nome`, `idLegislaturaInicial`, `idLegislaturaFinal` **mantidas**. `nomeCivil`, `cpf`, `dataNascimento`, `municipioNascimento`, `ufNascimento`, `dataFalecimento`, `siglaSexo`, `urlRedeSocial`, `urlWebsite` **não entram** no refined (dado pessoal ou sem uso nas perguntas).

**O id do CEAP não é o id da API.** `nuDeputadoId` (CEAP) e `id` da API são espaços de id diferentes, então não há JOIN direto. A ponte liga os dois:

1. **`votos`**: nome e UF iguais aos do arquivo de votos do mesmo ano. A UF desambigua homônimos (ex.: dois "Carlos Gomes").
2. **`cadastro_unico`**: nome igual a um único deputado do cadastro (sem UF). Usado quando não há voto no ano.
3. **Sem par**: lideranças partidárias (UF `NA`) e casos em que o nome difere entre as fontes.

Nomes são comparados em maiúsculas e sem acento. Nenhum nome do cadastro aparece com dois ids nos votos.

### Checagens antes dos marts

**(a) Linhas sem par no JOIN despesas × deputados, por ano:**

| Ano | Linhas | Por votos | Por cadastro único | Sem par (deputado) | Sem par (liderança) |
|---|---|---|---|---|---|
| 2023 | 232.754 | 226.941 | 4.703 | 255 (0,11%) | 855 (0,37%) |
| 2024 | 232.918 | 231.641 | 208 | 166 (0,07%) | 903 (0,39%) |
| 2025 | 209.081 | 207.895 | 97 | 152 (0,07%) | 937 (0,45%) |

Ids de deputado sem par: o caso principal é o id CEAP 3640, "Yury do Paredão" (CE), com 103 linhas em 2023, 166 em 2024 e 152 em 2025. No cadastro e nos votos ele é "Yury Bruno" (id 220660, CE). A ponte por nome não resolve. Em 2023 também ficam sem par ex-deputados sem voto no ano e com nome homônimo no cadastro: Paulo Ramos, Hélio Costa, Mariana Carvalho, João Roma, Ricardo Izar, Luiz Carlos e Bilac Pinto. Esses casos precisam de mapeamento manual ou de outra fonte.

**(b) Linhas de despesa idênticas em todas as colunas:** 0 por ano e entre anos. As repetições de `ideDocumento` são linhas diferentes (outra parcela, subcota ou valor).

### Limitações conhecidas

- `partido_atual` é o partido do voto mais recente em 2023–2025, não o status oficial. 213 dos 833 deputados com despesa ficam sem partido, porque não tiveram voto nominal no período (ex.: ministros).
- Votações simbólicas não têm voto por deputado. Só as nominais aparecem em `refined.votos`.
- A ponte depende de nome. Nomes que mudam entre as fontes (caso Yury) ficam sem par até haver mapeamento explícito.

## Próximas etapas

1. ✅ Estrutura, download e inspeção do dado bruto.
2. ✅ Carregar os CSVs no DuckDB (schema `raw`), tudo `VARCHAR`, re-executável.
3. ✅ Limpeza das despesas no refined, com testes pytest.
4. Deputados e votos: dados, limpeza e ponte prontos. Falta aprovar a definição de participação em votações.
5. Marts das perguntas 1 e 2.
6. Marts das perguntas 3, 4 e 5.
7. Runner único (`python -m src.run_pipeline`) e README final.
