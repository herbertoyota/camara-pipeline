-- marts.gasto_por_raiz: gasto externo agrupado pela raiz do CNPJ (8 primeiros dígitos), por período.
--
-- Filiais de uma mesma empresa são somadas. Pessoa física é o próprio identificador (hash curto).
-- cnpjs: quantos documentos (CNPJ ou pessoa física) compõem a raiz no período.
-- nome_principal: nome do documento de maior gasto da raiz. Empate no gasto: ordem alfabética do nome.
-- Exclui o lançamento interno (a confirmar). Raiz 00000000: cada documento é a própria raiz.

CREATE OR REPLACE TABLE marts.gasto_por_raiz AS
SELECT
    periodo,
    raiz,
    arg_min(fornecedor_nome, (-valor_liquido_total, COALESCE(fornecedor_nome, '')))
                                                                AS nome_principal,
    min(tipo_documento_fornecedor)                              AS tipo_documento_fornecedor,
    bool_or(eh_documento_generico)                              AS eh_documento_generico,
    count(*)                                                    AS cnpjs,
    sum(valor_liquido_total)                                    AS valor_liquido_total,
    sum(linhas)                                                 AS linhas
FROM marts.gasto_por_fornecedor
WHERE NOT eh_lancamento_interno
GROUP BY periodo, raiz;
