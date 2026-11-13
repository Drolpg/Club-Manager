# Auditoria de coerência — 2026-11-13

| Campo | Valor |
| --- | --- |
| Motivo | Fim do marco M2 (Identidade e acesso), antes do merge na `dev` e na `main` |
| Repositório | `feat/acesso-identidade-e-acesso` @ `b3c57f0` |
| Board | Não há board |
| Auditado por | Claude, a pedido de Leandro Nascimento |
| Não verificado | Issues do GitHub (nenhuma criada) |

## Resumo

Documentos e código estão coerentes: nenhum link quebrado, nenhum ID citado sem definição, e a spec técnica bate com
o que foi implementado, com três diferenças pequenas, todas registradas abaixo. O histórico tem dois assuntos de
commit acima de 72 caracteres.

| Classe | Quantidade |
| --- | --- |
| Igual | 5 |
| Espelho desatualizado | 0 |
| Ausente em um lado | 0 |
| Conflito | 0 |
| Inconsistência interna | 1 (aceita) |
| Referência quebrada | 0 |
| Desvio doc × código | 3 (documentação corrigida nesta auditoria) |

## Igual

- Links relativos de todos os `.md` versionados: todos abrem.
- IDs de requisito citados no repositório: todos definidos (156 no registro).
- Rotas da tabela da technical-spec e rotas em `backend/acesso/http/urls.py`: as mesmas.
- Códigos de erro da technical-spec e de `docs/api/README.md`: presentes no código e nos testes.
- Convenção de commits desde a `v0.1.0`: todos com tipo e escopo da lista, em português, sem trailer de IA.

## Inconsistências internas

| Fonte | Contradição | Ação proposta |
| --- | --- | --- |
| Histórico do git | Dois assuntos de commit com 73 e 77 caracteres, contra o limite de 72 do `CONTRIBUTING.md` | Aceito, como na auditoria anterior: já enviados. É a segunda vez; passo a conferir o tamanho em todo commit, e não só nos que lembro |

## Desvios documentação × código

| Documento | Afirma | Código faz | Ação |
| --- | --- | --- | --- |
| Technical-spec, "Persistência" | Uma migração `acesso/0001_usuario_e_convite` | Três: `0001_usuario`, `0002_convite`, `0003_convite_usado_por_opcional` | Adendo 1 na technical-spec |
| Technical-spec, "Contexto e desenho" | `acesso/services/` sem menção a `autorizacao`, `tokens`, `emails`, `google` | Esses quatro arquivos existem, além dos cinco listados | Adendo 1 na technical-spec |
| Technical-spec, tabela de erros | Não lista `CSRF_FAILED` nem os códigos 422 de situação (`USUARIO_NAO_ESTA_ATIVO` etc.) | O código e `docs/api/README.md` os têm | Adendo 1 na technical-spec |

Os três são detalhamentos que não mudam o comportamento aprovado; por isso entram como adendo, e não reabrem a spec.
O adendo precisa da aprovação do dono, que foi dada junto com a do marco.

## Não comparado

- O modelo de domínio (`docs/domain/domain-model.md`) contra o código: ele cobre só os módulos core, ainda sem código.

## Ações aprovadas

| Ação | Aprovado por / em | Feita em (commit) |
| --- | --- | --- |
| Adendo 1 da technical-spec | Leandro Nascimento / 2026-11-13, com a aprovação do M2 | Commit desta auditoria |
