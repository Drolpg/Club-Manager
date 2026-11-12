# Especificação Técnica: Identidade e acesso

| Campo | Valor |
| --- | --- |
| Feature | `acesso/identidade-e-acesso` |
| Status | Approved |
| Responsável | Leandro Nascimento |
| Atualizado em | 2026-11-12 |
| Aprovado por | Leandro Nascimento |
| Aprovado em | 2026-11-12 |
| Especificação funcional | `./functional-spec.md` (aprovada em 2026-11-12) |
| Decisões aplicadas | ADR-001, ADR-003, ADR-004, ADR-005, ADR-006; ADR-008; AD-006, AD-009, AD-012, AD-015; TD-001 |

## Contexto e desenho

Dois módulos são tocados, mais a base técnica e o site.

| Módulo | O que ganha | Por quê |
| --- | --- | --- |
| `auditoria` | Modelo `RegistroDeAuditoria` e `public.registrar(...)` | A funcional antecipou a gravação da auditoria (P10). É o módulo mais baixo do mapa; não importa ninguém |
| `acesso` | Modelos `Usuario` e `Convite`, serviços, rotas, comando `criar_admin`, tarefas de e-mail e de limpeza | É o dono de identidade e login |
| `kernel` | Limite de tentativas (`rate_limit`) e leitura do IP do cliente | Infraestrutura sem regra de negócio, reutilizada depois por outros módulos |
| `config` | Sessões, autenticação, cache, e-mail, agenda do Celery | Configuração |
| `frontend` | Roteamento e as telas desta feature | — |

Comunicação entre módulos: `acesso` chama `auditoria.public.registrar` direto, na mesma transação (ADR-003). Não há
evento de integração nesta feature: o aviso aos admins é um e-mail enviado pelo próprio `acesso` (P9). O despachante
de eventos e o evento `CadastroConcluido` são criados no M4, quando `notificacoes` existir para reagir.

Camadas dentro de `acesso`, conforme `docs/architecture/project-structure.md`:

```text
acesso/
├── public.py            usuario_por_id, usuarios_admins_ativos (o que M3 e M4 vão consumir)
├── models.py            Usuario, Convite
├── domain/              funções puras: situação do convite, normalização, validação do nome de usuário
├── services/            convites, cadastro, sessao, senha, usuarios
├── google.py            port VerificadorGoogle e o adapter que valida o token do Google
├── http/                serializers, views, urls
├── tasks.py             enviar e-mails; descartar cadastros vencidos
├── management/commands/criar_admin.py
└── tests/
```

### Autenticação e sessão (ADR-008)

- **Site:** sessão do Django guardada no banco, em cookie `HttpOnly`, `Secure` e `SameSite=Lax`, com proteção CSRF.
  O site e a API estão na mesma origem (o proxy repassa `/api`), então não há CORS.
- **Validade:** 7 dias sem uso, renovada a cada requisição.
- **Encerramento imediato:** a sessão é conferida no banco a cada requisição. Usuário que não está `ATIVO` deixa de
  ser reconhecido na hora; trocar a senha invalida as sessões antigas (mecanismo padrão do Django).
- **Aplicativo futuro:** vai usar token opaco no cabeçalho `Authorization`, guardado no servidor como a sessão. Não é
  construído agora; as rotas não mudam.
- **Google:** o site usa o botão do Google Identity Services, que devolve um token de identidade. A API valida a
  assinatura, o público-alvo (o ID de cliente do clube), a validade e o campo `email_verified`. Não há redirecionamento
  nem troca de código no servidor.

### Fronteiras e fakes

| Fronteira | Port | Implementação real | Fake nos testes |
| --- | --- | --- | --- |
| Identidade Google | `VerificadorGoogle.verificar(credencial) -> IdentidadeGoogle` | Biblioteca `google-auth` | Classe em memória, configurada por teste |
| E-mail | A abstração de e-mail do Django (`MAILERS`, no Django 6.1) | SMTP, por variável de ambiente | Backend em memória do Django |

O provedor de e-mail de produção (AD-012) não é decidido aqui: basta um servidor SMTP qualquer, escolhido no M12. Em
desenvolvimento, os e-mails saem no log da `api` e do `worker`.

## Modelo de domínio

`acesso` é módulo de apoio: camadas, sem aggregate formal (ADR-001). As regras que dependem só de dados ficam em
funções puras.

### Usuario

