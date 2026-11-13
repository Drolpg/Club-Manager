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

## Como executar um checkpoint (vale para qualquer sessão)

Os checkpoints 1 e 2 estão concluídos. Os de 3 a 6 foram detalhados para poderem ser feitos por outra sessão, sem
contexto desta conversa. Antes de começar, leia `AGENTS.md`, `./functional-spec.md` e `./technical-spec.md`.

1. Trabalhe na branch `feat/permissoes-catalogo-e-classificacao`. Um checkpoint por vez, na ordem.
2. Escreva os testes do checkpoint e rode-os antes do código, para vê-los falhar pelo motivo certo.
3. Escreva o código mínimo. Siga os arquivos já existentes como modelo de estilo:
   `permissoes/services/cargos_e_setores.py`, `permissoes/http/views.py`, `acesso/services/usuarios.py`.
4. Rode `uv run poe verify` em `backend/` (e `npm run verify` em `frontend/`, se mexeu no site) e **confira o
   código de saída**. Só faça commit com saída 0.
5. Um commit por checkpoint, no padrão do `CONTRIBUTING.md`, com assunto de até 72 caracteres (meça antes).
6. Acrescente a evidência (comando, resultado, data) e as linhas da matriz neste arquivo, no mesmo commit.
7. Não faça merge na `dev` nem na `main`. Pare ao fim do checkpoint 6 e peça a aprovação do dono.

Se um teste parecer errado, ou a spec não cobrir um caso, pare e pergunte: não mude teste nem spec para passar.

## Checkpoint 3 — Classificação, concessões e API pública

Critérios: CA-07 a CA-26 e CA-28. Regras: PER-R06, PER-R08, PER-R09, PER-R10.

**Serviços.** Os que alteram dados recebem `ator_id`, começam por `exigir_admin(ator_id)` (de
`services/autorizacao.py`), rodam em `transaction.atomic` e auditam com `auditoria.public.registrar`.

| Arquivo e função | Comportamento |
| --- | --- |
| `services/classificacao.py::classificar(ator_id, usuario_id, cargo_id, setor_ids)` | Usuário por `acesso.public.usuario_por_id`: inexistente → `NOT_FOUND` (404); não ativo → `USUARIO_NAO_ESTA_ATIVO` (422). `cargo_id` nulo: `setor_ids` precisa estar vazio (senão `VALIDATION_ERROR`, 400, com `details={"setor_ids": [...]}`); remove a `Classificacao` se existir e audita `CLASSIFICACAO_REMOVIDA`. Com cargo: cargo ou setor inexistente → `VALIDATION_ERROR`; inativo → `CARGO_INATIVO` ou `SETOR_INATIVO` (422); cria ou atualiza a linha e os setores; audita `USUARIO_CLASSIFICADO` com `dados={"cargo_id": ..., "setor_ids": [...]}`. Item da auditoria: `("usuario", usuario_id)` |
| `services/concessoes.py::conceder(ator_id, permissao, alvo_tipo, alvo_id)` | Devolve `(concessao, criada)`. Código fora de `catalogo.conhecida` → `VALIDATION_ERROR`. `ACESSO_TOTAL` com alvo que não é usuário → `ACESSO_TOTAL_SO_PARA_USUARIO` (422). Alvo inexistente → `VALIDATION_ERROR`. Se já há concessão ativa igual, devolve a existente com `criada=False`, sem auditar. Senão cria e audita `PERMISSAO_CONCEDIDA` no item do alvo (`usuario`, `cargo` ou `setor`), com `dados={"permissao": ..., "concessao_id": ...}` |
| `services/concessoes.py::revogar(ator_id, concessao_id)` | Inexistente → `NOT_FOUND`; já revogada → `CONCESSAO_JA_REVOGADA` (422). Chama `concessao.revogar(por=ator_id, agora=timezone.now())` e audita `PERMISSAO_REVOGADA` no item do alvo |
| `services/concessoes.py::listar_ativas(ator_id)` | Concessões com `revogada_em` nulo, com `select_related("cargo", "setor")` |
| `services/consulta.py::permissoes_de(usuario_id)` | Monta `Fatos` (de `domain/resolucao.py`) com: ativo e admin de `acesso.public.usuario_por_id`; `catalogo.mapa_para_resolucao()`; o cargo e os setores da `Classificacao`, cada um como `Grupo` com as permissões das concessões ativas dele; as concessões individuais ativas. Devolve `resolver_permissoes(fatos)`. Usuário inexistente → `{}` |
| `services/consulta.py::pode(usuario_id, codigo)` | `codigo in permissoes_de(usuario_id)` |
| `services/consulta.py::quem_pode(codigo)` | IDs dos usuários ativos que podem. Candidatos: `acesso.public.admins_ativos()`, os de concessão individual ativa (da permissão ou de `ACESSO_TOTAL`) e os classificados num cargo ou setor com concessão ativa da permissão; filtre os candidatos com `pode` |
| `services/consulta.py::classificacao_de(usuario_id)` | `None`, ou um dataclass congelado com o cargo (`id`, `nome`, `ativo`) e a lista de setores |

