# Especificação Técnica: Catálogo de permissões, classificação e histórico

| Campo | Valor |
| --- | --- |
| Feature | `permissoes/catalogo-e-classificacao` |
| Status | Implemented |
| Responsável | Leandro Nascimento |
| Atualizado em | 2026-11-13 |
| Aprovado por | Leandro Nascimento |
| Aprovado em | 2026-11-13 |
| Especificação funcional | `./functional-spec.md` (aprovada em 2026-11-13) |
| Decisões aplicadas | ADR-001, ADR-003, ADR-004, ADR-008; AD-007 e AD-014 (resolvidas por esta spec) |

## Contexto e desenho

| Módulo | O que ganha |
| --- | --- |
| `permissoes` | Modelos `Cargo`, `Setor`, `Classificacao`, `Concessao`; o catálogo; a resolução de permissões; serviços, rotas e a API pública que os marcos seguintes consomem |
| `acesso` | Duas portas que `permissoes` preenche (abaixo); rotas de histórico de usuário e de convite; `historico_com_nomes` na API pública |
| `auditoria` | Nada novo: `registrar` e `historico_do_item` já existem |
| `frontend` | Telas de cargos, setores, permissões e detalhe do usuário; a página inicial passa a mostrar cargo, setores e permissões |

### Quem conhece quem

`permissoes` fica acima de `acesso` no context map e o consulta pela API pública (o usuário está ativo? é admin?).
Mas duas coisas do `acesso` dependem de `permissoes`: quem pode gerenciar convites, e se um usuário tem cargo (campo
`tem_cargo`). `acesso` não pode importar `permissoes`.

Solução, no mesmo espírito da ADR-003 (o de baixo nunca conhece o de cima): `acesso` define duas **portas** com um
comportamento padrão, e `permissoes` registra a implementação ao iniciar.

| Porta em `acesso.public` | Padrão (sem `permissoes`) | Implementação registrada por `permissoes` |
| --- | --- | --- |
| `pode_gerenciar_convites(usuario_id)` | Só admin | Admin, ou quem tem a permissão `convites.gerenciar` |
| `usuarios_com_cargo(usuario_ids)` | Ninguém | Os que têm classificação |

É uma consulta, e não um evento; por isso entra como **adendo à ADR-003**, proposto com esta spec:

> Quando um módulo de baixo precisa de uma resposta que só um de cima sabe dar, ele define uma porta com padrão
> seguro (negar), e o de cima registra a implementação na inicialização. Hoje: as duas portas de `acesso`.

### Catálogo no código (AD-014)

Cada módulo declara as suas permissões ao iniciar, com `permissoes.public.registrar_permissao(codigo, nome,
descricao, fora_do_acesso_total=False)`. O código é estável, no formato `<recurso>.<acao>` (por exemplo,
`convites.gerenciar`). O painel lista o catálogo e concede o que existe nele; conceder um código desconhecido é
recusado. `acesso` declara `convites.gerenciar` pelo próprio `permissoes`, já que não pode importá-lo: a declaração
fica em `permissoes/catalogo.py`, junto com `ACESSO_TOTAL`.

### Estrutura

```text
permissoes/
├── public.py        pode, quem_pode, le_gestao, permissoes_de, classificacao_de, registrar_permissao
├── catalogo.py      registro das permissões conhecidas
├── models.py        Cargo, Setor, Classificacao, Concessao
├── domain/          resolucao.py: função pura que une as três origens
├── services/        cargos_e_setores, classificacao, concessoes, consulta
├── http/            serializers, views, urls
├── apps.py          registra as portas de `acesso` no `ready`
├── migrations/
└── tests/
```

## Modelo de domínio

Módulo de apoio, em camadas. A regra central é uma função pura.

| Modelo | Campos principais | Observação |
| --- | --- | --- |
| `Cargo`, `Setor` | `id` (UUID 7), `nome`, `ativo`, `criado_em` | Nome único sem diferenciar maiúsculas. Métodos `renomear`, `desativar`, `reativar` |
| `Classificacao` | `usuario_id` (único), `cargo`, `setores` (vários), `atualizada_em` | Existir a linha é "ter cargo". Tirar o cargo remove a linha; o histórico fica na auditoria |
| `Concessao` | `permissao` (código), `alvo_tipo` (`CARGO`, `SETOR`, `USUARIO`), `cargo`, `setor`, `usuario_id`, `concedida_por_id`, `concedida_em`, `revogada_por_id`, `revogada_em` | Revogar preenche os dois últimos campos; nada é apagado. No máximo uma concessão ativa por permissão e alvo |

A referência ao usuário é por ID, sem chave estrangeira, porque o usuário é de outro módulo.

`resolver_permissoes(...)`, em `permissoes/domain/resolucao.py`, recebe fatos e devolve, para cada permissão, a lista
de origens. Não toca no banco nem importa framework.

