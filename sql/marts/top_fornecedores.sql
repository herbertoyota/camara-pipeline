-- marts.top_fornecedores: 10 maiores fornecedores por período (2023, 2024, 2025 e TOTAL).
--
-- Ranking: valor_liquido_total decrescente. Empate no valor é desfeito pelo
-- documento_fornecedor em ordem crescente, então o top 10 tem sempre 10 linhas
-- por período (quando houver pelo menos 10 fornecedores) e é reproduzível.
-- participacao_pct: parcela do gasto total do período.

CREATE OR REPLACE TABLE marts.top_fornecedores AS
WITH totais AS (
    SELECT periodo, sum(valor_liquido_total) AS gasto_total
    FROM marts.gasto_por_fornecedor
    GROUP BY periodo
),
ranqueado AS (
    SELECT
        f.periodo,
        row_number() OVER (
            PARTITION BY f.periodo
            ORDER BY f.valor_liquido_total DESC, f.documento_fornecedor ASC
        )                                                       AS posicao,
        f.tipo_documento_fornecedor,
        f.identificador,
        f.fornecedor_nome,
        f.valor_liquido_total,
        f.linhas,
        f.documento_fornecedor
    FROM marts.gasto_por_fornecedor f
)
SELECT
    r.periodo,
    r.posicao,
    r.tipo_documento_fornecedor,
    r.identificador,
    r.fornecedor_nome,
    r.valor_liquido_total,
    r.linhas,
    100.0 * r.valor_liquido_total / t.gasto_total               AS participacao_pct
FROM ranqueado r
JOIN totais t ON t.periodo = r.periodo
WHERE r.posicao <= 10
ORDER BY r.periodo, r.posicao;
