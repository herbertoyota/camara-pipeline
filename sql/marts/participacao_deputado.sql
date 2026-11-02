-- marts.participacao_deputado: participação em votações do PLENÁRIO por deputado, 2023–2025.
--
-- Métrica:
--   - Universo: votações nominais de plenário (sigla_orgao = 'PLEN'). Votações de comissão têm
--     poucos votantes (mediana ~40 contra ~380 no plenário) e não entram.
--   - Período de exercício (proxy): do primeiro ao último voto do deputado em plenário em 2023–2025.
--   - Numerador: votos Sim, Não, Abstenção e Obstrução em plenário, dentro do período.
--   - Denominador: votações nominais de plenário no período, menos as em que o deputado votou
--     "Artigo 17" ou com tipo vazio (fora do numerador e do denominador).
--   - Ausência em uma votação do período conta no denominador (o deputado não votou).
--   - Sem nenhum voto de plenário em 2023–2025: não aparece no mart (participação NULL).
--   - votou_artigo_17: TRUE se o deputado tem ao menos um voto "Artigo 17" em plenário.
--
-- Colunas de comparação (todas as votações, plenário e comissões): *_todas. Não entram na correlação.
-- Limitações: o proxy de exercício não distingue licença ou afastamento no meio do período;
--   deputados que saíram antes do fim da janela têm janela menor; suplentes com poucos votos
--   ficam com denominador pequeno (ver o mínimo de votações elegíveis).

CREATE OR REPLACE TABLE marts.participacao_deputado AS
WITH plen AS (
    SELECT * FROM refined.votos WHERE sigla_orgao = 'PLEN'
),
nominais_plen AS (
    SELECT DISTINCT id_votacao, data_votacao FROM plen
),
janela AS (
    SELECT id_deputado, min(data_votacao) AS primeiro_voto, max(data_votacao) AS ultimo_voto
    FROM plen GROUP BY id_deputado
),
art17 AS (
    SELECT DISTINCT id_deputado FROM plen WHERE tipo_voto = 'Artigo 17'
),
excluidos AS (
    SELECT id_deputado, count(*) AS votos_excluidos
    FROM plen WHERE tipo_voto IS NULL OR tipo_voto = 'Artigo 17'
    GROUP BY id_deputado
),
numerador AS (
    SELECT id_deputado, count(*) AS votos_registrados
    FROM plen WHERE tipo_voto IN ('Sim', 'Não', 'Abstenção', 'Obstrução')
    GROUP BY id_deputado
),
no_periodo AS (
    SELECT j.id_deputado, count(*) AS votacoes_nominais_periodo
    FROM janela j JOIN nominais_plen n ON n.data_votacao BETWEEN j.primeiro_voto AND j.ultimo_voto
    GROUP BY j.id_deputado
),
-- Comparação: todas as votações nominais (plenário e comissões), mesma regra.
janela_todas AS (
    SELECT id_deputado, min(data_votacao) AS primeiro_voto, max(data_votacao) AS ultimo_voto
    FROM refined.votos GROUP BY id_deputado
),
nominais_todas AS (
    SELECT DISTINCT id_votacao, data_votacao FROM refined.votos
),
excluidos_todas AS (
    SELECT id_deputado, count(*) AS n FROM refined.votos
    WHERE tipo_voto IS NULL OR tipo_voto = 'Artigo 17' GROUP BY id_deputado
),
numerador_todas AS (
    SELECT id_deputado, count(*) AS n FROM refined.votos
    WHERE tipo_voto IN ('Sim', 'Não', 'Abstenção', 'Obstrução') GROUP BY id_deputado
),
no_periodo_todas AS (
    SELECT j.id_deputado, count(*) AS n
    FROM janela_todas j JOIN nominais_todas n ON n.data_votacao BETWEEN j.primeiro_voto AND j.ultimo_voto
    GROUP BY j.id_deputado
)
SELECT
    j.id_deputado,
    dep.nome_parlamentar,
    j.primeiro_voto,
    j.ultimo_voto,
    COALESCE(num.votos_registrados, 0)                                       AS votos_registrados,
    COALESCE(np.votacoes_nominais_periodo, 0)                                AS votacoes_nominais_periodo,
    COALESCE(ex.votos_excluidos, 0)                                          AS votos_excluidos,
    COALESCE(np.votacoes_nominais_periodo, 0) - COALESCE(ex.votos_excluidos, 0) AS denominador,
    ROUND(CASE WHEN COALESCE(np.votacoes_nominais_periodo, 0) - COALESCE(ex.votos_excluidos, 0) > 0
               THEN 100.0 * COALESCE(num.votos_registrados, 0)
                    / (COALESCE(np.votacoes_nominais_periodo, 0) - COALESCE(ex.votos_excluidos, 0))
          END, 4)                                                            AS participacao_pct,
    (a17.id_deputado IS NOT NULL)                                            AS votou_artigo_17,
    COALESCE(nt.n, 0) - COALESCE(ext.n, 0)                                   AS denominador_todas,
    ROUND(CASE WHEN COALESCE(nt.n, 0) - COALESCE(ext.n, 0) > 0
               THEN 100.0 * COALESCE(numt.n, 0) / (COALESCE(nt.n, 0) - COALESCE(ext.n, 0))
          END, 4)                                                            AS participacao_todas_pct
FROM janela j
LEFT JOIN refined.deputados dep ON dep.id_deputado = j.id_deputado
LEFT JOIN numerador num ON num.id_deputado = j.id_deputado
LEFT JOIN excluidos ex ON ex.id_deputado = j.id_deputado
LEFT JOIN no_periodo np ON np.id_deputado = j.id_deputado
LEFT JOIN no_periodo_todas nt ON nt.id_deputado = j.id_deputado
LEFT JOIN excluidos_todas ext ON ext.id_deputado = j.id_deputado
LEFT JOIN numerador_todas numt ON numt.id_deputado = j.id_deputado
LEFT JOIN art17 a17 ON a17.id_deputado = j.id_deputado;
