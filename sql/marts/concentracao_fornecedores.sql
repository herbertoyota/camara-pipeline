-- marts.concentracao_fornecedores: concentração do gasto em fornecedores externos, por período.
--
-- Universo: fornecedores externos (sem o lançamento interno, a confirmar). O lançamento interno
-- aparece à parte em valor_lancamento_interno, para o total do ano continuar fechando.
--
-- Métricas:
--   - participacao_top10_pct: parcela do gasto externo que os 10 maiores CNPJs/pessoas físicas concentram.
--   - participacao_top10_raiz_pct: o mesmo, agrupando por raiz do CNPJ (8 dígitos; filiais somadas).
--   - hhi / hhi_raiz: índice de Herfindahl-Hirschman (soma dos quadrados das participações em %),
--     escala 0 a 10.000. Calculado só sobre grupos com total positivo. Grupos com total zero ou
--     negativo ficam de fora; fornecedores_excluidos_hhi e valor_excluido_hhi registram quantos e quanto.

CREATE OR REPLACE TABLE marts.concentracao_fornecedores AS
WITH externos AS (
    SELECT * FROM marts.gasto_por_fornecedor WHERE NOT eh_lancamento_interno
),
lancamento AS (
    SELECT periodo, sum(valor_liquido_total) AS valor
    FROM marts.gasto_por_fornecedor WHERE eh_lancamento_interno
    GROUP BY periodo
),
totais AS (
    SELECT periodo,
           sum(valor_liquido_total)                              AS gasto_total,
           count(*)                                              AS fornecedores
    FROM externos
    GROUP BY periodo
),
participacoes AS (
    SELECT
        f.periodo,
        f.valor_liquido_total,
        100.0 * f.valor_liquido_total / t.gasto_total          AS part_pct,
        row_number() OVER (PARTITION BY f.periodo ORDER BY f.valor_liquido_total DESC, f.identificador ASC) AS posicao
    FROM externos f
    JOIN totais t ON t.periodo = f.periodo
),
raizes AS (
    SELECT periodo, raiz, sum(valor_liquido_total) AS valor
    FROM externos
    GROUP BY periodo, raiz
),
participacoes_raiz AS (
    SELECT
        r.periodo,
        r.valor,
        100.0 * r.valor / t.gasto_total                         AS part_pct,
        row_number() OVER (PARTITION BY r.periodo ORDER BY r.valor DESC, r.raiz ASC) AS posicao
    FROM raizes r
    JOIN totais t ON t.periodo = r.periodo
),
metricas_raiz AS (
    SELECT
        periodo,
        sum(part_pct) FILTER (WHERE posicao <= 10)                      AS participacao_top10_raiz_pct,
        sum(part_pct * part_pct) FILTER (WHERE valor > 0)               AS hhi_raiz
    FROM participacoes_raiz
    GROUP BY periodo
)
SELECT
    t.periodo,
    t.gasto_total,
    t.fornecedores,
    COALESCE(l.valor, 0)                                               AS valor_lancamento_interno,
    sum(p.valor_liquido_total) FILTER (WHERE p.posicao <= 10)          AS valor_top10,
    ROUND(sum(p.part_pct) FILTER (WHERE p.posicao <= 10), 4)           AS participacao_top10_pct,
    ROUND(m.participacao_top10_raiz_pct, 4)                            AS participacao_top10_raiz_pct,
    ROUND(sum(p.part_pct * p.part_pct) FILTER (WHERE p.valor_liquido_total > 0), 4) AS hhi,
    ROUND(m.hhi_raiz, 4)                                               AS hhi_raiz,
    count(*) FILTER (WHERE p.valor_liquido_total <= 0)                 AS fornecedores_excluidos_hhi,
    COALESCE(sum(p.valor_liquido_total) FILTER (WHERE p.valor_liquido_total <= 0), 0) AS valor_excluido_hhi
FROM totais t
JOIN participacoes p ON p.periodo = t.periodo
JOIN metricas_raiz m ON m.periodo = t.periodo
LEFT JOIN lancamento l ON l.periodo = t.periodo
GROUP BY t.periodo, t.gasto_total, t.fornecedores, l.valor, m.participacao_top10_raiz_pct, m.hhi_raiz
ORDER BY t.periodo;
