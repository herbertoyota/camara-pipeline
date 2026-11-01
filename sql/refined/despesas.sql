-- refined.despesas: as três tabelas do raw empilhadas e limpas.
--
-- Parâmetro $salt: salt do hash de CPF de fornecedor. Vem de CAMARA_SALT via
-- src/clean.py. Nunca escreva o valor aqui nem no git.
--
-- Regras (detalhes no README, seção "Limpeza (refined)"):
--   - campo vazio ('' no raw) vira NULL;
--   - valores e datas convertidos com TRY_CAST: falha vira NULL, e src/clean.py
--     confere que nenhum valor não-vazio virou NULL;
--   - nada é descartado: estornos, datas suspeitas e divergências viram booleanos;
--   - CPF de fornecedor vira hash SHA-256 salgado; CNPJ fica em claro;
--   - fornecedor pessoa física (CPF) tem o nome trocado pelo rótulo PESSOA FISICA;
--   - não entram: cpf do deputado e txtPassageiro (só o booleano tem_passageiro).

CREATE OR REPLACE TABLE refined.despesas AS
WITH bruto AS (
    SELECT 2023 AS ano_arquivo, * FROM raw.ceap_2023
    UNION ALL BY NAME
    SELECT 2024 AS ano_arquivo, * FROM raw.ceap_2024
    UNION ALL BY NAME
    SELECT 2025 AS ano_arquivo, * FROM raw.ceap_2025
),
base AS (
    SELECT
        ano_arquivo,
        TRY_CAST(NULLIF(TRIM(numAno), '') AS INTEGER)                    AS ano_exercicio,
        TRY_CAST(NULLIF(TRIM(numMes), '') AS INTEGER)                    AS mes,
        TRY_CAST(NULLIF(TRIM(codLegislatura), '') AS INTEGER)            AS cod_legislatura,
        TRY_CAST(NULLIF(TRIM(nuLegislatura), '') AS INTEGER)             AS num_legislatura,
        TRY_CAST(NULLIF(TRIM(nuDeputadoId), '') AS INTEGER)              AS nu_deputado_id,
        TRY_CAST(NULLIF(TRIM(ideCadastro), '') AS INTEGER)               AS ide_cadastro,
        NULLIF(TRIM(txNomeParlamentar), '')                              AS nome_parlamentar,
        NULLIF(TRIM(sgUF), '')                                           AS sigla_uf,
        NULLIF(TRIM(sgPartido), '')                                      AS sigla_partido,
        NULLIF(TRIM(txtDescricao), '')                                   AS tipo_despesa,
        TRY_CAST(NULLIF(TRIM(numSubCota), '') AS INTEGER)                AS num_sub_cota,
        TRY_CAST(NULLIF(TRIM(numEspecificacaoSubCota), '') AS INTEGER)   AS num_especificacao_sub_cota,
        NULLIF(TRIM(txtDescricaoEspecificacao), '')                      AS descricao_especificacao,
        NULLIF(upper(strip_accents(regexp_replace(TRIM(txtFornecedor), '\s+', ' ', 'g'))), '')
                                                                         AS fornecedor_nome,
        NULLIF(regexp_replace(txtCNPJCPF, '[^0-9]', '', 'g'), '')        AS documento_digitos,
        NULLIF(TRIM(txtNumero), '')                                      AS num_documento,
        TRY_CAST(NULLIF(TRIM(indTipoDocumento), '') AS INTEGER)          AS ind_tipo_documento,
        -- ideDocumento '0' é sentinela (não informado), não um id.
        TRY_CAST(NULLIF(NULLIF(TRIM(ideDocumento), ''), '0') AS BIGINT) AS id_documento,
        TRY_CAST(NULLIF(TRIM(datEmissao), '') AS TIMESTAMP)::DATE        AS data_emissao,
        TRY_CAST(NULLIF(TRIM(numParcela), '') AS INTEGER)                AS num_parcela,
        TRY_CAST(NULLIF(TRIM(vlrDocumento), '') AS DECIMAL(18, 2))       AS valor_documento,
        TRY_CAST(NULLIF(TRIM(vlrGlosa), '') AS DECIMAL(18, 2))           AS valor_glosa,
        TRY_CAST(NULLIF(TRIM(vlrLiquido), '') AS DECIMAL(18, 2))         AS valor_liquido,
        TRY_CAST(NULLIF(TRIM(numLote), '') AS BIGINT)                    AS num_lote,
        TRY_CAST(NULLIF(TRIM(numRessarcimento), '') AS BIGINT)           AS num_ressarcimento,
        TRY_CAST(NULLIF(TRIM(datPagamentoRestituicao), '') AS TIMESTAMP)::DATE
                                                                         AS data_pagamento_restituicao,
        TRY_CAST(NULLIF(TRIM(vlrRestituicao), '') AS DECIMAL(18, 2))     AS valor_restituicao,
        NULLIF(TRIM(txtTrecho), '')                                      AS trecho,
        NULLIF(TRIM(urlDocumento), '')                                   AS url_documento,
        NULLIF(TRIM(txtPassageiro), '') IS NOT NULL                      AS tem_passageiro
    FROM bruto
),
classificado AS (
    SELECT
        base.*,
        CASE
            WHEN length(documento_digitos) = 14 THEN 'CNPJ'
            WHEN length(documento_digitos) = 11 THEN 'CPF'
            WHEN documento_digitos IS NOT NULL THEN 'OUTRO'
        END AS tipo_documento_fornecedor
    FROM base
)
SELECT
    ano_arquivo,
    ano_exercicio,
    mes,
    cod_legislatura,
    num_legislatura,
    nu_deputado_id,
    ide_cadastro,
    nome_parlamentar,
    sigla_uf,
    sigla_partido,
    tipo_despesa,
    num_sub_cota,
    num_especificacao_sub_cota,
    descricao_especificacao,
    -- Pessoa física: o nome é dado pessoal, então fica só o hash do CPF.
    CASE
        WHEN tipo_documento_fornecedor = 'CPF' THEN 'PESSOA FISICA'
        ELSE fornecedor_nome
    END AS fornecedor_nome,
    tipo_documento_fornecedor,
    CASE
        WHEN tipo_documento_fornecedor = 'CPF' THEN sha256($salt || '|' || documento_digitos)
        ELSE documento_digitos
    END::VARCHAR AS documento_fornecedor,
    num_documento,
    ind_tipo_documento,
    id_documento,
    data_emissao,
    -- Sinaliza, não descarta: antes de 2015 ou data futura.
    COALESCE(year(data_emissao) < 2015 OR data_emissao > CURRENT_DATE, FALSE) AS data_emissao_suspeita,
    num_parcela,
    valor_documento,
    valor_glosa,
    valor_liquido,
    -- Estorno: valor negativo no documento ou no líquido.
    COALESCE(valor_documento < 0 OR valor_liquido < 0, FALSE) AS eh_estorno,
    -- Líquido deveria ser documento menos glosa (glosa vazia conta como zero).
    COALESCE(valor_liquido <> valor_documento - COALESCE(valor_glosa, 0), FALSE) AS liquido_diverge,
    num_lote,
    num_ressarcimento,
    data_pagamento_restituicao,
    COALESCE(year(data_pagamento_restituicao) < 2015 OR data_pagamento_restituicao > CURRENT_DATE, FALSE)
        AS data_pagamento_suspeita,
    valor_restituicao,
    trecho,
    url_documento,
    tem_passageiro
FROM classificado;
