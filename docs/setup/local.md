# Subir o sistema localmente

Tutorial. Os comandos foram executados em Windows 11 com Docker Desktop, em 2026-11-11.

## Pré-requisitos

| Ferramenta | Versão usada | Para quê |
| --- | --- | --- |
| Docker Desktop | 29 | Subir o sistema e o banco dos testes |
| uv | 0.12 | Ambiente e dependências do backend (ele instala o Python 3.14) |
| Node e npm | 22 e 10 | Dependências e testes do site |

## 1. Criar o `.env`

Na pasta `backend/`:

```text
uv sync
uv run python scripts/make_env.py
```

O script copia `.env.example` para `.env`, na raiz, com senha do banco e chave do Django aleatórias. Ele não
sobrescreve um `.env` que já exista. O `.env` não vai para o git.

## 2. Subir tudo

Na raiz do repositório:

```text
docker compose up --build
```

Sobem cinco serviços: `db`, `redis`, `api`, `worker` e `web`. A `api` aplica as migrações ao iniciar.

Como verificar:

| O quê | Onde | Resultado esperado |
| --- | --- | --- |
| Site | <http://localhost:8080> | Tela "Entrar" |
| Saúde da API | <http://localhost:8080/api/v1/health/> | `{"status":"ok","database":"ok"}` |
| Documentação da API | <http://localhost:8080/api/v1/docs/> | Sem login, erro `NOT_AUTHENTICATED`; logado como admin, a página do Swagger |
| Serviços | `docker compose ps` | Os seis com estado `Up` (o sexto é o `mailpit`, só em desenvolvimento); `db`, `redis` e `api` como `healthy` |
| E-mails de desenvolvimento | <http://localhost:8025> | A caixa do Mailpit, vazia no começo |
| Worker | `docker compose logs worker` | Linha terminando em `ready.` |

Para parar: `docker compose down`. Para apagar também os dados do banco local: `docker compose down --volumes`.

## 3. Criar o primeiro admin

O sistema nasce vazio e só se entra por convite gerado por um admin. O primeiro admin é criado por um comando,
que pede os dados na hora (não existe senha padrão):

```text
docker compose exec api python manage.py criar_admin
```

Resultado esperado: `Admin <nome de usuário> criado.` O mesmo comando cria outro admin se todos perderem o
acesso. O roteiro completo de teste do acesso está em [api/manual-testing.md](../api/manual-testing.md).

Em desenvolvimento os e-mails não saem para a internet: chegam ao Mailpit, que os mostra em <http://localhost:8025>,
com o link já inteiro e clicável. O SMTP do Mailpit (porta 1025) fica só na rede interna do compose, e a página
(8025) só responde em `127.0.0.1`. Em produção não há Mailpit: o `compose.yaml` não o contém.

## 4. Rodar os testes

Os testes do backend usam o PostgreSQL do compose, exposto na porta 5433. Basta o banco estar no ar:

```text
docker compose up -d db redis
```

Backend, em `backend/`:

```text
uv run poe verify
```

Roda formato, lint, tipos, fronteiras de módulo, migrações pendentes e testes com cobertura. Resultado esperado: a
última linha é `N passed`, com cobertura acima de 80%.

Site, em `frontend/`:

```text
npm install
npm run verify
```

Roda lint, tipos, testes com cobertura e build.

## 5. Desenvolver o site com recarga automática

Com o sistema no ar (passo 2), em `frontend/`:

```text
npm run dev
```

O Vite abre em <http://localhost:5173> e repassa `/api` para a API em `127.0.0.1:8000`.

## Problemas conhecidos

| Sintoma | Causa | Solução |
| --- | --- | --- |
| `Vitest failed to find the current suite` ao rodar os testes do site | No Windows, o terminal está numa pasta com a letra da unidade minúscula (`c:\…`) | Abra o terminal em `C:\…` (maiúscula): `Set-Location 'C:\projects_dro\Club-Manager\frontend'` |
| `VIRTUAL_ENV … does not match the project environment` ao usar o uv | Há outro ambiente virtual ativo no terminal | É só um aviso; o uv usa o `.venv` do `backend/`. Para sumir, desative o outro ambiente |
| `failed to connect to the docker API` | O Docker Desktop não está aberto | Abra o Docker Desktop, ou rode `docker desktop start` |
| Testes do backend falham com erro de senha do banco | O volume do banco foi criado com outra senha | `docker compose down --volumes` e suba de novo |
| Os testes do backend ficam parados, sem terminar | Algo aponta para `localhost`, que no Windows tenta IPv6 primeiro; as portas de desenvolvimento só atendem em `127.0.0.1` | Use `127.0.0.1` no `DATABASE_URL` e no `REDIS_URL` |
| O link copiado do log do `worker` dá "link inválido" | Só sem o Mailpit (por exemplo, `docker compose -f compose.yaml up`): o e-mail sai no log, codificado, com as linhas longas quebradas com `=` no fim | Use o Mailpit (<http://localhost:8025>) ou junte as linhas, tirando o `=` do fim de cada uma |
| O Mailpit não mostra o e-mail | O sistema subiu só com o `compose.yaml`, que não tem o Mailpit | Suba com `docker compose up -d` (aplica o `compose.override.yaml`); confira com `docker compose ps` |
| O editor marca linhas com mais de 79 colunas | O linter padrão do editor não lê a configuração do projeto | O limite do projeto é 110 (Ruff, em `backend/pyproject.toml`); use a extensão do Ruff no editor |
