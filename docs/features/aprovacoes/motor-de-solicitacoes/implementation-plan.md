# Plano de Implementação: Motor de solicitações e aprovações

| Campo | Valor |
| --- | --- |
| Feature | `aprovacoes/motor-de-solicitacoes` |
| Status | In Progress |
| Responsável | Leandro Nascimento |
| Atualizado em | 2026-11-13 |
| Especificação técnica | `./technical-spec.md` (aprovada em 2026-11-13) |
| Pré-requisito | M3 e M4 concluídos e integrados à `dev` |

## Objetivo

Um módulo registra um tipo de solicitação e ganha o ciclo inteiro: enviar, retirar, contestar, reenviar, recusar,
reabrir, editar, cancelar e aprovar, com versões e decisões imutáveis, e sem ninguém decidir o próprio pedido sem a
permissão de auto-aprovação.

## Como executar (vale para qualquer sessão)

Este plano foi escrito para ser executado sem o contexto da conversa que o criou. Antes de começar, leia
`AGENTS.md` (inclusive "Lições da implementação"), `./functional-spec.md`, `./technical-spec.md` e
`docs/domain/aggregates/solicitacao.md`.

1. Crie a branch `feat/aprovacoes-motor-de-solicitacoes` a partir da `dev` atualizada. Mude o status deste plano
   para `In Progress`.
2. Um checkpoint por vez, na ordem. Escreva os testes, rode-os e veja-os falhar pelo motivo certo; só então o código.
3. Este é um módulo **core**: o aggregate é o modelo do Django, o estado só muda pelos métodos dele, e as decisões
   ficam em funções puras em `aprovacoes/domain/`, sem importar Django. Não crie repository, entidade paralela nem
   mapper (veja "Não adicionar" no `AGENTS.md`).
4. Modelos de estilo: `backend/permissoes/` (serviços, rotas, catálogo em código, função pura) e
   `backend/acesso/` (tarefas, dados que rodam depois do commit).
5. Rode `uv run poe verify` em `backend/` (e `npm run verify` em `frontend/`, se mexeu no site, nunca os dois ao
   mesmo tempo) e confira o código de saída. Só faça commit com saída 0.
6. Um commit por checkpoint, com assunto de até 72 caracteres e escopo `aprovacoes`, `platform` ou `web`.
7. No mesmo commit, acrescente a evidência e as linhas da matriz neste arquivo.
8. Não faça merge na `dev` nem na `main`. Ao fim do último checkpoint, abra um pull request de rascunho para o CI
   rodar e relate ao dono: o que foi feito, o resultado de cada verificação, o que não foi validado e os desvios.

Se um teste parecer errado ou a spec não cobrir um caso, pare e pergunte. Não mude teste nem spec para passar.

## Checkpoint 1 — Domínio puro

- **O que muda:** `kernel/dinheiro.py`, `aprovacoes/domain/transicoes.py`, `aprovacoes/domain/decisores.py`.

| Peça | Comportamento |
| --- | --- |
| `Dinheiro` | `@dataclass(frozen=True)` com um `Decimal`. Aceita `Decimal`, `int` ou texto; recusa `float`; arredondamento não é feito: mais de duas casas é erro; negativo é erro. Tem comparação e `__str__` com duas casas |
| `Situacao` e `Comando` | `StrEnum` com as 8 situações e os comandos (`ENVIAR`, `RETIRAR`, `REENVIAR`, `REABRIR`, `EDITAR`, `CANCELAR`, `APROVAR`, `CONTESTAR`, `RECUSAR`, `INICIAR_EXECUCAO`, `ENCERRAR`) |
| `transicao_permitida(situacao, comando)` e `situacao_apos(situacao, comando)` | A tabela do diagrama da spec funcional, num dicionário só |
| `pode_decidir(...)` | Entradas: `ator_id`, `solicitante_id`, `aprovador_indicado_id`, `tem_permissao_de_aprovar`, `tem_auto_aprovacao`. Saída: um resultado com `pode` e `aprovacao_propria`. Regras: quem não é o solicitante pode se tem a permissão ou é o indicado; o solicitante só pode com auto-aprovação, e aí `aprovacao_propria` é verdadeiro |
| `precisa_indicar_aprovador(tem_permissao_de_aprovar, tem_auto_aprovacao)` | Verdadeiro só quando tem a primeira e não tem a segunda |

