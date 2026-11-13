# AGENTS.md — Club Manager

Instruções do projeto para pessoas e agentes de código. O projeto segue o plugin `sdd-method`; o nível, o estilo de
arquitetura e o estado dos ritos e dos marcos ficam em `docs/method.md`.

## Antes de tudo

1. Leia `docs/method.md`, depois os requisitos (`docs/requirements/`) e a feature ou o marco atual
   (`docs/features/`).
2. **A spec é a fonte da verdade.** Se código e spec divergirem, pare e reporte; não corrija em silêncio.
3. O enunciado literal está em `docs/challenge/phase-1-enunciado.md`. Ele define resultados, não o desenho interno.

## Contexto do projeto

- O Club Manager é um sistema de governança financeira e institucional de um time de futebol, usado pelos diretores:
  entradas e saídas escriturais, aprovação formal de gastos e eventos, e rastreabilidade de quem fez o quê e quando.
- Restrições do enunciado: custo mínimo (uma única instância AWS); só ambientes local e produção; API única que serve
  o site e depois o app, com regras de negócio, permissões e auditoria sempre na API; nada é apagado; não coletar CPF.
- Etapas futuras (app mobile, torcedor e jogador, gestão do time, multi-cliente) não são implementadas, mas nada pode
  impedi-las.
- O protótipo antigo está em `_prototipo/`, fora do git (ADR-002). É só consulta: nada dele é requisito nem ponto de
  partida de arquitetura, e nada dele é copiado para o projeto novo.
- Idioma da documentação: pt-BR. Nomes no código: domínio na língua do negócio (português, por exemplo `Cobranca`,
  `Solicitacao`, `Isencao`), infraestrutura em inglês (`repository`, `settings`, `tasks`).
- Stack: Python 3.14, Django 6.1 e DRF no backend, com uv (`uv run …`, em `backend/`); React 19, Vite e TypeScript
  no site, com npm (em `frontend/`); PostgreSQL, Celery e Redis. Perfil completo em
  `docs/architecture/stack-profile.md`; estrutura de pastas em `docs/architecture/project-structure.md`. Não adicione
  dependências fora da stack sem perguntar.
- No Windows, rode os comandos do site num terminal aberto em `C:\…` com a letra maiúscula (ver
  `docs/setup/local.md`).

## Regras de arquitetura

Estilo: monólito modular, com DDD tático nos módulos core (`aprovacoes`, `financeiro`, `eventos`) e camadas nos
demais — decisão em `docs/adr/ADR-001-estilo-arquitetural.md`, avaliação em `docs/architecture/assessment.md`.

- Um módulo de topo por área de negócio. Um módulo só importa a API pública de outro, nunca os modelos ou os serviços
  internos. A verificação de fronteira roda no CI.
- As dependências entre módulos são acíclicas. `aprovacoes` não conhece `financeiro` nem `eventos`; quem usa o motor
  se registra nele como tipo de solicitação.
- Dentro de um módulo: a camada de API não tem regra de negócio; os serviços abrem a transação, checam a permissão e
  registram a auditoria; as funções de decisão são puras e não importam o framework.
- Nos módulos core, o aggregate é o modelo persistido, e o estado só muda pelos métodos dele.
- Toda ação relevante registra auditoria na mesma transação do caso de uso.
- Tarefas agendadas são idempotentes: rodar duas vezes não duplica cobrança nem notificação.
- Ports só nas fronteiras reais: e-mail, armazenamento de anexos, identidade Google e canais de notificação. Use a
  abstração do framework quando ela existir.
- De outro módulo, importe só `<modulo>.public`. As funções de decisão ficam em `<modulo>/domain/` e não importam
  Django, DRF nem Celery.
- Views e serializers do DRF só validam a entrada, chamam um serviço e formatam a saída. Não use `ModelViewSet` nem
  `ModelSerializer` que gravem direto no modelo; declare os campos de saída (ADR-004).
