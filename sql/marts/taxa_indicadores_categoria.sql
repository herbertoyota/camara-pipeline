-- marts.taxa_indicadores_categoria: proporção de cada indicador de atipicidade por categoria e ano.
--
-- Só agregado: não contém deputado nem fornecedor. Cada taxa usa como denominador as linhas em que
-- o indicador se aplica (NULL não conta). Indicadores de atipicidade não são evidência de desvio de conduta.
-- Ver README, seção "Indicadores de atipicidade".

CREATE OR REPLACE TABLE marts.taxa_indicadores_categoria AS
SELECT
    tipo_despesa,
    ano,
    count(*)                                                                   AS linhas,
    count(valor_acima_do_p99_da_categoria)                                     AS aplicavel_p99,
    100.0 * avg(valor_acima_do_p99_da_categoria::INTEGER)
        FILTER (WHERE valor_acima_do_p99_da_categoria IS NOT NULL)             AS taxa_p99_pct,
    count(emissao_fim_de_semana)                                               AS aplicavel_fim_de_semana,
    100.0 * avg(emissao_fim_de_semana::INTEGER)
        FILTER (WHERE emissao_fim_de_semana IS NOT NULL)                       AS taxa_fim_de_semana_pct,
    count(mesmo_valor_mesmo_dia_mesmo_fornecedor_mesmo_deputado)               AS aplicavel_mesmo_valor,
    100.0 * avg(mesmo_valor_mesmo_dia_mesmo_fornecedor_mesmo_deputado::INTEGER)
        FILTER (WHERE mesmo_valor_mesmo_dia_mesmo_fornecedor_mesmo_deputado IS NOT NULL) AS taxa_mesmo_valor_pct,
    count(mesmo_fornecedor_mesmo_dia_mesmo_deputado)                           AS aplicavel_mesmo_fornecedor_contexto,
    100.0 * avg(mesmo_fornecedor_mesmo_dia_mesmo_deputado::INTEGER)
        FILTER (WHERE mesmo_fornecedor_mesmo_dia_mesmo_deputado IS NOT NULL)   AS taxa_mesmo_fornecedor_contexto_pct
FROM marts.indicadores_despesa_atipica
GROUP BY tipo_despesa, ano
ORDER BY tipo_despesa, ano;
