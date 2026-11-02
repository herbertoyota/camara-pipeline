-- marts.correlacao_gasto_participacao: correlação de Spearman entre gasto e participação em plenário.
--
-- CORRELAÇÃO NÃO INDICA CAUSA. Um rho alto ou baixo descreve só a ordem dos valores; não diz que
-- gastar mais causa mais ou menos presença, nem o contrário.
--
-- Unidade principal: deputado. x = gasto médio mensal do deputado (média dos meses com despesa),
-- y = participação em votações nominais de plenário. Usa-se o deputado, e não o par deputado-mês,
-- porque a participação é uma só por deputado: pares deputado-mês repetem o mesmo y e inflam n.
-- Linha 'pares deputado-mês' é só referência, com essa inflação.
--
-- Entram: deputados com pelo menos 30 votações elegíveis de plenário (denominador >= 30), com
-- participação. Ficam de fora: lideranças (não têm id de deputado) e deputados sem voto de plenário.
--
-- Spearman por postos: posto médio para empates (min + (k-1)/2, com k = tamanho do empate), e
-- rho = correlação de Pearson entre os postos. Esta é a definição com empates.
--
-- Recortes: (a) todos; (b) sem deputados que votaram Artigo 17; (c) por macrorregião (UF do mandato).
-- Limitações: proxy de exercício (primeiro e último voto de plenário); licenças não identificadas;
--   a Mesa (presidência) vota pouco e entra com participação baixa; n pequeno por macrorregião.

