# Método do projeto

> Lido pelo Claude no início de cada sessão (`sdd-method:guiding-projects`). Mantenha atualizado: é o estado do
> projeto.

## Configuração

| Campo | Valor |
| --- | --- |
| Projeto | Club Manager |
| Tipo de projeto | Sistema de domínio rico (com API e workers assíncronos como componentes) |
| Nível de processo | 2 — Padrão, com um elemento do nível 3 (ver "Desvios do método") |
| Estilo de arquitetura | Monólito modular, DDD tático no core (`aprovacoes`, `financeiro`, `eventos`), camadas no resto — `docs/adr/ADR-001-estilo-arquitetural.md` |
| Trilha de domínio | DDD completo restrito ao core, com o rito 3 simplificado |
| Situações | solo, com tracker (GitHub Issues), com board (Miro, a conectar), em fases |
| Idioma da documentação | pt-BR |
| Idioma dos nomes no código | Domínio na língua do negócio (português), infraestrutura em inglês |
| Stack | Python 3.14, Django 6.1, DRF, PostgreSQL 18, Celery e Redis; React 19, Vite, TypeScript — `docs/architecture/stack-profile.md` |
| Comando de verificação completa | `uv run poe verify` em `backend/` e `npm run verify` em `frontend/` |
| Meta de cobertura | 80%, no backend e no site |
| Git | `CONTRIBUTING.md` — modelo `main` + `dev`, sem trailer de IA |
| Board / tracker | Issues criadas marco a marco, na especificação de cada um, e não todas de uma vez. Miro: conector autorizado em 2026-11-11, ferramentas ainda não disponíveis na sessão; URL a registrar. Tracker: <https://github.com/Drolpg/Club-Manager/issues> |
| Prazo | Sem prazo fixo |
| IDs de requisitos | `RF-NN` (funcional), `RNF-NN` (não funcional) e `RN-NN` (regra de negócio), atribuídos no rito 6; cada um cita o ID de origem do enunciado (ex.: FIN-05) |
| Aprovado por / em | Leandro Nascimento / 2026-11-11 |

## Equipe

| Pessoa | Papel | Escopo | Aprova |
| --- | --- | --- | --- |
| Leandro Nascimento | Dono do projeto e único desenvolvedor | Tudo | Todos os gates, specs e decisões |
| Claude (agente) | Executor | Propõe, especifica, implementa e revisa | Nada: o agente nunca aprova |

## Mapa de artefatos

| Artefato | Caminho |
| --- | --- |
| Enunciados e entregáveis | `docs/challenge/` |
| Charter | `docs/project-charter.md` |
| Índice da documentação | `docs/README.md` |
| Avaliação e decisão de arquitetura | `docs/adr/` e `docs/architecture/` (avaliação, visão geral, estrutura, perfil de stack) |
| Guias de setup | `docs/setup/` |
| Requisitos | `docs/requirements/` |
| Specs, planos e tarefas por marco | `docs/features/<contexto>/<slug>/` |
| Domínio (se o estilo pedir) | `docs/domain/` |
| Decisões e débitos | `docs/decision-register.md`, `docs/adr/`, `docs/rfc/`, `docs/tech-debt/` |
| Segurança | `docs/security/` (um relatório por marco) |
| Auditorias de coerência | `docs/audits/` |
| Testes | `backend/tests/`, `backend/<modulo>/tests/`, `frontend/src/**/*.test.ts(x)` |
| Notas fora do git | `docs/_local/` |

## Estado dos ritos

