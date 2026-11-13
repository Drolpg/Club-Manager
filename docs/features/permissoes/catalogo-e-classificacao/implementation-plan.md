# Plano de Implementação: Catálogo de permissões, classificação e histórico

| Campo | Valor |
| --- | --- |
| Feature | `permissoes/catalogo-e-classificacao` |
| Status | In Progress |
| Responsável | Leandro Nascimento |
| Atualizado em | 2026-11-13 |
| Especificação técnica | `./technical-spec.md` (aprovada em 2026-11-13) |

## Objetivo

O admin mantém cargos e setores, classifica diretores e concede permissões por cargo, setor ou pessoa; qualquer
módulo pergunta "este usuário pode?" e recebe a união das três origens; e o histórico de cada item é consultável.

Cada checkpoint segue `sdd-method:driving-with-tests`: testes escritos e vistos falhando, código mínimo,
`uv run poe verify` com saída 0 conferida, um commit com assunto de até 72 caracteres.

## Checkpoint 1 — Catálogo e resolução de permissões

- O que muda: `permissoes/catalogo.py`, `permissoes/domain/resolucao.py`.
- Testes: PER-R01 a PER-R05, sem banco.
- Critérios: base de CA-14 a CA-22.

## Checkpoint 2 — Cargos e setores

- O que muda: `permissoes/models.py` (`Cargo`, `Setor`, `Classificacao`, `Concessao`), migrações `0001` e `0002`,
  `services/cargos_e_setores.py`, rotas `cargos/` e `setores/`.
- Testes: dados iniciais; criar, renomear, desativar, reativar; nome repetido; em uso; só admin; auditoria; reversão
  das migrações.
- Critérios: CA-01 a CA-06.

## Checkpoint 3 — Classificação, concessões e API pública

- O que muda: `services/classificacao.py`, `services/concessoes.py`, `services/consulta.py`, `permissoes/public.py`,
  rotas `catalogo/`, `concessoes/`, `usuarios/{id}/`, `usuarios/{id}/classificacao/`, `minhas/`.
- Testes: classificar, reclassificar, tirar o cargo; concessão por cargo, setor e usuário; união e revogação; cargo e
  setor inativos; usuário inativo; admin; acesso total; presidente sem concessão; idempotência; só admin; painel com
  origens; `le_gestao`.
- Critérios: CA-07 a CA-26, CA-28.

## Checkpoint 4 — Portas em `acesso` e histórico

- O que muda: `acesso/public.py` (portas e `historico_com_nomes`), `permissoes/apps.py` (registro), rotas de convite
  e `tem_cargo` usando as portas, rotas de histórico em `acesso` e em `permissoes`.
- Testes: padrão seguro sem implementação; convites com a permissão; `tem_cargo` na lista de usuários; histórico de
  usuário, convite, cargo e setor com o nome do ator; quem não pode ver é negado.
- Critérios: CA-27, CA-29 a CA-32.

## Checkpoint 5 — Site

- O que muda: telas de cargos, setores, permissões e detalhe do usuário; página inicial com cargo, setores e
  permissões.
- Testes: cada tela com a API simulada.
- Critérios: CA-26 (tela).

## Checkpoint 6 — Validação final

- `uv run poe verify` e `npm run verify`, com saída 0.
- Fluxo contra o sistema no ar; documentação da lista da technical-spec; revisão de segurança; registros.

## Matriz critério de aceite → teste

| Critério | Teste |
| --- | --- |

## Revisão de segurança

Preenchida no checkpoint 6.

| Item | Achado | Mitigação | Status |
| --- | --- | --- | --- |

## Definition of Done

- [ ] Checkpoints concluídos, com evidência.
- [ ] Todo CA com ao menos um teste.
- [ ] Verificação completa com saída 0; cobertura dentro da meta.
- [ ] Fronteiras de módulo verificadas.
- [ ] Toda ação da regra 17 da funcional auditada, com teste.
- [ ] Revisão de segurança registrada, sem achado crítico ou alto aberto.
- [ ] Migrations reversíveis; dados iniciais classificados.
- [ ] Contrato, `docs/api/` e guia de teste manual atualizados.
- [ ] Registro de requisitos, decisões e riscos atualizados.
- [ ] CI verde no GitHub.
- [ ] Critérios de aceite validados e aprovados pelo dono.

## Evidências de verificação

## Rollback ou recuperação

As migrações revertem com `python manage.py migrate permissoes zero`; a versão anterior é a tag `v0.2.0`.
