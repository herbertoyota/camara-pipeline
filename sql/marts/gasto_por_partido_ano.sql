-- marts.gasto_por_partido_ano: gasto por partido (da época do gasto) e ano.
--
-- deputados_com_despesa = deputados distintos com ao menos uma despesa no ano, no partido.
-- Um deputado que trocou de partido no ano conta nos dois. Para LIDERANCA,
-- gasto_medio_por_deputado é NULL (não há deputado).
-- Os totais por partido somam o gasto total do ano (inclui liderança).

CREATE OR REPLACE TABLE marts.gasto_por_partido_ano AS
SELECT
    ano,
    partido,
    count(*)                                                    AS linhas,
    COALESCE(sum(valor_liquido), 0)                             AS valor_liquido_total,
    COALESCE(sum(valor_liquido) FILTER (WHERE eh_convencao_sinal), 0) AS valor_convencao_sinal,
    count(*) FILTER (WHERE divergente_inexplicada)                     AS linhas_divergentes,
    count(DISTINCT id_deputado)                                 AS deputados_com_despesa,
    COALESCE(sum(valor_liquido) / NULLIF(count(DISTINCT id_deputado), 0), NULL)
                                                                AS gasto_medio_por_deputado
FROM marts.base_gasto
GROUP BY ano, partido;
