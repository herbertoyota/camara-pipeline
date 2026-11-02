# camara-pipeline

Pipeline de dados que organiza os gastos da cota parlamentar (CEAP) dos deputados federais, com dados abertos da Câmara dos Deputados, de 2023 a 2025. O projeto responde a cinco perguntas de negócio com tabelas de indicadores em DuckDB. Foi feito como projeto final de um curso de engenharia de dados.

> **Estado:** pipeline completo (raw, refined e marts das perguntas 1 a 5), com runner único e validação de execuções repetidas. Pendências de confirmação estão na seção [Pendências](#pendências).

## Fonte dos dados e licença

- Portal de Dados Abertos: https://dadosabertos.camara.leg.br (cotas: https://dadosabertos.camara.leg.br/cotas/)
- Despesas da CEAP, arquivo anual em massa: `https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip` (2023, 2024 e 2025). O ano de 2026 não é baixado: o arquivo ainda está incompleto.
- Cadastro e votos: `deputados.csv`, `votacoes-{ano}.csv` e `votacoesVotos-{ano}.csv`, em `dadosabertos.camara.leg.br/arquivos/`.
- Formato: CSV com separador `;`, UTF-8 com BOM, decimal com ponto, datas em ISO.

**Licença: a confirmar.** Não há licença específica identificada nas páginas consultadas. Antes de publicar o repositório, confira os **Termos de uso** do portal de Dados Abertos da Câmara. A página [Sobre os dados abertos](https://dadosabertos.camara.leg.br/howtouse/sobre-dados-abertos.html) afirma que os dados são "livres de licenças", com exceção dos que exigem sigilo e respeito à privacidade. Esse texto não substitui os Termos de uso.

## Camadas

| Camada | Pasta / schema | Conteúdo |
|---|---|---|
| `raw` | `data/raw/`, schema `raw` | Dado como veio da fonte. Nada alterado, tudo `VARCHAR`. |
| `refined` | schema `refined` | Dado limpo: valores `DECIMAL`, datas `DATE`, nomes normalizados, documento só com dígitos, CPF convertido em hash. |
| `marts` | schema `marts` | Tabelas que respondem às perguntas de negócio. Saem só de `refined`. |

Dados, `.duckdb` e `.env` ficam fora do git (ver `.gitignore`). Versionados: código, SQL, testes e este README.

## Como rodar do zero

Exemplo para Windows (PowerShell). Em outros sistemas, troque a ativação do venv e a variável de ambiente.

```powershell
# 1. Ambiente virtual e dependências
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. Salt do hash de CPF (gere uma vez e guarde fora do repositório)
python -c "import secrets; print(secrets.token_hex(32))"
$env:CAMARA_SALT = "<valor gerado>"

# 3. Pipeline completo: baixa o que faltar e roda raw, refined e marts
python -m src.run_pipeline

# 4. Testes
python -m pytest
```

Sem rede, use `python -m src.run_pipeline --skip-download` com os arquivos já em `data/raw/`. Cada camada é recriada a cada execução, então rodar de novo não duplica dados. Sem `CAMARA_SALT`, o pipeline para com mensagem clara.

**Salt do hash de CPF.** Nunca grave o salt em arquivo versionado, issue, PR ou log. Trocar o salt muda todos os hashes; para reproduzi-los, use sempre o mesmo valor. Os testes não leem o salt do ambiente: ele é definido por `monkeypatch`.

**Validação de execuções repetidas:** `python -m src.validar_runner` roda o pipeline duas vezes, em bancos temporários, e compara todas as tabelas de `raw`, `refined` e `marts`. Colunas DOUBLE: diferença até 1e-6. As demais colunas: igualdade exata. Sai com código 1 se houver diferença. Não reduz threads. Se `CAMARA_SALT` não estiver definida, usa um salt aleatório só para a validação, que não é gravado.

## Respostas às perguntas de negócio

Os números abaixo são do banco local gerado antes do último ajuste de desempate e de arredondamento. Esses ajustes mudam só nomes empatados e casas decimais, não os totais. Para os valores exatos, consulte os marts.

**1. Gasto médio por deputado, por partido e por UF, e a evolução por ano.**
Marts `gasto_por_partido_ano`, `gasto_por_uf_ano`, `gasto_por_deputado_ano` e `gasto_resumo_ano`. Total do gasto: R$ 245,5 mi (2023), R$ 250,4 mi (2024) e R$ 240,4 mi (2025). A comparação entre anos usa a média por deputado-mês (ver a seção seguinte): cerca de R$ 39 mil nos três anos.

**2. Concentração nos 10 maiores fornecedores.**
Marts `top_fornecedores`, `concentracao_fornecedores` e `comparacao_top10_cnpj_raiz`. O top 10 concentra 23,6% do gasto externo em 2023, 21,3% em 2024 e 17,3% em 2025 (20,7% no total). O índice HHI fica entre 71 e 157 por ano, longe de qualquer faixa de alta concentração. Os resultados por CNPJ e por raiz (filiais somadas) são quase iguais.

**3. Categorias que mais crescem.**
Mart `crescimento_categorias`. Entre as categorias com gasto positivo em 2023, as maiores altas absolutas de 2023 a 2025 são *divulgação da atividade parlamentar* (+6,2%) e *manutenção de escritório de apoio* (+11,7%). A família de passagens aéreas (agregado, `eh_agregado = TRUE`) caiu 39,5%. Cautela: as linhas SIGEPA e RPA podem refletir mudança de sistema de emissão, não de gasto. Leia o agregado como gasto total com passagens.

**4. Relação entre gasto e participação em votações.**
Mart `correlacao_gasto_participacao`. Participação = votos registrados em votações nominais de plenário, no período entre o primeiro e o último voto do deputado, sobre as votações elegíveis. Com 618 deputados (mínimo de 30 votações elegíveis, pré-aprovado e a reavaliar), o Spearman entre gasto médio mensal e participação é **rho = 0,127** (IC 95%: 0,049 a 0,204). A associação é positiva e pequena: explica muito pouco da variação. Os recortes regionais não se distinguem entre si, e Centro-Oeste (n = 51) não é conclusivo. **Correlação não indica causa.**

**5. Despesas atípicas.**
Marts `indicadores_despesa_atipica` e `taxa_indicadores_categoria`. Três indicadores de contagem: valor acima do p99 da categoria-ano, emissão em fim de semana e mesmo valor, no mesmo dia, com o mesmo fornecedor e o mesmo deputado. Há 130.993 linhas de 641.945 despesas positivas com ao menos um deles. **Os indicadores não são evidência de desvio de conduta.** Cada um sinaliza uma característica estatística ou de calendário que pode ter explicação legítima. Uso: priorizar leitura humana.

## Média por deputado: anual e mensal

A **média anual** divide o gasto do ano pelos deputados distintos com alguma despesa no ano. Ela **engana** para comparar anos: suplentes que ficam poucos meses entram com o mesmo peso de quem fica o ano inteiro. Em 2023 o denominador foi 788 deputados, contra cerca de 520 presentes por mês. A média anual sobe ou cai com a rotatividade, mesmo sem mudança no gasto mensal.

A **média por deputado-mês** é a medida comparável entre anos: divide o gasto de cada mês pelos deputados presentes naquele mês e tira a média dos meses. Ela fica em torno de **R$ 39 mil** em 2023, 2024 e 2025.

| Ano | Média anual (R$) | Deputados no ano | Média mensal (R$) | Deputados por mês (min–máx) |
|---|---|---|---|---|
| 2023 | 310.370 | 788 | 38.938 | 516–545 |
| 2024 | 428.464 | 582 | 39.595 | 516–536 |
| 2025 | 425.639 | 562 | 38.668 | 510–524 |

Denominador: deputados com despesa, **sem liderança**. Liderança fica fora dessas médias.

## Decisões de privacidade

- **CPF de fornecedor pessoa física** vira hash SHA-256 com salt vindo de `CAMARA_SALT`. Nos marts, aparece só como `ID-` + 8 caracteres do hash. Nunca o CPF, nunca o hash completo.
- **Nome de fornecedor pessoa física** sai como `PESSOA FISICA` no refined e nos marts.
- **CPF do deputado** (coluna `cpf`) não entra no refined. Não é necessário para nenhuma pergunta.
- **Nome de passageiro** não entra no refined. Fica só o indicador `tem_passageiro`.
- **Empresário individual (CNPJ)** cujo nome traz CPF ou nome de pessoa física: o nome vira `NOME OCULTADO`. O CNPJ fica.
- **Número de documento** com 11 dígitos em linha de pessoa física vira `NULL` (pode ser CPF).
- **Marts:** CNPJ aparece inteiro, por ser dado público do fornecedor. Não há nome de pessoa física nem número de documento. Os nomes de deputados são nomes parlamentares públicos.

## Decisões de limpeza (refined)

- **Vazio:** `''` vira `NULL` com `NULLIF(TRIM(col), '')`.
- **Valores:** decimal com ponto, convertidos para `DECIMAL(18,2)`. A carga falha se algum valor não vazio virar `NULL`.
- **Datas:** `datEmissao` e `datPagamentoRestituicao` viram `DATE`. Ano antes de 2015 ou data futura gera `data_*_fora_da_faixa = TRUE`, sem descartar.
- **Estorno:** valores negativos ficam e abatem o gasto. `eh_estorno` marca os casos.
- **Divergência de líquido** (`liquido_diverge`): 2.440 linhas são **convenção de sinal** (glosa vazia e líquido = −documento, quase todas de "COMPLEMENTAÇÃO DO AUXÍLIO-MORADIA"). 930 linhas têm líquido menor que o documento sem glosa que explique a diferença. Ficam sinalizadas, não corrigidas.
- **Liderança:** linha sem `ide_cadastro` (órgão, não deputado). `eh_lideranca = TRUE`, `id_deputado` NULL. Fica fora das análises por deputado e entra nas análises por partido como `LIDERANCA`.
- **Chave do deputado:** `ide_cadastro` (id da API da Câmara). Casa em 100% das linhas com o campo preenchido. `nuDeputadoId` é outro espaço de id e não é usado.
- **Partido e UF do deputado** (`refined.deputados`): vêm do voto mais recente em 2023–2025. Sem voto, vêm da despesa mais recente (`origem_partido_uf` diz qual).

## Empates e arredondamento nos marts

**Empates.** Quando duas opções têm a mesma contagem (ou o mesmo gasto), a escolha segue um critério total: contagem decrescente e, no empate, ordem alfabética. Antes, o resultado de um empate dependia da ordem das linhas.

| Campo | Mart | Critério |
|---|---|---|
| `partido`, `uf` do deputado (mês) | `gasto_por_deputado_mes` | o mais frequente no mês |
| `partido`, `uf` do deputado (ano) | `gasto_por_deputado_ano` | o mais frequente no último mês com despesa no ano |
| `fornecedor_nome`, `tipo_despesa_predominante` | `gasto_por_fornecedor` | o mais frequente no documento |
| `nome_principal` | `gasto_por_raiz` | o nome do documento de maior gasto da raiz |

**Valores únicos por grupo (`min`).** Três campos de texto ou id usam `min()`, que é total e determinístico:
- `tipo_documento_fornecedor` em `gasto_por_raiz`: o tipo é o mesmo em todo o grupo. Raiz de 8 dígitos só existe para CNPJ, e identificadores `ID-` nunca têm 8 dígitos.
- `id_deputado` em `ponte_deputado_ceap`: o grupo tem uma linha, pois o filtro é `HAVING count(*) = 1`.
- `nome_parlamentar` e `sigla_uf` em `clean_camara`: o mínimo em ordem alfabética, usado só para exibir o nome e a UF de deputados sem par.

**Arredondamento.** Colunas DOUBLE são arredondadas no último passo, para não depender de ruído de ponto flutuante. Somas em DECIMAL não são arredondadas. HHI e intervalo de confiança são calculados com precisão cheia e arredondados na saída.

| Precisão | Colunas |
|---|---|
| 4 casas (percentuais, índices, razões, correlação) | `participacao_pct`, `participacao_todas_pct`, `participacao_top10_pct`, `participacao_top10_raiz_pct`, `hhi`, `hhi_raiz`, `var_pct_*`, `taxa_*_pct`, `razao_sobre_mediana_categoria`, `spearman_rho`, `ic95_inf`, `ic95_sup` |
| 2 casas (R$) | `gasto_medio_por_deputado` (partido, UF, deputado-mês e resumo), `media_mensal_por_deputado` |

Testes com empate proposital: `tests/test_marts_desempate.py`. O valor alfabeticamente maior é inserido primeiro. Com o SQL anterior, esses testes falham.

## Lançamento interno (a confirmar)

O CNPJ `00530352000159` é tratado como **lançamento interno, identificado pelo nome na fonte; a confirmar**. Motivo: 2.440 das suas linhas são de convenção de sinal com o nome "COMPLEMENTAÇÃO DO AUXÍLIO-MORADIA", e 7 linhas são reembolsos de passagem ("PASSAGEM AÉREA - REEMBOLSO", com os nomes "CAMARA DOS DEPUTADOS" e "LATAM"). Ou seja, o critério não é só convenção de sinal. Ainda não foi confirmado no rodapé do portal.

Efeito: as linhas ficam no gasto total, para o total do ano fechar. O CNPJ sai do ranking e da concentração de fornecedores externos, e o valor aparece à parte em `valor_lancamento_interno`. Para trocar o critério, altere `sql/marts/base_gasto.sql`.

## Documentos genéricos (raiz `00000000`)

CNPJs que começam com oito zeros (ex.: celular funcional, ramal, software) não são empresas. Cada um é tratado como a própria raiz e marcado com `eh_documento_generico = TRUE`. Continuam como fornecedores externos. O critério pode ser revisto.

## Participação em votações: notas

- **Universo:** votações nominais de plenário (órgão `PLEN`). Votações de comissão têm poucos votantes (mediana de 37, contra 409 no plenário), então ficam de fora.
- **Artigo 17:** os votos com esse tipo ficam fora do numerador e do denominador. **A documentação oficial do arquivo não define o termo.** A exclusão é premissa; há 953 votos de 39 deputados, com 57% concentrados em dois presidentes da Câmara.
- **Presença não é voto.** O site da Câmara mostra presença em plenário como contagem de dias, em período não declarado. A métrica daqui é fração de votações nominais. As duas medidas divergem, e a comparação feita nas notas do projeto não valida a métrica.

## Limitações

- **Licenças e afastamentos** não são identificados: o arquivo em massa não traz datas de mandato. Um deputado licenciado aparece com participação baixa.
- **Janela de exercício:** do primeiro ao último voto de plenário. Quem entrou ou saiu cedo tem janela menor.
- **Partido e UF atuais** não são o status oficial. Vêm do voto ou da despesa mais recente.
- **Mesa:** quem preside vota pouco. Os recortes "sem Artigo 17" reduzem o efeito, mas não o eliminam.
- **Correlação** não controla cargo, partido, UF do mandato nem tempo de mandato.
- **Média mensal** é média de meses com despesa. Um mês de gasto alto eleva a média.
- **Recortes regionais** têm n pequeno.
- **Cota de passagens:** as linhas SIGEPA e RPA podem refletir mudança de sistema de emissão.
- **Votações simbólicas** não têm voto por deputado. Só as nominais estão em `refined.votos`.
- **Lideranças** não têm partido no campo `sigla_partido`. Aparecem como `LIDERANCA` nas análises por partido.

## Estrutura de pastas

```
src/                 código Python: download, carga do raw, limpeza, marts, runner e validação
  run_pipeline.py    runner único (raw, refined e marts)
  validar_runner.py  duas execuções seguidas e comparação
sql/
  refined/           regras de limpeza (despesas, deputados, votos, ponte, view de despesas)
  marts/             uma tabela por arquivo; base_gasto é a base de todos os marts de gasto
tests/               pytest com dados inventados, em memória (nenhum teste lê data/)
data/                dados locais, fora do git (raw/, refined/, marts/, camara.duckdb)
notebooks/           exploração
```

## Testes

```powershell
python -m pytest
```

Testes com dados inventados, em DuckDB em memória. Não abrem `data/camara.duckdb` e não leem `CAMARA_SALT`. Cobrem a limpeza, os marts de cada pergunta, o desempate, o comparador da validação e a conferência de totais entre marts.

## Pendências

1. **Licença dos dados:** confirmar nos Termos de uso do portal (ver a seção de fonte).
2. **Lançamento interno:** confirmar o CNPJ `00530352000159` no rodapé do portal de dados abertos.
3. **Banco local:** `data/camara.duckdb` foi gerado antes dos ajustes de desempate e arredondamento. Rode `python -m src.run_pipeline` com o `CAMARA_SALT` do projeto para atualizá-lo.
4. **Mínimo de 30 votações elegíveis:** pré-aprovado, a reavaliar.
5. **Artigo 17:** confirmar o significado no material oficial, ou tratar a exclusão como premissa explícita.
