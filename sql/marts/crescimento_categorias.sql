-- marts.crescimento_categorias: gasto por categoria (tipo_despesa) em 2023, 2024 e 2025,
-- com variação absoluta e percentual, 2023 → 2025 e ano a ano.
--
-- Categoria = texto exato de tipo_despesa. Nos três anos, os textos são idênticos (não há
-- renomeação visível), mas a descrição pode mudar entre anos em futuras cargas: confira
-- anos_presentes antes de comparar.
-- Categoria que não existe em todos os anos: presente_em_todos_os_anos = FALSE e anos_ausentes
--   listados. Quando a categoria não existe no ano-base, a variação percentual é NULL (não
--   se divide por zero); quando a base é negativa (ex.: convenção de sinal), o percentual também
--   é NULL, porque cresce e encolhe ao contrário. Se a categoria não tem linhas em um dos dois
--   anos comparados, o percentual também é NULL: ausência não é queda. base_nao_positiva registra o caso.
-- valor = SUM(valor_liquido), a métrica aprovada (estornos abatem; convenção e lançamento interno entram).

CREATE OR REPLACE TABLE marts.crescimento_categorias AS
WITH por_ano AS (
    SELECT tipo_despesa, ano, sum(valor_liquido) AS valor, count(*) AS linhas
    FROM marts.base_gasto
    GROUP BY tipo_despesa, ano
),
pivotado AS (
    SELECT
        tipo_despesa,
        COALESCE(sum(valor) FILTER (WHERE ano = 2023), 0) AS valor_2023,
        COALESCE(sum(valor) FILTER (WHERE ano = 2024), 0) AS valor_2024,
        COALESCE(sum(valor) FILTER (WHERE ano = 2025), 0) AS valor_2025,
        COALESCE(sum(linhas) FILTER (WHERE ano = 2023), 0) AS linhas_2023,
        COALESCE(sum(linhas) FILTER (WHERE ano = 2024), 0) AS linhas_2024,
        COALESCE(sum(linhas) FILTER (WHERE ano = 2025), 0) AS linhas_2025,
        array_to_string(list(DISTINCT ano ORDER BY ano), ',')          AS anos_presentes,
        count(DISTINCT ano)                                            AS n_anos
    FROM por_ano
    GROUP BY tipo_despesa
)
SELECT
    tipo_despesa,
    valor_2023, valor_2024, valor_2025,
    linhas_2023, linhas_2024, linhas_2025,
    valor_2025 - valor_2023                                            AS var_abs_2023_2025,
    CASE WHEN valor_2023 > 0 AND linhas_2023 > 0 AND linhas_2025 > 0 THEN 100.0 * (valor_2025 - valor_2023) / valor_2023 END AS var_pct_2023_2025,
    valor_2024 - valor_2023                                            AS var_abs_2023_2024,
    CASE WHEN valor_2023 > 0 AND linhas_2023 > 0 AND linhas_2024 > 0 THEN 100.0 * (valor_2024 - valor_2023) / valor_2023 END AS var_pct_2023_2024,
    valor_2025 - valor_2024                                            AS var_abs_2024_2025,
    CASE WHEN valor_2024 > 0 AND linhas_2024 > 0 AND linhas_2025 > 0 THEN 100.0 * (valor_2025 - valor_2024) / valor_2024 END AS var_pct_2024_2025,
    anos_presentes,
    n_anos = 3                                                         AS presente_em_todos_os_anos,
    CASE WHEN n_anos = 3 THEN NULL ELSE
        trim(
            CASE WHEN linhas_2023 = 0 THEN '2023 ' ELSE '' END ||
            CASE WHEN linhas_2024 = 0 THEN '2024 ' ELSE '' END ||
            CASE WHEN linhas_2025 = 0 THEN '2025' ELSE '' END
        )
    END                                                                AS anos_ausentes,
    (valor_2023 <= 0 OR valor_2025 <= 0 OR valor_2024 <= 0)            AS base_nao_positiva
FROM pivotado
ORDER BY valor_2025 DESC;
