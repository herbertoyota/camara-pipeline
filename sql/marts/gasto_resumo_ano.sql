-- marts.gasto_resumo_ano: total do ano e gasto médio por deputado.
--
-- Gasto médio por deputado = gasto de deputados (sem liderança) / deputados com
-- ao menos uma despesa no ano. O denominador é esse número de deputados.
-- valor_liquido_total inclui liderança, então bate com o total de gasto do ano.

CREATE OR REPLACE TABLE marts.gasto_resumo_ano AS
SELECT
    ano,
    count(*)                                                    AS linhas,
    COALESCE(sum(valor_liquido), 0)                             AS valor_liquido_total,
    COALESCE(sum(valor_liquido) FILTER (WHERE eh_convencao_sinal), 0) AS valor_convencao_sinal,
    count(*) FILTER (WHERE divergente_inexplicada)                     AS linhas_divergentes,
    count(DISTINCT id_deputado)                                 AS deputados_com_despesa,
    COALESCE(sum(valor_liquido) FILTER (WHERE NOT eh_lideranca), 0) AS valor_liquido_deputados,
    COALESCE(sum(valor_liquido) FILTER (WHERE NOT eh_lideranca), 0)
        / NULLIF(count(DISTINCT id_deputado), 0)                AS gasto_medio_por_deputado
FROM marts.base_gasto
GROUP BY ano
ORDER BY ano;
