# Estrutura do projeto

| Campo | Valor |
| --- | --- |
| Atualizado em | 2026-11-11 |
| Estilo | Monólito modular, DDD tático no core, camadas no resto — [ADR-001](../adr/ADR-001-estilo-arquitetural.md) |

## Árvore

```text
.
├── compose.yaml              Sobe o sistema inteiro
├── compose.override.yaml     Só em desenvolvimento: expõe portas do banco, do Redis e da API
├── .env.example              Variáveis de ambiente, sem valores reais
├── backend/                  API e worker (uma imagem, dois comandos)
│   ├── config/               Configuração do Django, rotas de topo, aplicação Celery
│   ├── kernel/               Base técnica: erros, saúde, logs. Não conhece nenhum módulo
│   ├── auditoria/            ┐
│   ├── acesso/               │
│   ├── permissoes/           │
│   ├── notificacoes/         │
│   ├── marca/                │ Um pacote por módulo do desenho estratégico
│   ├── aprovacoes/           │ (docs/domain/strategic-design.md)
│   ├── comunicacao/          │
│   ├── financeiro/           │
│   ├── eventos/              │
│   ├── relatorios/           ┘
│   ├── tests/                Testes da base técnica e de arquitetura
│   └── scripts/              Utilitários de desenvolvimento
├── frontend/                 Site (React, Vite, TypeScript)
│   └── src/
│       ├── api/              Cliente da API; nenhuma regra de negócio
│       └── test/             Configuração dos testes
└── docs/                     Método, enunciado, domínio, requisitos, decisões
```

### Dentro de um módulo

Os arquivos são criados quando a primeira feature do módulo precisar deles. Hoje cada módulo tem só `apps.py` e
`public.py`.

```text
<modulo>/
├── public.py        API pública em processo: o único arquivo que outros módulos importam
├── models.py        Modelos. Nos módulos core, os aggregates, com os métodos de negócio
├── domain/          Só nos módulos com regra: funções de decisão e value objects, sem framework
├── services.py      Casos de uso: abre a transação, checa a permissão, chama o aggregate, registra auditoria
├── http/            Transporte: serializers, views e urls. Sem regra de negócio
├── handlers.py      Tratadores de eventos de integração de módulos abaixo (ADR-003)
├── tasks.py         Tarefas do Celery; só chamam um serviço
├── migrations/      Migrações do Django
└── tests/           Testes do módulo
```

`services.py`, `http/` e `domain/` viram pacotes quando crescerem; a regra de quem importa quem não muda.

## Módulos ou pacotes

| Módulo / pacote | Responsabilidade | Pode importar |
| --- | --- | --- |
| `config` | Configuração, rotas de topo, Celery | Tudo |
| `relatorios` | Dashboards, perfil e relatórios; só leitura | `public` de todos os módulos |
| `eventos` | Eventos e calendário | `public` de `financeiro`, `aprovacoes` e dos de baixo |
| `financeiro` | Cobranças, pagamentos, entradas, saídas | `public` de `aprovacoes` e dos de baixo |
| `aprovacoes` | Motor de solicitações | `public` de `notificacoes`, `permissoes`, `acesso`, `auditoria` |
| `comunicacao` | Feed e documentos | Idem |
| `marca` | Escudo, cores, temas | Idem |
| `notificacoes` | Notificações, caixa de entrada, e-mail | `public` de `permissoes`, `acesso`, `auditoria` |
| `permissoes` | Cargos, setores, permissões, concessões | `public` de `acesso`, `auditoria` |
| `acesso` | Usuários, convites, login | `public` de `auditoria` |
| `auditoria` | Trilha imutável | `kernel` |
| `kernel` | Erros, saúde, logs | Nenhum módulo |

`aprovacoes`, `comunicacao` e `marca` estão no mesmo nível e não se importam.

## Regras de dependência

| Regra | Como é verificada |
| --- | --- |
| Um módulo só importa os que estão abaixo dele no context map | Contrato `layers` do import-linter (`uv run poe imports`) |
| De outro módulo, só se importa `<modulo>.public` | `tests/test_architecture.py::test_modulo_so_importa_a_api_publica_de_outro_modulo` |
| Todo módulo tem `public.py` | `tests/test_architecture.py::test_todo_modulo_tem_api_publica` |
| `<modulo>.domain` não importa Django, DRF, Celery nem drf-spectacular | `tests/test_architecture.py::test_pacotes_de_dominio_nao_importam_framework` |
| `kernel` não conhece nenhum módulo | `tests/test_architecture.py::test_kernel_nao_conhece_os_modulos` |
| Rota sem permissão declarada é negada | Permissão padrão do DRF; `tests/test_errors.py::test_rota_sem_permissao_explicita_e_negada_por_padrao` |
| Não há migração pendente | `uv run poe migrations-check` |

Todas rodam em `uv run poe verify`, na máquina e no CI.

Regras ainda sem verificação automática, conferidas na revisão de cada feature:

- views e serializers sem regra de negócio, e escrita sempre por um serviço (ADR-004);
- estado de aggregate alterado só pelos métodos dele (ADR-001);
- chave estrangeira entre módulos só para o usuário; as demais referências entre módulos são por ID. Esta regra é
  proposta e é confirmada na primeira technical-spec com modelo (M2).

## Placeholders

| Placeholder | Onde | Feature que vai criá-lo |
| --- | --- | --- |
| Conteúdo de cada `public.py` | `backend/<modulo>/public.py` | A primeira feature de cada módulo (M2 a M11) |
| Despachante de eventos em processo | `backend/kernel/` | M2 (`CadastroConcluido`) |
| Value object `Dinheiro` | `backend/kernel/` ou `financeiro/domain/` | M5 (valor da solicitação); o lugar é decidido na technical-spec |
| Autenticação e usuário | `backend/acesso/` | M2 (AD-006) |
| Armazenamento de anexos | Configuração `STORAGES` | M6 (AD-011) |
| Envio de e-mail | Configuração de e-mail do Django | M2 (AD-012) |
| Roteamento, componentes e temas do site | `frontend/src/` | M2 e M11 |
