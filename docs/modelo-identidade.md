# Modelo de identidade e contas — AtlasLoL

Data: 2026-10-22  
Estado: desenho aprovado para orientar as primeiras migrations; nenhuma tabela
deste documento existe ainda.

## Objetivo e fronteiras

O AtlasLoL terá pessoas diferentes usando a plataforma, cada uma podendo ter
mais de uma forma de entrar (senha, Google, Discord e provedores futuros) e
mais de uma conta Riot. Esses conceitos não são a mesma coisa:

```text
app_users ──< user_emails
    |
    +──< auth_identities ── 0..1 password_credentials
    |
    +──< user_riot_accounts >── riot_accounts
```

- `app_users` é a pessoa dentro do produto e é dona dos seus dados.
- `auth_identities` informa como essa pessoa provou sua identidade.
- `riot_accounts` representa qualquer conta Riot conhecida — de usuário,
  pro player ou jogador de coorte — mesmo sem conta na plataforma.

O banco não armazena tokens OAuth, segredos de clientes Google/Discord nem
senha em texto. Segredos de integração pertencem ao ambiente/Vault. Tokens só
serão considerados quando houver um caso de uso que realmente exija acesso à
API de um provedor em nome do usuário.

## Tabelas da primeira migration de identidade

### `app_users`

| Coluna | Tipo | Regra | Motivo |
|---|---|---|---|
| `id` | `uuid` | PK; gerado pela aplicação | Identificador interno que nunca muda nem revela volume de usuários. |
| `display_name` | `text` | nulo inicialmente | Nome editável de interface; não é login nem chave. |
| `status` | `text` | `active`, `suspended` ou `deleted` | Permite bloquear uma conta sem apagar relações e auditoria. |
| `created_at` | `timestamptz` | obrigatório | Auditoria e ordenação. |
| `updated_at` | `timestamptz` | obrigatório | Registro de alterações de perfil/estado. |

Índices: a chave primária já atende as relações. Um índice adicional em
`(status)` só será criado se consultas administrativas por estado se tornarem
frequentes; hoje seria índice sem benefício.

### `user_emails`

| Coluna | Tipo | Regra | Motivo |
|---|---|---|---|
| `id` | `uuid` | PK | Permite ter e-mail histórico/adicional sem depender do texto como chave. |
| `user_id` | `uuid` | FK para `app_users(id)` | Dono do endereço. |
| `email` | `text` | obrigatório, valor informado | Preserva a forma apresentada pela pessoa. |
| `email_normalized` | `text` | obrigatório, único | Forma canônica usada na busca de login e na prevenção de duplicidade. |
| `verified_at` | `timestamptz` | nulo até confirmação | Um e-mail recebido de OAuth não é automaticamente uma prova de controle. |
| `is_primary` | `boolean` | obrigatório, padrão `false` | Endereço preferencial para comunicação e login local. |
| `created_at` | `timestamptz` | obrigatório | Auditoria. |
| `updated_at` | `timestamptz` | obrigatório | Auditoria. |

Restrições e índices:

- `UNIQUE (email_normalized)`: um endereço ativo pertence a uma única conta;
- índice em `user_id`: carregar os e-mails do perfil não faz varredura;
- índice único parcial em `user_id WHERE is_primary`: no máximo um principal
  por usuário;
- a aplicação normaliza com `strip().lower()`; validação de entrega e domínio
  não é inferida pelo banco.

Não haverá um campo `email` em `app_users`: duplicá-lo criaria duas fontes de
verdade quando a pessoa mudar seu endereço.

### `auth_identities`

| Coluna | Tipo | Regra | Motivo |
|---|---|---|---|
| `id` | `uuid` | PK | Identificador da relação de autenticação. |
| `user_id` | `uuid` | FK para `app_users(id)` | Usuário interno autenticado por essa identidade. |
| `issuer` | `text` | obrigatório | Namespace que emitiu a identidade, por exemplo `https://accounts.google.com`, `https://discord.com` ou `atlaslol.local`. |
| `subject` | `text` | obrigatório | Identificador imutável dentro do emissor: `sub` do OIDC, ID Discord, ou UUID aleatório para senha local. |
| `created_at` | `timestamptz` | obrigatório | Quando o método foi vinculado. |
| `last_authenticated_at` | `timestamptz` | nulo inicialmente | Apoia segurança e suporte sem guardar tokens. |

