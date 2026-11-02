-- intermediario.base_gasto: base interna dos marts de gasto. Uma linha por despesa.
--
-- Fica fora do schema marts de propósito: é intermediária, e carrega id_documento
-- (número do documento, usado só para contar documentos distintos nos indicadores).
-- Nenhum mart expõe essa coluna. O hash completo do CPF não entra aqui: o fornecedor
-- entra só como identificador_fornecedor (CNPJ, ou 'ID-' + 8 caracteres do hash).
--
-- Métrica aprovada: gasto = SUM(valor_liquido). Estornos (valor negativo) abatem.
-- As linhas de convenção de sinal e as divergentes ENTRAM no padrão; as colunas
-- eh_convencao_sinal e liquido_diverge deixam a sensibilidade visível nos marts.
--
-- divergente_inexplicada: liquido_diverge e não convenção (as 930 do README).
-- Convenção de sinal: glosa vazia e valor_liquido = -valor_documento (2.440 linhas
-- em 2023–2025, quase todas COMPLEMENTAÇÃO DO AUXÍLIO-MORADIA).
--
-- Partido: o da despesa (época do gasto), nunca o do cadastro atual.
-- Liderança (eh_lideranca): não tem id de deputado (fica fora das análises por
-- deputado) e entra nas análises por partido como 'LIDERANCA'. A UF da liderança é 'NA'.

CREATE SCHEMA IF NOT EXISTS intermediario;

CREATE OR REPLACE VIEW intermediario.base_gasto AS
SELECT
    d.ano_arquivo                                                        AS ano,
    d.mes                                                                AS mes,
    CASE WHEN d.eh_lideranca THEN NULL ELSE d.id_deputado END            AS id_deputado,
    d.eh_lideranca                                                       AS eh_lideranca,
    COALESCE(d.sigla_partido, CASE WHEN d.eh_lideranca THEN 'LIDERANCA' END) AS partido,
    d.sigla_uf                                                           AS uf,
    CASE
        WHEN d.tipo_documento_fornecedor = 'CNPJ' THEN d.documento_fornecedor
        ELSE 'ID-' || left(d.documento_fornecedor, 8)
    END                                                                  AS identificador_fornecedor,
    d.tipo_documento_fornecedor                                          AS tipo_documento_fornecedor,
    d.fornecedor_nome                                                    AS fornecedor_nome,
    d.tipo_despesa                                                       AS tipo_despesa,
    d.data_emissao                                                       AS data_emissao,
    d.id_documento                                                       AS id_documento,
    d.valor_liquido                                                      AS valor_liquido,
    COALESCE(d.valor_glosa IS NULL AND d.valor_liquido = -d.valor_documento, FALSE)
                                                                         AS eh_convencao_sinal,
    -- Lançamento interno: CNPJ identificado pelo nome na fonte e pelas linhas que recebe (a confirmar
    -- no rodapé do portal de dados abertos). Não afirmar que é o CNPJ da Câmara até confirmar.
    -- fica no gasto total, mas sai do ranking e da concentração de fornecedores externos.
    COALESCE(d.documento_fornecedor = '00530352000159', FALSE)           AS eh_lancamento_interno,
    COALESCE(d.liquido_diverge AND NOT COALESCE(d.valor_glosa IS NULL AND d.valor_liquido = -d.valor_documento, FALSE), FALSE)
                                                                         AS divergente_inexplicada
FROM refined.despesas_deputado d;
