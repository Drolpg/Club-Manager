# Auditoria de coerência — 2026-11-12

| Campo | Valor |
| --- | --- |
| Motivo | Fim do marco M1 (Fundação), antes do merge na `main` |
| Repositório | `dev` @ `632ac3f` |
| Board | Não há board (Miro não conectado à sessão) |
| Auditado por | Claude, a pedido de Leandro Nascimento |
| Não verificado | Board; issues do GitHub (nenhuma criada ainda) |

## Resumo

Os documentos estão coerentes entre si e com o código: nenhum link quebrado, nenhum ID de requisito ou de invariante
citado sem definição, e os módulos do código são os do desenho estratégico. Houve uma contagem errada de invariantes
(58 no lugar de 56), já corrigida, e dois assuntos de commit acima do limite de 72 caracteres, que ficam como estão.

| Classe | Quantidade |
| --- | --- |
| Igual | 6 |
| Espelho desatualizado | 2 (corrigidos) |
| Ausente em um lado | 0 |
| Conflito | 0 |
| Inconsistência interna | 2 (1 corrigida, 1 aceita) |
| Referência quebrada | 0 |
| Desvio doc × código | 0 |

## Igual

- Links relativos de todos os arquivos `.md` versionados: todos abrem.
- IDs `RF-NNN`, `RN-NNN` e `RNF-NN` citados no repositório: todos definidos em `docs/requirements/requirements.md`
  (115 RF, 23 RN, 14 RNF).
- IDs `INV-…` citados: todos definidos nos canvases de `docs/domain/aggregates/` (56).
- Módulos em `backend/config/settings.py`, no contrato do import-linter, em `tests/test_architecture.py`, no
  `AGENTS.md` e em `docs/domain/strategic-design.md`: a mesma lista de dez, mais `kernel`.
- Testes citados em `docs/architecture/project-structure.md` e no relatório de segurança: existem com esses nomes.
- Convenção de commits: os 14 commits (fora os de merge) usam tipo e escopo da lista, em português, sem trailer de
  IA.

## Espelho desatualizado

| Artefato | Lado mais novo | Evidência | Ação proposta | Dono |
| --- | --- | --- | --- | --- |
| Status da ADR-001 (`Proposed`) | A decisão: o gate da arquitetura base foi cumprido em 2026-11-12, com o CI verde | `docs/method.md`, rito 7 | Passar a `Accepted` — feito | Leandro |
| Status da ADR-007 (`Proposed`) e do perfil de stack (`Draft`) | A aprovação do dono, em 2026-11-12 | Conversa de aprovação do rito 7 | Passar a `Accepted` e `Approved` — feito | Leandro |

## Ausente em um lado

Nenhum.

## Conflitos (decisão necessária)

Nenhum.

## Inconsistências internas

| Fonte | Contradição | Ação proposta |
| --- | --- | --- |
| `docs/architecture/assessment.md` | Dizia "58 invariantes em 8 aggregates"; os canvases definem 56 (11 + 13 + 9 + 7 nos quatro principais, 16 nos quatro menores) | Corrigido para 56 |
| Histórico do git | Dois assuntos de commit passam de 72 caracteres (73 e 76), contra o `CONTRIBUTING.md` | Aceito: os commits já foram enviados, e reescrever o histórico publicado custa mais do que o desvio. Conferir o tamanho antes de commitar daqui em diante |

## Referências quebradas

Nenhuma.

## Desvios documentação × código

Nenhum. O que os documentos descrevem e ainda não existe está listado como placeholder em
`docs/architecture/project-structure.md`, com a feature que vai criá-lo.

## Não comparado

- O modelo de domínio (`docs/domain/domain-model.md`) contra o código: ainda não há código de domínio.
- O contrato da API contra uma documentação escrita: só existe o contrato gerado.

## Ações aprovadas

| Ação | Aprovado por / em | Feita em (commit) |
| --- | --- | --- |
| ADR-001 e ADR-007 para `Accepted`; perfil de stack para `Approved` | Leandro Nascimento / 2026-11-12 | Commit desta auditoria |
| Correção da contagem de invariantes | Correção factual, sem decisão | Commit desta auditoria |
