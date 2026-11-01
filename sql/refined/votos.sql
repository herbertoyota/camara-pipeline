-- refined.votos: um voto por linha, com id da votação, id do deputado, tipo e data.
--
-- Restrito às votações de 2023 a 2025 (pela data da votação, não pelo arquivo).
-- tipo_voto vazio no raw vira NULL. Os demais valores ficam como vieram da fonte
-- (Sim, Não, Abstenção, Obstrução, Artigo 17).
--
-- Só votos nominais aparecem aqui: votações simbólicas não têm voto por deputado.

CREATE OR REPLACE TABLE refined.votos AS
WITH votos AS (
    SELECT idVotacao, deputado_id, voto FROM raw.votacoes_votos_2023
    UNION ALL BY NAME
    SELECT idVotacao, deputado_id, voto FROM raw.votacoes_votos_2024
    UNION ALL BY NAME
    SELECT idVotacao, deputado_id, voto FROM raw.votacoes_votos_2025
),
votacoes AS (
    SELECT id, "data" FROM raw.votacoes_2023
    UNION ALL BY NAME
    SELECT id, "data" FROM raw.votacoes_2024
    UNION ALL BY NAME
    SELECT id, "data" FROM raw.votacoes_2025
)
SELECT
    NULLIF(TRIM(v.idVotacao), '')                          AS id_votacao,
    TRY_CAST(NULLIF(TRIM(v.deputado_id), '') AS INTEGER)   AS id_deputado,
    NULLIF(TRIM(v.voto), '')                               AS tipo_voto,
    TRY_CAST(NULLIF(TRIM(t."data"), '') AS DATE)           AS data_votacao
FROM votos v
JOIN votacoes t ON t.id = v.idVotacao
WHERE TRY_CAST(NULLIF(TRIM(t."data"), '') AS DATE) BETWEEN DATE '2023-01-01' AND DATE '2025-12-31';
