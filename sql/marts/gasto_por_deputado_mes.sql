-- marts.gasto_por_deputado_mes: gasto por deputado, ano e mês. Só deputados (sem liderança).
--
-- partido e uf: os da despesa do próprio mês (época do gasto).
-- Um deputado que trocou de partido no mês aparece com o partido mais frequente do mês.
-- nome_parlamentar: nome público do deputado.

CREATE OR REPLACE TABLE marts.gasto_por_deputado_mes AS
SELECT
    b.ano,
    b.mes,
    b.id_deputado,
    dep.nome_parlamentar,
    mode(b.partido)                                             AS partido,
    mode(b.uf)                                                  AS uf,
    count(*)                                                    AS linhas,
    COALESCE(sum(b.valor_liquido), 0)                           AS valor_liquido_total,
    COALESCE(sum(b.valor_liquido) FILTER (WHERE b.eh_convencao_sinal), 0) AS valor_convencao_sinal,
    count(*) FILTER (WHERE b.divergente_inexplicada)            AS linhas_divergentes
FROM marts.base_gasto b
LEFT JOIN refined.deputados dep ON dep.id_deputado = b.id_deputado
WHERE NOT b.eh_lideranca AND b.id_deputado IS NOT NULL
GROUP BY b.ano, b.mes, b.id_deputado, dep.nome_parlamentar;
