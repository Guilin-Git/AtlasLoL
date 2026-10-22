# ADR-022 — Identidade interna e provedores de login desacoplados

Data: 2026-10-22

## Contexto

O AtlasLoL será usado por pessoas diferentes e precisa aceitar senha local,
Google, Discord e provedores futuros. A plataforma também armazena contas Riot
que não correspondem a usuários do produto, como pro players e jogadores de
coorte. Misturar essas três noções na mesma tabela inviabilizaria vínculo de
contas e produziria usuários duplicados.

## Alternativas consideradas

1. **Uma tabela `users` com `email`, `password_hash`, `google_id` e
   `discord_id`.** Simples no primeiro dia, mas cada novo provedor exige coluna
   e migration; também confunde e-mail com identidade.
2. **Usar o e-mail como identidade universal.** Descartada: e-mail pode mudar,
   faltar no provedor, não estar verificado ou pertencer a contas distintas que
   não devem ser unidas automaticamente.
3. **Fazer a conta Riot ser o usuário.** Descartada: pro players e coortes não
   usam o Atlas, e uma pessoa pode ter várias contas Riot.
4. **Confiar apenas no usuário de um provedor externo.** Descartada: vincula
   ownership, papéis e dados de produto ao fornecedor escolhido e dificulta
   migração de autenticador.
5. **Usuário interno com identidades externas em tabela própria.** Escolhida.

## Decisão

`app_users` será a entidade canônica de pessoa no AtlasLoL. Cada forma de
login será uma linha em `auth_identities`, identificada unicamente por
`(issuer, subject)`. E-mails ficam em `user_emails`; senha, se existir, fica
em `password_credentials`, com hash Argon2id.

Contas Riot serão modeladas posteriormente como outro domínio, ligável a um
usuário por tabela de associação, mas independente dele.

O banco não armazenará secrets de OAuth nem tokens de acesso de provedores sem
necessidade explícita. A escolha entre autenticação local e um serviço gerido,
como Cognito na AWS, fica para a etapa que implementará o fluxo de login; a
API preserva a mesma fronteira `issuer + subject` nos dois casos.

O desenho completo está em [`docs/modelo-identidade.md`](../modelo-identidade.md).

## Consequências

- Uma pessoa pode vincular ou remover provedores sem migrar colunas de usuário.
- A API pode mudar de provedor de autenticação sem reatribuir dados de produto.
- O primeiro login social cria uma identidade; vínculo de contas requer ação
  autenticada ou prova forte, nunca coincidência automática de e-mail.
- O primeiro schema fica maior que uma tabela de senha simples, mas suas
  relações representam o problema real e recebem constraints no banco.
- Login por senha só será entregue com controles próprios: hash lento,
  verificação de e-mail, recuperação, rate limit e mensagens que não enumeram
  usuários.

## Gatilho de revisão

- Necessidade de organizações, equipes ou recursos compartilhados: adicionar
  `workspaces` e `workspace_members`; não transformar `app_users` em tenant.
- Múltiplas aplicações Atlas com requisitos de privacidade entre elas: avaliar
  subject pairwise por cliente e a estratégia de `issuer`.
- Adoção definitiva de Cognito ou outro broker: decidir se sessões são JWT do
  emissor ou sessões opacas do Atlas; a identidade interna permanece igual.
