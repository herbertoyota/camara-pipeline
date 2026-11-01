-- refined.deputados: dimensão de deputados (id da API da Câmara).
--
-- Fonte: cadastro (raw.deputados) + votos (raw.votacoes_votos_*), porque o
-- cadastro em massa não traz partido nem UF do mandato.
--
-- Mantém: id, nome parlamentar, legislaturas, partido e UF do voto mais recente.
-- NÃO entra: cpf, nomeCivil, dataNascimento, municipioNascimento, ufNascimento,
-- dataFalecimento, siglaSexo, urlRedeSocial, urlWebsite (dado pessoal ou sem uso
-- nas perguntas de negócio).
--
-- partido_atual e uf_atual = partido/UF no voto mais recente registrado em
-- 2023-2025. Quando não há voto no período, usa-se a despesa mais recente (CEAP).
-- origem_partido_uf diz de onde veio: 'voto' ou 'despesa'. NULL só se não houver
-- nem voto nem despesa. Não é o status oficial.

CREATE OR REPLACE TABLE refined.deputados AS
WITH cadastro AS (
    SELECT
        TRY_CAST(regexp_extract(uri, '[0-9]+$') AS INTEGER)               AS id_deputado,
        NULLIF(TRIM(nome), '')                                            AS nome_parlamentar,
        TRY_CAST(NULLIF(TRIM(idLegislaturaInicial), '') AS INTEGER)       AS legislatura_inicial,
        TRY_CAST(NULLIF(TRIM(idLegislaturaFinal), '') AS INTEGER)         AS legislatura_final
    FROM raw.deputados
),
votos AS (
    SELECT deputado_id, deputado_siglaPartido, deputado_siglaUf, dataHoraVoto FROM raw.votacoes_votos_2023
    UNION ALL BY NAME
    SELECT deputado_id, deputado_siglaPartido, deputado_siglaUf, dataHoraVoto FROM raw.votacoes_votos_2024
    UNION ALL BY NAME
    SELECT deputado_id, deputado_siglaPartido, deputado_siglaUf, dataHoraVoto FROM raw.votacoes_votos_2025
),
ultimo_voto AS (
    SELECT
        TRY_CAST(deputado_id AS INTEGER)                    AS id_deputado,
        NULLIF(TRIM(deputado_siglaPartido), '')             AS partido_atual,
        NULLIF(TRIM(deputado_siglaUf), '')                  AS uf_atual,
        row_number() OVER (PARTITION BY deputado_id ORDER BY dataHoraVoto DESC) AS posicao
    FROM votos
    WHERE NULLIF(TRIM(deputado_id), '') IS NOT NULL
),
-- Despesa mais recente de cada deputado (fallback quando não há voto no período).
ultima_despesa AS (
    SELECT
        ide_cadastro                              AS id_deputado,
        NULLIF(TRIM(sigla_partido), '')           AS partido_atual,
        NULLIF(TRIM(sigla_uf), '')                AS uf_atual,
        row_number() OVER (PARTITION BY ide_cadastro ORDER BY ano_arquivo DESC, mes DESC) AS posicao
    FROM refined.despesas
    WHERE ide_cadastro IS NOT NULL
)
SELECT
    c.id_deputado,
    c.nome_parlamentar,
    c.legislatura_inicial,
    c.legislatura_final,
    COALESCE(u.partido_atual, d.partido_atual)  AS partido_atual,
    COALESCE(u.uf_atual, d.uf_atual)            AS uf_atual,
    CASE
        WHEN u.partido_atual IS NOT NULL THEN 'voto'
        WHEN d.partido_atual IS NOT NULL THEN 'despesa'
    END AS origem_partido_uf
FROM cadastro c
LEFT JOIN ultimo_voto u ON u.id_deputado = c.id_deputado AND u.posicao = 1
LEFT JOIN ultima_despesa d ON d.id_deputado = c.id_deputado AND d.posicao = 1;
