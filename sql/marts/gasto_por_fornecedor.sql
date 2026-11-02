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
-- tipo_despesa_predominante: a categoria mais frequente do documento.
-- Empate na contagem (nome ou categoria): ordem alfabética (critério total).
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
),
contagem_nome AS (
    SELECT periodo, tipo_documento_fornecedor, identificador, fornecedor_nome, count(*) AS n
    FROM identificado WHERE fornecedor_nome IS NOT NULL
    GROUP BY periodo, tipo_documento_fornecedor, identificador, fornecedor_nome
),
contagem_despesa AS (
    SELECT periodo, tipo_documento_fornecedor, identificador, tipo_despesa, count(*) AS n
    FROM identificado WHERE tipo_despesa IS NOT NULL
    GROUP BY periodo, tipo_documento_fornecedor, identificador, tipo_despesa
),
nome_principal AS (
    SELECT periodo, tipo_documento_fornecedor, identificador,
           arg_min(fornecedor_nome, (-n, fornecedor_nome)) AS fornecedor_nome
    FROM contagem_nome GROUP BY periodo, tipo_documento_fornecedor, identificador
),
despesa_predominante AS (
    SELECT periodo, tipo_documento_fornecedor, identificador,
           arg_min(tipo_despesa, (-n, tipo_despesa)) AS tipo_despesa
    FROM contagem_despesa GROUP BY periodo, tipo_documento_fornecedor, identificador
),
agregado AS (
    SELECT
        periodo,
        tipo_documento_fornecedor,
        identificador,
        bool_or(eh_lancamento_interno)                              AS eh_lancamento_interno,
        bool_or(tipo_documento_fornecedor = 'CNPJ' AND left(identificador, 8) = '00000000')
                                                                    AS eh_documento_generico,
        sum(valor_liquido)                                          AS valor_liquido_total,
        count(*)                                                    AS linhas
    FROM identificado
    GROUP BY periodo, tipo_documento_fornecedor, identificador
)
-- O documento completo não sai no mart: nem o CPF, nem o hash inteiro.
SELECT
    a.periodo,
    a.tipo_documento_fornecedor,
    a.identificador,
    -- Raiz '00000000' não é uma empresa: são documentos genéricos (linhas de telefonia e
    -- serviços sem CNPJ próprio). Esses documentos não se agrupam: cada um é a própria raiz.
    CASE
        WHEN a.tipo_documento_fornecedor = 'CNPJ' AND left(a.identificador, 8) <> '00000000'
            THEN left(a.identificador, 8)
        ELSE a.identificador
    END                                                         AS raiz,
    n.fornecedor_nome,
    d.tipo_despesa                                              AS tipo_despesa_predominante,
    a.eh_lancamento_interno,
    a.eh_documento_generico,
    a.valor_liquido_total,
    a.linhas
FROM agregado a
LEFT JOIN nome_principal n USING (periodo, tipo_documento_fornecedor, identificador)
LEFT JOIN despesa_predominante d USING (periodo, tipo_documento_fornecedor, identificador);
