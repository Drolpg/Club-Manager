# Especificações de features

Um diretório por feature não trivial, agrupado por bounded context: `docs/features/<contexto>/<feature-slug>/`. Use
`platform` para mudanças transversais que não pertencem a um contexto.

Os documentos são criados em sequência, cada um sobre o anterior aprovado:

1. `functional-spec.md` — comportamento desejado e critérios de aceite.
2. Aprovação humana explícita, com nome e data no documento.
3. `technical-spec.md` — desenho, contratos, persistência, segurança e testes.
4. Aprovação humana explícita, com nome e data no documento.
5. `implementation-plan.md` — checkpoints executáveis e evidências.

Status permitidos: `Draft`, `Approved`, `In Progress`, `Implemented`. Um agente não infere aprovação nem aprova em nome
de uma pessoa. Mudança material numa spec aprovada a devolve a `Draft` e invalida os documentos seguintes até nova
aprovação. Ajuste pontual entra como adendo numerado, com aprovação própria.

## Features

| Contexto | Feature | RFs | Status | Plano |
| --- | --- | --- | --- | --- |
| Identidade e Permissões | [identidade-e-acesso](acesso/identidade-e-acesso/functional-spec.md) (M2) | RF-001 a RF-014, RF-116, RF-117 | Implemented (`v0.2.0`) | [plano](acesso/identidade-e-acesso/implementation-plan.md) |
| Identidade e Permissões | [catalogo-e-classificacao](permissoes/catalogo-e-classificacao/functional-spec.md) (M3) | RF-015 a RF-027, RF-118 | Implemented (na `dev`) | [plano](permissoes/catalogo-e-classificacao/implementation-plan.md) |
| Notificações | [caixa-e-email](notificacoes/caixa-e-email/functional-spec.md) (M4) | RF-028 a RF-032, RF-119 | Especificada; aguardando implementação | [plano](notificacoes/caixa-e-email/implementation-plan.md) |
| Aprovações | [motor-de-solicitacoes](aprovacoes/motor-de-solicitacoes/functional-spec.md) (M5) | RF-033 a RF-045, RF-120 a RF-122 | Especificada; aguardando implementação | [plano](aprovacoes/motor-de-solicitacoes/implementation-plan.md) |
| Financeiro | [cobrancas-e-recebimentos](financeiro/cobrancas-e-recebimentos/functional-spec.md) (M6) | RF-046 a RF-072, RF-123 a RF-125 | Funcional aprovada em 2026-11-13; falta a técnica | — |
| Financeiro | [gastos-e-prestacao-de-contas](financeiro/gastos-e-prestacao-de-contas/functional-spec.md) (M7) | RF-073 a RF-083, RF-126 a RF-128 | Funcional aprovada em 2026-11-13; falta a técnica | — |
| Eventos | [eventos-e-calendario](eventos/eventos-e-calendario/functional-spec.md) (M8) | RF-084 a RF-093, RF-129 a RF-131 | Funcional aprovada em 2026-11-13; falta a técnica | — |
