# INSTALAÇÃO

## Índice
1. [Requisitos](#requisitos)
2. [Criar uma Skill Amazon Alexa](#criar-uma-skill-amazon-alexa)
3. [Criar uma Função AWS Lambda](#criar-uma-função-aws-lambda)
4. [Adicionar Código à Função Lambda](#adicionar-código-à-função-lambda)
5. [Testar a Função Lambda](#testar-a-função-lambda)
6. [Configurar o Endpoint do Serviço da Skill](#configurar-o-endpoint-do-serviço-da-skill)
7. [Vinculação de Conta](#vinculação-de-conta)
8. [Habilitar a Skill no App Alexa](#habilitar-a-skill-no-app-alexa)
9. [Localização da Alexa](#localização-da-alexa)

---

## Requisitos
- Esta skill Alexa requer que sua instância do Home Assistant esteja acessível pela Internet via HTTPS na porta 443 usando um certificado SSL/TLS. Um certificado autoassinado não funcionará, mas um certificado confiável público ou um certificado assinado por uma autoridade certificadora aprovada pela Amazon deve funcionar.
- Uma conta de desenvolvedor da Amazon. Inscreva-se [aqui](https://developer.amazon.com/).
- Uma conta Amazon Web Services (AWS) é necessária para hospedar a função Lambda para sua skill Alexa Smart Home. O AWS Lambda é gratuito para até 1 milhão de solicitações e 1 GB de transferência de dados por mês.

## Criar uma Skill Amazon Alexa
- Faça login no [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask). Você pode criar sua conta gratuita na página de login.
_Nota: Isso deve ser feito com a mesma conta Amazon que você usa nos seus dispositivos Alexa e app._
- Vá para a página `Alexa Skills`, se ainda não estiver lá, e clique no botão `Create Skill` para iniciar o processo.
- No passo `Name, Locale`: Insira o `Skill name` como preferir, depois selecione o `language` padrão da skill e clique em `Next`.
- No passo `Experience, Model, Hosting service`: Selecione `Other` > `Custom` > `Provision your own`, depois clique em `Next`.
- No passo `Template`: Selecione `Start from Scratch` e clique em `Next`.
- Revise e clique em `Create Skill`.

  ![](../en/images/skill_review.png)
- Isso pode levar alguns segundos, por favor, aguarde…
- Na próxima tela, você verá algumas opções, e no painel direito `Building your skill`, siga estes passos:

  ![](../en/images/skill_build.png)

  - Clique em `Invocation Name >` altere o nome de invocação padrão conforme desejar, e depois clique em `Save`.
  - No menu de navegação à esquerda, vá para `CUSTOM` > `Interaction Model` > `JSON Editor`, arraste e solte o [arquivo interactionModels.json](../interactionModels.json), depois clique em `Save`.

  ![](../en/images/skill_intmodel.png)

  - Ainda no menu de navegação à esquerda, vá para `CUSTOM` > `Interfaces`, role para baixo até `Alexa Presentation Language`, habilite e desmarque `Hub Round` _(Esta skill não é compatível)_.

  ![](../en/images/skill_interfaces.png)

  - Agora, vá para `CUSTOM` > `Endpoint` e anote o `Your Skill ID`.
- Você criou a estrutura da skill. No próximo passo, faremos algum trabalho de desenvolvedor, mas mantenha o `Alexa Developer Console` aberto, pois precisaremos alterar a configuração da skill mais tarde.

## Criar uma Função AWS Lambda
Escreveremos um pequeno código hospedado como uma `função AWS Lambda` que redirecionará as solicitações da skill Alexa para sua instância do Home Assistant. Certifique-se de que você tem a API habilitada no Home Assistant, pois ela processará a solicitação e enviará a resposta. A função Lambda então entregará a resposta de volta para a skill Alexa.

Primeiro, você precisa fazer login no [console AWS](https://aws.amazon.com/console/). Se você ainda não tem uma conta AWS, pode criar um novo usuário com o benefício de 12 meses de uso gratuito. Você não precisa se preocupar com custos, mesmo que sua conta já tenha passado dos primeiros 12 meses, já que a AWS oferece até 1 milhão de solicitações Lambda, 1 GB de dados de saída e todos os dados de entrada gratuitamente todos os meses para todos os usuários. Veja mais detalhes sobre [preços do Lambda](https://aws.amazon.com/lambda/pricing/).

## Adicionar Código à Função Lambda
Agora você precisa criar uma função Lambda.
- Clique em `Services` na barra de navegação superior, expanda o menu para exibir todos os serviços AWS, depois, na seção `Compute`, clique em `Lambda` para navegar até o console Lambda ou use o campo de busca _(Dica: Adicione `Lambda` aos favoritos)_.
- **IMPORTANTE** - Skills Alexa só são suportadas em certas regiões da AWS. A localização do seu servidor atual será exibida no canto superior direito (por exemplo, Ohio). Selecione um servidor disponível abaixo que esteja mais próximo da sua localização e na sua região, com base no país da sua conta Amazon. Funções Alexa Lambda criadas em outros servidores não funcionarão corretamente e podem impedir a vinculação de contas!
  - **US East (N. Virginia)** região para Américas: skills em `English (US)`, `English (CA)`, `Portuguese (BR)`.
  - **EU (Ireland)** região para skills em `English (UK)`, `Italian`, `German (DE)`, `Spanish (ES)`, `French (FR)`.
  - **US West (Oregon)** região para skills em `Japanese` e `English (AU)` _(não testado ainda)_.
- Clique em `Functions` na barra de navegação à esquerda para exibir a lista de suas funções Lambda.
- Clique em `Create function`:
  - Selecione `Author from scratch`, depois insira um nome para a função como `HomeAssistantAssist`.
  - Selecione **Python 3.12** como Runtime e **x86_64** como arquitetura.
  - Não altere a `default execution role`, deixe como padrão `Create a new role with basic Lambda permissions`.
- Clique em `Create function`, depois configure os detalhes da função Lambda.

  ![](../en/images/lambda_function.png)

- Expanda a seção `Function overview` (se ela não estiver expandida), depois clique em `+ Add trigger` na parte esquerda do painel, depois selecione `Alexa` na lista suspensa para adicionar um gatilho Alexa à sua função Lambda.

  ![](../en/images/lambda_overview.png)

- Selecione `Alexa Skills Kit` e insira o `Skill ID` da skill que você criou no passo anterior. _(Dica: Você pode precisar voltar ao `Alexa Developer Console` para copiar o `Skill ID`)._, depois clique no botão `Add`.

  ![](../en/images/lambda_trigger.png)

- Agora role até a aba `Code` > `Code source`, depois clique no botão `Upload from` à direita e selecione `zip file`.
  - Faça upload do arquivo `lambda_function.zip` baixado dos [últimos lançamentos](https://github.com/fabianosan/HomeAssistantAssistAWS/releases/download/lambda_functions_v0.1/lambda_functions_v0.1.zip).
  - Todo o código será substituído pelo arquivo enviado, e você não poderá editá-lo _(Se quiser editar algum arquivo, faça isso em sua estação antes deste passo)_.
- Clique no botão `Deploy` para publicar o código atualizado.
- Navegue até a aba `Configuration`, selecione `Environment variables` no menu de navegação à esquerda. Você precisa adicionar `pelo menos uma variável de ambiente` da lista abaixo. As variáveis restantes são `opcionais`, mas configuram recursos específicos no funcionamento da skill. Para adicionar uma variável, clique no botão `Edit`, depois adicione as seguintes chaves e valores:

  ![](../en/images/lambda_envvar.png)
  - (obrigatório) Chave = **home_assistant_url**, Valor = a URL acessível pela Internet da sua instância do Home Assistant. Não inclua a barra `/` no final.
  - (opcional) Chave = **home_assistant_agent_id**, Valor = Seu Assist Agent ID. (instruções aqui)
  - (opcional) Chave = **home_assistant_language**, Valor = Seu Assist Language. (O padrão é o idioma configurado no Assist)
  - (opcional) Chave = **home_assistant_dashboard**, Valor = O nome do caminho do seu painel. (O padrão é `lovelace`)
  - (opcional) Chave = **home_assistant_kioskmode**, Valor = `True`. Defina esta variável para habilitar o KIOSKMODE (certifique-se de que você tenha este componente instalado, configurado e funcionando em sua instância do Home Assistant).
  - (opcional) Chave = **debug**, Valor = `True`. Defina esta variável para registrar as mensagens de depuração e permitir a variável de ambiente `home_assistant_token`.
  - (opcional, _não recomendado_) Chave = **home_assistant_token**, Valor = Seu Home Assistant Long-Lived Access Token. Você conectará sua skill Alexa à sua conta de usuário do Home Assistant nos próximos passos, então não precisará adicioná-lo aqui. No entanto, você pode adicioná-lo aqui para fins de depuração. _(Você deve remover e excluir essa variável de ambiente depois que a depuração terminar)_.
- Clique no botão **Save** no canto inferior direito.
- **Importante:** Se você estiver usando um modelo IA, ou a resposta da API do Home Assistant é `maior que 3 segundos` _(configuração padrão)_, você precisa aumentar o tempo limite da função Lambda, seguinido os passos abaixo:
  - Permaneça na aba `Configuração`, vá em `Configuração geral`, clique em `Editar` no canto direito do painel, agora edite as configurações básicas, no painel `Configurações básicas` e no campo `Tempo limite` você pode alterar para 30, 60 segundos ou o tempo que você precisar.
  - Clique em `Salvar` no canto inferior direito.

    ![](../en/images/lambda_timeout.png)

## Testar a Função Lambda
Agora que você criou a função Lambda, você vai fazer um teste básico.
- Navegue até a aba `Test`, depois selecione `Create new event`.
- Nomeie seu evento como preferir, por exemplo: `AssistTest`.
- Insira os seguintes dados na caixa de código chamada `Event JSON`:

```json
{
    "version": "1.0",
    "session": {
      "new": true,
      "sessionId": "SessionId.sample-session-id"
    },
    "context": {
      "System": {
        "application": {
          "applicationId": "amzn1.ask.skill.sample-application-id"
        },
        "user": {
          "userId": "amzn1.ask.account.sample-user-id",
          "accessToken": "sample-access-token"
        },
        "device": {
          "deviceId": "amzn1.ask.device.sample-device-id",
          "supportedInterfaces": {
            "Alexa.Presentation.APL": {}
          }
        }
      }
    },
    "request": {
      "type": "LaunchRequest",
      "requestId": "sample-request-id",
      "timestamp": "2024-10-18T00:00:00Z",
      "locale": "en-US"
    }
}
```

- Clique em `Save` no canto superior direito do painel.
- Faça login no Home Assistant e gere um `long-lived access token`. Depois de inserir seu long-lived access token na variável de ambiente `home_assistant_token` e definir a variável de ambiente `debug` para `True`, você pode executar o teste.
- Para testar, clique em `Test` no canto superior direito do painel.
- Se o teste correr bem e tudo estiver funcionando com sua função, o resultado aparecerá destacado em verde como `Executing function: succeeded`, o que significa que a skill foi iniciada corretamente.

  ![](../en/images/lambda_test.png)

## Configurar o Endpoint do Serviço da Skill
Agora, remova o `long-lived access token` _(se preferir, recomendado)_ das variáveis de ambiente e exclua-o do seu Home Assistant.
- Ainda no `AWS Console`, copie o `Function ARN` da sua função Lambda.
- Retorne ao `Alexa Developer Console` e vá para a página `Alexa Skills` _(se você ainda não estiver lá)_.
- Encontre a skill que você acabou de criar e clique no link `Edit` na lista suspensa `Actions`.
- Vá para `CUSTOM` > `Endpoint` na barra de navegação à esquerda da página `Build`.
- Cole o `Function ARN` copiado da sua função Lambda no campo `Default region` e clique no botão `Save` no canto superior direito.

  ![](../en/images/skill_endpoint.png)

## Vinculação de Conta
Alexa precisa vincular sua conta Amazon à sua conta do Home Assistant. Assim, o Home Assistant pode garantir que apenas solicitações autenticadas da Alexa possam acessar sua API.
Para vincular a conta, você precisa garantir que seu Home Assistant esteja acessível da Internet na porta 443.
- Retorne ao `Alexa Developer Console` e vá para a página `Alexa Skills` _(se você ainda não estiver lá)_.
- Encontre a skill que você acabou de criar e clique no link `Edit` na lista suspensa `Actions`.
- Clique em `ACCOUNT LINKING` na barra de navegação à esquerda da página `Build`.
- Marque o botão `Do you allow users to create an account or link to an existing account with you?`.
- Em `Settings`, desmarque a opção `Allow users to enable skill without account linking`.
- Role para baixo e certifique-se de que `Auth Code Grant` esteja selecionado.
- Insira todas as informações necessárias. Supondo que seu Home Assistant possa ser acessado por `https://[YOUR HOME ASSISTANT URL]`. Para a vinculação de conta Alexa, por padrão, a porta 443 é usada _(use seu firewall para redirecionar isso, se necessário)_:
  - **Your Web Authorization URI**: https://[YOUR HOME ASSISTANT URL]/auth/authorize
  - **Access Token URI**: https://[YOUR HOME ASSISTANT URL]/auth/token
  **Nota:** Embora seja possível atribuir uma porta diferente, a Alexa exige que você use a porta 443, então certifique-se de que seu firewall/proxy esteja redirecionando via porta 443. _(Leia mais na [documentação do desenvolvedor Alexa](https://developer.amazon.com/en-US/docs/alexa/smarthome/build-smart-home-skills-account-linking.html) sobre requisitos para vinculação de contas)_.
Apesar do aviso de isenção de responsabilidade da documentação da Alexa, os certificados `Let’s Encrypt` ainda são aceitos.
**Importante:** Você deve usar um `certificado SSL válido/confiável` para que a vinculação de contas funcione. Certificados autoassinados não funcionarão, mas você pode usar um certificado gratuito `Let’s Encrypt`.
  - **Your Client ID**:
    - https://pitangui.amazon.com/ se você estiver nas Américas.
    - https://layla.amazon.com/ se você estiver na Europa.
    - https://alexa.amazon.co.jp/ se você estiver no Japão ou Austrália _(não verificado ainda)_.

    **Importante:** A barra no final é importante _(não altere a URL acima)_.
  - **Your Secret**: Insira qualquer coisa que desejar; o Home Assistant não verifica este campo.
  - **Your Authentication Scheme**: Certifique-se de que selecionou `Credentials in request body`. _(O Home Assistant não suporta HTTP Basic)_.
  - Você pode deixar `Scope`, `Domain List` e `Default Access Token Expiration Time` em branco.
- Clique no botão `Save` no canto superior direito.
- Clique em `CUSTOM` na barra de navegação à esquerda da página `Build` e em `Build Skill` no canto superior direito.

  ![](../en/images/skill_accountlinking.png)

## Habilitar a Skill no App Alexa
- Você precisa usar o `Alexa Mobile App` para vincular sua conta.
  - No `app Alexa`, vá para `More` > `Skills & Games` > `Your Skills` -> `Dev`.
  - Clique na skill que você acabou de criar.
  - Clique em `Enable to use`.
  - Uma nova janela será aberta para direcioná-lo à tela de login do seu Home Assistant.
  - Depois de fazer login com sucesso, você será redirecionado de volta ao app Alexa.
  - Agora, você pode pedir à Alexa no seu dispositivo Echo ou no App Alexa para abrir a skill, como **Alexa, [seu Nome de Invocação]**.

## Localização da Alexa
A localização deve corresponder ao local e idioma usados em seus dispositivos Amazon Echo.
_Os locais suportados pela skill atualmente estão descritos na página principal._