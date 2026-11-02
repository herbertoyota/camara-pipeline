-- marts.top_fornecedores: 10 maiores fornecedores externos por período (2023, 2024, 2025 e TOTAL).
--
-- Exclui o lançamento interno (CNPJ da própria Câmara). participacao_pct é sobre o gasto
-- de fornecedores externos do período, não sobre o gasto total.
-- Ranking: valor_liquido_total decrescente. Empate no valor é desfeito pelo identificador
-- em ordem crescente, então o top 10 tem sempre 10 linhas quando há 10 fornecedores externos.

CREATE OR REPLACE TABLE marts.top_fornecedores AS
WITH externos AS (
    SELECT * FROM marts.gasto_por_fornecedor WHERE NOT eh_lancamento_interno
),
totais AS (
    SELECT periodo, sum(valor_liquido_total) AS gasto_total
    FROM externos
    GROUP BY periodo
),
ranqueado AS (
    SELECT
        f.periodo,
        row_number() OVER (
            PARTITION BY f.periodo
            ORDER BY f.valor_liquido_total DESC, f.identificador ASC
        )                                                       AS posicao,
        f.tipo_documento_fornecedor,
        f.identificador,
        f.raiz,
        f.fornecedor_nome,
        f.tipo_despesa_predominante,
        f.valor_liquido_total,
        f.linhas
    FROM externos f
)
SELECT
    r.periodo,
    r.posicao,
    r.tipo_documento_fornecedor,
    r.identificador,
    r.raiz,
    r.fornecedor_nome,
    r.tipo_despesa_predominante,
    r.valor_liquido_total,
    r.linhas,
    100.0 * r.valor_liquido_total / t.gasto_total               AS participacao_pct
FROM ranqueado r
JOIN totais t ON t.periodo = r.periodo
WHERE r.posicao <= 10
ORDER BY r.periodo, r.posicao;