- Uma tarefa do Celery só chama um serviço do módulo dono (ADR-006).
- Toda rota é negada por padrão; a que for aberta declara a permissão explicitamente.
- Toda rota de escrita declara quem pode: uma permissão do catálogo (`permissoes.public.pode`), o admin,
  ou uma condição que a spec define (ter cargo, ser o dono do item). A conferência é feita na rota e no
  serviço. Um módulo declara as suas permissões com `registrar_permissao` ao iniciar.

**Não adicionar** (decidido contra; adicionar qualquer um exige nova decisão):

- port ou repository para o banco, ou núcleo sem ORM;
- entidade de domínio separada do modelo de persistência, ou mapper entre as duas;
- interactors, presenters ou DTOs de boundary;
- ports para o que não é fronteira (relógio, banco, framework);
- container de injeção de dependência;
- aggregates, value objects ou eventos de domínio fora de `aprovacoes`, `financeiro` e `eventos`;
- mensageria entre módulos, barramento de eventos ou outbox;
- event sourcing, ou CQRS com read models;
- um segundo serviço de backend;
- coluna de cliente (tenant) ou schema por cliente;
- port de pagamento.

Os gatilhos que reabrem cada item estão na ADR-001.

### Bounded contexts

Fonte: `docs/domain/strategic-design.md`, `docs/domain/context-map.md` e `docs/adr/ADR-003-integracao-entre-contextos.md`.

| Contexto | Tipo | Módulos | Pode importar a API pública de |
| --- | --- | --- | --- |
| Auditoria | Generic | `auditoria` | — |
| Identidade e Permissões | Supporting | `acesso`, `permissoes` | `auditoria` |
| Notificações | Generic | `notificacoes` | `acesso`, `auditoria` |
| Marca | Generic | `marca` | `permissoes`, `auditoria` |
| Aprovações | Core | `aprovacoes` | `permissoes`, `notificacoes`, `auditoria` |
| Financeiro | Core | `financeiro` | `aprovacoes` e os de cima |
| Eventos | Core | `eventos` | `financeiro`, `aprovacoes` e os de cima |
| Comunicação | Supporting | `comunicacao` | `permissoes`, `notificacoes`, `auditoria` |
| Relatórios | Supporting | `relatorios` | todos, só para leitura |

- Para um contexto de cima na tabela: chamada direta à API pública. Para um de baixo: evento de integração em
  processo, síncrono e na mesma transação. Hoje só existem dois: decisão de solicitação e cadastro concluído.
- E-mail e trabalho pesado são enfileirados depois do commit.
- `relatorios` nunca altera dados de outro contexto.

### Linguagem

Use os termos de `docs/domain/ubiquitous-language.md`, inclusive a coluna "Não usar". Em especial: só solicitações são
aprovadas, só pagamentos são validados, só saídas são liquidadas, só eventos são realizados; o devedor questiona uma
cobrança e o aprovador contesta uma solicitação; o termo é permissão, nunca regra, role ou privilégio.

Sempre:

- Mude estado por funções ou métodos que revelam a intenção, não por atualizações de campo espalhadas pelas camadas.
- Dinheiro em tipo decimal; nunca ponto flutuante.
- Nunca exponha entidades de persistência como contrato da API; valide a entrada na fronteira.
- Registros liquidados são imutáveis; estorno e cancelamento são lançamentos novos ligados ao original.
- Nada é apagado: desative, cancele ou estorne.

## Fluxo guiado por spec

- Toda feature não trivial começa em `docs/features/<contexto>/<slug>/`: functional-spec → aprovação humana →
  technical-spec → aprovação humana → implementation-plan → implementação com evidência.
- Um agente nunca infere nem concede aprovação. Aprovação é explícita, do dono, registrada com nome e data.
- Mudança material numa spec aprovada devolve a spec a Draft.
- Um marco por vez, na ordem de `docs/method.md`. As pendências da seção 15 do enunciado são decididas no refinamento
  do marco, perguntando ao dono quando não houver hipótese razoável.

## Desenvolvimento guiado por testes

- Os testes são o critério de aceite. Escreva-os primeiro e veja-os falhar pelo motivo certo.
- **Nunca edite testes, configuração de teste ou a spec para fazer algo passar.** Se um teste parecer errado,
  explique por quê e espere a decisão.