CREATE OR REPLACE TABLE marts.correlacao_gasto_participacao AS
WITH elegiveis AS (
    SELECT
        p.id_deputado,
        p.participacao_pct,
        p.votou_artigo_17,
        d.uf_atual,
        CASE d.uf_atual
            WHEN 'AC' THEN 'Norte' WHEN 'AP' THEN 'Norte' WHEN 'AM' THEN 'Norte' WHEN 'PA' THEN 'Norte'
            WHEN 'RO' THEN 'Norte' WHEN 'RR' THEN 'Norte' WHEN 'TO' THEN 'Norte'
            WHEN 'AL' THEN 'Nordeste' WHEN 'BA' THEN 'Nordeste' WHEN 'CE' THEN 'Nordeste' WHEN 'MA' THEN 'Nordeste'
            WHEN 'PB' THEN 'Nordeste' WHEN 'PE' THEN 'Nordeste' WHEN 'PI' THEN 'Nordeste' WHEN 'RN' THEN 'Nordeste'
            WHEN 'SE' THEN 'Nordeste'
            WHEN 'DF' THEN 'Centro-Oeste' WHEN 'GO' THEN 'Centro-Oeste' WHEN 'MT' THEN 'Centro-Oeste' WHEN 'MS' THEN 'Centro-Oeste'
            WHEN 'ES' THEN 'Sudeste' WHEN 'MG' THEN 'Sudeste' WHEN 'RJ' THEN 'Sudeste' WHEN 'SP' THEN 'Sudeste'
            WHEN 'PR' THEN 'Sul' WHEN 'RS' THEN 'Sul' WHEN 'SC' THEN 'Sul'
        END AS macro
    FROM marts.participacao_deputado p
    JOIN refined.deputados d ON d.id_deputado = p.id_deputado
    WHERE p.denominador >= 30 AND p.participacao_pct IS NOT NULL
),
gasto_medio AS (
    SELECT id_deputado, avg(valor_liquido_total) AS gasto_medio_mes
    FROM marts.gasto_por_deputado_mes
    GROUP BY id_deputado
),
deputados AS (
    SELECT e.*, g.gasto_medio_mes
    FROM elegiveis e JOIN gasto_medio g ON g.id_deputado = e.id_deputado
),
pares_mes AS (
    SELECT e.participacao_pct, m.valor_liquido_total AS gasto_mes
    FROM elegiveis e JOIN marts.gasto_por_deputado_mes m ON m.id_deputado = e.id_deputado
),
recortes AS (
    SELECT 'todos' AS recorte, 'deputado' AS unidade, gasto_medio_mes AS x, participacao_pct AS y FROM deputados
    UNION ALL
    SELECT 'sem votou_artigo_17', 'deputado', gasto_medio_mes, participacao_pct FROM deputados WHERE NOT votou_artigo_17
    UNION ALL
    SELECT 'macro: Norte', 'deputado', gasto_medio_mes, participacao_pct FROM deputados WHERE macro = 'Norte'
    UNION ALL
    SELECT 'macro: Nordeste', 'deputado', gasto_medio_mes, participacao_pct FROM deputados WHERE macro = 'Nordeste'
    UNION ALL
    SELECT 'macro: Centro-Oeste', 'deputado', gasto_medio_mes, participacao_pct FROM deputados WHERE macro = 'Centro-Oeste'
    UNION ALL
    SELECT 'macro: Sudeste', 'deputado', gasto_medio_mes, participacao_pct FROM deputados WHERE macro = 'Sudeste'
    UNION ALL
    SELECT 'macro: Sul', 'deputado', gasto_medio_mes, participacao_pct FROM deputados WHERE macro = 'Sul'
    UNION ALL
    SELECT 'pares deputado-mes (referencia, n inflado)', 'deputado-mes', gasto_mes, participacao_pct FROM pares_mes
),
postos AS (
    SELECT
        recorte,
        unidade,
        x,
        y,
        rank() OVER (PARTITION BY recorte ORDER BY x)
            + (count(*) OVER (PARTITION BY recorte, x) - 1) / 2.0 AS rx,
        rank() OVER (PARTITION BY recorte ORDER BY y)
            + (count(*) OVER (PARTITION BY recorte, y) - 1) / 2.0 AS ry
    FROM recortes
),
-- rho é NULL quando não dá para calcular: menos de 3 pontos, ou um dos lados sem variação.
-- Recortes sem nenhum ponto aparecem com n = 0, para o quadro ficar completo.
resumo AS (
    SELECT
        recorte,
        unidade,
        count(*)                                                AS n,
        CASE
            WHEN count(*) >= 3 AND stddev_pop(rx) > 0 AND stddev_pop(ry) > 0 THEN corr(rx, ry)
        END                                                     AS spearman_rho
    FROM postos
    GROUP BY recorte, unidade
)
-- Intervalo de confiança de 95% por transformação de Fisher: z = atanh(rho), erro = 1/sqrt(n-3),
-- IC = tanh(z +/- 1,96 x erro). Exige n > 3 e |rho| < 1; caso contrário, NULL.
SELECT
    r.recorte,
    r.unidade,
    COALESCE(s.n, 0)         AS n,
    s.spearman_rho,
    CASE WHEN s.n > 3 AND abs(s.spearman_rho) < 0.9999999999
         THEN tanh(atanh(s.spearman_rho) - 1.96 / sqrt(s.n - 3)) END AS ic95_inf,
    CASE WHEN s.n > 3 AND abs(s.spearman_rho) < 0.9999999999
         THEN tanh(atanh(s.spearman_rho) + 1.96 / sqrt(s.n - 3)) END AS ic95_sup
FROM (VALUES
    ('todos', 'deputado'),
    ('sem votou_artigo_17', 'deputado'),
    ('macro: Norte', 'deputado'),
    ('macro: Nordeste', 'deputado'),
    ('macro: Centro-Oeste', 'deputado'),
    ('macro: Sudeste', 'deputado'),
    ('macro: Sul', 'deputado'),
    ('pares deputado-mes (referencia, n inflado)', 'deputado-mes')
) AS r(recorte, unidade)
LEFT JOIN resumo s ON s.recorte = r.recorte AND s.unidade = r.unidade
ORDER BY r.recorte;