**API pública** (`permissoes/public.py`): reexporte `pode`, `quem_pode`, `le_gestao`, `permissoes_de`,
`classificacao_de` e `catalogo.registrar_permissao`. Devolva dataclasses, nunca modelos.

**Rotas** (em `permissoes/http/`, sob `/api/v1/permissoes/`; veja a tabela da technical-spec):

| Rota | Permissão | Observação |
| --- | --- | --- |
| `GET catalogo/` | `EhAdmin` | `codigo`, `nome`, `descricao` |
| `GET concessoes/`, `POST concessoes/` | `EhAdmin` | `POST` responde 201 se criou e 200 se já existia. Saída: `id`, `permissao`, `alvo_tipo`, `alvo` (`id` e `nome`), `concedida_em` |
| `POST concessoes/{id}/revogar/` | `EhAdmin` | |
| `GET usuarios/{id}/` | `EhAdmin` | `cargo`, `setores`, `permissoes` (lista de `codigo`, `nome` e `origens`; cada origem com `tipo`, `id`, `nome`) |
| `PUT usuarios/{id}/classificacao/` | `EhAdmin` | Entrada: `cargo_id` (pode ser nulo) e `setor_ids` (lista) |
| `GET minhas/` | `IsAuthenticated` | O mesmo formato de `usuarios/{id}/`, sempre de quem pergunta |

O nome do usuário alvo de uma concessão vem de `acesso.public.usuario_por_id`.

**Testes** (em `permissoes/tests/`, um arquivo por assunto; use `tests.apoio` para criar usuários e nunca importe
`acesso.models`): um teste por critério CA-07 a CA-26 e CA-28, com o número no nome (por exemplo,
`test_ca14_permissao_concedida_a_um_cargo_vale_para_quem_tem_o_cargo`); mais: cada código de erro da tabela;
`quem_pode` incluindo admin e excluindo inativo; o serviço recusando quem não é admin sem passar pela rota; a
auditoria de cada ação; e um usuário com acesso total recebendo 403 nas rotas de admin (CA-21). Para CA-21, registre
no teste uma permissão com `fora_do_acesso_total=True` e remova-a no fim com `catalogo.remover_para_testes`.

## Checkpoint 4 — Portas em `acesso` e histórico

Critérios: CA-27, CA-29 a CA-32. Decisão: adendo 1 da ADR-003.

| O que | Como |
| --- | --- |
| Portas | Crie `acesso/portas.py` com duas funções substituíveis e os padrões seguros: `pode_gerenciar_convites(usuario_id)` → só admin ativo; `usuarios_com_cargo(usuario_ids)` → conjunto vazio. Em `acesso/public.py`, exponha `registrar_portas(*, pode_gerenciar_convites=None, usuarios_com_cargo=None)` e `restaurar_portas()` (para os testes) |
| Registro | Em `permissoes/apps.py`, no `ready`, chame `acesso.public.registrar_portas` com: admin ativo ou `pode(usuario_id, "convites.gerenciar")`; e os IDs que têm `Classificacao` |
| Convites | Em `acesso/services/convites.py`, troque `exigir_admin` por uma conferência que usa a porta. Em `acesso/http/`, as quatro rotas de convite passam a usar uma permissão `PodeGerenciarConvites`. `usuarios/` continua só para admin |
| `tem_cargo` | `UsuarioSerializer.get_tem_cargo` passa a consultar a porta. Na lista de usuários, consulte a porta uma vez para todos os IDs e passe o conjunto pelo `context` do serializer |
| Histórico | `acesso.public.historico_com_nomes(item_tipo, item_id)`: lê `auditoria.public.historico_do_item`, do mais recente para o mais antigo, e troca o `ator_id` por `{"id", "nome"}` (nulo para ações do sistema). Não devolve `dados` |
| Rotas de histórico | `GET acesso/usuarios/{id}/historico/` (admin), `GET acesso/convites/{id}/historico/` (quem gerencia convites), `GET permissoes/cargos/{id}/historico/` e `GET permissoes/setores/{id}/historico/` (admin). Item inexistente → 404 |