| Entrada | Vem de |
| --- | --- |
| Usuário ativo? É admin? | `acesso.public` |
| Catálogo | `permissoes.catalogo` |
| Cargo ativo do usuário e setores ativos dele | `Classificacao` |
| Concessões ativas do cargo, dos setores e do usuário | `Concessao` |

| ID | Regra | Onde |
| --- | --- | --- |
| PER-R01 | Usuário inativo não tem permissão nenhuma | `resolver_permissoes` |
| PER-R02 | Admin ativo tem todas as permissões do catálogo, com origem "admin" | Idem |
| PER-R03 | O resultado é a união das concessões ativas do cargo ativo, dos setores ativos e do usuário | Idem |
| PER-R04 | `ACESSO_TOTAL` acrescenta todas as permissões do catálogo que não estão marcadas como `fora_do_acesso_total` | Idem |
| PER-R05 | Só existe permissão que está no catálogo; concessão de código que saiu do catálogo é ignorada | Idem |
| PER-R06 | `ACESSO_TOTAL` só é concedido a usuário, nunca a cargo ou setor | Serviço de concessões |
| PER-R07 | Cargo ou setor com usuário ativo classificado nele não é desativado | Serviço de cargos e setores |
| PER-R08 | Só se classifica usuário ativo, com cargo e setores ativos | Serviço de classificação |
| PER-R09 | Só admin altera cargos, setores, classificação e concessões; `ACESSO_TOTAL` não dá isso | Permissão `EhAdmin` na rota e conferência no serviço |
| PER-R10 | Lê dados de gestão quem é admin ativo, ou é ativo e tem classificação com cargo ativo | `le_gestao` |

## Interfaces e fluxo de dados

### API pública de `permissoes` (em processo)

| Função | Devolve | Usada por |
| --- | --- | --- |
| `pode(usuario_id, codigo)` | Booleano | Todos os módulos de cima |
| `quem_pode(codigo)` | IDs dos usuários ativos que podem (inclui admins) | Notificações, aprovações |
| `le_gestao(usuario_id)` | Booleano | Módulos com dados de gestão |
| `permissoes_de(usuario_id)` | Permissões com origens | Painel e página inicial |
| `classificacao_de(usuario_id)` | Cargo e setores, ou nada | Painel, relatórios |
| `registrar_permissao(...)` | — | Cada módulo, ao iniciar |

Não há cache: cada pergunta consulta o banco, o que garante a regra de valer na requisição seguinte. Com poucos
usuários, o custo é irrelevante.

### Rotas, sob `/api/v1/permissoes/`

| Método e caminho | Quem | Entrada | Saída |
| --- | --- | --- | --- |
| `GET cargos/`, `GET setores/` | Quem lê gestão | — | Lista, com `ativo` |
| `POST cargos/`, `POST setores/` | Admin | `nome` | Criado |
| `POST cargos/{id}/renomear/` (e `setores/`) | Admin | `nome` | Atualizado |
| `POST cargos/{id}/desativar/`, `…/reativar/` (e `setores/`) | Admin | — | Atualizado |
| `GET cargos/{id}/historico/` (e `setores/`) | Admin | — | Histórico |
| `GET catalogo/` | Admin | — | Permissões: `codigo`, `nome`, `descricao` |
| `GET concessoes/` | Admin | — | Concessões ativas, com o alvo |
| `POST concessoes/` | Admin | `permissao`, `alvo_tipo`, `alvo_id` | Concessão (a existente, se já havia) |
| `POST concessoes/{id}/revogar/` | Admin | — | Concessão revogada |
| `GET usuarios/{id}/` | Admin | — | Classificação e permissões com origens |
| `PUT usuarios/{id}/classificacao/` | Admin | `cargo_id` (ou nulo), `setor_ids` | Classificação |
| `GET minhas/` | Logado | — | O próprio cargo, setores e permissões |

Em `acesso`: `GET acesso/usuarios/{id}/historico/` (admin) e `GET acesso/convites/{id}/historico/` (quem gerencia
convites). As rotas de convite passam a aceitar quem tem `convites.gerenciar`.

Formato de um item de histórico: `acao`, `ator` (`id` e `nome`, ou nulo para o sistema), `justificativa`,
`criado_em`.

| Situação | Código HTTP | Código de erro |
| --- | --- | --- |
| Nome de cargo ou setor já usado | 409 | `NOME_EM_USO` |
| Desativar cargo ou setor com usuário ativo | 422 | `CARGO_EM_USO`, `SETOR_EM_USO` (com a quantidade em `details`) |
| Atribuir cargo ou setor inativo | 422 | `CARGO_INATIVO`, `SETOR_INATIVO` |
| Desativar o que já está inativo, ou reativar o que está ativo | 422 | `JA_ESTA_INATIVO`, `JA_ESTA_ATIVO` |
| Classificar usuário que não está ativo | 422 | `USUARIO_NAO_ESTA_ATIVO` |
| Setores informados sem cargo | 400 | `VALIDATION_ERROR` |
| Permissão fora do catálogo, alvo inexistente | 400 | `VALIDATION_ERROR` |
| `ACESSO_TOTAL` para cargo ou setor | 422 | `ACESSO_TOTAL_SO_PARA_USUARIO` |
| Revogar concessão já revogada | 422 | `CONCESSAO_JA_REVOGADA` |
| Item não encontrado | 404 | `NOT_FOUND` |
| Sem sessão; sem ser admin | 401; 403 | `NOT_AUTHENTICATED`; `PERMISSION_DENIED` |

