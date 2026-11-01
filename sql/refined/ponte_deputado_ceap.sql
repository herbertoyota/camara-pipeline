-- refined.ponte_deputado_ceap: liga o id de deputado do CEAP ao id da API da Câmara.
--
-- Motivo: nuDeputadoId (CEAP) e o id da API (cadastro e votos) são espaços de id
-- diferentes. Não há JOIN direto.
--
-- Regra, por ano e nome+UF, nesta ordem:
--   1. 'votos': nome e UF iguais aos do arquivo de votos do mesmo ano. Desambigua
--      homônimos porque o voto traz a UF.
--   2. 'cadastro_unico': nome igual a um único deputado do cadastro (sem UF).
--   3. NULL: sem par. Inclui lideranças partidárias (UF = 'NA') e nomes que
--      diferem entre as fontes (ex.: CEAP 'Yury do Paredão' = cadastro 'Yury Bruno').
--
-- Nomes são comparados em maiúsculas e sem acento.

CREATE OR REPLACE TABLE refined.ponte_deputado_ceap AS
WITH ceap AS (
    SELECT DISTINCT
        ano_arquivo,
        nu_deputado_id,
        upper(strip_accents(nome_parlamentar)) AS nome,
        sigla_uf                               AS uf
    FROM refined.despesas
    WHERE nu_deputado_id IS NOT NULL
),
votos_ponte AS (
    SELECT DISTINCT
        ano,
        upper(strip_accents(TRIM(deputado_nome))) AS nome,
        TRIM(deputado_siglaUf)                    AS uf,
        TRY_CAST(deputado_id AS INTEGER)          AS id_deputado
    FROM (
        SELECT 2023 AS ano, deputado_id, deputado_nome, deputado_siglaUf FROM raw.votacoes_votos_2023
        UNION ALL BY NAME
        SELECT 2024 AS ano, deputado_id, deputado_nome, deputado_siglaUf FROM raw.votacoes_votos_2024
        UNION ALL BY NAME
        SELECT 2025 AS ano, deputado_id, deputado_nome, deputado_siglaUf FROM raw.votacoes_votos_2025
    )
    WHERE NULLIF(TRIM(deputado_id), '') IS NOT NULL
),
cadastro_unico AS (
    SELECT nome, any_value(id_deputado) AS id_deputado
    FROM (SELECT upper(strip_accents(nome_parlamentar)) AS nome, id_deputado FROM refined.deputados)
    GROUP BY nome
    HAVING count(*) = 1
)
SELECT
    c.ano_arquivo,
    c.nu_deputado_id,
    coalesce(v.id_deputado, cu.id_deputado) AS id_deputado,
    CASE
        WHEN v.id_deputado IS NOT NULL THEN 'votos'
        WHEN cu.id_deputado IS NOT NULL THEN 'cadastro_unico'
    END AS metodo
FROM ceap c
LEFT JOIN votos_ponte v
    ON v.ano = c.ano_arquivo AND v.nome = c.nome AND v.uf = c.uf
LEFT JOIN cadastro_unico cu
    ON cu.nome = c.nome AND v.id_deputado IS NULL;
