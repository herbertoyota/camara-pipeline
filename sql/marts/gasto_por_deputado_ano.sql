-- marts.gasto_por_deputado_ano: gasto por deputado e ano. Só deputados (sem liderança).
--
-- partido e uf: os do último mês com despesa do deputado no ano (época do gasto).
-- Se o deputado tem mais de um partido nesse mês, vale o mais frequente no mês.
-- Empate na contagem: ordem alfabética (critério total, para o resultado não depender da ordem das linhas).
-- nome_parlamentar: nome público do deputado (não é dado de fornecedor).

CREATE OR REPLACE TABLE marts.gasto_por_deputado_ano AS
WITH base AS (
    SELECT * FROM marts.base_gasto WHERE NOT eh_lideranca AND id_deputado IS NOT NULL
),
contagem_partido AS (
    SELECT ano, id_deputado, mes, partido, count(*) AS n FROM base GROUP BY ano, id_deputado, mes, partido
),
contagem_uf AS (
    SELECT ano, id_deputado, mes, uf, count(*) AS n FROM base GROUP BY ano, id_deputado, mes, uf
),
partido_ano AS (
    SELECT ano, id_deputado, arg_min(partido, (-mes, -n, partido)) AS partido
    FROM contagem_partido GROUP BY ano, id_deputado
),
uf_ano AS (
    SELECT ano, id_deputado, arg_min(uf, (-mes, -n, uf)) AS uf
    FROM contagem_uf GROUP BY ano, id_deputado
),
totais AS (
    SELECT
        b.ano,
        b.id_deputado,
        dep.nome_parlamentar,
        count(*)                                                    AS linhas,
        count(DISTINCT b.mes)                                       AS meses_com_despesa,
        COALESCE(sum(b.valor_liquido), 0)                           AS valor_liquido_total,
        COALESCE(sum(b.valor_liquido) FILTER (WHERE b.eh_convencao_sinal), 0) AS valor_convencao_sinal,
        count(*) FILTER (WHERE b.divergente_inexplicada)            AS linhas_divergentes
    FROM base b
    LEFT JOIN refined.deputados dep ON dep.id_deputado = b.id_deputado
    GROUP BY b.ano, b.id_deputado, dep.nome_parlamentar
)
SELECT
    t.ano,
    t.id_deputado,
    t.nome_parlamentar,
    p.partido,
    u.uf,
    t.linhas,
    t.meses_com_despesa,
    t.valor_liquido_total,
    t.valor_convencao_sinal,
    t.linhas_divergentes
FROM totais t
LEFT JOIN partido_ano p USING (ano, id_deputado)
LEFT JOIN uf_ano u USING (ano, id_deputado);