- **Testes:** sem banco. `Dinheiro`: cada entrada válida e inválida. Transições: **todos** os pares situação e
  comando, parametrizados a partir de uma tabela escrita no teste (independente da do código). `pode_decidir`: todas
  as combinações relevantes, incluindo o indicado que também é o solicitante (não pode).

## Checkpoint 2 — Modelos e motivos de decisão

- **O que muda:** `aprovacoes/models.py`, `aprovacoes/tipos.py` (tipos de decisão), migrações `0001` e `0002`,
  `services/motivos.py`, rotas `motivos/`.

| Peça | Comportamento |
| --- | --- |
| `Solicitacao`, `Versao`, `Decisao`, `MotivoDeDecisao` | Os campos da technical-spec. `Versao` e `Decisao` recusam alteração (exceto `lembrete_em` e `aviso_ao_admin_em` na versão) e exclusão. `Decisao.versao` é um para um |
| `tipos.registrar_tipo_de_decisao(codigo, nome)` | Mesmo padrão do catálogo de permissões. Registra `solicitacao.aprovar`, `solicitacao.contestar`, `solicitacao.recusar` |
| `services/motivos.py` | `listar(tipo_de_decisao, incluir_inativos)`, `criar`, `editar`, `desativar`, `reativar`: só admin; texto único por tipo, sem diferenciar maiúsculas (`MOTIVO_JA_EXISTE`); tipo de decisão desconhecido → `VALIDATION_ERROR`; auditoria de cada ação |
| `public.motivo_aplicado(motivo_id, tipo_de_decisao)` | Devolve o texto do motivo; recusa com `VALIDATION_ERROR` em `motivo_id` se não existe, está inativo ou é de outro tipo de decisão |
| Migração `0002_motivos_iniciais` | Os dez motivos da technical-spec; reversível (remove os que nenhuma decisão usa) |

- **Testes:** CA-29 a CA-31; imutabilidade de versão e de decisão; uma decisão por versão no banco; reversão das
  migrações.

## Checkpoint 3 — Tipos de solicitação e o ciclo do solicitante

- **O que muda:** `aprovacoes/tipos.py` (tipos de solicitação), `aprovacoes/public.py`, métodos do aggregate,
  `services/solicitacoes.py`, rotas de `solicitacoes/` (criar, retirar, reenviar, reabrir, editar, cancelar).

| Peça | Comportamento |
| --- | --- |
| `public.registrar_tipo(...)` e `MudancaDeSolicitacao` | Como na technical-spec. `preparar` devolve um objeto com `conteudo`, `valor` (`Dinheiro` ou nada) e `resumo` |
| Métodos do aggregate | `retirar`, `reenviar`, `reabrir`, `editar`, `cancelar`: cada um consulta `transicao_permitida`, levanta o código de erro da tabela da technical-spec e muda `situacao`. Os que criam versão recebem o conteúdo já preparado |
| `services/solicitacoes.py::enviar` | Confere a permissão de enviar do tipo (ou `le_gestao`); chama `preparar`; aplica `precisa_indicar_aprovador` e valida o indicado (INV-SOL-15); cria a solicitação e a versão 1; audita; notifica (checkpoint 6) |
| Demais serviços | Bloqueiam a linha (`select_for_update`), conferem quem pode (regra 11 da funcional), chamam o método, auditam e chamam `tipo.ao_mudar` com o acontecimento |
| Permissões | Registre `solicitacoes.auto_aprovar` (fora do acesso total), `solicitacoes.reabrir` e `solicitacoes.cancelar` no `ready` |

- **Fixture de teste:** registre o tipo `teste.pedido` (com valor, permissão `teste.aprovar`, `preparar` que exige
  `descricao` e `valor`, e um `ao_mudar` que guarda o que recebeu), e remova-o ao fim.
- **Testes:** CA-01, CA-02, CA-09 a CA-17, CA-20, CA-21 (a parte do envio); INV-SOL-05, 06, 08, 09, 12, 13, 15.

