-- marts.concentracao_fornecedores: quanto do gasto cabe a poucos fornecedores, por período.
--
-- Métricas:
--   - participacao_top10_pct: parcela do gasto total que os 10 maiores fornecedores concentram.
--   - hhi: índice de Herfindahl-Hirschman, soma dos quadrados das participações (em %)
--     na escala 0 a 10.000. 10.000 = um fornecedor concentra tudo; perto de 0 = pulverizado.
--     Calculado SÓ sobre fornecedores com total positivo no período. Fornecedores com
--     total zero ou negativo (estornos maiores que as compras) ficam de fora do HHI;
--     fornecedores_excluidos_hhi e valor_excluido_hhi registram quantos e quanto.
--   - Participação sempre sobre gasto_total (líquido), para o top 10 e o HHI usarem a mesma base.

CREATE OR REPLACE TABLE marts.concentracao_fornecedores AS
WITH totais AS (
    SELECT periodo,
           sum(valor_liquido_total)                              AS gasto_total,
           count(*)                                              AS fornecedores
    FROM marts.gasto_por_fornecedor
    GROUP BY periodo
),
participacoes AS (
    SELECT
        f.periodo,
        f.valor_liquido_total,
        100.0 * f.valor_liquido_total / t.gasto_total          AS part_pct,
        row_number() OVER (PARTITION BY f.periodo ORDER BY f.valor_liquido_total DESC, f.identificador ASC) AS posicao
    FROM marts.gasto_por_fornecedor f
    JOIN totais t ON t.periodo = f.periodo
)
SELECT
    t.periodo,
    t.gasto_total,
    t.fornecedores,
    sum(p.valor_liquido_total) FILTER (WHERE p.posicao <= 10)  AS valor_top10,
    sum(p.part_pct) FILTER (WHERE p.posicao <= 10)             AS participacao_top10_pct,
    sum(p.part_pct * p.part_pct) FILTER (WHERE p.valor_liquido_total > 0) AS hhi,
    count(*) FILTER (WHERE p.valor_liquido_total <= 0)         AS fornecedores_excluidos_hhi,
    COALESCE(sum(p.valor_liquido_total) FILTER (WHERE p.valor_liquido_total <= 0), 0) AS valor_excluido_hhi
FROM totais t
JOIN participacoes p ON p.periodo = t.periodo
GROUP BY t.periodo, t.gasto_total, t.fornecedores
ORDER BY t.periodo;
