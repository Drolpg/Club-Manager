# Plano de Implementação: Motor de solicitações e aprovações

| Campo | Valor |
| --- | --- |
| Feature | `aprovacoes/motor-de-solicitacoes` |
| Status | Implemented |
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
| CA-09 | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_ca09_a_contestada_reenviada_vira_a_versao_seguinte_e_a_anterior_continua` |
| CA-10 | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_ca10_a_recusada_reaberta_com_justificativa_vira_versao_nova_por_varias_rodadas`, `::test_ca10_reabrir_sem_justificativa_e_recusado` |
| CA-11 | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_ca11_so_o_admin_ou_quem_tem_a_permissao_reabre_a_de_outra_pessoa` |
| CA-12 (checkpoint 3b; a fila entra no 7) | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_ca12_o_solicitante_retira_a_solicitacao_em_analise`, `::test_ca12_a_retirada_volta_por_reenvio_como_versao_nova` |
| CA-13 | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_ca13_ninguem_alem_do_solicitante_retira` |
| CA-14 | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_ca14_a_aprovada_editada_vira_versao_nova_em_analise_e_o_dono_e_avisado` |
| CA-15 (editar, retirar e cancelar) | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_ca15_em_execucao_nao_edita_nao_retira_nem_cancela` |
| CA-16 | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_ca16_o_solicitante_cancela_com_motivo`, `::test_ca16_cancelar_sem_motivo_e_recusado`, `::test_ca16_inv_sol_08_cancelada_e_encerrada_nao_aceitam_mais_nada` |
| CA-17 | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_ca17_so_o_admin_ou_quem_tem_a_permissao_cancela_a_de_outra_pessoa` |
| CA-33 (ações do solicitante) | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_ca33_cada_acao_do_solicitante_gera_registro_de_auditoria` |
| INV-SOL-05 e INV-SOL-13 (serviço) | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_ca09_a_contestada_reenviada_vira_a_versao_seguinte_e_a_anterior_continua`, `::test_inv_sol_13_so_se_reenvia_contestada_ou_retirada` |
| INV-SOL-06 | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_inv_sol_06_a_versao_nova_da_editada_nao_tem_decisao` |
| INV-SOL-08 (serviço) | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_ca16_inv_sol_08_cancelada_e_encerrada_nao_aceitam_mais_nada` |
| INV-SOL-09 (serviço) | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_ca15_em_execucao_nao_edita_nao_retira_nem_cancela` |
| INV-SOL-12 (serviço) | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_inv_sol_12_a_retirada_nao_cria_versao`, `::test_inv_sol_12_so_se_retira_em_analise` |
| Adendo 1, A4 | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_a4_reabrir_sem_conteudo_copia_a_anterior_valida_em_nome_do_solicitante_e_o_autor_e_quem_reabriu` |
| Adendo 1, A11 (textos do solicitante) | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_textos_livres_ate_1000_caracteres` |
| Erro no módulo dono desfaz a ação | `aprovacoes/tests/test_ciclo_do_solicitante.py::test_o_erro_no_aviso_ao_modulo_dono_desfaz_a_acao` |
| CA-03 (checkpoint 4; a notificação entra no 6) | `aprovacoes/tests/test_decisoes.py::test_ca03_o_aprovador_aprova_com_motivo_e_a_decisao_guarda_tudo` |
| CA-04 | `aprovacoes/tests/test_decisoes.py::test_ca04_decisao_sem_motivo_e_recusada`, `::test_ca04_motivo_desativado_e_recusado`, `::test_ca04_motivo_de_outro_tipo_de_decisao_e_recusado` |
| CA-05 e INV-SOL-01 | `aprovacoes/tests/test_decisoes.py::test_ca05_inv_sol_01_fora_de_analise_nao_se_decide` (7 situações × 3 decisões), `::test_inv_sol_01_a_decisao_vale_para_a_versao_vigente` |
| CA-06 | `aprovacoes/tests/test_concorrencia.py::test_ca06_duas_decisoes_simultaneas_so_uma_vale` (duas threads; 15 de 15 verdes em sequência); segunda barreira: `test_modelos.py::test_inv_sol_14_uma_decisao_por_versao_no_banco` |
| CA-07 (checkpoint 4; a notificação entra no 6) | `aprovacoes/tests/test_decisoes.py::test_ca07_o_aprovador_contesta_com_motivo_mensagem_e_teto` |
| CA-08 | `aprovacoes/tests/test_decisoes.py::test_ca08_inv_sol_04_contestar_sem_mensagem_e_recusado`, `::test_ca08_inv_sol_07_teto_em_solicitacao_sem_valor_e_recusado` |
| CA-12 (não pode ser decidida) | `aprovacoes/tests/test_decisoes.py::test_ca12_a_retirada_nao_pode_ser_decidida` |
| CA-19 | `aprovacoes/tests/test_decisoes.py::test_ca19_sem_a_permissao_nao_decide_o_proprio_nem_o_de_outro` |
| CA-21 (decisão) e INV-SOL-11 | `aprovacoes/tests/test_decisoes.py::test_ca21_inv_sol_11_o_indicado_decide_aquela_solicitacao_e_nenhuma_outra`, `::test_inv_sol_11_a_indicacao_vale_para_as_versoes_seguintes`, `::test_p3_com_indicado_os_demais_aprovadores_e_o_admin_continuam_decidindo` |
| CA-22 | `aprovacoes/tests/test_decisoes.py::test_ca22_inv_sol_02_quem_tem_a_permissao_sem_auto_aprovacao_nao_decide_o_proprio_mesmo_com_indicado` |
| CA-23 (checkpoint 4; o aviso ao admin entra no 6) | `aprovacoes/tests/test_decisoes.py::test_ca23_inv_sol_02_com_auto_aprovacao_decide_o_proprio_marcado_como_aprovacao_propria` |
| CA-24 (decisão) | `aprovacoes/tests/test_decisoes.py::test_ca24_inv_sol_02_acesso_total_sem_auto_aprovacao_nao_decide_o_proprio`, `::test_ca24_acesso_total_decide_o_de_outro` |
| CA-25 | `aprovacoes/tests/test_decisoes.py::test_ca25_inv_sol_02_o_admin_decide_qualquer_uma_inclusive_a_propria` |
| CA-33 (decisões) | `aprovacoes/tests/test_decisoes.py::test_ca33_cada_decisao_gera_registro_de_auditoria` |
| INV-SOL-02 (serviço, todos os caminhos) | `test_ca19_*`, `test_ca22_*`, `test_ca21_*`, `test_ca24_*`, `test_ca23_*`, `test_ca25_*` acima |
| INV-SOL-03 | `aprovacoes/tests/test_decisoes.py::test_inv_sol_03_a_versao_decidida_nao_recebe_outra_decisao` |
| INV-SOL-04 | `aprovacoes/tests/test_decisoes.py::test_ca08_inv_sol_04_contestar_sem_mensagem_e_recusado`, `::test_inv_sol_04_contestar_sem_teto_tambem_vale`, `::test_ca04_*` |
| INV-SOL-07 | `aprovacoes/tests/test_decisoes.py::test_ca08_inv_sol_07_teto_em_solicitacao_sem_valor_e_recusado`, `::test_inv_sol_07_teto_precisa_ser_maior_que_zero` |
| Adendo 1, A2 | `aprovacoes/tests/test_decisoes.py::test_a2_quem_tem_a_permissao_e_nao_tem_cargo_nao_decide`, `::test_a2_o_servico_tambem_exige_a_leitura_de_gestao` |
| Adendo 1, A11 (textos da decisão) | `aprovacoes/tests/test_decisoes.py::test_a11_textos_da_decisao_ate_1000_caracteres` |
| Adendo 1, A12 | `aprovacoes/tests/test_decisoes.py::test_adendo_a12_teto_maior_que_o_valor_pedido_e_aceito` |
| Erro no módulo dono desfaz a decisão | `aprovacoes/tests/test_decisoes.py::test_o_erro_no_aviso_ao_modulo_dono_desfaz_a_decisao` |
| CA-15 (pelo caminho real, checkpoint 5) | `aprovacoes/tests/test_execucao.py::test_ca15_inv_sol_09_depois_de_iniciada_a_execucao_nao_edita_nao_retira_nem_cancela` |
| CA-18 | `aprovacoes/tests/test_execucao.py::test_ca18_nenhuma_rota_poe_em_execucao_ou_encerra`, `::test_ca18_nenhum_nome_de_rota_fala_de_execucao_ou_encerramento` |
| CA-34 | `aprovacoes/tests/test_execucao.py::test_ca34_com_dois_tipos_cada_modulo_recebe_so_os_avisos_do_seu`, `::test_ca34_o_motor_nao_importa_financeiro_nem_eventos`; `tests/test_architecture.py` |
| CA-33 (execução e encerramento) | `aprovacoes/tests/test_execucao.py::test_o_modulo_dono_poe_a_aprovada_em_execucao`, `::test_o_modulo_dono_encerra_a_aprovada_ou_em_execucao`, `::test_sem_ator_a_execucao_fica_registrada_como_do_sistema` |
| INV-SOL-08 (encerramento) | `aprovacoes/tests/test_execucao.py::test_inv_sol_08_so_aprovada_ou_em_execucao_encerra` |
| `iniciar_execucao` só de aprovada | `aprovacoes/tests/test_execucao.py::test_so_a_aprovada_entra_em_execucao` |
| CA-01 (notificação) e linha 1 da tabela | `aprovacoes/tests/test_notificacoes.py::test_ca01_o_envio_notifica_quem_pode_decidir_e_pede_acao`, `::test_a_versao_nova_notifica_quem_pode_decidir_de_novo` (reenviada, reaberta, editada), `::test_o_solicitante_com_auto_aprovacao_tambem_e_avisado_porque_pode_decidir` |
| CA-03 (notificação) e linha 2 | `aprovacoes/tests/test_notificacoes.py::test_ca03_a_decisao_notifica_o_solicitante_sem_pedir_acao` (aprovada e recusada) |
| CA-07 (notificação) e linha 3 | `aprovacoes/tests/test_notificacoes.py::test_ca07_a_contestacao_notifica_o_solicitante_com_texto_padrao_mensagem_e_teto` |
| CA-21 (notificação), linha 4 e A6 | `aprovacoes/tests/test_notificacoes.py::test_ca21_a6_o_indicado_recebe_so_o_aviso_de_indicacao_e_o_admin_e_informado`, `::test_a6_nas_versoes_seguintes_o_indicado_recebe_o_aviso_de_decidir` |
| CA-23 (notificação), linha 5 e A5 | `aprovacoes/tests/test_notificacoes.py::test_ca23_a_aprovacao_propria_avisa_os_admins`, `::test_a5_a_aprovacao_propria_de_um_admin_avisa_os_outros_admins`, `::test_a5_sem_outro_admin_fica_so_a_auditoria` |
| CA-32, linhas 6 e 7 e A10 | `aprovacoes/tests/test_lembretes.py::test_ca32_antes_de_3_dias_ninguem_e_lembrado`, `::test_ca32_aos_3_dias_corridos_quem_pode_decidir_e_lembrado`, `::test_ca32_aos_7_dias_o_admin_e_avisado`, `::test_ca32_rodar_de_novo_nao_repete_nenhum_dos_dois`, `::test_ca32_a_versao_nova_zera_a_contagem`, `::test_so_a_solicitacao_em_analise_e_lembrada`, `::test_a10_a_tarefa_roda_uma_vez_por_dia_de_manha` |
| Linha 8 e A7 | `aprovacoes/tests/test_notificacoes.py::test_retirada_ou_cancelada_em_analise_avisa_quem_podia_decidir`, `::test_a7_cancelada_fora_da_analise_nao_avisa_que_saiu_da_fila` |
| A11 (texto da notificação) | `aprovacoes/tests/test_notificacoes.py::test_a11_o_texto_da_notificacao_e_cortado_para_caber` |
| Chave impede duplicata | `aprovacoes/tests/test_notificacoes.py::test_a_notificacao_nao_se_repete_para_o_mesmo_fato` |
| CA-12 (sai da fila) | `aprovacoes/tests/test_consultas.py::test_ca26_a_retirada_sai_da_fila` |
| CA-26 e A9 (fila) | `aprovacoes/tests/test_consultas.py::test_ca26_a_fila_traz_so_o_que_o_aprovador_pode_decidir_da_mais_antiga_para_a_mais_nova`, `::test_a9_a_fila_conta_a_espera_a_partir_da_versao_atual`, `::test_ca26_o_indicado_ve_so_a_que_foi_indicado`, `::test_ca26_com_auto_aprovacao_a_propria_aparece`, `::test_ca26_o_admin_ve_todas_inclusive_as_proprias`, `::test_ca26_quem_nao_aprova_o_tipo_tem_a_fila_vazia` |
| A2 (fila) | `aprovacoes/tests/test_consultas.py::test_a2_a_fila_exige_leitura_de_gestao` |
| CA-27 e A9 (lista) | `aprovacoes/tests/test_consultas.py::test_ca27_quem_tem_cargo_ve_todas_da_mais_recente_para_a_mais_antiga`, `::test_ca27_filtros_por_tipo_situacao_e_as_minhas`, `::test_ca27_a_lista_e_paginada`, `::test_ca27_parametros_invalidos_da_lista`, `::test_ca27_diretor_sem_cargo_nao_ve_a_lista` |
| CA-28 | `aprovacoes/tests/test_consultas.py::test_ca28_o_detalhe_mostra_versoes_decisoes_indicacao_e_acoes`, `::test_ca28_detalhe_e_historico_exigem_leitura_e_respondem_404` |
| CA-33 (histórico com todas as ações) | `aprovacoes/tests/test_consultas.py::test_ca28_e_ca33_o_historico_traz_todas_as_acoes_com_os_nomes` |
| Paridade entre `acoes` e as rotas | `aprovacoes/tests/test_consultas.py::test_acoes_do_detalhe_coincidem_com_o_que_as_rotas_aceitam` (6 papéis × 8 situações × 8 comandos) |
| Tipos registrados | `aprovacoes/tests/test_consultas.py::test_quem_le_gestao_ve_os_tipos_registrados`, `::test_os_tipos_exigem_leitura_de_gestao` |
| Site: menu e guarda (checkpoint 8a) | `frontend/src/aprovacoes.test.tsx` — "menu e guarda das telas de aprovações" (3 testes) |
| CA-27 (site) | `frontend/src/aprovacoes.test.tsx` — "lista de solicitações" (situação, valor, solicitante; filtros; carregar mais; erro) |
| CA-26 (site) | `frontend/src/aprovacoes.test.tsx` — "fila de pendências" (ordem da API; fila vazia) |
| CA-28 (site) | `frontend/src/aprovacoes.test.tsx` — "detalhe da solicitação" (cabeçalho e versões; decisão; conteúdo genérico como texto; histórico; 404) |
| Botões seguindo `acoes` (site, checkpoint 8b) | `frontend/src/aprovacoes.test.tsx` — "mostra só os botões que vieram em acoes", "sem nenhuma ação, a seção de ações não aparece" |
| CA-03, CA-07, CA-08 (site) | `frontend/src/aprovacoes.test.tsx` — "aprova com o motivo escolhido…", "contesta com motivo, mensagem e teto sugerido", "sem valor no tipo, a contestação não pede teto", "recusa com o motivo da lista de recusa", "mostra o erro da API e os erros por campo", "mostra a recusa de quem não pode decidir" |
| CA-09, CA-10, CA-12, CA-14, CA-16 (site) | `frontend/src/aprovacoes.test.tsx` — "retira com uma confirmação", "cancela com motivo e reabre com justificativa", "reenvia o conteúdo editado…", "conteúdo que não é JSON não é enviado" |
| CA-29 a CA-31 (site) | `frontend/src/aprovacoes.test.tsx` — "motivos de decisão" (5 testes: lista por tipo com inativos, criar, editar/desativar/reativar, repetido, não admin) |
| Tipo de demonstração (adendo 1) | `aprovacoes/tests/test_demonstracao.py` (com `DEBUG` desligado a variável é ignorada; com `DEBUG` ligado e sem a variável, nada; com os dois, o tipo existe e funciona) |

## Revisão de segurança

| Item | Achado | Mitigação | Status |
| --- | --- | --- | --- |
| Decidir o próprio pedido (INV-SOL-02) | Seis caminhos (sem permissão, com permissão, indicado, acesso total, auto-aprovação, admin) passam pela mesma função pura | Testes por caminho; `acoes` e rotas com teste de paridade | Sem achado aberto |
| Elevação pela indicação | Quem não precisa indicar poderia escolher quem decide | Recusado (A1); o indicado decide só aquela solicitação, sem ganhar permissão | Sem achado aberto |
| Decisão sem cargo | Quem tem a permissão por concessão individual e não tem cargo | Decidir e ver a fila exigem a leitura de gestão (A2) | Sem achado aberto |
| Enumeração de IDs | Uma solicitação inexistente responderia 404 a quem não lê | Leitura de gestão antes da existência; 403 igual nos dois casos | Sem achado aberto |
| Concorrência | Duas decisões na mesma versão | Bloqueio da linha; índice único; teste com duas threads | Sem achado aberto |
| Imutabilidade | Versão e decisão alteradas por `QuerySet.update` ou SQL | Gatilho no banco, com teste por SQL direto | Sem achado aberto |
| Conteúdo do tipo | JSON livre vindo do cliente | Objeto de até 64 KB, validado pelo módulo dono, mostrado como texto (teste com HTML) | Sem achado aberto |
| Textos livres e notificação | Mensagem longa estoura o limite da notificação | Até 1000 caracteres na entrada; corte na notificação (A11) | Sem achado aberto |
| Tipo de demonstração | Existir em produção | Só com `DEBUG` ligado (teste e conferência no contêiner); fora do `compose.yaml` | Sem achado aberto |
| Logs | Dado pessoal no log | O aviso do tipo de demonstração loga só ID e código; nenhum outro log novo | Sem achado aberto |
| Aprovador indicado desativado | O pedido pode ficar parado | Os demais aprovadores e o admin decidem; aviso de 7 dias ao admin | Aceito (backlog) |
| Dependências | Nenhuma dependência nova | — | Sem achado |

Modelo de ameaças: seção "M5: motor de aprovações" em `docs/security/threat-model.md`. Nenhum achado crítico ou
alto aberto. Não rodei SCA, SAST nem DAST neste marco.

## Definition of Done

- [x] Checkpoints concluídos, com evidência.
- [x] Todo CA com ao menos um teste; INV-SOL-01 a INV-SOL-15, cada uma com teste, e a coluna "Teste" do canvas
      preenchida.
- [x] Verificação completa com saída 0; cobertura dentro da meta (backend 97,8%; site com 160 testes).
- [x] Fronteiras de módulo verificadas.
- [x] Revisão de segurança registrada, sem achado crítico ou alto aberto.
- [x] Migrations reversíveis; dados iniciais classificados.
- [x] Contrato, `docs/api/` e guia de teste manual atualizados.
- [x] Registro de requisitos, decisões e riscos atualizados.
- [x] CI verde no GitHub (PR #4, workflows `backend` e `frontend`, 2026-11-14).
- [x] Critérios de aceite validados e aprovados pelo dono (Leandro Nascimento, 2026-11-14). A
      implementação foi feita por uma sessão executora e revisada por outra em dois momentos (depois
      do checkpoint 4 e no fim), contra a spec, os adendos e este plano. A revisão final leu o backend;
      o código das telas do site não foi lido, só exercitado.

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

### Checkpoint 3b — Retirar, reenviar, reabrir, editar e cancelar (2026-11-13)

- `uv run poe verify` em `backend/`: saída 0, 883 testes (833 + 50 novos), cobertura 97,68%, contratos do
  import-linter 1 mantido, 0 quebrados; nenhuma migração pendente.
- Cinco rotas, uma view por comando (para o contrato mostrar a entrada de cada um). Os serviços seguem a ordem
  do adendo: entrada → leitura de gestão → existência (com a linha bloqueada) → `avaliar` → `preparar` →
  método do aggregate → auditoria → aviso ao módulo dono. A autorização (`avaliar`) fica separada da mudança de
  estado (método do aggregate), que confere a transição de novo.
- Os códigos de erro e as mensagens foram para `aprovacoes/erros.py`, usado pelo aggregate e pelos serviços.
- O reenvio não avisa o módulo dono: `REENVIADA` não está na lista de acontecimentos da technical-spec (o aviso
  no envio e no reenvio ficou para o M7 e o M8, adendo 1).
- Nos testes deste checkpoint, contestada, recusada, aprovada, em execução e encerrada são postas direto no banco
  para montar o cenário, porque as decisões e a execução só entram nos checkpoints 4 e 5.
- Nenhum teste existente alterado.

### Checkpoint 4 — Decisões e concorrência (2026-11-13)

- `uv run poe verify` em `backend/`: saída 0, 948 testes (883 + 65 novos), cobertura 97,64%, contratos do
  import-linter 1 mantido, 0 quebrados; nenhuma migração pendente.
- Teste de concorrência (CA-06) rodado 15 vezes seguidas, sozinho: 15 verdes. Ele cria os próprios dados (motivos
  inclusive), porque um teste transacional anterior esvazia as sementes.
- O teto sugerido entra como texto e vira `Dinheiro` no serviço: nunca passa por ponto flutuante. Zero, negativo,
  mais de duas casas e texto que não é número são recusados com `VALIDATION_ERROR` em `teto_sugerido`.
- A auditoria da decisão leva no `justificativa` o texto do motivo, e em `dados` a versão, a decisão, o motivo e
  a marca de aprovação própria.
- Nenhum teste existente alterado.

### Checkpoint 5 — Execução, encerramento e isolamento entre tipos (2026-11-13)

- `uv run poe verify` em `backend/`: saída 0, 978 testes (948 + 30 novos), cobertura 97,72%, contratos do
  import-linter 1 mantido, 0 quebrados; nenhuma migração pendente.
- Ajuste pedido na revisão dos checkpoints 1 a 4: os testes do 3b e do 4 deixaram de gravar a situação direto no
  banco. O cenário é montado por `levar_a` (em `aprovacoes/tests/conftest.py`), que leva a solicitação da análise
  até a situação pedida pelos serviços reais: decisões por um aprovador de cenário, retirar e cancelar pelo
  solicitante, e `public.iniciar_execucao` e `public.encerrar`. Os avisos ao módulo dono gerados pelo cenário são
  tirados da lista do tipo de teste, e por isso as asserções sobre `ao_mudar` ficaram as mesmas. Duas mudanças de
  seleção, sem mudar o que se espera: a auditoria do `test_ca33` do 3b passou a filtrar as ações do solicitante
  (as decisões do cenário são de outro ator), e o `test_ca05` do 4 passou de "nenhuma decisão existe" para
  "nenhuma decisão nova", porque a aprovada, a contestada e a recusada agora têm a decisão que as levou até ali.
- Ainda criam linhas direto pelo ORM só `test_modelos.py` e `test_motivos.py::_decisao_com`: eles testam a
  persistência (imutabilidade no modelo e no banco, unicidade, a cópia do texto do motivo) e não passam pelo
  ciclo; nenhum deles grava uma situação diferente de `EM_ANALISE`.
- `iniciar_execucao`, `encerrar` e `situacao_de` na API pública, sem rota; recebem `ator_id` opcional (adendo 1)
  e não avisam o módulo dono de volta, porque foi ele quem pediu a mudança. A API pública devolve `None` ou a
  `Situacao`, e não o modelo.
- Nenhum teste anterior a esta branch alterado.

### Checkpoint 6 — Notificações e lembretes (2026-11-13)

- `uv run poe verify` em `backend/`: saída 0, 1013 testes (978 + 35 novos), cobertura 97,67%, contratos do
  import-linter 1 mantido, 0 quebrados; nenhuma migração pendente.
- Duas verificações falharam antes desta, por motivos diferentes e corrigidos: (1) o teste da agenda importava
  `config.celery`, e `aprovacoes` não pode importar `config` (contrato de camadas); passou a ler
  `settings.CELERY_BEAT_SCHEDULE`, que é de onde o Celery tira a agenda; (2)
  `test_ca32_a_versao_nova_zera_a_contagem` passava sozinho e falhava na suíte, porque o reenvio usava o relógio real, que andou uns 90 segundos desde a
  importação do módulo; o relógio passou a ser fixado também no reenvio.
- Os nove tipos de notificação se registram no `ready`. A chave é `<tipo>:<solicitação>:<número da versão>`.
  Os testes leem as notificações pela caixa de cada destinatário (`GET notificacoes/`), sem importar os internos
  de `notificacoes`.
- "Quem pode decidir" usa a mesma função pura da decisão (`pode_decidir`) e exige a leitura de gestão (A2): quem
  tem a permissão e não tem cargo não é avisado, porque não pode decidir.
- O aviso de "saiu da fila" não vai para quem fez a retirada ou o cancelamento.
- Lembretes: serviço `lembrar_paradas(agora)`, uma transação por solicitação, com a linha bloqueada; a tarefa
  `aprovacoes.lembrar_solicitacoes_paradas` só chama o serviço, e a agenda a roda às 8h (America/Sao_Paulo).
- O teste de concorrência agora também dispara as notificações e o e-mail depois do commit: 5 de 5 verdes
  rodado em sequência.
- Nenhum teste anterior a esta branch alterado.

### Checkpoint 7 — Consultas e paridade (2026-11-13)

- `uv run poe verify` em `backend/`: saída 0, 1082 testes (1013 + 69 novos), cobertura 97,82%, contratos do
  import-linter 1 mantido, 0 quebrados; nenhuma migração pendente.
- Rotas: `tipos/`, `fila/`, `solicitacoes/` (lista, com `tipo`, `situacao`, `minhas`, `antes` e `limite`),
  `solicitacoes/{id}/` (detalhe, com `acoes`) e `solicitacoes/{id}/historico/`. Todas com `LeGestao`; a fila
  também (adendo 1, A2), e não "logado", como a tabela de rotas da technical-spec dizia antes do adendo.
- `acoes` sai de `acoes_disponiveis`, a mesma função pura que os serviços usam; os nomes são os das rotas
  (`retirar`, `aprovar`...). A fila é a regra de `pode_decidir` escrita como consulta, e a paridade das duas é
  coberta pelos testes de fila por papel.
- Teste de paridade: para cada um dos 6 papéis (solicitante que precisou indicar, indicado, aprovador, admin,
  leitor, quem reabre e cancela de outros) e cada uma das 8 situações, toda ação em `acoes` é aceita pela rota
  (200) e toda ação fora dela é recusada (403 ou 422).
- Os testes do checkpoint foram escritos antes do código, mas o código foi escrito antes de eu rodá-los. Para
  conferir a falha pelo motivo certo, tirei o código de lado e rodei: 68 de 69 falharam (rotas inexistentes);
  depois o devolvi.
- Nenhum teste anterior a esta branch alterado.

### Checkpoint 8a — Site: cliente, guarda, menu, lista, fila e detalhe (2026-11-14)

- `npm run verify` em `frontend/`: saída 0, 143 testes (129 + 14 novos), cobertura de linhas 95,38%
  (`Aprovacoes.tsx` 96,1%); lint e build sem aviso. O backend não mudou neste checkpoint.
- Os atalhos ficam num menu próprio, "Aprovações" (Fila de pendências, Solicitações), para quem tem cargo e
  para o admin. Não entraram no menu "Administração", porque um teste existente
  (`notificacoes.test.tsx`, "mostra o nome, o menu do admin…") fixa a lista exata dos links dele. A moldura
  não ganhou consulta nova: o menu depende só da sessão (`admin`, `tem_cargo`).
- Guarda `ProtegidaDeGestao`: sem cargo e sem ser admin, volta à página inicial; sem sessão, vai para entrar.
- Dinheiro chega da API como texto e é formatado em reais só mexendo no texto (`formatos.reais`), sem passar
  por ponto flutuante. O conteúdo de cada versão é mostrado de forma genérica (chave e valor, listas e objetos
  aninhados), sempre como texto.
- Nenhum teste existente alterado.

### Checkpoint 8b — Site: formulários das ações e tela de motivos (2026-11-14)

- `npm run verify` em `frontend/`: saída 0, 160 testes (143 + 17 novos), cobertura de linhas 95,57%; lint e
  build sem aviso.
- A primeira verificação completa falhou num teste existente, `App.test.tsx` > "entra com a credencial
  devolvida pelo Google", por tempo (5056 ms contra o limite de 5 s). Sozinho, o arquivo passou 26 de 26, e o
  teste entra como diretor sem cargo, que não passa por nada do que este checkpoint mudou. A verificação
  seguinte passou inteira. Leio como instabilidade por carga (os arquivos rodam em paralelo com cobertura, e o
  arquivo novo é pesado); não alterei o teste. Fica o risco de voltar a acontecer no CI.
- A seção "Ações" mostra só os comandos que vieram em `acoes`. Aprovar, contestar e recusar carregam os motivos
  do tipo de decisão certo num seletor; o teto só aparece quando o tipo tem valor. Reenviar e editar mostram o
  conteúdo da versão atual em JSON, num campo de texto: o site do motor não conhece o formato de nenhum tipo, e
  o M7 e o M8 trocam esse campo pelo formulário dos tipos deles. Depois de cada comando, o detalhe e o histórico
  vêm de novo da API.
- Tela `/admin/motivos`, só do admin, com o atalho "Motivos de decisão" no menu "Aprovações" (não no menu
  "Administração", pelo mesmo motivo do 8a).
- Linhas de até 110 colunas em tudo o que este marco escreveu no site. Duas linhas anteriores ao marco passam
  disso (`App.tsx:23`, `Moldura.tsx:14`) e ficaram como estavam.
- Nenhum teste existente alterado.

### Checkpoint 9 — Tipo de demonstração, validação final e documentação (2026-11-14)

- `uv run poe verify` em `backend/`: saída 0, 1093 testes (1082 + 11 novos), cobertura 97,82%, contratos do
  import-linter 1 mantido, 0 quebrados; nenhuma migração pendente. O site não mudou neste checkpoint: vale a
  verificação do 8b (saída 0, 160 testes).
- Tipo de demonstração: `aprovacoes/demonstracao.py`, registrado no `ready` só com `DEBUG` ligado e
  `APROVACOES_TIPO_DE_DEMONSTRACAO=1`; a variável entrou no `.env.example`, em `docs/setup/configuration.md` e só no
  `compose.override.yaml` (desenvolvimento), para a `api` e o `worker`.
- Sistema de verdade: `DJANGO_DEBUG=1 APROVACOES_TIPO_DE_DEMONSTRACAO=1 docker compose up -d --build`, saída 0;
  migrações `aprovacoes` 0001 a 0003 aplicadas; o tipo registrado na `api` e no `worker`. Ciclo percorrido como
  descrito em `docs/api/manual-testing.md`, seção "Aprovações (M5)": envio pela API; fila, sino, contestação com
  teto, reenvio e aprovação no Chrome; aprovação própria recusada (403 `SOLICITANTE_NAO_DECIDE`) e envio sem
  indicação recusado (422) pela API; lembrete de 3 dias (uma vez, sem repetir) e aviso de 7 dias; e-mails
  conferidos no Mailpit. Com `DJANGO_DEBUG=0`, o tipo não existe no contêiner, mesmo com a variável ligada.
- Achado na validação e corrigido depois dela: o título da notificação ao indicado era "Você foi indicado…",
  com o gênero de quem recebe. Passou a "Indicação para decidir uma solicitação". As notificações já gravadas
  na validação ficaram com o título antigo (notificação não muda), e os contêineres rodaram o texto anterior.
- Usuários de validação criados só no banco local, pelo shell, com senha gerada na hora e guardada fora do git.
- Documentação: `docs/api/README.md` (erros e rotas), `docs/api/manual-testing.md`,
  `docs/architecture/project-structure.md` (como registrar um tipo), `docs/security/threat-model.md` (seção do M5) e o canvas
  `docs/domain/aggregates/solicitacao.md` (códigos de erro alinhados ao código e coluna "Teste" preenchida).
  Não alterei `domain-events.md` nem `domain-model.md`, que a technical-spec também lista: o canvas era o único
  documento de domínio liberado.
- Nenhum teste existente alterado.

## Rollback ou recuperação

As migrações revertem com `python manage.py migrate aprovacoes zero`. A versão anterior é o commit de merge do M4 na `dev` (`ca84df0`).
