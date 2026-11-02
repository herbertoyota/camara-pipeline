-- marts.gasto_por_raiz: gasto externo agrupado pela raiz do CNPJ (8 primeiros dígitos), por período.
--
-- Filiais de uma mesma empresa são somadas. Pessoa física é o próprio identificador (hash curto).
-- cnpjs: quantos documentos (CNPJ ou pessoa física) compõem a raiz no período.
-- nome_principal: nome do documento de maior gasto da raiz.
-- Exclui o lançamento interno da Câmara.

CREATE OR REPLACE TABLE marts.gasto_por_raiz AS
SELECT
    periodo,
    raiz,
    arg_max(fornecedor_nome, valor_liquido_total)               AS nome_principal,
    any_value(tipo_documento_fornecedor)                        AS tipo_documento_fornecedor,
    count(*)                                                    AS cnpjs,
    sum(valor_liquido_total)                                    AS valor_liquido_total,
    sum(linhas)                                                 AS linhas
FROM marts.gasto_por_fornecedor
WHERE NOT eh_lancamento_interno
GROUP BY periodo, raiz;
