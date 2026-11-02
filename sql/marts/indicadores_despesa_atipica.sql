-- marts.indicadores_despesa_atipica: indicadores de atipicidade por linha de despesa.
--
-- ATENÇÃO: os indicadores NÃO são evidência de desvio de conduta. Cada um sinaliza uma característica
-- estatística ou de calendário que pode ter explicações legítimas (ver README, seção "Indicadores
-- de atipicidade"). Uso: priorizar leitura humana, não concluir nada sobre uma despesa.
--
-- Universo: despesas positivas (valor_liquido > 0) de deputados. Ficam de fora:
--   - liderança (não tem deputado, eh_lideranca);
--   - estornos e linhas de convenção de sinal (valor <= 0): são abatimentos, não gasto a avaliar.
--
-- Indicadores (cada um é booleano, ou NULL quando não se aplica):
--   1. valor_acima_do_p99_da_categoria: valor > percentil 99 de (tipo_despesa, ano), calculado só com
--      despesas positivas. Só existe quando a categoria-ano tem pelo menos 100 linhas positivas; abaixo
--      disso o indicador é NULL. Por construção, sinaliza cerca de 1% das linhas de cada categoria-ano.
--      razao_sobre_mediana_categoria = valor / mediana da categoria-ano (mesma regra de mínimo).
--   2. emissao_fim_de_semana: data_emissao cai em sábado ou domingo. NULL quando data_emissao é nula.
--   3. mesmo_fornecedor_mesmo_dia_mesmo_deputado (CONTEXTO, fora da contagem): o mesmo deputado tem 2 ou
--      mais documentos distintos com o mesmo fornecedor na mesma data. Muito comum e com motivos legítimos
--      (várias contas no mesmo dia), por isso não entra em motivos_contagem.
--   4. mesmo_valor_mesmo_dia_mesmo_fornecedor_mesmo_deputado: 2 ou mais documentos distintos com o mesmo
--      fornecedor, na mesma data e com o mesmo valor. Mais específico que o indicador 3.
--      NULL quando id_documento ou data_emissao é nulo; documento sem identificador não conta.
--
-- motivos_contagem = quantos dos indicadores 1, 2 e 4 estão TRUE na linha (0 a 3).
-- Não contém número de documento, URL, nome de fornecedor pessoa física nem nome de fornecedor:
-- só o identificador (CNPJ ou 'ID-' + 8 caracteres do hash).

CREATE OR REPLACE TABLE marts.indicadores_despesa_atipica AS
WITH positivas AS (
    SELECT
        b.id_deputado,
        dep.nome_parlamentar,
        b.identificador_fornecedor,
        b.tipo_documento_fornecedor,
        b.tipo_despesa,
        b.ano,
        b.mes,
        b.data_emissao,
        b.id_documento,
        b.valor_liquido
    FROM intermediario.base_gasto b
    LEFT JOIN refined.deputados dep ON dep.id_deputado = b.id_deputado
    WHERE NOT b.eh_lideranca AND b.id_deputado IS NOT NULL AND b.valor_liquido > 0
),
estatistica_categoria AS (
    SELECT
        tipo_despesa,
        ano,
        count(*)                                        AS linhas_positivas,
        quantile_cont(valor_liquido, 0.99)              AS p99,
        quantile_cont(valor_liquido, 0.5)               AS mediana
    FROM positivas
    GROUP BY tipo_despesa, ano
),
documentos_do_dia AS (
    SELECT
        id_deputado,
        identificador_fornecedor,
        data_emissao,
        count(DISTINCT id_documento) AS documentos
    FROM positivas
    WHERE id_documento IS NOT NULL AND data_emissao IS NOT NULL
    GROUP BY id_deputado, identificador_fornecedor, data_emissao
),
documentos_do_dia_valor AS (
    SELECT
        id_deputado,
        identificador_fornecedor,
        data_emissao,
        valor_liquido,
        count(DISTINCT id_documento) AS documentos
    FROM positivas
    WHERE id_documento IS NOT NULL AND data_emissao IS NOT NULL
    GROUP BY id_deputado, identificador_fornecedor, data_emissao, valor_liquido
),
com_indicadores AS (
    SELECT
        p.id_deputado,
        p.nome_parlamentar,
        p.identificador_fornecedor,
        p.tipo_despesa,
        p.ano,
        p.mes,
        p.data_emissao,
        p.valor_liquido,
        ROUND(CASE WHEN e.linhas_positivas >= 100 AND e.mediana > 0
                   THEN p.valor_liquido / e.mediana END, 4)             AS razao_sobre_mediana_categoria,
        CASE WHEN e.linhas_positivas >= 100
             THEN p.valor_liquido > e.p99 END                           AS valor_acima_do_p99_da_categoria,
        CASE WHEN p.data_emissao IS NULL THEN NULL
             ELSE isodow(p.data_emissao) IN (6, 7) END                  AS emissao_fim_de_semana,
        CASE WHEN p.id_documento IS NULL OR p.data_emissao IS NULL THEN NULL
             ELSE g.documentos >= 2 END                                 AS mesmo_fornecedor_mesmo_dia_mesmo_deputado,
        CASE WHEN p.id_documento IS NULL OR p.data_emissao IS NULL THEN NULL
             ELSE gv.documentos >= 2 END                                AS mesmo_valor_mesmo_dia_mesmo_fornecedor_mesmo_deputado
    FROM positivas p
    LEFT JOIN documentos_do_dia_valor gv
        ON gv.id_deputado = p.id_deputado
       AND gv.identificador_fornecedor = p.identificador_fornecedor
       AND gv.data_emissao = p.data_emissao
       AND gv.valor_liquido = p.valor_liquido
    LEFT JOIN estatistica_categoria e
        ON e.tipo_despesa = p.tipo_despesa AND e.ano = p.ano
    LEFT JOIN documentos_do_dia g
        ON g.id_deputado = p.id_deputado
       AND g.identificador_fornecedor = p.identificador_fornecedor
       AND g.data_emissao = p.data_emissao
)
SELECT
    c.*,
    (COALESCE(c.valor_acima_do_p99_da_categoria, FALSE)::INTEGER
     + COALESCE(c.emissao_fim_de_semana, FALSE)::INTEGER
     + COALESCE(c.mesmo_valor_mesmo_dia_mesmo_fornecedor_mesmo_deputado, FALSE)::INTEGER) AS motivos_contagem
FROM com_indicadores c;
