-- marts.comparacao_top10_cnpj_raiz: os dois rankings lado a lado, por período.
--
-- ranking = 'CNPJ' : top 10 por documento (pessoa física aparece pelo hash curto).
-- ranking = 'RAIZ' : top 10 por raiz do CNPJ (filiais somadas).
-- posicao_no_outro_ranking:
--   - linha CNPJ: posição da raiz desse documento no ranking por raiz.
--   - linha RAIZ: melhor posição, no ranking por CNPJ, de algum documento dessa raiz.
-- Se a posição muda, o grupo ocupa lugar diferente conforme o critério. Pessoa física: raiz = o próprio documento.

CREATE OR REPLACE TABLE marts.comparacao_top10_cnpj_raiz AS
WITH rank_raiz AS (
    SELECT periodo, raiz,
           row_number() OVER (PARTITION BY periodo ORDER BY valor_liquido_total DESC, raiz ASC) AS pos
    FROM marts.gasto_por_raiz
),
rank_cnpj AS (
    SELECT periodo, identificador, raiz,
           row_number() OVER (PARTITION BY periodo ORDER BY valor_liquido_total DESC, identificador ASC) AS pos
    FROM marts.gasto_por_fornecedor
    WHERE NOT eh_lancamento_interno
),
melhor_cnpj_da_raiz AS (
    SELECT periodo, raiz, min(pos) AS pos FROM rank_cnpj GROUP BY periodo, raiz
)
SELECT
    t.periodo,
    'CNPJ'                                                       AS ranking,
    t.posicao,
    t.identificador                                              AS chave,
    t.raiz,
    t.fornecedor_nome                                            AS nome,
    t.valor_liquido_total,
    t.participacao_pct,
    rr.pos                                                       AS posicao_no_outro_ranking
FROM marts.top_fornecedores t
LEFT JOIN rank_raiz rr ON rr.periodo = t.periodo AND rr.raiz = t.raiz
UNION ALL
SELECT
    r.periodo,
    'RAIZ',
    r.posicao,
    r.raiz,
    r.raiz,
    r.nome_principal,
    r.valor_liquido_total,
    r.participacao_pct,
    mc.pos
FROM marts.top_raizes r
LEFT JOIN melhor_cnpj_da_raiz mc ON mc.periodo = r.periodo AND mc.raiz = r.raiz
ORDER BY periodo, ranking, posicao;