Restrições e índices:

- `UNIQUE (issuer, subject)`: a mesma conta Google/Discord/local não pode
  apontar para duas pessoas Atlas;
- índice em `user_id`: permite mostrar e remover métodos ligados ao perfil;
- não existe `google_id`, `discord_id` ou enum de provedores. Adicionar um
  provedor torna-se inserir uma nova linha, não alterar o schema;
- o par `issuer + subject`, e nunca o e-mail ou apelido, resolve uma
  autenticação federada.

Para senha local, `issuer` será `atlaslol.local` e `subject` será um UUID
aleatório. Isso evita tratar e-mail como identificador imutável.

### `password_credentials`

Esta tabela pertence ao desenho inicial, mas pode entrar na migration seguinte
quando o fluxo de senha, recuperação e e-mail estiver pronto.

| Coluna | Tipo | Regra | Motivo |
|---|---|---|---|
| `identity_id` | `uuid` | PK e FK para `auth_identities(id)` | Uma credencial por identidade local. |
| `password_hash` | `text` | obrigatório | Saída completa do Argon2id, incluindo parâmetros e salt. |
| `password_changed_at` | `timestamptz` | obrigatório | Invalidação e auditoria após troca. |
| `created_at` | `timestamptz` | obrigatório | Auditoria. |
| `updated_at` | `timestamptz` | obrigatório | Auditoria. |

O hash codifica o algoritmo e seus parâmetros. Não serão criadas colunas para
salt, senha, chave de criptografia ou algoritmo duplicado. A aplicação impede
que uma credencial seja associada a uma identidade cujo `issuer` não seja
`atlaslol.local`.

## Regras de vínculo e login

1. Primeiro login por Google ou Discord: cria `app_users`, uma
   `auth_identities` e, se houver e-mail, uma entrada em `user_emails` ainda
   sujeita à regra de verificação aplicável.
2. Novo login com a mesma combinação `issuer + subject`: encontra exatamente o
   mesmo usuário interno.
3. Adicionar Google/Discord a uma conta existente: a pessoa precisa estar
   autenticada na conta atual e concluir o fluxo do novo provedor. Não haverá
   mesclagem automática apenas por igualdade de e-mail.
4. Senha local: a pessoa informa um e-mail já verificado da própria conta; a
   aplicação localiza o usuário, cria uma identidade `atlaslol.local` e grava
   apenas o hash Argon2id em `password_credentials`.
5. Remoção de identidade: só é permitida se restar outro método de login ativo.
   A regra evita bloquear o próprio usuário fora da conta.

## Contas Riot pesquisáveis e vínculos pessoais

Uma busca por Riot ID é pública e não depende de haver uma conta Atlas. Ao
receber `gameName#tagLine` e a plataforma escolhida, a API resolve o PUUID na
Riot, cria ou atualiza a conta no nosso catálogo e devolve seu perfil. O PUUID
é a chave estável; Riot ID é a forma humana de encontrá-la e pode mudar.

### `riot_accounts`

| Coluna | Tipo | Regra | Motivo |
|---|---|---|---|
| `id` | `uuid` | PK | Identificador interno para relações do produto. |
| `puuid` | `text` | obrigatório, único | Identificador estável devolvido pela Riot e usado para partidas. |
| `game_name` | `text` | nulo | Riot ID observado mais recentemente; não é chave. |
| `tag_line` | `text` | nulo | Parte observada mais recentemente do Riot ID; não é chave. |
| `current_platform` | `text` | nulo | Plataforma atual para endpoints de League, por exemplo `BR1`. |
| `first_seen_at` | `timestamptz` | obrigatório | Quando Atlas conheceu a conta. |
| `last_refreshed_at` | `timestamptz` | nulo | Permite aplicar cache e evitar chamadas Riot desnecessárias. |
| `created_at` | `timestamptz` | obrigatório | Auditoria. |
| `updated_at` | `timestamptz` | obrigatório | Auditoria. |