## Checkpoint 4 — Decisões

- **O que muda:** métodos `aprovar`, `contestar`, `recusar` no aggregate; `services/decisoes.py`; as três rotas.

| Peça | Comportamento |
| --- | --- |
| Quem pode | O serviço reúne os fatos (permissão de aprovar o tipo e auto-aprovação, de `permissoes.public.pode`; admin tem as duas) e chama `pode_decidir`. Solicitante sem auto-aprovação → `SOLICITANTE_NAO_DECIDE` (403); quem não pode → `PERMISSION_DENIED` (403) |
| Motivo | `public.motivo_aplicado` com o tipo de decisão certo; a decisão guarda a cópia do texto |
| Contestar | Exige mensagem; teto só se a versão tem valor (`TETO_SEM_VALOR`), e maior que zero |
| Efeitos | Cria a `Decisao`, muda a situação, audita, chama `tipo.ao_mudar`. Aprovação própria: marca a decisão e notifica o admin (checkpoint 6) |

- **Testes:** CA-03 a CA-08, CA-19, CA-21 a CA-25; INV-SOL-01 a 04, 07, 10, 11, 14. **Concorrência (CA-06):** com
  `@pytest.mark.django_db(transaction=True)` e duas threads, cada uma com a própria conexão, decidindo a mesma
  versão; exatamente uma tem sucesso.

## Checkpoint 5 — Execução, encerramento e isolamento entre tipos

- **O que muda:** `services/execucao.py`; `public.iniciar_execucao`, `public.encerrar`, `public.situacao_de`.
- Só a API pública em processo; **nenhuma rota**. Auditam `SOLICITACAO_EM_EXECUCAO` e `SOLICITACAO_ENCERRADA`.
- **Testes:** CA-15, CA-18 (nenhuma rota aceita esses comandos), CA-34 (dois tipos de teste; cada `ao_mudar` recebe
  só o seu; o teste de arquitetura confirma que `aprovacoes` não importa `financeiro` nem `eventos`).

## Checkpoint 6 — Notificações e lembretes

- **O que muda:** `aprovacoes/apps.py` (registra os tipos de notificação), chamadas a `notificacoes.public.notificar`
  nos serviços, `services/lembretes.py`, `aprovacoes/tasks.py`, agenda do Celery em `config/settings.py`.
- Destinatários de "quem pode decidir": `permissoes.public.quem_pode(tipo.permissao_de_aprovar)`, mais o indicado,
  menos o solicitante que não tem auto-aprovação. Chave de cada notificação: fato, solicitação e número da versão.
  Caminho no site: `/solicitacoes/<id>`.
- Lembretes: tarefa diária; 3 dias → quem pode decidir, grava `lembrete_em`; 7 dias → admins, grava
  `aviso_ao_admin_em`. Conta a partir de `Versao.criada_em` da versão atual.
- **Testes:** cada linha da tabela de notificações da funcional (quem recebe, se pede ação); CA-32 com o relógio
  fixado, rodando a tarefa duas vezes e depois com uma versão nova.

## Checkpoint 7 — Consultas

- **O que muda:** `services/consulta.py`; rotas `tipos/`, `solicitacoes/` (lista e detalhe), `fila/`,
  `solicitacoes/{id}/historico/`.
- O detalhe traz `acoes`: a lista dos comandos que quem pergunta pode executar agora, calculada com as mesmas funções
  puras e conferências dos serviços (extraia as conferências para funções reutilizadas; não as duplique).
- **Testes:** CA-26 a CA-28, CA-33 (histórico com todas as ações); `acoes` coerente com o que as rotas aceitam, para
  cada papel (solicitante, aprovador, indicado, admin, leitor).

## Checkpoint 8 — Site

- **O que muda:** `frontend/src/api/aprovacoes.ts`; telas `/solicitacoes` (lista com filtros), `/fila`,
  `/solicitacoes/:id` (versões, decisões, histórico e os botões de `acoes`), `/admin/motivos`; atalhos no menu.
