# Perfil de stack

| Campo | Valor |
| --- | --- |
| Status | Approved |
| Atualizado em | 2026-11-11 |
| Aprovado por / em | Leandro Nascimento / 2026-11-12 |
| Decisões | ADR-001 (estilo), ADR-003 (integração), ADR-004 (backend), ADR-005 (site), ADR-006 (filas), ADR-007 (repositório e CI) |

As versões são as resolvidas em 2026-11-11; a fonte exata é `backend/uv.lock` e `frontend/package-lock.json`.

## Ferramentas do backend

| Preocupação | Ferramenta | Versão | Comando | Observação |
| --- | --- | --- | --- | --- |
| Build e execução | uv, Python | 0.12, 3.14 | `uv sync`, `uv run …` | Lockfile versionado |
| Framework | Django, Django REST Framework | 6.1, 3.18 | `uv run python manage.py …` | ADR-004 |
| Regras de dependência | import-linter e teste com grimp | 2.16 | `uv run poe imports`, `tests/test_architecture.py` | Rodam em toda verificação |
| Checagem de tipos | mypy (strict), django-stubs, djangorestframework-stubs | 2.4 | `uv run poe types` | |
| Testes unitários | pytest | 9.2 | `uv run pytest` | Funções de decisão testadas sem banco |
| Integração com banco real | pytest-django com o PostgreSQL do compose | 4.14 | `uv run pytest` | Sem SQLite; no CI, contêiner de serviço |
| Testes HTTP | `APIClient` do DRF | — | `uv run pytest` | |
| Cobertura | pytest-cov | 7.1 | Parte do `pytest` | Meta: 80%, com ramos |
| Migrations | Migrações do Django | — | `uv run python manage.py makemigrations` | Convenção abaixo; `poe migrations-check` falha se faltar migração |
| Contrato de API gerado | drf-spectacular, com `drf-spectacular-sidecar` | 0.30 | — | Em `/api/v1/schema/` e `/api/v1/docs/`, só para admin logado; sem CDN |
| Validação na borda | Serializers do DRF | — | — | Só validam e formatam (ADR-004) |
| Eventos em processo | Despachante próprio, síncrono | — | — | Criado no M4, quando `notificacoes` reagir ao cadastro concluído (ADR-003) |
| Fila e agendador | Celery, Redis | 5.7, 8 | `celery -A config worker -B` | ADR-006 |
| Lint e formatação | Ruff | 0.17 | `uv run poe lint`, `uv run poe format` | Inclui as regras de segurança `S` (Bandit) |
| SCA | pip-audit | 2.10 | `uv run poe audit` | Roda no CI |
| SAST | Regras `S` do Ruff | — | `uv run poe lint` | |
| DAST | A definir | — | — | Avaliar no M12, guiado pelo contrato |
| Servidor | gunicorn, WhiteNoise | 27, 6.12 | Comando da imagem | Dois processos |
| Senhas | Argon2 (`argon2-cffi`) | — | — | Nos testes, o mesmo algoritmo com custo mínimo (`tests/hashers.py`) |
| Sessão | Sessões do Django no banco, com CSRF | — | — | ADR-008 |
| Login com Google | `google-auth` | — | — | Atrás da port `VerificadorGoogle`; fake nos testes |
| E-mail | `MAILERS` do Django 6.1, SMTP por `EMAIL_URL` | — | — | Sem `EMAIL_URL`, sai no log; nos testes, em memória |
| Limite de tentativas | `kernel.rate_limit`, no cache (Redis) | — | — | Nos testes, cache em memória |

## Ferramentas do site

| Preocupação | Ferramenta | Versão | Comando | Observação |
| --- | --- | --- | --- | --- |
| Build e execução | Node, npm, Vite | 22, 10, 8 | `npm run dev`, `npm run build` | Lockfile versionado |
| Biblioteca de interface | React | 19 | — | ADR-005 |
| Roteamento | React Router | 8 | — | |
| Checagem de tipos | TypeScript | 7 | `npm run types` | |
| Testes | Vitest, Testing Library, jsdom | 5, 16, 31 | `npm test` | |
| Cobertura | Cobertura v8 do Vitest | 5 | `npm run coverage` | Meta: 80% |
| Lint | oxlint | 1.9x | `npm run lint` | Padrão do gerador do Vite; avisos falham |
| SCA | `npm audit` | — | `npm audit --audit-level=high` | Roda no CI |
| Servidor | Caddy | 2 | Imagem `club-manager-web` | Serve o site e repassa `/api` |