**Testes:** com as portas restauradas ao padrão, convites são só do admin e ninguém tem cargo; com `permissoes`
registrado, CA-27 (diretor com a permissão gera, lista, regenera e revoga; sem ela, 403); `tem_cargo` verdadeiro na
lista e na sessão depois de classificar; histórico de cada tipo de item com o nome do ator e em ordem; 403 para quem
não pode ver; nenhuma rota `DELETE` para cargo, setor ou concessão (CA-32). O teste de arquitetura precisa continuar
verde: `acesso` não importa `permissoes`.

## Checkpoint 5 — Site

Critério: CA-26 (tela). Modelo de estilo: `frontend/src/paginas/Admin.tsx` e `frontend/src/App.test.tsx`.

| Tela | Rota do site | O que faz |
| --- | --- | --- |
| Cargos e Setores | `/admin/cargos`, `/admin/setores` | Lista, cria, renomeia, desativa e reativa; mostra o erro `CARGO_EM_USO` ou `SETOR_EM_USO` com a quantidade |
| Permissões | `/admin/permissoes` | Catálogo com descrição; concessões ativas; conceder a cargo, setor ou usuário; revogar |
| Usuário | `/admin/usuarios/:id` | Classificar (cargo e setores), ver permissões com origens, conceder acesso total, ver o histórico |
| Página inicial | `/` | Com cargo: mostra cargo, setores e permissões (de `GET permissoes/minhas/`). Sem cargo: continua "aguarda a classificação" |

Acrescente as funções em `frontend/src/api/` (um arquivo `permissoes.ts`), os textos dos códigos de erro novos em
`frontend/src/mensagens.ts` e os atalhos no menu do admin. Testes com `simularApi` (`frontend/src/test/api.ts`): cada
tela com o caminho feliz e um erro. No Windows, rode o `npm` num terminal aberto em `C:\…`, com a letra maiúscula.

## Checkpoint 6 — Validação final

1. `uv run poe verify` e `npm run verify`, com saída 0.
2. Suba o sistema (`docker compose up -d --build`) e percorra, pela API ou pelo site: criar cargo; classificar um
   diretor; conceder `convites.gerenciar` ao setor dele; o diretor gera um convite; revogar a concessão; o diretor
   deixa de conseguir; conferir o histórico do usuário.
3. Atualize a documentação da lista "Documentação a atualizar" da technical-spec.
4. Preencha a "Revisão de segurança" deste plano com `sdd-method:reviewing-security` e acrescente a seção do M3 em
   `docs/security/threat-model.md`.
5. Atualize o registro de requisitos (RF-015 a RF-027 e RF-118) para `Implementado` só depois da aprovação do dono.
6. Abra um pull request de rascunho para a `dev`, para o CI rodar, e relate ao dono: o que foi feito, o resultado
   de cada verificação, o que não foi validado e qualquer desvio.

## Matriz critério de aceite → teste