Ações auditadas, todas na transação do caso de uso: `CARGO_CRIADO`, `CARGO_RENOMEADO`, `CARGO_DESATIVADO`,
`CARGO_REATIVADO` (e as quatro de setor), `USUARIO_CLASSIFICADO` (com os IDs do cargo e dos setores),
`CLASSIFICACAO_REMOVIDA`, `PERMISSAO_CONCEDIDA`, `PERMISSAO_REVOGADA`. A concessão a um usuário é registrada no
histórico do usuário; a de cargo ou setor, no histórico do cargo ou setor.

Não há evento de integração nem e-mail nesta feature.

## Persistência e dados

| Migração | Conteúdo |
| --- | --- |
| `permissoes/0001_cargo_setor_classificacao_concessao` | As quatro tabelas, com os índices únicos |
| `permissoes/0002_cargos_e_setores_iniciais` | Os quatro setores e os cinco cargos de partida |

Classificação dos dados: os setores e cargos iniciais são **referência obrigatória**, criados por migração e
reversíveis (a reversão remove os que ninguém usa). Nenhuma concessão, classificação ou usuário é criado por
migração.

Unicidade: `Lower(nome)` em cargo e em setor; uma classificação por usuário; uma concessão ativa por permissão e
alvo (índices únicos parciais, onde `revogada_em` é nulo).

## Segurança e operação

| Tema | Decisão |
| --- | --- |
| Autorização | Negada por padrão. Rotas de escrita exigem admin na rota e no serviço. `ACESSO_TOTAL` nunca passa em `EhAdmin` |
| Padrão seguro das portas | Sem `permissoes` registrado, `acesso` trata convites como só do admin e ninguém como "com cargo" |
| Elevação de privilégio | Ninguém concede a si mesmo: só o admin concede, e o admin já tem tudo. Um diretor com acesso total não concede nem classifica |
| Exposição | `minhas/` devolve só os dados de quem pergunta; o detalhe de outro usuário é só do admin; o histórico segue a regra do item |
| Auditoria | Toda mudança de quem pode o quê fica registrada, com ator e alvo |
| Dados pessoais | O histórico mostra o nome do ator; a auditoria guarda só o ID e resolve o nome na leitura |
| Modelo de ameaças | `docs/security/threat-model.md` ganha a seção deste marco: elevação por concessão, porta sem implementação, permissão órfã |

Sem configuração nova e sem dependência nova. Rollback: as migrações revertem; a versão anterior é a `v0.2.0`.

## Estratégia de testes

| Camada | O que cobre | Tipo de teste |
| --- | --- | --- |
| Função pura | PER-R01 a PER-R05: cada origem sozinha, a união, cargo e setor inativos, usuário inativo, admin, acesso total e a exclusão de `fora_do_acesso_total`, código fora do catálogo | Unitário, sem banco |
| Serviços | Cada cenário da funcional; PER-R06 a PER-R10; auditoria de cada ação | Integração com PostgreSQL |
| Contrato | Cada rota: sucesso, cada erro da tabela, e os três níveis de acesso (sem sessão, diretor, admin) | Integração HTTP |
| Portas | `acesso` sem implementação registrada usa o padrão seguro; com `permissoes`, convites e `tem_cargo` seguem as concessões | Integração |
| Persistência | Unicidade sem diferenciar maiúsculas; uma concessão ativa por alvo; reversão das migrações; dados iniciais | Integração com PostgreSQL |
| Fronteiras | `permissoes` só importa `acesso.public` e `auditoria.public`; `acesso` não importa `permissoes`; `permissoes/domain` sem framework | Teste de arquitetura existente |
| Site | Telas de cargos, setores, permissões e usuário; página inicial com e sem cargo | Vitest e Testing Library |

Cada critério de aceite CA-01 a CA-32 tem ao menos um teste; a matriz fica no plano de implementação.

## Documentação a atualizar

- [ ] Contrato gerado (anotações das rotas novas)
- [ ] `docs/api/README.md`: recursos e códigos de erro novos
- [ ] `docs/api/manual-testing.md`: roteiro de classificação e concessão
- [ ] `docs/adr/ADR-003`: adendo das portas
- [ ] `docs/architecture/project-structure.md` e `stack-profile.md`: como um módulo declara permissões e pergunta
- [ ] `docs/security/threat-model.md`: seção do M3
- [ ] `AGENTS.md`: regra "toda rota de escrita confere uma permissão do catálogo"
- [ ] Registro de requisitos e de decisões (AD-007, AD-014)

## Adendos

Nenhum.
