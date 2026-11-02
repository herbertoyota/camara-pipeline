-- marts.gasto_por_fornecedor: gasto líquido por fornecedor e período (2023, 2024, 2025 e TOTAL).
--
-- Fornecedor identificado pelo documento (exibido como identificador):
--   - CNPJ: aparece inteiro (dado público do fornecedor).
--   - CPF (pessoa física): aparece só como 'ID-' + 8 primeiros caracteres do hash
--     salgado. Nunca o CPF, nunca o hash completo, nunca o nome.
-- raiz: os 8 primeiros dígitos do CNPJ (empresa, com filiais). Pessoa física e a raiz
--   '00000000' (documentos genéricos, não empresas) usam o próprio identificador.
-- fornecedor_nome: o nome mais frequente do documento. Pessoa física sai como
-- 'PESSOA FISICA' e nome ocultado como 'NOME OCULTADO'.
-- eh_lancamento_interno: identificado pelo nome na fonte e pelas linhas que recebe (a confirmar
--   no rodapé do portal). Fica no gasto total; o ranking e a concentração de externos o excluem.
-- eh_documento_generico: CNPJ de raiz 00000000 (documento genérico, não empresa). Continua como
--   fornecedor externo, sem agrupamento por raiz.
--
-- valor_liquido_total usa a métrica aprovada (SUM(valor_liquido), estornos abatem).

CREATE OR REPLACE TABLE marts.gasto_por_fornecedor AS
WITH base AS (
    SELECT CAST(ano AS VARCHAR) AS periodo, documento_fornecedor, tipo_documento_fornecedor,
           fornecedor_nome, tipo_despesa, eh_lancamento_interno, valor_liquido
    FROM marts.base_gasto
    UNION ALL
    SELECT 'TOTAL' AS periodo, documento_fornecedor, tipo_documento_fornecedor,
           fornecedor_nome, tipo_despesa, eh_lancamento_interno, valor_liquido
    FROM marts.base_gasto
),
identificado AS (
    SELECT
        periodo,
        tipo_documento_fornecedor,
        CASE
            WHEN tipo_documento_fornecedor = 'CNPJ' THEN documento_fornecedor
            ELSE 'ID-' || left(documento_fornecedor, 8)
        END AS identificador,
        fornecedor_nome,
        tipo_despesa,
        eh_lancamento_interno,
        valor_liquido
    FROM base
)
-- O documento completo não sai no mart: nem o CPF, nem o hash inteiro.
SELECT
    periodo,
    tipo_documento_fornecedor,
    identificador,
    -- Raiz '00000000' não é uma empresa: são documentos genéricos (linhas de telefonia e
    -- serviços sem CNPJ próprio). Esses documentos não se agrupam: cada um é a própria raiz.
    CASE
        WHEN tipo_documento_fornecedor = 'CNPJ' AND left(identificador, 8) <> '00000000'
            THEN left(identificador, 8)
        ELSE identificador
    END                                                         AS raiz,
    mode(fornecedor_nome)                                       AS fornecedor_nome,
    mode(tipo_despesa)                                          AS tipo_despesa_predominante,
    bool_or(eh_lancamento_interno)                              AS eh_lancamento_interno,
    bool_or(tipo_documento_fornecedor = 'CNPJ' AND left(identificador, 8) = '00000000')
                                                                AS eh_documento_generico,
    sum(valor_liquido)                                          AS valor_liquido_total,
    count(*)                                                    AS linhas
FROM identificado
GROUP BY periodo, tipo_documento_fornecedor, identificador;
