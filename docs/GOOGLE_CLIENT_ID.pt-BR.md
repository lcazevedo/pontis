# Criando um `client_id` OAuth do Google Drive para o Pontis

Por padrão, o `rclone` utiliza um `client_id` global compartilhado entre todos os usuários do mundo, o que frequentemente causa limites de cota na API do Google (`403 rateLimitExceeded` ou lentidão ao listar pastas).

Criar o seu próprio **`client_id` e `client_secret` gratuitos no Google Cloud** garante cota exclusiva para a sua conta e deixa a sincronização muito mais rápida e estável.

---

## Passo 1: Criar um projeto no Google Cloud

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/).
2. Clique no seletor de projetos no topo e selecione **Novo projeto** (*New Project*).
3. Dê um nome (por exemplo, `Pontis-Drive-Sync`) e clique em **Criar**.
4. Certifique-se de que o projeto recém-criado está selecionado na barra superior.

## Passo 2: Ativar a Google Drive API

1. No menu lateral esquerdo, acesse **APIs e serviços → Biblioteca** (*APIs & Services → Library*).
2. Pesquise por **Google Drive API**.
3. Clique em **Google Drive API** e depois em **Ativar** (*Enable*).

## Passo 3: Configurar a tela de consentimento OAuth

1. Acesse **APIs e serviços → Tela de permissão OAuth** (*OAuth consent screen* / *Google Auth platform*).
2. Escolha **Externo** (*External*) como tipo de usuário (a menos que use Google Workspace corporativo apenas para uso interno) e clique em **Criar**.
3. Preencha os campos obrigatórios:
   - **Nome do app:** `Pontis Sync` (ou qualquer nome pessoal).
   - **E-mail de suporte:** seu endereço de e-mail.
   - **Dados de contato do desenvolvedor:** seu endereço de e-mail.
4. Na etapa de **Escopos** (*Scopes*), adicione `.../auth/drive` (ou prossiga e deixe o `rclone` solicitar o escopo na autorização).
5. Na etapa de **Usuários de teste** (*Test users / Audience*), clique em **Adicionar usuários** e inclua **o seu próprio e-mail do Google**.
   > 💡 Manter o app em modo **Em teste** (*Testing*) evita passar pela verificação pública do Google. Porém, no modo *Testing*, os tokens de atualização expiram em **7 dias** (exigindo nova autorização). Se preferir não reautorizar semanalmente, você pode clicar em **Publicar aplicativo** para uso pessoal próprio — ao autorizar no navegador, o Google exibirá o aviso *"Este app não foi verificado pelo Google"*, onde basta clicar em **Avançado → Acessar ... (não seguro)**, pois o projeto OAuth é seu.

## Passo 4: Criar as credenciais OAuth para Desktop

1. Acesse **APIs e serviços → Credenciais** (*Credentials*).
2. Clique em **+ Criar credenciais → ID do cliente OAuth** (*OAuth client ID*).
3. Em **Tipo de aplicativo**, selecione **App para computador** (*Desktop app*).
4. Dê um nome (por exemplo, `Pontis Linux Desktop`) e clique em **Criar**.
5. Copie o **ID do cliente** (`client_id`) e a **Chave secreta do cliente** (`client_secret`).

## Passo 5: Configurar no Pontis

### Opção A: Criar um novo remoto pelo CLI do Pontis

```bash
pontis remote add gdrive drive \
  --param client_id=SEU_CLIENT_ID.apps.googleusercontent.com \
  --param client_secret=SEU_CLIENT_SECRET
```

O navegador será aberto para você fazer login e autorizar o acesso à sua conta Google. Ao concluir, teste a conexão:

```bash
pontis remote test gdrive
```

### Opção B: Importar de um `rclone.conf` já existente

Se você já configurou um remoto com `client_id` próprio no `rclone config`, importe-o diretamente para a configuração isolada do Pontis (`~/.config/pontis/rclone.conf`):

```bash
pontis remote import --remote gdrive
pontis remote test gdrive
```

---

## Boas práticas de segurança

- Mantenha seu `client_secret` privado e nunca envie `~/.config/pontis/rclone.conf` para o Git.
- O Pontis salva seu `rclone.conf` com permissão `0600` e remove quaisquer credenciais ao exportar perfis (`pontis profile export`).
