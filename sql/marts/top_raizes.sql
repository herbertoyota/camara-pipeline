-- marts.top_raizes: 10 maiores raízes de CNPJ externas por período (2023, 2024, 2025 e TOTAL).
--
-- Mesma regra do top de CNPJ completo (desempate pela raiz em ordem crescente), mas somando as filiais.
-- participacao_pct é sobre o gasto externo do período.

CREATE OR REPLACE TABLE marts.top_raizes AS
WITH totais AS (
    SELECT periodo, sum(valor_liquido_total) AS gasto_total FROM marts.gasto_por_raiz GROUP BY periodo
),
ranqueado AS (
    SELECT
        g.*,
        row_number() OVER (PARTITION BY g.periodo ORDER BY g.valor_liquido_total DESC, g.raiz ASC) AS posicao
    FROM marts.gasto_por_raiz g
)
SELECT
    r.periodo,
    r.posicao,
    r.raiz,
    r.nome_principal,
    r.tipo_documento_fornecedor,
    r.eh_documento_generico,
    r.cnpjs,
    r.valor_liquido_total,
    r.linhas,
    ROUND(100.0 * r.valor_liquido_total / t.gasto_total, 4)     AS participacao_pct
FROM ranqueado r
JOIN totais t ON t.periodo = r.periodo
WHERE r.posicao <= 10
ORDER BY r.periodo, r.posicao;
