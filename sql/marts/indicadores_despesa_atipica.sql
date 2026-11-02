-- marts.indicadores_despesa_atipica: indicadores de atipicidade por linha de despesa.
--
-- ATENÇÃO: os indicadores NÃO são evidência de irregularidade. Cada um sinaliza uma característica
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
--   3. mesmo_fornecedor_mesmo_dia_mesmo_deputado: o mesmo deputado tem 2 ou mais documentos distintos
--      (id_documento) com o mesmo fornecedor na mesma data. NULL quando id_documento ou data_emissao é
--      nulo. Documento sem identificador não conta, para não inflar o indicador.
--
-- motivos_contagem = quantos dos três indicadores estão TRUE na linha (0 a 3).
-- Não contém número de documento, URL, nome de fornecedor pessoa física nem nome de fornecedor:
-- só o identificador (CNPJ ou 'ID-' + 8 caracteres do hash).

CREATE OR REPLACE TABLE marts.indicadores_despesa_atipica AS
WITH positivas AS (
    SELECT
        b.id_deputado,
        dep.nome_parlamentar,
        b.documento_fornecedor,
        b.tipo_documento_fornecedor,
        b.tipo_despesa,
        b.ano,
        b.mes,
        b.data_emissao,
        b.id_documento,
        b.valor_liquido
    FROM marts.base_gasto b
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
        documento_fornecedor,
        data_emissao,
        count(DISTINCT id_documento) AS documentos
    FROM positivas
    WHERE id_documento IS NOT NULL AND data_emissao IS NOT NULL
    GROUP BY id_deputado, documento_fornecedor, data_emissao
),
com_indicadores AS (
    SELECT
        p.id_deputado,
        p.nome_parlamentar,
        CASE
            WHEN p.tipo_documento_fornecedor = 'CNPJ' THEN p.documento_fornecedor
            ELSE 'ID-' || left(p.documento_fornecedor, 8)
        END                                                             AS identificador_fornecedor,
        p.tipo_despesa,
        p.ano,
        p.mes,
        p.data_emissao,
        p.valor_liquido,
        CASE WHEN e.linhas_positivas >= 100 AND e.mediana > 0
             THEN p.valor_liquido / e.mediana END                       AS razao_sobre_mediana_categoria,
        CASE WHEN e.linhas_positivas >= 100
             THEN p.valor_liquido > e.p99 END                           AS valor_acima_do_p99_da_categoria,
        CASE WHEN p.data_emissao IS NULL THEN NULL
             ELSE isodow(p.data_emissao) IN (6, 7) END                  AS emissao_fim_de_semana,
        CASE WHEN p.id_documento IS NULL OR p.data_emissao IS NULL THEN NULL
             ELSE g.documentos >= 2 END                                 AS mesmo_fornecedor_mesmo_dia_mesmo_deputado
    FROM positivas p
    LEFT JOIN estatistica_categoria e
        ON e.tipo_despesa = p.tipo_despesa AND e.ano = p.ano
    LEFT JOIN documentos_do_dia g
        ON g.id_deputado = p.id_deputado
       AND g.documento_fornecedor = p.documento_fornecedor
       AND g.data_emissao = p.data_emissao
)
SELECT
    c.*,
    (COALESCE(c.valor_acima_do_p99_da_categoria, FALSE)::INTEGER
     + COALESCE(c.emissao_fim_de_semana, FALSE)::INTEGER
     + COALESCE(c.mesmo_fornecedor_mesmo_dia_mesmo_deputado, FALSE)::INTEGER) AS motivos_contagem
FROM com_indicadores c;