## Comandos do dia a dia

| Para | Comando |
| --- | --- |
| Subir tudo localmente | `docker compose up --build` (na raiz) |
| Subir só banco e Redis, para rodar os testes | `docker compose up -d db redis` |
| Rodar os testes do backend | `uv run pytest` (em `backend/`) |
| Verificação completa do backend | `uv run poe verify` (em `backend/`) |
| Rodar os testes do site | `npm test` (em `frontend/`) |
| Verificação completa do site | `npm run verify` (em `frontend/`) |
| Criar o `.env` com segredos aleatórios | `uv run python scripts/make_env.py` (em `backend/`) |

A verificação completa do projeto são os dois comandos `verify`. O CI roda exatamente os mesmos.

## Convenções

- **Pacotes:** um pacote de topo por módulo, direto em `backend/` (`financeiro`, `aprovacoes`…), mais `config` e
  `kernel`.
- **Nomes:** domínio em português sem acento (`Cobranca`, `validar_pagamento`); infraestrutura em inglês
  (`services`, `public`, `settings`, `tasks`). Estados em maiúsculas (`EM_VALIDACAO`).
- **Rotas:** tudo sob `/api/v1/`. Os nomes de recursos e campos de domínio na API ficam em português.
- **Erros:** envelope `{"error": {"code", "message", "details"}}`. O código de regra de negócio é o do canvas do
  aggregate (`NAO_ESTA_EM_ANALISE`); os técnicos são em inglês (`VALIDATION_ERROR`, `NOT_FOUND`).
- **Migrations:** pasta `<modulo>/migrations/`, geradas pelo Django e nomeadas com `--name` descritivo em português
  (`0002_cobranca_limite_de_inadimplencia`). Toda migração tem reversão; a que não puder ter é registrada como
  decisão.
- **Estilo:** linhas de até 110 colunas; formatação do Ruff; sem imports curinga (exceto em `settings_test.py`).
- **Injeção de dependência:** nenhuma. As fronteiras trocam por configuração do Django.
- **Chaves primárias:** UUID versão 7 (`uuid.uuid7`), em todos os modelos.
- **Referência entre módulos:** por ID (campo UUID), sem chave estrangeira; dentro do módulo, chave estrangeira
  normal. A auditoria guarda só IDs.
- **Depois do commit:** e-mail e trabalho pesado são enfileirados com `transaction.on_commit`; a tarefa recebe só
  IDs e nunca um token.

## Mapeamento de conceitos

| Conceito do método | Neste projeto |
| --- | --- |
| Módulo (bounded context) | Aplicação Django de topo, com `public.py` como única porta para os outros módulos |
| Aggregate root | Modelo do Django com métodos de negócio; o estado só muda por eles (ADR-001) |
| Entity dentro do aggregate | Modelo filho, alterado só pelos métodos da raiz |
| Value object | `@dataclass(frozen=True)` validado em `__post_init__`, em `<modulo>/domain/` |
| Função de decisão | Função pura em `<modulo>/domain/`, sem import de Django, DRF ou Celery |
| Port | A abstração do Django (armazenamento, e-mail); `Protocol` só onde não houver uma |
| Permissão | Código `<recurso>.<acao>` declarado com `permissoes.public.registrar_permissao` no `ready`; conferida com `permissoes.public.pode` (a rota de escrita declara quem pode: permissão do catálogo, admin, ou condição da spec; conferido na rota e no serviço) |
| Porta de consulta (módulo de baixo pergunta ao de cima) | Função com padrão seguro no módulo de baixo, substituída por `registrar_portas` no `ready` do de cima (adendo 1 da ADR-003) |
| Evento de integração | `@dataclass(frozen=True)` publicado no despachante em processo (ADR-003) |
| Transação do caso de uso | `transaction.atomic()` na função de serviço, com a linha do aggregate bloqueada |
| Erro de negócio → código estável | `kernel.errors.BusinessError(code, message)` → envelope com HTTP 422 (ou o status informado) |
| Dinheiro | `Decimal` com duas casas dentro do value object `Dinheiro`; `DecimalField` no banco; texto na API |