| Campo | Tipo | Observação |
| --- | --- | --- |
| `id` | UUID versão 7 | Chave primária; padrão para os modelos do projeto |
| `nome` | Texto, até 120 | |
| `nome_de_usuario` | Texto, 3 a 30 | Único sem diferenciar maiúsculas (índice único sobre a forma minúscula) |
| `email` | E-mail | Único sem diferenciar maiúsculas |
| `telefone` | Texto, até 20 | Só dígitos e `+`; sem validação de operadora |
| `password` | Hash | Argon2 (ver dependências) |
| `situacao` | `AGUARDANDO_VERIFICACAO`, `ATIVO`, `INATIVO` | Só muda pelos métodos `verificar_email`, `desativar`, `reativar` |
| `admin` | Booleano | Só muda por `tornar_admin`, `remover_admin` |
| `google_sub` | Texto, opcional, único | Identificador da conta Google, gravado no primeiro uso |
| `email_verificado_em`, `criado_em`, `last_login` | Data e hora | |

Não há campo de cargo nem de setor: eles chegam no M3, no módulo `permissoes`. "Tem cargo?" na lista de usuários
(CA-27) responde "não" para todos até lá.

### Convite

| Campo | Tipo | Observação |
| --- | --- | --- |
| `id` | UUID versão 7 | |
| `token_hash` | SHA-256 do token | O token em claro só existe na resposta de gerar ou regenerar |
| `gerado_por_id` | UUID | Referência ao usuário |
| `gerado_em`, `expira_em` | Data e hora | `expira_em` = `gerado_em` + 24 horas |
| `usado_em`, `usado_por_id` | Opcionais | |
| `revogado_em` | Opcional | |
| `substitui_id` | Opcional | Convite que este regenerou |

A situação do convite não é gravada: é calculada por uma função pura, nesta ordem (o primeiro que casar vence):
`USADO` (tem `usado_em`), `REVOGADO` (tem `revogado_em`), `EXPIRADO` (agora ≥ `expira_em`), `ATIVO`. Por isso a
expiração não precisa de tarefa agendada e é exata.

### Regras verificadas no código

| ID | Regra | Onde |
| --- | --- | --- |
| ACE-R01 | Convite só é usado se a situação calculada é `ATIVO`; o uso bloqueia a linha do convite | `services/cadastro.py` |
| ACE-R02 | Nome de usuário e e-mail únicos sem diferenciar maiúsculas | Índices únicos funcionais; o serviço traduz a violação |
| ACE-R03 | Só usuário `ATIVO` autentica | Backend de autenticação |
| ACE-R04 | Ninguém desativa a si mesmo nem remove o próprio papel de admin | `services/usuarios.py` |
| ACE-R05 | Só admin ativo executa as ações de administração | Permissão `EhAdmin` nas views e conferência no serviço |
| ACE-R06 | Cadastro `AGUARDANDO_VERIFICACAO` com mais de 24 horas não verifica e é descartado | Função pura mais tarefa agendada |
| ACE-R07 | Toda ação da regra 19 da funcional grava auditoria na mesma transação | Serviços |

## Interfaces e fluxo de dados

Todas as rotas ficam sob `/api/v1/acesso/`. Corpo em JSON. Os nomes de recursos e campos são em português.

| Método e caminho | Quem | Entrada | Saída |
| --- | --- | --- | --- |
| `GET configuracao/` | Aberta | — | `{google_client_id}` (ou nulo) |
| `GET sessao/` | Aberta | — | Usuário logado ou `{usuario: null}`; define o cookie CSRF |
| `POST sessao/` | Aberta | `identificador`, `senha` | Usuário logado |
| `POST sessao/google/` | Aberta | `credencial` | Usuário logado |
| `DELETE sessao/` | Logado | — | 204 |
| `POST convites/` | Admin | — | Convite, com `link` (única vez) |
| `GET convites/` | Admin | — | Lista, com situação, quem gerou e quando |
| `POST convites/{id}/regenerar/` | Admin | — | Convite novo, com `link` |
| `POST convites/{id}/revogar/` | Admin | — | Convite |
| `POST convites/consultar/` | Aberta | `token` | 204 se ativo |
| `POST cadastros/` | Aberta | `token`, `nome`, `nome_de_usuario`, `telefone`, `email`, `senha` | 201 |
| `POST cadastros/google/` | Aberta | `token`, `credencial`, `nome`, `nome_de_usuario`, `telefone`, `senha` | 201, já logado |
| `POST verificacoes/` | Aberta | `token` | 204 |
| `POST verificacoes/reenviar/` | Aberta | `identificador` | 204, sempre |
| `POST senhas/recuperar/` | Aberta | `email` | 204, sempre |
| `POST senhas/redefinir/` | Aberta | `token`, `senha` | 204 |
| `GET usuarios/` | Admin | — | Lista, com situação, `admin` e `tem_cargo` |
| `POST usuarios/{id}/desativar/` · `reativar/` · `tornar-admin/` · `remover-admin/` | Admin | — | Usuário |

O token de convite vai no corpo, nunca na URL da API, para não ficar em log de acesso. No site, o link é
`/convite/<token>`; o site lê o token e o envia no corpo.

