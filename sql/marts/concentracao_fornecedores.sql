-- marts.concentracao_fornecedores: quanto do gasto cabe a poucos fornecedores, por período.
--
-- Métricas:
--   - participacao_top10_pct: parcela do gasto total que os 10 maiores fornecedores concentram.
--   - hhi: índice de Herfindahl-Hirschman, soma dos quadrados das participações (em %)
--     de cada fornecedor, na escala 0 a 10.000. 10.000 = um fornecedor concentra tudo;
--     próximo de 0 = gasto muito pulverizado.
--   - Participação calculada sobre valor_liquido_total (líquido). Um fornecedor com
--     saldo negativo fica com participação negativa; o quadrado a torna positiva no HHI.
--     Com o padrão de estornos e convenções, isso é raro; a checagem de saldo
--     negativo no top 10 é feita no módulo Python.

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
    sum(p.part_pct * p.part_pct)                               AS hhi
FROM totais t
JOIN participacoes p ON p.periodo = t.periodo
GROUP BY t.periodo, t.gasto_total, t.fornecedores
ORDER BY t.periodo;
