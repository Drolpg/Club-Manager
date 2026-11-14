# Configuração

Referência. Tudo que varia por ambiente vem de variável de ambiente; não há valor de segredo no código nem senha
padrão. O modelo é o `.env.example`, na raiz.

## Variáveis

| Variável | Usada por | Obrigatória | Padrão | O que é |
| --- | --- | --- | --- | --- |
| `POSTGRES_DB` | `db`, `api`, `worker` | Não | `clubmanager` | Nome do banco |
| `POSTGRES_USER` | `db`, `api`, `worker` | Não | `clubmanager` | Usuário do banco |
| `POSTGRES_PASSWORD` | `db`, `api`, `worker` | Sim | — | Senha do banco; o compose não sobe sem ela |
| `DJANGO_SECRET_KEY` | `api`, `worker` | Sim | — | Chave do Django; a aplicação não inicia sem ela |
| `DJANGO_DEBUG` | `api`, `worker` | Não | `0` | `1` liga a depuração; nunca em produção |
| `DJANGO_ALLOWED_HOSTS` | `api` | Em produção | `localhost,127.0.0.1` | Domínios aceitos, separados por vírgula |
| `SITE_URL` | `api`, `worker` | Sim | `http://localhost:8080` no compose | Endereço público do site, usado nos links de convite e nos e-mails |
| `EMAIL_URL` | `api`, `worker` | Em produção | vazio | Servidor SMTP: `smtp://usuário:senha@host:587` ou `smtps://…:465`. Vazio: os e-mails saem no log. `smtp://host:porta?tls=0` desliga a criptografia e existe só para o Mailpit; é a única opção aceita depois do `?`, e só em `smtp://`. Em desenvolvimento, o `compose.override.yaml` aponta a `api` e o `worker` para o Mailpit (`smtp://mailpit:1025?tls=0`), mesmo que o `.env` tenha um valor |
| `DEFAULT_FROM_EMAIL` | `api`, `worker` | Em produção | `Club Manager <nao-responda@localhost>` | Remetente dos e-mails |
| `GOOGLE_CLIENT_ID` | `api` | Não | vazio | ID de cliente do Google ([google.md](google.md)). Vazio: login com Google desligado |
| `WEB_PORT` | `web` | Não | `8080` | Porta do site na máquina |
| `IMAGE_TAG` | `api`, `worker`, `web` | Não | `dev` | Versão das imagens; em produção, a tag publicada |
| `LOG_LEVEL` | `api`, `worker` | Não | `INFO` | Nível do log |
| `APROVACOES_TIPO_DE_DEMONSTRACAO` | `api`, `worker`, só em desenvolvimento | Não | `0` | `1` registra o tipo de solicitação `demonstracao.pedido` e a permissão `demonstracao.aprovar`, para percorrer o ciclo de aprovação no navegador antes de existir um tipo de verdade (M7). Só vale com `DJANGO_DEBUG=1`; com `DJANGO_DEBUG=0` é ignorada, mesmo definida. Só o `compose.override.yaml` a repassa aos contêineres; o `compose.yaml` (produção) não. Para usar: dê a permissão a um diretor no painel de permissões e envie a solicitação pela API (`POST /api/v1/aprovacoes/solicitacoes/`, com `tipo` `demonstracao.pedido` e `conteudo` `{"descricao": …, "valor": "150.00"}`) ou pelo shell do Django (`aprovacoes.public.enviar`) |

Montadas pelo `compose.yaml` a partir das de cima, e lidas pela aplicação:

| Variável | Valor no compose | O que é |
| --- | --- | --- |
| `DATABASE_URL` | `postgres://<usuário>:<senha>@db:5432/<banco>` | Conexão com o banco; obrigatória para a aplicação |
| `REDIS_URL` | `redis://redis:6379/0` | Fila do Celery e contadores de tentativas |

Só no desenvolvimento do site:

| Variável | Padrão | O que é |
| --- | --- | --- |
| `API_PROXY_TARGET` | `http://127.0.0.1:8000` | Para onde o Vite repassa `/api` |

## Testes

Os testes usam `config/settings_test.py`, que fixa a chave e a depuração e monta o `DATABASE_URL` com a senha do
`.env`, apontando para `127.0.0.1:5433`. No CI, o `DATABASE_URL` vem do workflow.

## Onde cada valor é definido

| Ambiente | Onde |
| --- | --- |
| Local | `.env` na raiz, criado por `backend/scripts/make_env.py` |
| CI | No próprio workflow; o banco é descartável e não usa segredo |
| Produção | A definir no M12 (AD-013) |
