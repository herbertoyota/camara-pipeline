-- marts.gasto_por_deputado_mes: gasto por deputado, ano e mês. Só deputados (sem liderança).
--
-- partido e uf: os da despesa do próprio mês (época do gasto).
-- Um deputado que trocou de partido no mês aparece com o partido mais frequente do mês.
-- Empate na contagem: ordem alfabética (critério total, para o resultado não depender da ordem das linhas).
-- nome_parlamentar: nome público do deputado.

CREATE OR REPLACE TABLE marts.gasto_por_deputado_mes AS
WITH base AS (
    SELECT * FROM intermediario.base_gasto WHERE NOT eh_lideranca AND id_deputado IS NOT NULL
),
contagem_partido AS (
    SELECT ano, mes, id_deputado, partido, count(*) AS n FROM base GROUP BY ano, mes, id_deputado, partido
),
contagem_uf AS (
    SELECT ano, mes, id_deputado, uf, count(*) AS n FROM base GROUP BY ano, mes, id_deputado, uf
),
partido_mes AS (
    SELECT ano, mes, id_deputado, arg_min(partido, (-n, partido)) AS partido
    FROM contagem_partido GROUP BY ano, mes, id_deputado
),
uf_mes AS (
    SELECT ano, mes, id_deputado, arg_min(uf, (-n, uf)) AS uf
    FROM contagem_uf GROUP BY ano, mes, id_deputado
),
totais AS (
    SELECT
        b.ano,
        b.mes,
        b.id_deputado,
        dep.nome_parlamentar,
        count(*)                                                    AS linhas,
        COALESCE(sum(b.valor_liquido), 0)                           AS valor_liquido_total,
        COALESCE(sum(b.valor_liquido) FILTER (WHERE b.eh_convencao_sinal), 0) AS valor_convencao_sinal,
        count(*) FILTER (WHERE b.divergente_inexplicada)            AS linhas_divergentes
    FROM base b
    LEFT JOIN refined.deputados dep ON dep.id_deputado = b.id_deputado
    GROUP BY b.ano, b.mes, b.id_deputado, dep.nome_parlamentar
)
SELECT
    t.ano,
    t.mes,
    t.id_deputado,
    t.nome_parlamentar,
    p.partido,
    u.uf,
    t.linhas,
    t.valor_liquido_total,
    t.valor_convencao_sinal,
    t.linhas_divergentes
FROM totais t
LEFT JOIN partido_mes p USING (ano, mes, id_deputado)
LEFT JOIN uf_mes u USING (ano, mes, id_deputado);