- O formulário de cada ação pede o que a rota pede (motivo num seletor carregado de `motivos/`, texto, mensagem,
  teto). O conteúdo de uma versão é mostrado de forma genérica (chave e valor); o M7 e o M8 acrescentam a
  apresentação e o formulário de envio dos próprios tipos.
- **Testes:** cada tela com `simularApi`: lista e filtros; fila; detalhe com duas versões; aprovar, contestar e
  recusar com o seletor de motivo; botões seguindo `acoes`; tela de motivos.

## Checkpoint 9 — Validação final

1. `uv run poe verify` e `npm run verify`, com saída 0.
2. Suba o sistema. Como não há tipo real, exercite o ciclo pelo shell do Django, registrando um tipo temporário, ou
   por um comando de gestão só de desenvolvimento, e confira nas telas: fila, detalhe, decisão, notificação.
3. Documentação da lista da technical-spec, incluindo o adendo do canvas do aggregate (já escrito; confira se o
   código bate com ele); revisão de segurança neste plano; seção do M5 no modelo de ameaças.
4. Pull request de rascunho e relato ao dono.

## Matriz critério de aceite → teste

Inclui as invariantes do canvas (INV-SOL-NN). Caminhos de teste relativos a `backend/`.

| Critério | Teste |
| --- | --- |
| INV-SOL-02 (função pura, checkpoint 1) | `aprovacoes/tests/test_decisores.py::test_inv_sol_02_*` (8 casos: com e sem permissão, auto-aprovação, solicitante indicado) |
| INV-SOL-08 (tabela, checkpoint 1) | `aprovacoes/tests/test_transicoes.py::test_inv_sol_08_encerrada_e_cancelada_nao_aceitam_nenhum_comando` |
| INV-SOL-09 (tabela, checkpoint 1) | `aprovacoes/tests/test_transicoes.py::test_inv_sol_09_em_execucao_nao_edita_nao_cancela_nem_retira` |
| INV-SOL-10 (função pura, checkpoint 1) | `aprovacoes/tests/test_decisores.py::test_inv_sol_10_precisa_indicar_so_quem_aprovaria_o_proprio_pedido_sem_auto_aprovacao`, `::test_inv_sol_10_quem_aprovaria_o_proprio_pedido_precisa_indicar`, `::test_inv_sol_10_com_indicacao_valida_envia` |
| INV-SOL-11 (função pura, checkpoint 1) | `aprovacoes/tests/test_decisores.py::test_inv_sol_11_o_indicado_decide_sem_a_permissao_do_tipo`, `::test_inv_sol_11_o_indicado_de_outro_pedido_nao_decide_este` |
| INV-SOL-12 (função pura, checkpoint 1) | `aprovacoes/tests/test_decisores.py::test_inv_sol_12_retirar_so_em_analise` |
| INV-SOL-13 (função pura, checkpoint 1) | `aprovacoes/tests/test_decisores.py::test_inv_sol_13_reenviar_so_contestada_ou_retirada` |
| INV-SOL-15 (função pura, checkpoint 1) | `aprovacoes/tests/test_decisores.py::test_inv_sol_15_nao_indica_a_si_mesmo`, `::test_inv_sol_15_o_indicado_precisa_ler_gestao` |
| Adendo 1, A1 (função pura, checkpoint 1) | `aprovacoes/tests/test_decisores.py::test_indicacao_de_quem_nao_precisa_indicar_e_recusada` |
| Adendo 1, A3 (função pura, checkpoint 1) | `aprovacoes/tests/test_decisores.py::test_envio_exige_leitura_de_gestao_e_a_permissao_de_enviar` |
| Tabela de transições (checkpoint 1) | `aprovacoes/tests/test_transicoes.py::test_cada_par_situacao_e_comando` (80 pares, contra tabela escrita no teste), `::test_codigo_de_erro_de_situacao_de_cada_comando` |
| `Dinheiro` (checkpoint 1) | `kernel/tests/test_dinheiro.py` |
| CA-29 | `aprovacoes/tests/test_motivos.py::test_ca29_o_sistema_nasce_com_motivos_sugeridos` |
| CA-30 | `aprovacoes/tests/test_motivos.py::test_ca30_o_admin_cria_edita_e_desativa_e_a_lista_de_opcoes_muda`, `::test_ca30_a_decisao_antiga_continua_com_o_texto_que_tinha` |
| CA-31 | `aprovacoes/tests/test_motivos.py::test_ca31_quem_nao_e_admin_nao_altera_motivo`, `::test_ca31_quem_nao_e_admin_nao_cria_motivo`, `::test_ca31_o_servico_confere_o_admin_de_novo` |
| CA-33 (motivos, checkpoint 2) | `aprovacoes/tests/test_motivos.py::test_ca33_cada_acao_sobre_o_motivo_gera_registro_de_auditoria` |
| Adendo 1, A8 | `aprovacoes/tests/test_motivos.py::test_a8_motivo_com_o_texto_de_um_inativo_e_recusado` |
| INV-SOL-05 (modelo e banco, checkpoint 2) | `aprovacoes/tests/test_modelos.py::test_inv_sol_05_versao_nao_muda`, `::test_banco_recusa_alterar_e_apagar_versao` |
| INV-SOL-14 | `aprovacoes/tests/test_modelos.py::test_inv_sol_14_uma_decisao_por_versao_no_banco` |
| Imutabilidade da decisão (adendo 1) | `aprovacoes/tests/test_modelos.py::test_decisao_nao_muda`, `::test_banco_recusa_alterar_e_apagar_decisao`, `::test_nada_e_apagado` |
| CA-01 (envio, checkpoint 3a; a notificação entra no 6) | `aprovacoes/tests/test_envio.py::test_ca01_envio_valido_fica_em_analise_com_a_versao_1`, `::test_ca01_o_modulo_dono_envia_pela_api_publica` |
| CA-02 | `aprovacoes/tests/test_envio.py::test_ca02_tipo_desconhecido_nao_cria_nada`, `::test_ca02_conteudo_recusado_pelo_modulo_dono_nao_cria_nada` |
| CA-20 | `aprovacoes/tests/test_envio.py::test_ca20_*` (sem indicar, a si mesmo, inativo, sem cargo, inexistente) |
| CA-21 (envio, checkpoint 3a) | `aprovacoes/tests/test_envio.py::test_ca21_a_indicacao_valida_fica_na_solicitacao_e_no_historico` |
| CA-24 (envio, checkpoint 3a) | `aprovacoes/tests/test_envio.py::test_ca24_acesso_total_sem_auto_aprovacao_precisa_indicar` |
| CA-33 (envio, checkpoint 3a) | `aprovacoes/tests/test_envio.py::test_ca33_o_envio_gera_registro_de_auditoria` |
| INV-SOL-10 e INV-SOL-15 (serviço, checkpoint 3a) | os `test_ca20_*` e `test_ca21_*` acima |
| Adendo 1, A1 (serviço) | `aprovacoes/tests/test_envio.py::test_a1_indicar_sem_precisar_e_recusado` |
| Adendo 1, A3 (serviço) | `aprovacoes/tests/test_envio.py::test_a3_tipo_com_permissao_de_enviar_exige_a_permissao_e_o_cargo` |
| `registrar_tipo` (adendo 1) | `aprovacoes/tests/test_envio.py::test_registrar_tipo_*`, `::test_tipo_com_valor_que_nao_devolve_valor_e_erro_de_programacao` |