- Todo requisito tem pelo menos um teste; a matriz requisito → teste fica atualizada.
- Fakes só em fronteiras reais; banco real nos testes de integração; sem rede real em testes unitários.
- Os fluxos críticos (aprovação, validação, permissões, recorrência) têm cobertura reforçada, porque não há ambiente
  de homologação.
- Rode o teste alvo, depois a verificação completa antes de dizer que uma tarefa terminou:
  `uv run poe verify` em `backend/` e `npm run verify` em `frontend/`. O banco dos testes é o PostgreSQL do compose
  (`docker compose up -d db redis`).
- Meta de cobertura: 80%. Não reduza a cobertura do código alterado.

## Dados persistidos

- Migrações versionadas e reversíveis são o único mecanismo de schema: migrações do Django, em
  `<modulo>/migrations/`, com `--name` descritivo. `uv run poe migrations-check` falha se faltar uma.
- A produção nunca deixa o ORM criar ou atualizar o schema.
- Backup do banco antes de qualquer mudança com dados em produção.
- Seeds: dados de demonstração só atrás de uma flag explícita de desenvolvimento; os testes usam as próprias
  fixtures. Nenhum usuário ou senha padrão.

## Erros, logs e segurança

- Erros para o cliente usam envelope e código estáveis; nunca stack trace, SQL ou mensagem interna.
- Logs são estruturados, carregam ID de correlação e nunca contêm dados pessoais, tokens ou segredos.
- Segredos só por variável de ambiente; `.env` e `docs/_local/` nunca vão para o git.
- Acesso a anexos sempre controlado por permissão.
- Toda feature registra uma revisão de segurança (`sdd-method:reviewing-security`); cada marco fecha com um relatório.

## Lições da implementação

Erros que já aconteceram neste projeto. Confira cada um antes de dizer que terminou.

- **Confira o código de saída da verificação.** Encadear `verify | grep … && git commit` deixa o commit sair com a
  verificação falhando. Rode a verificação, leia a saída e só então faça o commit.
- **Não rode a suíte do backend e a do site ao mesmo tempo:** os testes do site ficam instáveis.
- **Meça o assunto do commit:** até 72 caracteres.
- **Linhas de até 110 colunas**, inclusive em comentários, docstrings e textos longos.
- **Testes de um módulo não importam os internos de outro.** Para criar usuários, use `backend/tests/apoio.py`; as
  fixtures comuns estão em `backend/conftest.py`.
- **O que roda depois do commit não roda sozinho nos testes.** Veja o padrão em
  `backend/acesso/tests/test_cadastro.py`.
- **`localhost` no Windows tenta IPv6 primeiro.** Use `127.0.0.1` para o banco e o Redis de desenvolvimento.
- **Suba o sistema de verdade antes de fechar um marco.** O CI não sobe os contêineres, e dois defeitos só
  apareceram assim: uma dependência que faltava na imagem e a falha de CSRF fora do formato de erro.
- **Diga o que não foi validado.** Um relato com "não conferi X" vale mais do que um "tudo certo" incompleto.

## Decisões

- `docs/decision-register.md`, `docs/adr/`, `docs/rfc/`, `docs/tech-debt/`.
- O próximo número é sempre o maior existente + 1.
- Toda decisão registra o que foi escolhido e o que foi descartado. Só o dono muda um status para aceito ou resolvido.

## Estilo de código

- Funções pequenas e coesas, nomes explícitos, validação cedo em vez de condicionais aninhados.
- Comentários explicam decisões não óbvias, não o que o código diz.
- Sem abstrações especulativas, interfaces sem uso ou pacotes genéricos de utilitários.
- Backend: Ruff para formato e lint, mypy em modo estrito, linhas de até 110 colunas. Site: oxlint e `tsc`.

## Git

Branches, commits e pull requests seguem o `CONTRIBUTING.md`. Um ciclo verde = um commit. Nunca faça push ou merge na
`main` sem autorização explícita.

## Ao terminar uma tarefa, responda com

1. Arquivos criados ou alterados.
2. Comandos executados e os resultados.
3. Decisões não óbvias, em até cinco linhas, com o porquê.
4. Qualquer divergência em relação à spec.
