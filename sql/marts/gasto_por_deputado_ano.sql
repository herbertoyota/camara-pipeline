-- marts.gasto_por_deputado_ano: gasto por deputado e ano. Só deputados (sem liderança).
--
-- partido e uf: os da despesa mais recente do deputado no ano (época do gasto).
-- Se o deputado trocou de partido no ano, aparece com o partido do último mês.
-- nome_parlamentar: nome público do deputado (não é dado de fornecedor).

CREATE OR REPLACE TABLE marts.gasto_por_deputado_ano AS
SELECT
    b.ano,
    b.id_deputado,
    dep.nome_parlamentar,
    arg_max(b.partido, b.mes)                                   AS partido,
    arg_max(b.uf, b.mes)                                        AS uf,
    count(*)                                                    AS linhas,
    COALESCE(sum(b.valor_liquido), 0)                           AS valor_liquido_total,
    COALESCE(sum(b.valor_liquido) FILTER (WHERE b.eh_convencao_sinal), 0) AS valor_convencao_sinal,
    count(*) FILTER (WHERE b.divergente_inexplicada)                   AS linhas_divergentes
FROM marts.base_gasto b
LEFT JOIN refined.deputados dep ON dep.id_deputado = b.id_deputado
WHERE NOT b.eh_lideranca AND b.id_deputado IS NOT NULL
GROUP BY b.ano, b.id_deputado, dep.nome_parlamentar;
