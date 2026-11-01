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
-- 2023-2025. Não é o status oficial: deputados sem voto no período ficam NULL.

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
)
SELECT
    c.id_deputado,
    c.nome_parlamentar,
    c.legislatura_inicial,
    c.legislatura_final,
    u.partido_atual,
    u.uf_atual
FROM cadastro c
LEFT JOIN ultimo_voto u ON u.id_deputado = c.id_deputado AND u.posicao = 1;
