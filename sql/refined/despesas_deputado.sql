-- refined.despesas_deputado: cada linha de despesa com o id do deputado na API.
--
-- Chave principal: ide_cadastro (o ideCadastro do CEAP é o id da API da Câmara;
-- casa em 100% das linhas com ide_cadastro preenchido).
-- Reserva: refined.ponte_deputado_ceap, só para linhas sem ide_cadastro que não
-- sejam liderança. Hoje essa reserva não resolve nenhuma linha (as sem
-- ide_cadastro são todas lideranças).
--
-- metodo_vinculo: 'ide_cadastro' | 'votos' | 'cadastro_unico' | NULL (sem par).
-- Linha de liderança (eh_lideranca) fica com id_deputado NULL.

CREATE OR REPLACE VIEW refined.despesas_deputado AS
SELECT
    d.*,
    COALESCE(d.ide_cadastro, p.id_deputado) AS id_deputado,
    CASE
        WHEN d.ide_cadastro IS NOT NULL THEN 'ide_cadastro'
        ELSE p.metodo
    END AS metodo_vinculo
FROM refined.despesas d
LEFT JOIN refined.ponte_deputado_ceap p
    ON p.ano_arquivo = d.ano_arquivo AND p.nu_deputado_id = d.nu_deputado_id;
