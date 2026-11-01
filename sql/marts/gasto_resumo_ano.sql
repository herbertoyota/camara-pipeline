-- marts.gasto_resumo_ano: total do ano e duas médias por deputado.
--
-- gasto_medio_por_deputado (anual) = gasto de deputados no ano / deputados distintos
--   com ao menos uma despesa no ano.
-- media_mensal_por_deputado = média, sobre os meses do ano, de
--   (gasto de deputados no mês / deputados com despesa naquele mês).
--   Compara um deputado-mês típico com o deputado-ano.
--   Diferença grande entre as duas é esperada quando deputados entram e saem no ano:
--   o anual conta cada deputado uma vez; o mensal conta só os presentes em cada mês.
-- Liderança fica fora das duas médias e do numerador de deputados.
-- valor_liquido_total inclui liderança, então bate com o total de gasto do ano.

CREATE OR REPLACE TABLE marts.gasto_resumo_ano AS
WITH mensal AS (
    SELECT
        ano,
        mes,
        sum(valor_liquido_total)              AS gasto_deputados_mes,
        count(DISTINCT id_deputado)           AS deputados_mes
    FROM marts.gasto_por_deputado_mes
    GROUP BY ano, mes
),
media_mensal AS (
    SELECT ano, avg(gasto_deputados_mes / deputados_mes) AS media_mensal_por_deputado
    FROM mensal
    GROUP BY ano
),
anual AS (
    SELECT
        ano,
        count(*)                                                    AS linhas,
        COALESCE(sum(valor_liquido), 0)                             AS valor_liquido_total,
        COALESCE(sum(valor_liquido) FILTER (WHERE eh_convencao_sinal), 0) AS valor_convencao_sinal,
        count(*) FILTER (WHERE divergente_inexplicada)              AS linhas_divergentes,
        count(DISTINCT id_deputado)                                 AS deputados_com_despesa,
        COALESCE(sum(valor_liquido) FILTER (WHERE NOT eh_lideranca), 0) AS valor_liquido_deputados
    FROM marts.base_gasto
    GROUP BY ano
)
SELECT
    a.ano,
    a.linhas,
    a.valor_liquido_total,
    a.valor_convencao_sinal,
    a.linhas_divergentes,
    a.deputados_com_despesa,
    a.valor_liquido_deputados,
    a.valor_liquido_deputados / NULLIF(a.deputados_com_despesa, 0)  AS gasto_medio_por_deputado,
    m.media_mensal_por_deputado
FROM anual a
LEFT JOIN media_mensal m ON m.ano = a.ano
ORDER BY a.ano;
