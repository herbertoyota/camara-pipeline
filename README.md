# camara-pipeline

Pipeline de dados em três camadas (`raw`, `refined`, `marts`) com dados abertos da Câmara dos Deputados, feito como projeto final de um curso de engenharia de dados.

> Status: **etapas 1, 2 e 3 de 7 concluídas** (estrutura, download, carga do raw e limpeza das despesas). **Etapa 4 concluída, exceto a métrica de participação**, que aguarda aprovação das regras (ver seção própria). Os próximos passos estão listados no fim deste README.

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
python -m src.clean_camara         # refined.deputados, refined.votos, refined.ponte_deputado_ceap, view despesas_deputado
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
| CPF ou nome de pessoa dentro de um CNPJ | Empresário individual (CNPJ) cujo nome traz o CPF do dono, ou cujo nome é igual ao de uma pessoa física em outra linha: `fornecedor_nome` = `NOME OCULTADO`. O CNPJ fica. 2.461 linhas. |
| Número do documento | Em linha de pessoa física, número com 11 dígitos é tratado como possível CPF e vira `NULL`. 25 linhas. |
| Liderança | `eh_lideranca = TRUE` quando não há `ide_cadastro` (2.695 linhas). Ver seção de deputados e votos. |
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
| `refined.deputados` | id da API, nome parlamentar, legislatura inicial e final, partido e UF atuais e a origem deles | Partido e UF vêm do voto mais recente em 2023–2025 (o cadastro em massa não traz); sem voto, da despesa mais recente. |
| `refined.votos` | id da votação, id do deputado, tipo de voto, data da votação | Só votações de 2023–2025. `tipo_voto` vazio vira `NULL`. |
| `refined.ponte_deputado_ceap` | id CEAP → id da API, com o método usado | Reserva para linhas sem `ide_cadastro`. Ver abaixo. |
| `refined.despesas_deputado` (view) | cada linha de despesa com `id_deputado` e `metodo_vinculo` | Chave principal `ide_cadastro`. Ver abaixo. |

Colunas do cadastro e o que foi mantido: `uri` (vira `id_deputado`), `nome`, `idLegislaturaInicial`, `idLegislaturaFinal` **mantidas**. `nomeCivil`, `cpf`, `dataNascimento`, `municipioNascimento`, `ufNascimento`, `dataFalecimento`, `siglaSexo`, `urlRedeSocial`, `urlWebsite` **não entram** no refined (dado pessoal ou sem uso nas perguntas).

**Chave principal do JOIN: `ide_cadastro`.** O `ideCadastro` do CEAP é o id da API da Câmara: casa em 100% das linhas com esse campo preenchido (672.058 de 672.058). Não usamos `nuDeputadoId` do CEAP, que é outro espaço de id (ex.: 3554 no CEAP, outro id na API).

A `refined.despesas_deputado` (view) expõe `id_deputado` e `metodo_vinculo`:

1. **`ide_cadastro`**: chave principal.
2. **Reserva, `ponte_deputado_ceap`**: só para linhas sem `ide_cadastro` que não sejam liderança. Liga por nome e UF do arquivo de votos do ano; se não houver voto, por nome único no cadastro. Hoje essa reserva não resolve nenhuma linha: todas as linhas sem `ide_cadastro` são lideranças.
3. **Liderança (`eh_lideranca = TRUE`)**: linha sem `ide_cadastro` (órgão, não deputado). Fica com `id_deputado` NULL. Regra de uso: fica **fora das análises por deputado** e **dentro das análises por partido**, onde deve ser agrupada explicitamente como `LIDERANÇA`, porque `sigla_partido` é sempre vazio nessas linhas (o partido, quando aparece, só está no nome: "LIDERANÇA DO PT").

Nomes na ponte são comparados em maiúsculas e sem acento.

**Partido e UF em `refined.deputados`:** vêm do voto mais recente em 2023–2025. Quando o deputado não votou no período, vêm da despesa mais recente (`origem_partido_uf` diz qual). Dos 842 deputados que aparecem nas despesas, todos ficam com partido: 621 pelo voto e 221 pela despesa. Os 7.047 sem partido são ex-deputados sem despesa nem voto no período; não entram em nenhuma análise.

### Checagens antes dos marts

**(a) Linhas sem par no JOIN despesas × deputados (`ide_cadastro`), por ano:**

| Ano | Linhas | Por `ide_cadastro` | Sem par (deputado) | Liderança |
|---|---|---|---|---|
| 2023 | 232.754 | 231.899 | 0 (0%) | 855 (0,37%) |
| 2024 | 232.918 | 232.015 | 0 (0%) | 903 (0,39%) |
| 2025 | 209.081 | 208.144 | 0 (0%) | 937 (0,45%) |

Sem par de deputado: zero nos três anos. A ponte por nome dava 255 / 166 / 152 linhas sem par, e errava o caso do Yury (CEAP 3640): as 421 linhas dele têm `ide_cadastro = 220660` ("Yury Bruno", CE). Por isso o `mapeamento_manual.csv` não foi criado: não sobrou deputado a mapear.

**(b) Linhas de despesa idênticas em todas as colunas:** 0 por ano e entre anos. As repetições de `ideDocumento` são linhas diferentes (outra parcela, subcota ou valor).

### Limitações conhecidas

- `partido_atual` e `uf_atual` não são o status oficial: vêm do voto mais recente e, sem voto, da despesa mais recente.
- Votações simbólicas não têm voto por deputado. Só as nominais aparecem em `refined.votos`.
- Lideranças não têm partido no campo `sigla_partido`. Em análises por partido, agrupe-as como `LIDERANÇA`.

## Participação em votações: decisões (métrica ainda não implementada)

A métrica entra nos marts da pergunta 4. Estas são as regras já decididas:

- **Exercício (proxy):** o período de exercício de um deputado vai do primeiro ao último voto dele registrado em 2023–2025. Limitação: isso pode inflar um pouco a participação, porque um deputado que assumiu no meio do período só é contado a partir do primeiro voto, e deputados que saíram antes do último voto deixam de contar. Quando houver as datas de mandato, a regra deve ser trocada.
- **Obstrução conta como participação.** A documentação do arquivo diz que o campo traz "o voto (ou posicionamento de obstrução)". Obstrução é uma forma de presença registrada, então entra no numerador.
- **Artigo 17 fica fora do numerador e do denominador.** Premissa a validar: a documentação oficial do arquivo de votos (`https://dadosabertos.camara.leg.br/swagger/api.html`) não define "Artigo 17". A decisão baseia-se na escolha do usuário, não em texto da fonte.
- **Sem voto no período vira NULL, não zero.** Deputado sem nenhum voto em 2023–2025 não tem métrica; contar como zero distorceria o indicador.
- **Votos com tipo vazio** (`tipo_voto` NULL) ficam fora do numerador e do denominador.
- **Denominador:** votações nominais (as que têm voto individual) dentro do período de exercício. Votações simbólicas não entram.

## Próximas etapas

1. ✅ Estrutura, download e inspeção do dado bruto.
2. ✅ Carregar os CSVs no DuckDB (schema `raw`), tudo `VARCHAR`, re-executável.
3. ✅ Limpeza das despesas no refined, com testes pytest.
4. ✅ Deputados e votos: dados, limpeza e JOIN por `ide_cadastro`. Falta aprovar a métrica de participação (marts da pergunta 4).
5. Marts das perguntas 1 e 2.
6. Marts das perguntas 3, 4 e 5.
7. Runner único (`python -m src.run_pipeline`) e README final.