Comando: `python manage.py criar_admin`, interativo, que lê a senha sem ecoar.

| Situação | Código HTTP | Código de erro |
| --- | --- | --- |
| Convite usado, expirado, revogado ou inexistente | 404 | `CONVITE_INVALIDO` |
| Identificador ou senha errados, conta inexistente ou inativa | 401 | `CREDENCIAIS_INVALIDAS` |
| Login de conta que aguarda verificação, com a senha certa | 403 | `EMAIL_NAO_VERIFICADO` |
| Limite de tentativas ou de requisições | 429 | `MUITAS_TENTATIVAS` |
| Nome de usuário em uso | 409 | `NOME_DE_USUARIO_EM_USO` |
| E-mail em uso | 409 | `EMAIL_EM_USO` |
| Senha fora da política, ou campo inválido | 400 | `VALIDATION_ERROR` |
| Token de verificação ou de recuperação inválido ou vencido | 400 | `LINK_INVALIDO` |
| Credencial do Google inválida | 401 | `GOOGLE_INVALIDO` |
| Google com e-mail sem conta, no login | 403 | `ACESSO_SO_POR_CONVITE` |
| Google com e-mail que já tem conta, no cadastro | 409 | `CONTA_JA_EXISTE` |
| Desativar a si mesmo ou remover o próprio papel | 422 | `NAO_PODE_ALTERAR_A_SI_MESMO` |
| Usuário não encontrado | 404 | `NOT_FOUND` |
| Sem sessão | 401 | `NOT_AUTHENTICATED` |
| Logado, sem ser admin | 403 | `PERMISSION_DENIED` |

### Tokens de verificação e de recuperação

Sem tabela própria: são assinados pelo Django com a chave do sistema.

| Token | Mecanismo | Validade | Uso único |
| --- | --- | --- | --- |
| Verificação de e-mail | Assinatura com data (ID do usuário e e-mail) | 24 horas | A conta deixa de estar aguardando verificação |
| Recuperação de senha | Gerador de token de redefinição do Django | 1 hora | O token depende do hash da senha, que muda |

### E-mails

| E-mail | Para quem | Quando |
| --- | --- | --- |
| Verifique seu e-mail | O convidado | Cadastro com senha; reenvio |
| Redefinição de senha | O dono da conta | Pedido de recuperação de conta ativa |
| Diretor aguardando classificação | Todos os admins ativos | Conta ativada (CA-11 e CA-15) |

Os e-mails são enfileirados depois do commit. A tarefa recebe só o ID do usuário e o tipo, e gera o link na hora de
enviar: nenhum token passa pela fila.

### Limites

| Limite | Valor | Chave |
| --- | --- | --- |
| Tentativas de login erradas | 5 em 15 minutos | Conta (identificador normalizado) |
| Requisições às rotas abertas de escrita | 20 por minuto | IP do cliente |
| Reenvio de verificação e pedido de recuperação | 3 por hora | Conta ou e-mail |

Os contadores ficam no cache (Redis, que já existe).

## Persistência e dados

Migrações novas, todas reversíveis; nenhuma existente é alterada (não há nenhuma).

| Migração | Conteúdo |
| --- | --- |
| `auditoria/0001_registro_de_auditoria` | Tabela, índices por item e por ator, e um gatilho no banco que recusa `UPDATE` e `DELETE` |
| `acesso/0001_usuario_e_convite` | Tabelas `Usuario` e `Convite`, com os índices únicos funcionais |

Entram também as tabelas das aplicações do Django que passam a ser usadas: `contenttypes`, `auth` e `sessions`.

`RegistroDeAuditoria`: `id` (UUID 7), `ator_id` (opcional: nulo quando a ação vem do comando ou do sistema), `acao`
(código estável, como `CONVITE_GERADO`), `item_tipo`, `item_id`, `justificativa` (opcional), `dados` (JSON, sem dado
pessoal além de IDs) e `criado_em`. A modelagem geral da trilha (AD-009) é esta; a consulta entra no M3.

Classificação dos dados: **nenhum seed**. Não há usuário, senha nem convite criados por migração. Os testes usam as
próprias fixtures.

Dados pessoais guardados: nome, nome de usuário, telefone, e-mail, hash da senha, identificador do Google. Avaliação
em `docs/security/lgpd.md`.

## Segurança e operação

Modelo de ameaças: `docs/security/threat-model.md` (STRIDE, feito para este marco conforme `docs/method.md`).

