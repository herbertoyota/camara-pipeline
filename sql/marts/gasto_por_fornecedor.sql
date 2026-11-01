-- marts.gasto_por_fornecedor: gasto líquido por fornecedor e período (2023, 2024, 2025 e TOTAL).
--
-- Fornecedor identificado pelo documento:
--   - CNPJ: aparece inteiro (dado público do fornecedor).
--   - CPF (pessoa física): aparece só como 'ID-' + 8 primeiros caracteres do hash
--     salgado. Nunca o CPF, nunca o nome.
-- fornecedor_nome: o nome mais frequente do documento. Pessoa física sai como
-- 'PESSOA FISICA' e nome ocultado como 'NOME OCULTADO'.
--
-- valor_liquido_total usa a mesma métrica aprovada (SUM(valor_liquido), estornos abatem).
-- Os valores de liderança entram: são gasto da Câmara com fornecedor.
-- Documento vazio não existe nos dados; se aparecer, a carga de marts falha.

CREATE OR REPLACE TABLE marts.gasto_por_fornecedor AS
WITH base AS (
    SELECT CAST(ano AS VARCHAR) AS periodo, documento_fornecedor, tipo_documento_fornecedor,
           fornecedor_nome, valor_liquido
    FROM marts.base_gasto
    UNION ALL
    SELECT 'TOTAL' AS periodo, documento_fornecedor, tipo_documento_fornecedor,
           fornecedor_nome, valor_liquido
    FROM marts.base_gasto
)
SELECT
    periodo,
    documento_fornecedor,
    tipo_documento_fornecedor,
    CASE
        WHEN tipo_documento_fornecedor = 'CNPJ' THEN documento_fornecedor
        ELSE 'ID-' || left(documento_fornecedor, 8)
    END                                                         AS identificador,
    mode(fornecedor_nome)                                       AS fornecedor_nome,
    sum(valor_liquido)                                          AS valor_liquido_total,
    count(*)                                                    AS linhas
FROM base
GROUP BY periodo, documento_fornecedor, tipo_documento_fornecedor;
