# Como colocar o site no ar com atualização diária

Depois destes passos, o GitHub (gratuito) vai, **todo dia às 6h**:

1. coletar os preços da Siñeriz, Neutral, Yury's e Barão;
2. ler a planilha de preços manuais (Brasil Free Shop e outras lojas sem site);
3. guardar o histórico de preços;
4. publicar o site atualizado em `https://SEU-USUARIO.github.io/precos-rivera/`.

Funciona mesmo com o computador desligado.

## 1. Criar a conta e o repositório

1. Crie uma conta grátis em https://github.com/signup.
2. Instale o **GitHub Desktop**: https://desktop.github.com e entre com a conta.
3. No GitHub Desktop: **File → Add local repository…** e escolha a pasta `precos-rivera`
   (em `Meu Drive`). O projeto já está preparado como repositório.
4. Clique em **Publish repository**:
   - nome: `precos-rivera`
   - **desmarque** "Keep this code private" (o GitHub Pages grátis exige repositório público).

## 2. Ligar o site

1. Abra o repositório em https://github.com/SEU-USUARIO/precos-rivera.
2. **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Vá em **Actions**, clique em **Coletar preços e publicar site → Run workflow**.
   A primeira coleta leva de 30 a 60 minutos.
4. Quando terminar (bolinha verde), o endereço do site aparece no resultado da execução.

Pronto: a partir daí roda sozinho todo dia.

## 3. Planilha da Brasil Free Shop (e outras lojas de Instagram)

O jeito mais prático é uma **planilha do Google**, que você edita pelo celular:

1. Crie uma planilha com estas colunas na primeira linha:

   `loja, produto, preco_usd, data, categoria, link, imagem, marca`

   - **loja**: `Brasil Free Shop` (ou o nome de outra loja — ela aparece no site automaticamente)
   - **produto**: nome com marca e tamanho, ex.: `Perfume Lattafa Asad EDP 100ml`
     (tamanho e marca ajudam o site a comparar com as outras lojas)
   - **preco_usd**: ex.: `25,00`
   - **data**: quando o preço foi visto, ex.: `13/11/2026`
   - **link**: link do post (opcional) · **categoria, imagem, marca**: opcionais
2. **Arquivo → Compartilhar → Publicar na Web** → escolha a aba → formato **CSV** → Publicar.
3. Copie o link gerado e cole em `dados/config.json`:

   ```json
   { "planilha_url": "COLE-O-LINK-AQUI" }
   ```

4. No GitHub Desktop: **Commit to main → Push origin**.

A cada coleta diária o site lê a planilha de novo. Linha apagada da planilha some do site.
No site, esses preços aparecem com o aviso "Preço informado em (data)".

Sem planilha do Google, também dá para editar o arquivo `dados/precos-manuais.csv` e enviar pelo GitHub Desktop.

## Observações

- Se uma loja ficar fora do ar num dia, o site mantém os preços anteriores dela.
- Para rodar a coleta na hora, use **Actions → Run workflow**.
- Se alguma loja bloquear os acessos vindos do GitHub, a execução mostra o aviso
  "nada coletado" para ela — dá para ver em **Actions**.