| # | Rito | Aplica-se? | Status | Concluído em | Aprovado por | Artefatos |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | Fundação | Sim | Concluído | 2026-11-11 | Leandro Nascimento | `docs/method.md`, `docs/challenge/phase-1.md`, `docs/project-charter.md`, `docs/README.md`, `docs/decision-register.md`, `AGENTS.md`, `CLAUDE.md` |
| 1 | Git e colaboração | Sim | Concluído | 2026-11-11 | Leandro Nascimento | `CONTRIBUTING.md`, `.github/pull_request_template.md` |
| 2 | Avaliação de arquitetura | Sim | Concluído (preliminar e confirmação) | 2026-11-11 | Leandro Nascimento | `docs/architecture/assessment.md`, `docs/adr/ADR-001-estilo-arquitetural.md` |
| 3 | Descoberta do domínio | Sim, só o core | Concluído — Simplificado (entrevista guiada) | 2026-11-11 | Leandro Nascimento | `docs/domain/discovery/domain-storytelling.md`, `event-storming.md`, `hotspots.md` |
| 4 | Desenho estratégico | Sim, sistema inteiro | Concluído | 2026-11-11 | Leandro Nascimento | `docs/domain/strategic-design.md`, `context-map.md`, `ubiquitous-language.md`, `docs/adr/ADR-003-integracao-entre-contextos.md` |
| 5 | Desenho tático | Sim, só `aprovacoes`, `financeiro` e `eventos` | Concluído | 2026-11-11 | Leandro Nascimento | `docs/domain/aggregates/`, `docs/domain/domain-events.md`, `docs/domain/domain-model.md` |
| 6 | Especificação | Sim | Concluído (registro de requisitos; as specs de feature são escritas marco a marco, no rito 8) | 2026-11-11 | Leandro Nascimento | `docs/requirements/requirements.md`, `epics.md`, `definition-of-ready-done.md`, `backlog.md` |
| 7 | Arquitetura base | Sim | Concluído | 2026-11-12 | Leandro Nascimento | `backend/`, `frontend/`, `compose.yaml`, `.github/workflows/`, `docs/architecture/`, `docs/setup/`, ADR-004 a ADR-007; CI verde na `dev` (execuções `backend` e `frontend` de 2026-11-12) |
| 8 | Entrega incremental | Contínuo | Próximo: M2 | | | |

Status: `Pendente`, `Em andamento`, `Concluído`, `Não se aplica (estilo)`, `Simplificado (<motivo>)`,
`Pulado (<motivo>)`.

## Fases

| Fase | Enunciado | Entrega | Status | Auditoria |
| --- | --- | --- | --- | --- |
| 1 (etapa 1: diretores, no site) | `docs/challenge/phase-1.md` | Sem prazo fixo | Em andamento | M1: `docs/audits/2026-11-12-coherence.md`; M2: `docs/audits/2026-11-13-coherence.md` |

## Marcos da fase 1

Os marcos vêm da seção 14 do enunciado. O M0 corresponde aos ritos 0 a 6 (até as especificações dos marcos seguintes);
o M1 corresponde ao rito 7; do M2 em diante, cada marco passa pelo rito 8 (spec, plano, tarefas, implementação,
validação), com revisão de segurança e auditoria de coerência ao fim.

| Marco | Entregável | Status | Concluído em | Aprovado por |
| --- | --- | --- | --- | --- |
| M0 Arquitetura | E1 | Concluído | 2026-11-11 | Leandro Nascimento |
| M1 Fundação | E2 | Concluído (`v0.1.0`) | 2026-11-12 | Leandro Nascimento |
| M2 Identidade e acesso | E3 | Concluído (`v0.2.0`) | 2026-11-13 | Leandro Nascimento |
| M3 Permissões e auditoria | E4 | Em andamento (especificação) | | |
| M4 Notificações | E5 | Especificado; aguardando implementação | | |
| M5 Motor de aprovações | E6 | Especificado; aguardando implementação | | |
| M6 Financeiro: entradas | E7 | Funcional aprovada (2026-11-13) | | |
| M7 Financeiro: saídas | E8 | Funcional aprovada (2026-11-13) | | |
| M8 Eventos | E9 | Funcional aprovada (2026-11-13) | | |
| M9 Feed, documentos e perfil | E10 | Pendente | | |
| M10 Dashboard e relatórios | E11 | Pendente | | |
| M11 Personalização | E12 | Pendente | | |
| M12 Produção | E13 | Pendente | | |

## Índice do board

Links para o board seguem sempre `<URL do board>/?moveToWidget=<ID>`; trocar de board é um único replace.

Board ainda não criado: o layout de frames será proposto quando o Miro estiver acessível na sessão.

| Frame | ID | Espelha | Tipo |
| --- | --- | --- | --- |

## Desvios do método

| Data | Desvio | Motivo | Aprovado por |
| --- | --- | --- | --- |
| 2026-11-11 | Threat model (STRIDE), elemento do nível 3, feito uma vez no M2 | O sistema guarda dados pessoais e financeiros e o enunciado pede avaliação de LGPD (RNF-07) | Leandro Nascimento |
| 2026-11-11 | Rito 3 simplificado: entrevista guiada sobre os fluxos do core e os hotspots da seção 15 do enunciado, sem Event Storming completo | Projeto solo; o enunciado já traz glossário, estados e fluxos | Leandro Nascimento |
| 2026-11-11 | Texto literal do enunciado em arquivo próprio (`docs/challenge/phase-1-enunciado.md`), e não dentro de `phase-1.md` | O enunciado tem títulos e numeração de seções próprios, citados pelos requisitos | Leandro Nascimento |