Restrições e índices:

- `UNIQUE (puuid)` é a identidade canônica no catálogo;
- índice de busca em `(lower(game_name), lower(tag_line))`; ele acelera
  resultados já conhecidos, mas não substitui a resolução oficial na Riot;
- `current_platform` não participa de identidade: uma transferência pode
  atualizá-la sem criar outra conta;
- o histórico de Riot IDs será uma tabela futura (`riot_id_observations`) se a
  experiência exigir mostrar renomes. Não vale armazenar histórico antes de
  haver essa funcionalidade.

### `user_riot_account_links`

| Coluna | Tipo | Regra | Motivo |
|---|---|---|---|
| `user_id` | `uuid` | FK para `app_users(id)` | Dono da coleção pessoal. |
| `riot_account_id` | `uuid` | FK para `riot_accounts(id)` | Perfil Riot fixado ou escolhido pela pessoa. |
| `link_kind` | `text` | obrigatório, padrão `self_reported` | Explicita a intenção: conta declarada como própria, favorita ou outro uso futuro. |
| `is_default` | `boolean` | obrigatório, padrão `false` | Define a conta aberta no dashboard pessoal. |
| `verified_at` | `timestamptz` | nulo | Só é preenchido por método de comprovação real. |
| `verification_method` | `text` | nulo | Registra como a verificação ocorreu, sem assumir que ela existe hoje. |
| `created_at` | `timestamptz` | obrigatório | Auditoria. |

Chave e índices:

- `PRIMARY KEY (user_id, riot_account_id)`: a mesma conta aparece uma vez na
  coleção de cada usuário;
- índice único parcial em `user_id WHERE is_default`: somente uma conta padrão
  por usuário;
- várias pessoas podem fixar a mesma conta pública; isso não cria cópias de
  partidas nem de estatísticas.

**Importante:** digitar um Riot ID ou buscá-lo não prova propriedade. No início,
o produto chamará isso de “adicionar ao meu dashboard” ou “conta declarada”.
`verified_at` só poderá ser usado se adotarmos um mecanismo Riot de autorização
apropriado e permitido para o produto. A chave pessoal da Riot autoriza nossa
aplicação a consultar a API; ela não autentica o jogador final.

## Sessões e autorização: deliberadamente posteriores

As tabelas abaixo não entrarão na primeira migration porque ainda não há fluxo
que as use. O desenho já prevê seus vínculos para evitar retrabalho.

| Domínio futuro | Tabelas previstas | Regra estrutural |
|---|---|---|
| Sessão | `auth_sessions` | Cookie/ticket opaco no cliente; somente o hash do token fica no banco, com expiração e revogação. Se Cognito for o emissor definitivo de sessão, essa tabela pode não ser necessária. |
| Autorização | `roles`, `user_roles` | Papéis são dados, não uma coluna booleana `is_admin`; ownership de recursos continua por `user_id`. |
| Recuperação/verificação | `auth_action_tokens` | Tokens de uso único serão guardados somente como hash, com propósito, expiração e consumo. |

## Ordem de implementação

1. Migration manual: `app_users`, `user_emails`, `auth_identities`,
   `riot_accounts` e `user_riot_account_links`, com os índices e constraints
   deste documento.
2. Teste Alembic: `upgrade` → `downgrade` → `upgrade`, sem dados de domínio.
3. Endpoints internos de leitura de usuário, ainda sem login público.
4. Escolher e implementar o emissor de autenticação e as sessões.
5. Adicionar `password_credentials` somente junto com rate limit, mensagens
   genéricas de erro, recuperação de senha e envio/verificação de e-mail.
6. Adicionar histórico de Riot IDs e dados processados de partidas quando as
   consultas precisarem deles.

O objetivo não é impedir migrations futuras. É garantir que as próximas sejam
aditivas e localizadas, em vez de exigirem renomear a base inteira por confundir
usuário, e-mail, provedor e conta Riot.
