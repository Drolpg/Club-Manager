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
| Identidade e Permissões | [catalogo-e-classificacao](permissoes/catalogo-e-classificacao/functional-spec.md) (M3) | RF-015 a RF-027, RF-118 | Funcional aprovada; [técnica](permissoes/catalogo-e-classificacao/technical-spec.md) em Draft | — |