| Tema | Decisão |
| --- | --- |
| Senhas | Argon2; validadores do Django para tamanho mínimo 10, senha comum, só números e semelhança com os dados do usuário |
| Enumeração de contas | Respostas iguais em login, recuperação e reenvio; tempo de resposta do login nivelado calculando o hash mesmo quando a conta não existe |
| Enumeração no cadastro | `NOME_DE_USUARIO_EM_USO` e `EMAIL_EM_USO` revelam existência a quem tem um convite válido. Aceito: o convite é entregue pelo admin a uma pessoa conhecida, e a rota tem limite por IP |
| Sessão | Cookie `HttpOnly`, `Secure` fora de depuração, `SameSite=Lax`; CSRF em toda escrita; nova chave de sessão no login |
| Tokens | Convite com 32 bytes aleatórios, guardado só como hash; nunca em log, auditoria ou fila |
| Autorização | Negada por padrão; rotas abertas declaram `AllowAny`; rotas de admin exigem `EhAdmin` na view e no serviço |
| IP do cliente | Lido do cabeçalho do proxy, confiando em exatamente um proxy (o Caddy) |
| Logs | Sem e-mail, telefone, senha, token ou credencial; só IDs |
| Documentação da API | `schema/` e `docs/` passam a exigir admin logado, e os arquivos do Swagger passam a ser servidos pela própria imagem. Encerra a TD-001 |
| LGPD | Aviso de privacidade no cadastro, com o texto de `docs/security/lgpd.md` |

Configuração nova (entra em `docs/setup/configuration.md` e no `.env.example`):

| Variável | Obrigatória | O que é |
| --- | --- | --- |
| `SITE_URL` | Sim | Endereço público do site, usado nos links dos e-mails |
| `GOOGLE_CLIENT_ID` | Não | ID de cliente do Google; sem ele, o botão do Google não aparece e as rotas do Google respondem `GOOGLE_INVALIDO` |
| `EMAIL_URL` | Em produção | Servidor SMTP (`smtp://usuário:senha@host:porta`); sem ela, os e-mails saem no log |
| `DEFAULT_FROM_EMAIL` | Em produção | Remetente |

O dono precisa criar o ID de cliente no Google Cloud Console (gratuito) para usar o login com Google; o passo a passo
entra em `docs/setup/`.

Dependências novas, aprovadas com esta spec:

| Dependência | Onde | Para quê |
| --- | --- | --- |
| `google-auth` | Backend | Validar o token de identidade do Google |
| `argon2-cffi` | Backend | Hash de senha Argon2, recomendado pelo Django |
| `drf-spectacular-sidecar` | Backend | Servir os arquivos do Swagger sem CDN (TD-001) |
| `react-router` | Site | Roteamento das telas |

Operação: a tarefa `acesso.descartar_cadastros_vencidos` roda de hora em hora e é idempotente. Rollback: as migrações
revertem; não há dado de produção.

## Estratégia de testes

| Camada | O que cobre | Tipo de teste |
| --- | --- | --- |
| Funções puras | Situação do convite (as quatro, e a precedência), normalização de identificador, validação do nome de usuário, vencimento do cadastro | Unitário, sem banco |
| Serviços | Cada cenário da funcional, incluindo concorrência no uso do convite, ACE-R01 a ACE-R07 e a gravação de auditoria | Integração com PostgreSQL |
| Contrato | Cada rota: sucesso, cada código de erro da tabela, autorização (aberta, logado, admin) e CSRF | Integração HTTP |
| Persistência | Unicidade sem diferenciar maiúsculas; gatilho que recusa alterar e apagar auditoria; reversão das migrações | Integração com PostgreSQL |
| Fronteiras | `acesso` só importa `auditoria.public`; `acesso/domain` sem framework | Teste de arquitetura existente |
| Tarefas | Descarte de cadastros vencidos executado duas vezes; e-mails enviados depois do commit | Integração, com a fila em modo imediato |
| Comando | `criar_admin` com dados válidos e inválidos | Integração |
| Site | Cada tela: caminho feliz e as mensagens de erro por código | Vitest e Testing Library, com a API simulada |

Tempo: os testes fixam o relógio substituindo `timezone.now`; nenhuma dependência nova para isso. Google: sempre o
fake. E-mail: backend em memória.

Cada critério de aceite CA-01 a CA-36 tem ao menos um teste, e a matriz CA → teste fica no plano de implementação.

## Documentação a atualizar

- [ ] Contrato gerado (anotações das rotas novas)
- [ ] `docs/api/README.md`: como autenticar (sessão, CSRF) e os códigos de erro
- [ ] Guia de teste manual do fluxo completo, em `docs/api/manual-testing.md`
- [ ] `docs/setup/configuration.md` e `.env.example`: variáveis novas
- [ ] `docs/setup/`: como criar o ID de cliente do Google e o primeiro admin
- [ ] `docs/architecture/stack-profile.md`: dependências novas, UUID 7 como chave primária
- [ ] `docs/architecture/project-structure.md`: placeholders resolvidos
- [ ] Registro de requisitos, decisões (AD-006, AD-009, AD-015) e TD-001

## Adendos

Nenhum.