| Critério | Teste |
| --- | --- |
| CA-01 | `permissoes/tests/test_cargos_e_setores.py::test_ca01_sistema_nasce_com_quatro_setores_e_cinco_cargos_sem_permissao` |
| CA-02 | `permissoes/tests/test_cargos_e_setores.py::test_ca02_admin_cria_e_o_item_aparece_ativo_na_lista` |
| CA-03 | `permissoes/tests/test_cargos_e_setores.py::test_ca03_nome_repetido_em_qualquer_caixa_e_recusado_ao_criar_e_ao_renomear` |
| CA-04 | `permissoes/tests/test_cargos_e_setores.py::test_ca04_item_sem_uso_e_desativado_e_pode_ser_reativado` |
| CA-05 | `permissoes/tests/test_cargos_e_setores.py::test_ca05_item_que_um_usuario_ativo_tem_nao_e_desativado` |
| CA-06 | `permissoes/tests/test_cargos_e_setores.py::test_ca06_quem_nao_e_admin_nao_altera`, `::test_ca06_diretor_com_cargo_lista_e_diretor_sem_cargo_nao` |
| CA-07 | `permissoes/tests/test_classificacao.py::test_ca07_diretor_sem_cargo_recebe_cargo_e_dois_setores`, `permissoes/tests/test_portas.py::test_ca07_lista_e_sessao_mostram_com_cargo_depois_de_classificar` |
| CA-08 | `permissoes/tests/test_classificacao.py::test_ca08_reclassificar_vale_na_requisicao_seguinte_do_diretor` |
| CA-09 | `permissoes/tests/test_classificacao.py::test_ca09_tirar_o_cargo_remove_cargo_e_setores_e_audita` |
| CA-10 | `permissoes/tests/test_classificacao.py::test_ca10_usuario_que_nao_esta_ativo_nao_e_classificado` |
| CA-11 | `permissoes/tests/test_classificacao.py::test_ca11_cargo_desativado_nao_e_atribuido`, `permissoes/tests/test_classificacao.py::test_ca11_setor_desativado_nao_e_atribuido` |
| CA-12 | `permissoes/tests/test_classificacao.py::test_ca12_quem_nao_e_admin_nao_classifica`, `permissoes/tests/test_classificacao.py::test_ca12_o_servico_tambem_recusa_quem_nao_e_admin` |
| CA-13 | `permissoes/tests/test_concessoes.py::test_ca13_admin_ve_o_catalogo_com_nome_e_descricao` |
| CA-14 | `permissoes/tests/test_consulta.py::test_ca14_permissao_concedida_a_um_cargo_vale_para_quem_tem_o_cargo` |
| CA-15 | `permissoes/tests/test_consulta.py::test_ca15_permissao_concedida_a_um_setor_vale_para_quem_e_do_setor` |
| CA-16 | `permissoes/tests/test_consulta.py::test_ca16_concessao_individual_vale_mesmo_fora_do_setor_de_origem`, `permissoes/tests/test_consulta.py::test_ca16_concessao_individual_vale_ate_sem_classificacao` |
| CA-17 | `permissoes/tests/test_consulta.py::test_ca17_a_permissao_dura_enquanto_restar_uma_concessao_ativa` |
| CA-18 | `permissoes/tests/test_consulta.py::test_ca18_cargo_ou_setor_desativado_deixa_de_conceder` |
| CA-19 | `permissoes/tests/test_consulta.py::test_ca19_usuario_desativado_nao_tem_permissao_e_reativado_volta_a_ter` |
| CA-20 | `permissoes/tests/test_consulta.py::test_ca20_admin_tem_todas_as_permissoes_do_catalogo_sem_concessao` |
| CA-21 | `permissoes/tests/test_consulta.py::test_ca21_acesso_total_da_tudo_menos_o_que_esta_fora_dele`, `permissoes/tests/test_consulta.py::test_ca21_acesso_total_nao_da_a_administracao` |
| CA-22 | `permissoes/tests/test_consulta.py::test_ca22_presidente_sem_concessao_nao_tem_permissao_nenhuma` |
| CA-23 | `permissoes/tests/test_concessoes.py::test_ca23_conceder_duas_vezes_ao_mesmo_alvo_deixa_uma_concessao_so` |
| CA-24 | `permissoes/tests/test_concessoes.py::test_ca24_quem_nao_e_admin_nao_concede_nem_revoga`, `permissoes/tests/test_concessoes.py::test_ca24_os_servicos_tambem_recusam_quem_nao_e_admin` |
| CA-25 | `permissoes/tests/test_consulta.py::test_ca25_admin_ve_cada_permissao_com_todas_as_origens`, `permissoes/tests/test_consulta.py::test_ca25_detalhe_de_outro_usuario_e_so_do_admin` |
| CA-26 | `permissoes/tests/test_consulta.py::test_ca26_diretor_ve_o_proprio_cargo_setores_e_permissoes_e_nao_os_de_outro` (API) |
| CA-28 | `permissoes/tests/test_consulta.py::test_ca28_le_gestao_so_com_cargo_e_ativo` |
| CA-27 | `permissoes/tests/test_portas.py::test_ca27_diretor_com_a_permissao_gera_lista_regenera_e_revoga_convites`, `permissoes/tests/test_portas.py::test_ca27_sem_a_permissao_o_sistema_nega_as_quatro_rotas`, `permissoes/tests/test_portas.py::test_ca27_perder_a_permissao_vale_na_requisicao_seguinte` |
| CA-29 | `permissoes/tests/test_historico.py::test_ca29_toda_acao_da_regra_17_gera_registro_com_quem_o_que_quando_e_o_item` (e os testes de auditoria de cada serviço) |
| CA-30 | `acesso/tests/test_historico.py::test_ca30_historico_do_usuario_vem_do_mais_recente_com_o_nome_do_ator`, `acesso/tests/test_historico.py::test_ca30_historico_do_convite_mostra_gerado_e_revogado_com_o_nome_de_quem_agiu`, `permissoes/tests/test_historico.py::test_ca30_historico_do_item_vem_do_mais_recente_com_o_nome_do_ator` (cargo e setor) |
| CA-31 | `acesso/tests/test_historico.py::test_ca31_quem_nao_e_admin_nao_ve_o_historico_do_usuario`, `acesso/tests/test_historico.py::test_ca31_quem_nao_gerencia_convites_nao_ve_o_historico_do_convite`, `permissoes/tests/test_historico.py::test_ca31_quem_nao_e_admin_nao_ve_o_historico` |
| CA-32 | `permissoes/tests/test_historico.py::test_ca32_nenhuma_rota_de_permissoes_aceita_delete`, `permissoes/tests/test_historico.py::test_ca32_apagar_cargo_setor_ou_concessao_nao_e_possivel` |

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

