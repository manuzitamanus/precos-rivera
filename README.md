# Preços Rivera

Protótipo de comparador de preços dos free shops de Rivera (Uruguai), no estilo do Compras Paraguai.

Lojas incluídas: **Siñeriz**, **Neutral**, **Yury's** e **Barão** (coleta automática) e **Brasil Free Shop** (preços informados numa planilha).

Para publicar o site com atualização diária automática, veja [PUBLICAR.md](PUBLICAR.md).

## Como usar

1. Coletar os preços (leva alguns minutos, porque o coletor faz uma pausa entre cada página para não sobrecarregar as lojas):

   ```bash
   python3 coletor/coletar.py
   ```

2. Abrir o site:

   ```bash
   python3 -m http.server 8765 --directory site
   ```

   Depois acesse http://localhost:8765 no navegador.

Rode a coleta uma vez por dia para formar o histórico de preços: cada mudança de preço fica guardada em `dados/historico.json` (não apague esse arquivo).

## Como funciona

- `coletor/coletar.py` lê as páginas públicas de categorias das lojas, guarda os preços em `dados/historico.json` e gera `site/dados.json`.
- O coletor tenta juntar o mesmo produto vendido em lojas diferentes comparando marca, palavras do nome e tamanho (ml, g, litros). Quando não tem certeza, deixa os produtos separados.
- `site/` é um site estático (HTML, CSS e JavaScript, sem dependências): busca, filtros, comparação entre lojas, histórico e uma lista de compras que soma com a cota de US$ 500.

## Limitações conhecidas

- Na Siñeriz, cada subcategoria mostra só os 50 primeiros produtos sem paginação pelo endereço da página; o coletor avisa quais páginas ficaram incompletas.
- Os preços são os dos sites; na loja física podem ser diferentes.
- A conversão para reais usa o dólar comercial; cada loja aplica a própria cotação.
- A junção de produtos iguais é automática e pode errar; nomes muito diferentes entre lojas não são reconhecidos.

## Próximos passos possíveis

- Incluir outras lojas (Class, Zebra, The Place…). Lojas feitas no Wix entram só com uma linha em `LOJAS` e outra em `coletores`.
- Alertas de queda de preço.
