-- marts.gasto_por_partido_mes: gasto por partido (da época do gasto), ano e mês.
--
-- deputados_com_despesa: deputados distintos com despesa no partido naquele mês.
-- Liderança entra como partido LIDERANCA e não tem deputado, então a média fica NULL.
-- gasto_medio_por_deputado: gasto do partido no mês / deputados com despesa no mês.

CREATE OR REPLACE TABLE marts.gasto_por_partido_mes AS
SELECT
    ano,
    mes,
    partido,
    count(*)                                                    AS linhas,
    COALESCE(sum(valor_liquido), 0)                             AS valor_liquido_total,
    COALESCE(sum(valor_liquido) FILTER (WHERE eh_convencao_sinal), 0) AS valor_convencao_sinal,
    count(*) FILTER (WHERE divergente_inexplicada)              AS linhas_divergentes,
    count(DISTINCT id_deputado)                                 AS deputados_com_despesa,
    ROUND(COALESCE(sum(valor_liquido) / NULLIF(count(DISTINCT id_deputado), 0), NULL), 2)
                                                                AS gasto_medio_por_deputado
FROM intermediario.base_gasto
GROUP BY ano, mes, partido;
