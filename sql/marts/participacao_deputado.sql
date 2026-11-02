-- marts.participacao_deputado: participação em votações nominais por deputado, 2023–2025.
--
-- Métrica aprovada:
--   - Período de exercício (proxy): do primeiro ao último voto do deputado em 2023–2025.
--   - Numerador: votos Sim, Não, Abstenção e Obstrução dentro do período.
--   - Denominador: votações nominais (com ao menos um voto individual) dentro do período,
--     menos as votações em que o deputado votou "Artigo 17" ou com tipo vazio (ficam fora
--     do numerador e do denominador).
--   - Sem nenhum voto em 2023–2025: participacao = NULL (não zero).
-- Limitação: o proxy de exercício inclui votações entre o primeiro e o último voto, mesmo quando o
--   deputado estava afastado; tende a inflar um pouco a participação dos que saem antes do fim.

CREATE OR REPLACE TABLE marts.participacao_deputado AS
WITH nominais AS (
    SELECT DISTINCT id_votacao, data_votacao FROM refined.votos
),
janela AS (
    SELECT id_deputado, min(data_votacao) AS primeiro_voto, max(data_votacao) AS ultimo_voto,
           count(*) AS votos_totais
    FROM refined.votos
    GROUP BY id_deputado
),
numerador AS (
    SELECT id_deputado, count(*) AS votos_registrados
    FROM refined.votos
    WHERE tipo_voto IN ('Sim', 'Não', 'Abstenção', 'Obstrução')
    GROUP BY id_deputado
),
excluidos AS (
    SELECT id_deputado, count(*) AS votos_excluidos
    FROM refined.votos
    WHERE tipo_voto IS NULL OR tipo_voto = 'Artigo 17'
    GROUP BY id_deputado
),
votacoes_no_periodo AS (
    SELECT j.id_deputado, count(*) AS votacoes_nominais_periodo
    FROM janela j
    JOIN nominais n ON n.data_votacao BETWEEN j.primeiro_voto AND j.ultimo_voto
    GROUP BY j.id_deputado
)
SELECT
    j.id_deputado,
    dep.nome_parlamentar,
    j.primeiro_voto,
    j.ultimo_voto,
    COALESCE(num.votos_registrados, 0)                              AS votos_registrados,
    COALESCE(v.votacoes_nominais_periodo, 0)                        AS votacoes_nominais_periodo,
    COALESCE(ex.votos_excluidos, 0)                                 AS votos_excluidos,
    COALESCE(v.votacoes_nominais_periodo, 0) - COALESCE(ex.votos_excluidos, 0) AS denominador,
    CASE
        WHEN COALESCE(v.votacoes_nominais_periodo, 0) - COALESCE(ex.votos_excluidos, 0) > 0
        THEN 100.0 * COALESCE(num.votos_registrados, 0)
             / (COALESCE(v.votacoes_nominais_periodo, 0) - COALESCE(ex.votos_excluidos, 0))
    END                                                             AS participacao_pct
FROM janela j
LEFT JOIN refined.deputados dep ON dep.id_deputado = j.id_deputado
LEFT JOIN numerador num ON num.id_deputado = j.id_deputado
LEFT JOIN excluidos ex ON ex.id_deputado = j.id_deputado
LEFT JOIN votacoes_no_periodo v ON v.id_deputado = j.id_deputado;
