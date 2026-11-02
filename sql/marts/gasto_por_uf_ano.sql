-- marts.gasto_por_uf_ano: gasto por UF do mandato (da época do gasto) e ano.
--
-- Liderança tem UF 'NA' e fica nessa linha, para os totais baterem com o gasto do ano.
-- gasto_medio_por_deputado: gasto total da UF / deputados com despesa na UF no ano.
-- Liderança não é deputado: para 'NA' o gasto médio é NULL.

CREATE OR REPLACE TABLE marts.gasto_por_uf_ano AS
SELECT
    ano,
    uf,
    count(*)                                                    AS linhas,
    COALESCE(sum(valor_liquido), 0)                             AS valor_liquido_total,
    COALESCE(sum(valor_liquido) FILTER (WHERE eh_convencao_sinal), 0) AS valor_convencao_sinal,
    count(*) FILTER (WHERE divergente_inexplicada)                     AS linhas_divergentes,
    count(DISTINCT id_deputado)                                 AS deputados_com_despesa,
    ROUND(COALESCE(sum(valor_liquido) / NULLIF(count(DISTINCT id_deputado), 0), NULL), 2)
                                                                AS gasto_medio_por_deputado
FROM marts.base_gasto
GROUP BY ano, uf;