## Revisão de segurança

Preenchida no checkpoint 9.

| Item | Achado | Mitigação | Status |
| --- | --- | --- | --- |

## Definition of Done

- [ ] Checkpoints concluídos, com evidência.
- [ ] Todo CA com ao menos um teste; INV-SOL-01 a INV-SOL-15, cada uma com teste, e a coluna "Teste" do canvas
      preenchida.
- [ ] Verificação completa com saída 0; cobertura dentro da meta.
- [ ] Fronteiras de módulo verificadas.
- [ ] Revisão de segurança registrada, sem achado crítico ou alto aberto.
- [ ] Migrations reversíveis; dados iniciais classificados.
- [ ] Contrato, `docs/api/` e guia de teste manual atualizados.
- [ ] Registro de requisitos, decisões e riscos atualizados.
- [ ] CI verde no GitHub.
- [ ] Critérios de aceite validados e aprovados pelo dono.

## Evidências de verificação

### Checkpoint 1 — Domínio puro (2026-11-13)

- Ponto de partida (`dev` em `baccaa2`): `uv run poe verify` em `backend/`, saída 0, 576 testes;
  `npm run verify` em `frontend/`, saída 0, 129 testes.
- `uv run poe verify` em `backend/`: saída 0, 751 testes (576 + 175 novos), cobertura 97,97%, contratos do
  import-linter 1 mantido, 0 quebrados; nenhuma migração pendente.
