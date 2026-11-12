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
| `WEB_PORT` | `web` | Não | `8080` | Porta do site na máquina |
| `IMAGE_TAG` | `api`, `worker`, `web` | Não | `dev` | Versão das imagens; em produção, a tag publicada |
| `LOG_LEVEL` | `api`, `worker` | Não | `INFO` | Nível do log |

Montadas pelo `compose.yaml` a partir das de cima, e lidas pela aplicação:

| Variável | Valor no compose | O que é |
| --- | --- | --- |
| `DATABASE_URL` | `postgres://<usuário>:<senha>@db:5432/<banco>` | Conexão com o banco; obrigatória para a aplicação |
| `REDIS_URL` | `redis://redis:6379/0` | Fila do Celery |

Só no desenvolvimento do site:

| Variável | Padrão | O que é |
| --- | --- | --- |
| `API_PROXY_TARGET` | `http://127.0.0.1:8000` | Para onde o Vite repassa `/api` |

## Testes

Os testes usam `config/settings_test.py`, que fixa a chave e a depuração e monta o `DATABASE_URL` com a senha do
`.env`, apontando para `localhost:5433`. No CI, o `DATABASE_URL` vem do workflow.

## Onde cada valor é definido

| Ambiente | Onde |
| --- | --- |
| Local | `.env` na raiz, criado por `backend/scripts/make_env.py` |
| CI | No próprio workflow; o banco é descartável e não usa segredo |
| Produção | A definir no M12 (AD-013) |