### Checkpoint 1 — Catálogo e resolução de permissões (2026-11-13)

```text
uv run poe verify → saída 0; 239 passed; cobertura 96,68%
```

Testes novos: `backend/permissoes/tests/test_resolucao.py` (14) e `test_catalogo.py` (8), vistos falhando antes do
código.

### Checkpoint 2 — Cargos e setores (2026-11-13)

```text
uv run poe verify → saída 0; 279 passed; cobertura 96,38%
```

Testes novos: `backend/permissoes/tests/test_cargos_e_setores.py` (40, a maioria rodando para cargo e para setor),
vistos falhando antes do código. O teste de arquitetura barrou uma primeira versão em que os testes de `permissoes`
importavam `acesso.models`; os testes passaram a usar `backend/tests/apoio.py`, e as fixtures comuns foram para
`backend/conftest.py`.

### Checkpoint 3 — Classificação, concessões e API pública (2026-11-13)

```text
uv run poe verify → saída 0; 349 passed; cobertura 96,91%
```

Testes novos (70): `test_classificacao.py` (19), `test_concessoes.py` (26) e `test_consulta.py` (25), vistos
falhando antes do código (os módulos de serviço ainda não existiam). CA-07 (coluna "com cargo" da lista de
usuários) e CA-26 (tela) completam-se nos checkpoints 4 e 5.

### Checkpoint 4 — Portas em `acesso` e histórico (2026-11-13)

```text
uv run poe verify → saída 0; 386 passed; cobertura 97,13%
```

Testes novos (37): `acesso/tests/test_portas.py` (5), `acesso/tests/test_historico.py` (8),
`permissoes/tests/test_portas.py` (10) e `permissoes/tests/test_historico.py` (14), vistos falhando antes do
código. O teste de arquitetura segue verde: `acesso` não importa `permissoes`, e os testes de `permissoes` usam só
`acesso.public`. Os testes de `acesso` que exigem o comportamento padrão trocam o estado das portas por uma cópia
(`monkeypatch`), que o pytest desfaz no fim; os de `permissoes` restauram o padrão e chamam o `ready` de novo.

## Rollback ou recuperação

As migrações revertem com `python manage.py migrate permissoes zero`; a versão anterior é a tag `v0.2.0`.