- Nenhum teste existente alterado.
- Além do que o plano lista, já aqui (adendo 1 da technical-spec): `avaliar(comando, fatos)`, `avaliar_envio`,
  `acoes_disponiveis` e o mapa comando → código de erro de situação (`ERRO_DE_SITUACAO`).
- O solicitante com auto-aprovação só decide o próprio pedido se também tiver a permissão de aprovar o tipo: a
  auto-aprovação é exceção à regra do próprio pedido, e o adendo 1 (A2) exige a permissão de aprovar para decidir.
  O admin tem as duas pelo catálogo.
- Reabrir e cancelar de outra pessoa sem a permissão respondem `PERMISSION_DENIED`; `SO_O_SOLICITANTE` fica para
  retirar, reenviar e editar, que só o solicitante faz.

### Checkpoint 2 — Modelos, motivos e imutabilidade (2026-11-13)

- `uv run poe verify` em `backend/`: saída 0, 806 testes (751 + 55 novos), cobertura 97,79%, contratos do
  import-linter 1 mantido, 0 quebrados; `migrations-check` sem pendência.
- Migrações: `0001_solicitacao_versao_decisao_motivo`, `0002_motivos_iniciais` (referência obrigatória; a
  reversão remove só os que nenhuma decisão usa) e `0003_versao_e_decisao_imutaveis` (gatilhos). Reversão e
  reaplicação testadas (`test_migracoes_revertem_e_reaplicam_com_os_motivos_iniciais`).
- O gatilho da versão compara a linha inteira, menos as duas datas de lembrete (`to_jsonb(NEW) - ...`): uma
  coluna nova também fica protegida sem mudar o gatilho.
- `tests/apoio.py` ganhou `dar_cargo`, `conceder`, `registrar_permissao_de_teste` e
  `remover_permissao_de_teste` (os testes de `aprovacoes` não importam os internos de `permissoes`).
- Rotas novas: `motivos/` (lista e criação), `motivos/{id}/editar|desativar|reativar/` e `tipos-de-decisao/`
  (adendo 1). `?todos=1` de quem não é admin responde 403, em vez de ser ignorado.
- Nenhum teste existente alterado.

### Checkpoint 3a — Tipos de solicitação e envio (2026-11-13)

- `uv run poe verify` em `backend/`: saída 0, 833 testes (806 + 27 novos), cobertura 97,81%, contratos do
  import-linter 1 mantido, 0 quebrados; nenhuma migração pendente.
- `registrar_tipo`, `enviar`, `ConteudoPreparado`, `MudancaDeSolicitacao` e `Acontecimento` na API pública;
  rota `POST solicitacoes/`. As permissões `solicitacoes.auto_aprovar` (fora do acesso total),
  `solicitacoes.reabrir` e `solicitacoes.cancelar` entram no catálogo no `ready`.
- `registrar_tipo` falha se a permissão de aprovar ou de enviar não está no catálogo; o `preparar` roda dentro da
  transação do serviço, e o que ele devolve é conferido (valor de acordo com `tem_valor`; resumo cortado em 200
  com reticências).
- A rota declara `LeGestao`, como as demais do projeto, e por isso quem não lê gestão recebe 403 antes da
  validação da entrada (400). A ordem do adendo (entrada → leitura) vale para quem passa pela rota; o ponto que
  ela protege, a leitura antes da existência, continua valendo. Relatado ao dono no checkpoint 4.
- Nenhum teste existente alterado.

## Rollback ou recuperação

As migrações revertem com `python manage.py migrate aprovacoes zero`. A versão anterior é o commit de merge do M4 na `dev` (`ca84df0`).
