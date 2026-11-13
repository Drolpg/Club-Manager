# Plano de Implementação: Notificações, com caixa de entrada e e-mail

| Campo | Valor |
| --- | --- |
| Feature | `notificacoes/caixa-e-email` |
| Status | Implemented |
| Responsável | Leandro Nascimento |
| Atualizado em | 2026-11-13 |
| Especificação técnica | `./technical-spec.md` (aprovada em 2026-11-13) |
| Pré-requisito | M3 concluído e integrado à `dev` |

## Objetivo

Qualquer módulo avisa pessoas sobre um item; o aviso fica registrado, aparece na caixa do site e vai por e-mail
conforme o tipo e as preferências; e o diretor acompanha tudo por um sino que se atualiza sozinho.

## Como executar (vale para qualquer sessão)

Este plano foi escrito para ser executado sem o contexto da conversa que o criou. Antes de começar, leia
`AGENTS.md` (inclusive "Lições da implementação"), `./functional-spec.md` e `./technical-spec.md`.

1. Crie a branch `feat/notificacoes-caixa-e-email` a partir da `dev` atualizada. Mude o status deste plano para
   `In Progress`.
2. Um checkpoint por vez, na ordem. Escreva os testes, rode-os e veja-os falhar pelo motivo certo; só então o código.
3. Modelos de estilo: `backend/permissoes/` (serviços, rotas, testes) e `backend/acesso/tasks.py` (tarefas).
4. Rode `uv run poe verify` em `backend/` (e `npm run verify` em `frontend/`, se mexeu no site, nunca os dois ao
   mesmo tempo) e confira o código de saída. Só faça commit com saída 0.
5. Um commit por checkpoint, com assunto de até 72 caracteres e escopo `notificacoes`, `acesso`, `permissoes`,
   `platform` ou `web`, conforme o que mudou.
6. No mesmo commit, acrescente a evidência e as linhas da matriz neste arquivo.
7. Não faça merge na `dev` nem na `main`. Ao fim do último checkpoint, abra um pull request de rascunho para o CI
   rodar e relate ao dono: o que foi feito, o resultado de cada verificação, o que não foi validado e os desvios.

Se um teste parecer errado ou a spec não cobrir um caso, pare e pergunte. Não mude teste nem spec para passar.

## Checkpoint 1 — Despachante de eventos e eventos publicados

- **O que muda:** `kernel/events.py`; `acesso/public.py` (eventos `CadastroConcluido` e `PapelDeAdminAlterado`);
  `permissoes/public.py` (eventos `ClassificacaoAlterada` e `ConcessaoIndividualAlterada`); os serviços que os
  publicam.

| Peça | Comportamento |
| --- | --- |
| `kernel.events.subscribe(tipo, tratador)` | Registra o tratador para aquele tipo de evento; registrar o mesmo tratador duas vezes não duplica |
| `kernel.events.publish(evento)` | Chama, na hora e na ordem de registro, os tratadores do tipo exato do evento. Exceção de um tratador propaga |
| `kernel.events.unsubscribe_all_for_tests()` e uma fixture que guarda e restaura os tratadores | Só para os testes |
| `acesso/services/cadastro.py::concluir_cadastro` | Passa a publicar `CadastroConcluido(usuario_id)`, e **deixa de** enfileirar `avisar_admins_de_diretor_a_classificar`. Remova essa tarefa de `acesso/tasks.py` e a função de `acesso/services/emails.py` |
| `acesso/services/usuarios.py::tornar_admin` e `remover_admin` | Publicam `PapelDeAdminAlterado(usuario_id, admin)` |
| `permissoes/services/classificacao.py::classificar` | Publica `ClassificacaoAlterada(usuario_id)` nos dois ramos (classificar e tirar o cargo) |
| `permissoes/services/concessoes.py` | Publica `ConcessaoIndividualAlterada(usuario_id, permissao, concedida)` ao conceder e ao revogar para um usuário; não publica para cargo nem setor |

- **Testes:** `backend/tests/test_events.py` (entrega, ordem, tipos que não se misturam, exceção que propaga,
  transação desfeita quando o tratador falha); em `acesso/tests/` e `permissoes/tests/`, cada serviço publica o evento
  certo (registre um tratador de teste que guarda o que recebeu). Atualize os testes do M2 que esperavam o e-mail aos
  admins: essa expectativa muda para "evento publicado", porque a spec funcional deste marco substitui o e-mail
  (CA-20). Registre no relato que esses testes mudaram por mudança de spec.
- **Critérios:** base de CA-20 a CA-22.

## Checkpoint 2 — Registro, `notificar` e preferências

- **O que muda:** `notificacoes/models.py`, `notificacoes/tipos.py`, `notificacoes/domain/envio.py`,
  `notificacoes/services/`, `notificacoes/public.py`, migração `0001_notificacao_e_preferencia`.

| Peça | Comportamento |
| --- | --- |
| `Notificacao`, `PreferenciaDeAlerta` | Os campos da technical-spec. `Notificacao.save` recusa alteração de `titulo`, `texto`, `tipo`, `item_tipo`, `item_id`, `destinatario_id` e `chave` depois de criada; `delete` recusa sempre. Método `marcar_lida(agora)`, que não muda uma data já preenchida |
| `tipos.registrar_tipo(codigo, *, pede_acao, descricao)` | Mesmo padrão de `permissoes/catalogo.py`: formato `<modulo>.<fato>`, repetir igual não duplica, redefinir diferente é erro |
| `domain/envio.py::deve_enviar_email(pede_acao, email_informativos)` | Função pura (NOT-R03) |
| `services/envio.py::notificar(...)` | Tipo desconhecido → `ValueError` (erro de programação). Filtra destinatários com `acesso.public.ids_ativos`. Para cada um, `get_or_create` por (`destinatario_id`, `chave`). Notificação nova: `email_situacao` é `PENDENTE` ou `DISPENSADO` conforme a função pura e a preferência; se `PENDENTE`, agenda com `transaction.on_commit` a tarefa `notificacoes.enviar_email` com o ID. Devolve quantas criou |
| `services/preferencias.py::obter(usuario_id)` e `alterar(usuario_id, *, aviso_na_tela=None, email_informativos=None)` | Sem linha, devolve os padrões (os dois verdadeiros). Alterar cria ou atualiza a linha |

- **Testes:** CA-01, CA-02, CA-04 (a parte do registro), CA-05, CA-07, CA-16, CA-17, CA-19; imutabilidade
  (NOT-R05); função pura em todas as combinações. Use o padrão de `acesso/tests/test_cadastro.py` para o que roda
  depois do commit.

## Checkpoint 3 — Tarefa de e-mail

- **O que muda:** `notificacoes/tasks.py`, `notificacoes/services/email.py`.

| Peça | Comportamento |
| --- | --- |
| `services/email.py::enviar(notificacao_id)` | Se a situação não é `PENDENTE`, não faz nada. Monta o e-mail em texto puro: assunto = título; corpo = texto, linha em branco, `settings.SITE_URL` + `caminho`. Envia ao e-mail do destinatário (`acesso.public.usuario_por_id`); destinatário que ficou inativo → marca `DISPENSADO`. Sucesso → `ENVIADO` e `email_enviado_em`. Sempre incrementa `email_tentativas` |
| `tasks.py::enviar_email` | `shared_task` com nova tentativa automática para `OSError` e `smtplib.SMTPException`, espera crescente, no máximo 5 tentativas. Ao esgotar, grava `FALHOU` (use o gancho de falha da tarefa) |

- **Testes:** CA-03, CA-04 (nenhum e-mail), CA-06 (falha, nova tentativa e `FALHOU`; simule o servidor que falha
  substituindo o envio), CA-08 (conteúdo e link, sem token); idempotência.

## Checkpoint 4 — Tratadores dos quatro eventos

- **O que muda:** `notificacoes/handlers.py`, `notificacoes/apps.py` (`ready` registra os tipos e os tratadores).

| Evento | Notificação |
| --- | --- |
| `CadastroConcluido` | Tipo `acesso.cadastro_concluido`; destinatários: `acesso.public.admins_ativos()`; título "Novo diretor para classificar"; texto com o nome do diretor; item (`usuario`, ID); caminho `/admin/usuarios/<id>`; chave `cadastro-concluido:<id>` |
| `ClassificacaoAlterada` | Tipo `permissoes.classificacao_alterada`; destinatário: o usuário; texto com o cargo e os setores atuais (de `permissoes.public.classificacao_de`), ou "você ficou sem cargo"; caminho `/`; chave com o ID e o instante, para cada mudança gerar a sua |
| `PapelDeAdminAlterado` | Tipo `acesso.papel_de_admin_alterado`; destinatário: o usuário; caminho `/` |
| `ConcessaoIndividualAlterada` | Tipo `permissoes.concessao_individual_alterada`; destinatário: o usuário; texto com o nome da permissão (do catálogo) e se foi concedida ou revogada; caminho `/` |

- **Testes:** CA-20 (por senha e pelo Google; nenhum e-mail simples do M2), CA-21, CA-22; o teste de arquitetura
  continua verde (`acesso` e `permissoes` não importam `notificacoes`).

## Checkpoint 5 — Rotas da caixa e das preferências

- **O que muda:** `notificacoes/services/consulta.py`, `notificacoes/http/`, `config/urls.py`.
- As cinco rotas da technical-spec. Toda consulta filtra por `destinatario_id` igual ao usuário logado; a
  notificação de outro responde 404, inclusive para o admin. Paginação por cursor: `antes` é o ID da última recebida.
- **Testes:** CA-09 a CA-15, CA-17 (rota), CA-19 (não existe rota nem campo que desligue o registro); validação de
  `limite` e de `antes`; 401 sem sessão.

## Checkpoint 6 — Site

- **O que muda:** `frontend/src/` — a moldura comum das telas logadas, o sino, a caixa, o aviso flutuante e a tela
  `/preferencias`; `frontend/src/api/notificacoes.ts`.

| Peça | Comportamento |
| --- | --- |
| Moldura | Envolve todas as rotas protegidas de `App.tsx`: cabeçalho com o nome do usuário, o menu (os atalhos de hoje), o sino e "Sair" |
| Sino | Consulta `resumo/` ao montar e a cada 60 segundos, só com a aba visível (`document.visibilityState`); mostra a quantidade de não lidas |
| Aviso flutuante | Quando `mais_recente_id` muda entre duas consultas e a preferência `aviso_na_tela` está ligada; some sozinho depois de alguns segundos |
| Caixa | Abre ao clicar no sino; lista com as não lidas destacadas; "carregar mais"; "marcar todas como lidas"; clicar num item chama `ler/` e navega para `caminho` |
| Preferências | As duas chaves, salvando em `PUT preferencias/` |

- **Testes:** CA-18, CA-23, CA-24, com `simularApi` e relógio simulado do Vitest para os 60 segundos; a caixa e as
  preferências com caminho feliz e erro.

## Checkpoint 7 — Mailpit e validação final

1. Acrescente o Mailpit ao `compose.override.yaml` (imagem `axllent/mailpit`, portas `127.0.0.1:8025` e SMTP
   interno) e faça `EMAIL_URL` aceitar `?tls=0` em `config/settings.py`, com teste. No `compose.override.yaml`,
   aponte `EMAIL_URL` da `api` e do `worker` para o Mailpit. Antes de usar a imagem, confirme a versão atual dela.
2. `uv run poe verify` e `npm run verify`, com saída 0.
3. Suba o sistema e percorra: convite, cadastro, verificação pelo e-mail visto no Mailpit; o admin recebe a
   notificação e o e-mail; o admin classifica; o diretor vê o sino aumentar em até um minuto e abre a notificação.
4. Documentação da lista da technical-spec; revisão de segurança neste plano; seção do M4 no modelo de ameaças.
5. Pull request de rascunho e relato ao dono.

## Matriz critério de aceite → teste

| Critério | Teste |
| --- | --- |
| CA-20 (base, checkpoint 1) | `acesso/tests/test_eventos.py::test_concluir_o_cadastro_publica_cadastro_concluido`, `::test_verificar_o_link_publica_cadastro_concluido`, `::test_o_cadastro_pelo_google_publica_cadastro_concluido`, `::test_entrar_pelo_google_de_quem_aguardava_verificacao_publica_cadastro_concluido`, `::test_concluir_o_cadastro_nao_manda_mais_o_email_simples_aos_admins` |
| CA-21 (base, checkpoint 1) | `permissoes/tests/test_eventos.py::test_classificar_publica_classificacao_alterada`, `::test_reclassificar_publica_de_novo`, `::test_tirar_o_cargo_de_quem_tinha_publica`, `::test_tirar_o_cargo_de_quem_nao_tinha_nao_publica` |
| CA-22 (base, checkpoint 1) | `acesso/tests/test_eventos.py::test_tornar_admin_publica_papel_de_admin_alterado`, `::test_remover_admin_publica_papel_de_admin_alterado`; `permissoes/tests/test_eventos.py::test_conceder_a_um_usuario_publica_concessao_individual_alterada`, `::test_revogar_de_um_usuario_publica_com_concedida_falso`, `::test_o_acesso_total_tambem_publica` |
| CA-01 | `notificacoes/tests/test_notificar.py::test_ca01_dois_destinatarios_ativos_recebem_uma_notificacao_cada` |
| CA-02 | `notificacoes/tests/test_notificar.py::test_ca02_destinatario_inativo_nao_recebe_notificacao_nova` |
| CA-03 (agendamento, checkpoint 2) | `notificacoes/tests/test_notificar.py::test_ca03_o_que_pede_acao_agenda_o_email_mesmo_com_os_informativos_desligados` |
| CA-04 (registro, checkpoint 2) | `notificacoes/tests/test_notificar.py::test_ca04_informativo_com_email_desligado_fica_na_caixa_e_nao_agenda_email` |
| CA-05 | `notificacoes/tests/test_notificar.py::test_ca05_o_email_so_e_agendado_depois_do_commit`, `::test_ca05_transacao_desfeita_nao_deixa_notificacao_nem_email` |
| CA-07 | `notificacoes/tests/test_notificar.py::test_ca07_o_mesmo_fato_duas_vezes_gera_uma_notificacao_e_um_email` |
| CA-16 | `notificacoes/tests/test_preferencias.py::test_ca16_usuario_novo_tem_as_duas_preferencias_ligadas` |
| CA-17 (serviço, checkpoint 2) | `notificacoes/tests/test_preferencias.py::test_ca17_a_mudanca_de_um_usuario_nao_toca_a_do_outro`, `test_alterar_cria_a_linha_e_a_mudanca_vale`; `test_notificar.py::test_a_preferencia_vale_por_destinatario` |
| CA-19 (registro, checkpoint 2) | `notificacoes/tests/test_notificar.py::test_ca19_nenhuma_preferencia_impede_o_registro` |
| CA-03 (envio, checkpoint 3) | `notificacoes/tests/test_email.py::test_ca03_o_que_pede_acao_vai_por_email_mesmo_com_os_informativos_desligados` |
| CA-04 (nenhum e-mail, checkpoint 3) | `notificacoes/tests/test_email.py::test_ca04_informativo_com_email_desligado_nao_envia_nenhum_email` |
| CA-06 | `notificacoes/tests/test_email.py::test_ca06_servidor_que_falha_duas_vezes_o_envio_e_tentado_de_novo_e_acaba_enviado`, `::test_ca06_esgotadas_as_cinco_tentativas_a_falha_definitiva_fica_registrada`, `::test_ca06_uma_notificacao_que_falhou_nao_e_enviada_de_novo`, `::test_cada_tentativa_que_falha_fica_contada_e_a_notificacao_segue_pendente` |
| CA-08 | `notificacoes/tests/test_email.py::test_ca08_o_email_traz_o_titulo_o_texto_e_o_link_do_item_sem_token`, `::test_o_email_nao_traz_dado_pessoal_alem_do_que_o_texto_diz` |
| Idempotência do envio (ADR-006) | `notificacoes/tests/test_email.py::test_o_envio_e_idempotente_a_tarefa_duas_vezes_manda_um_email_so`, `::test_so_a_pendente_e_enviada` (3 situações) |
| Nova tentativa e `on_failure` | `notificacoes/tests/test_email.py::test_a_nova_tentativa_vale_para_falha_de_rede_e_de_smtp`, `::test_um_erro_de_programacao_nao_e_tentado_de_novo_e_marca_falhou` |
| NOT-R01 | `notificacoes/tests/test_notificar.py::test_ca02_…`, `::test_notificacoes_antigas_de_quem_foi_desativado_continuam_guardadas` |
| NOT-R02 | `notificacoes/tests/test_modelos.py::test_not_r02_uma_notificacao_por_destinatario_e_chave` |
| NOT-R03 | `notificacoes/tests/test_envio_domain.py::test_not_r03_todas_as_combinacoes` (4 casos) |
| NOT-R04 | `notificacoes/tests/test_modelos.py::test_not_r04_marcar_lida_de_novo_nao_muda_a_data_da_primeira_leitura`, `::test_not_r04_o_modelo_recusa_trocar_uma_data_de_leitura_ja_preenchida` |
| NOT-R05 | `notificacoes/tests/test_modelos.py::test_not_r05_o_modelo_recusa_alterar_o_conteudo` (9 campos), `::test_not_r05_nenhuma_notificacao_e_apagada` |
| Tipos (`registrar_tipo`) | `notificacoes/tests/test_tipos.py` |
| CA-20 | `notificacoes/tests/test_tratadores.py::test_ca20_cadastro_concluido_notifica_todos_os_admins_ativos_com_pedido_de_acao`, `::test_ca20_o_mesmo_cadastro_concluido_duas_vezes_gera_uma_notificacao_por_admin`; por senha: `tests/test_notificacoes_de_ponta_a_ponta.py::test_ca20_cadastro_por_senha_verificado_notifica_o_admin_e_o_email_simples_do_m2_nao_existe_mais`; pelo Google: `::test_ca20_cadastro_pelo_google_notifica_o_admin_e_o_email_simples_do_m2_nao_existe_mais`, `::test_ca20_entrar_pelo_google_de_quem_aguardava_verificacao_notifica_o_admin` |
| CA-21 | `notificacoes/tests/test_tratadores.py::test_ca21_classificar_notifica_o_diretor_com_o_cargo_e_os_setores`, `::test_ca21_classificar_sem_setores_diz_que_nao_ha_setores`, `::test_ca21_cada_mudanca_gera_a_sua_notificacao`, `::test_ca21_tirar_o_cargo_de_quem_nao_tinha_nao_notifica` |
| CA-22 | `notificacoes/tests/test_tratadores.py::test_ca22_ganhar_e_perder_o_papel_de_admin_notifica_o_usuario`, `::test_ca22_ganhar_e_perder_uma_permissao_individual_notifica_com_o_nome_do_catalogo`, `::test_ca22_o_acesso_total_notifica_pelo_nome`, `::test_ca22_conceder_o_que_o_usuario_ja_tem_nao_notifica_de_novo`, `::test_ca22_permissao_dada_a_cargo_ou_setor_nao_gera_notificacao` |
| Registro no `ready` | `notificacoes/tests/test_tratadores.py::test_o_ready_registra_os_quatro_tipos_do_modulo`, `::test_o_ready_registra_um_tratador_para_cada_evento_e_nao_duplica_ao_rodar_de_novo` |
| Fronteiras (`acesso` e `permissoes` não importam `notificacoes`) | `backend/tests/test_architecture.py` e o contrato do import-linter (existentes, verdes) |
| `nome_da_permissao` | `permissoes/tests/test_nome_da_permissao.py` |
| CA-09 | `notificacoes/tests/test_rotas.py::test_ca09_a_caixa_traz_so_as_do_usuario_da_mais_recente_para_a_mais_antiga`, `::test_ca09_o_item_traz_so_os_campos_do_contrato`, `::test_ca09_o_admin_tambem_so_ve_a_propria_caixa` |
| CA-10 | `notificacoes/tests/test_rotas.py::test_ca10_o_resumo_conta_so_as_nao_lidas_do_usuario`, `::test_ca10_o_resumo_sem_notificacoes`, `::test_ca10_o_mais_recente_e_o_ultimo_que_chegou_mesmo_que_ja_lido` |
| CA-11 | `notificacoes/tests/test_rotas.py::test_ca11_abrir_a_notificacao_a_marca_lida_com_data_e_diminui_o_resumo` |
| CA-12 | `notificacoes/tests/test_rotas.py::test_ca12_abrir_de_novo_nao_muda_a_data_da_primeira_leitura` |
| CA-13 | `notificacoes/tests/test_rotas.py::test_ca13_marcar_todas_como_lidas_so_mexe_nas_do_usuario`, `::test_ca13_marcar_todas_sem_nenhuma_nao_lida_marca_zero` |
| CA-14 | `notificacoes/tests/test_rotas.py::test_ca14_a_notificacao_de_outro_responde_que_nao_existe_inclusive_para_o_admin` (diretor e admin), `::test_ca14_notificacao_que_nao_existe_responde_igual_a_de_outro`, `::test_ca14_a_de_outro_nao_aparece_na_caixa_nem_no_resumo_nem_como_cursor` |
| CA-15 | `notificacoes/tests/test_rotas.py::test_ca15_a_caixa_carrega_as_seguintes_por_cursor_sem_repetir_nem_pular`, `::test_ca15_o_limite_padrao_e_20`, `::test_ca15_o_limite_maximo_e_50_e_o_minimo_e_1` |
| CA-16 (rota) | `notificacoes/tests/test_rotas.py::test_ca16_as_preferencias_de_um_usuario_novo_estao_ligadas` |
| CA-17 (rota) | `notificacoes/tests/test_rotas.py::test_ca17_alterar_as_preferencias_muda_so_as_do_usuario`, `::test_ca17_o_put_aceita_so_uma_chave_e_deixa_a_outra_como_esta`, `::test_ca17_a_mudanca_vale_para_as_proximas_notificacoes` |
| CA-19 (rota e campo) | `notificacoes/tests/test_rotas.py::test_ca19_nenhuma_rota_apaga_nem_desliga_o_registro`, `::test_ca19_o_put_de_preferencias_ignora_campo_que_tentaria_desligar_o_registro`, `::test_ca19_as_rotas_do_modulo_sao_so_as_da_especificacao` |
| Validação e 401 | `notificacoes/tests/test_rotas.py::test_parametro_invalido_da_caixa_responde_400` (`limite` 0, 51, -1, texto; `antes` inválido), `::test_cursor_de_notificacao_que_nao_existe_responde_400`, `::test_preferencia_que_nao_e_booleana_responde_400_e_nao_muda_nada` (3 casos), `::test_sem_sessao_toda_rota_responde_401` (6 rotas) |
| CA-18 | `frontend/src/notificacoes.test.tsx` > aviso flutuante: "CA-18: com o aviso desligado não mostra o aviso, e o indicador continua aparecendo" |
| CA-23 | `frontend/src/notificacoes.test.tsx` > sino: "CA-23: mostra a quantidade de não lidas ao carregar", "CA-23: a quantidade se atualiza sozinha a cada 60 segundos" (relógio simulado), "com a aba escondida não consulta, e ao voltar a ficar visível consulta na hora", "a falha ao consultar não mostra alerta…", "ao sair da tela o sino para de consultar e limpa o temporizador", "acima de 99 mostra 99+", "sem não lidas mostra o sino sem número"; moldura: "mostra o nome, o menu do admin, o sino, as preferências e Sair em qualquer tela" |
| CA-24 | `frontend/src/notificacoes.test.tsx` > aviso flutuante: "CA-24: ao chegar uma notificação com o aviso ligado, aparece o aviso flutuante", "o aviso flutuante some sozinho depois de alguns segundos", "a primeira consulta não gera aviso…", "consulta igual à anterior não gera aviso", "mostra o texto do aviso como texto, sem interpretar HTML" |
| Caixa (caminho feliz e erro) | `frontend/src/notificacoes.test.tsx` > caixa de entrada (12 casos: abrir e destacar não lidas, vazia, fechar, carregar mais por cursor, abrir item e navegar, caminho fora do site, marcar todas, erros ao carregar, ao ler, ao carregar mais e ao marcar todas, texto sem HTML) |
| Preferências (CA-16, CA-17, CA-19 na tela) | `frontend/src/notificacoes.test.tsx` > tela de preferências (8 casos: valores da API, nascem ligadas, salvar com CSRF, erro ao salvar, erro ao carregar, só duas chaves e o aviso de que o que pede ação sempre chega, sem sessão, link na moldura) |
| Moldura | `frontend/src/notificacoes.test.tsx` > moldura das telas logadas (7 casos: menu do admin, atalho Convites do diretor, sem atalho, sem consulta de permissões sem cargo, uma só consulta de permissões, sem moldura sem sessão, Sair) |
| `EMAIL_URL` com `?tls=0` | `backend/tests/test_email_url.py` (13 casos) |
| Revisão de segurança (CP7) | seção "Revisão de segurança" deste plano |
| ADR-003 (despachante) | `tests/test_events.py` (entrega, ordem, tipos que não se misturam, exceção que propaga, transação desfeita) |

## Revisão de segurança

Preenchida no checkpoint 7 (2026-11-13), com `sdd-method:reviewing-security`. Sem achado crítico ou alto. Um
defeito de interface (cabeçalho cortado por rolagem indevida) foi visto no roteiro e corrigido no mesmo checkpoint;
não é de segurança.

| Item | Como foi conferido | Achado | Mitigação | Status |
| --- | --- | --- | --- | --- |
| Validação de entrada | `limite` (1 a 50), `antes` (UUID) e as duas chaves de preferência (só `true` ou `false`) são validados nos serializers; o `{id}` da rota é UUID; os serviços não confiam só na rota | Nenhum | — | OK |
| Mass assignment | Nenhum serializer grava no modelo; o `PUT` aceita só as duas chaves, e os campos desconhecidos são ignorados (teste) | Nenhum | — | OK |
| Autenticação | As cinco rotas declaram `IsAuthenticated`; sem sessão, 401 `NOT_AUTHENTICATED` (6 casos testados) | Nenhum | — | OK |
| Autorização | Posse do recurso: toda consulta e escrita filtram por `destinatario_id` do logado (NOT-R06); a de outro, 404, inclusive para o admin; não há permissão de admin sobre a caixa alheia | Nenhum | — | OK |
| Exposição de dados | A saída traz só `id`, `tipo`, `pede_acao`, `titulo`, `texto`, `caminho`, `criada_em` e `lida_em`; nunca a chave, o item nem o estado do e-mail; o texto é curto e sem valores; o e-mail não leva token, senha nem dado de contato | Nenhum | — | OK |
| Segredos | Nenhum segredo novo; o `EMAIL_URL` do Mailpit não tem credencial | — | — | N/A (sem segredo novo) |
| Logs | Um log novo (falha de e-mail): ID da notificação, número da tentativa e o nome do tipo do erro; sem endereço, sem texto, sem traceback | Nenhum | — | OK |
| Persistência | Só ORM; migração `notificacoes/0001` com índice único (`destinatario_id`, `chave`) e índices de leitura; a notificação não é apagada (modelo recusa); reversível (`migrate notificacoes zero`, conferido no checkpoint 7) | Nenhum | — | OK |
| Respostas de erro | Códigos estáveis (`NOT_FOUND`, `VALIDATION_ERROR`, `NOT_AUTHENTICATED`) pelo envelope comum | Nenhum | — | OK |
| Dependências | Nenhuma dependência de Python nem de npm. Única novidade: a imagem `axllent/mailpit:v1.33.1`, só em desenvolvimento, fixada na versão atual e fora do `compose.yaml` de produção | Imagem de terceiros em desenvolvimento, sem passar pelo SCA do CI (que cobre dependências de Python e npm) | Só em `127.0.0.1`, só no override, versão fixada | Mitigado |
| Abuso | `limite` máximo de 50; consulta de 60 s só com a aba visível; chave única impede duplicata; sem rota de criação | Os diretores consultam `resumo/` a cada minuto: carga proporcional ao número de diretores (poucas dezenas) | Duas contagens indexadas | OK |
| Integrações externas | Servidor SMTP: tempo máximo de 10 s por envio, nova tentativa limitada; `?tls=0` só em `smtp://` e é a única opção aceita | Nenhum | — | OK |

Não coberto por esta revisão: DAST (o perfil de stack deixa para o M12) e o relatório de vulnerabilidades do marco
(`docs/security/vulnerability-report-m4.md`), que fecha o M4 depois da aprovação do dono.

## Definition of Done

- [x] Checkpoints concluídos, com evidência.
- [x] Todo CA com ao menos um teste.
- [x] Verificação completa com saída 0; cobertura dentro da meta (backend 97%, site 95% das linhas).
- [x] Fronteiras de módulo verificadas.
- [x] Revisão de segurança registrada, sem achado crítico ou alto aberto.
- [x] Migration reversível; nenhum seed.
- [x] Contrato, `docs/api/` e guia de teste manual atualizados.
- [x] Registro de requisitos, decisões e riscos atualizados.
- [x] CI verde no GitHub (PR #3, workflows `backend` e `frontend`, 2026-11-13).
- [x] Critérios de aceite validados e aprovados pelo dono (Leandro Nascimento, 2026-11-13). A
      implementação foi feita por uma sessão executora e revisada por outra, contra a spec e este
      plano, antes da aprovação.

## Evidências de verificação

### Checkpoint 1 — Despachante de eventos e eventos publicados (2026-11-13)

- Ponto de partida: `uv run poe verify` em `backend/`, saída 0, 390 testes; `npm run verify` em `frontend/`, saída 0,
  83 testes.
- `uv run poe verify` em `backend/`: saída 0, 424 testes, cobertura 97,47%, contratos do import-linter 1 mantido,
  0 quebrados.
- Testes existentes alterados, por mudança de spec (CA-20: o e-mail simples aos admins virou o evento):
  `acesso/tests/test_cadastro.py::test_ca11_…`, `acesso/tests/test_google.py::test_ca15_…` e
  `acesso/tests/test_google.py::test_entrar_pelo_google_verifica_a_conta_que_aguardava_verificacao`. A expectativa
  "e-mail aos admins" virou "`CadastroConcluido` publicado e nenhum e-mail do acesso"; o `test_ca11` foi renomeado
  (`…_e_publica_o_cadastro_concluido`). O resto de cada teste ficou igual.

### Checkpoint 2 — Registro, `notificar` e preferências (2026-11-13)

- `uv run poe verify` em `backend/`: saída 0, 481 testes (424 + 57 novos), cobertura 97,27%, contratos do
  import-linter 1 mantido, 0 quebrados; `migrations-check` sem pendência (migração
  `notificacoes/0001_notificacao_e_preferencia`).
- Nenhum teste existente alterado neste checkpoint.
- `notificar` agenda a tarefa `notificacoes.enviar_email`, que o plano só cria no checkpoint 3. Para o código ser
  completo e tipado já aqui, o checkpoint 2 traz a declaração fina da tarefa (`tasks.py`, só chama o serviço) e um
  `services/email.py` provisório que levanta `NotImplementedError`. Os testes deste checkpoint substituem o
  `delay` da tarefa. O envio de verdade, a nova tentativa e o `FALHOU` entram no checkpoint 3, com testes
  escritos antes.
- Além dos campos que o plano lista, o modelo também recusa alterar `pede_acao` e `caminho`, e recusa trocar uma
  `lida_em` já preenchida (NOT-R04 também no `save`, e não só em `marcar_lida`).

### Checkpoint 3 — Tarefa de e-mail (2026-11-13)

- `uv run poe verify` em `backend/`: saída 0, 499 testes (481 + 18 novos), cobertura 97,53%, contratos do
  import-linter 1 mantido, 0 quebrados.
- Nenhum teste existente alterado neste checkpoint. O `services/email.py` provisório do checkpoint 2 foi
  substituído pelo envio de verdade.
- Os testes de falha rodam a tarefa como um worker (`tasks.enviar_email.apply(...)`, com a propagação do modo
  imediato desligada só dentro do teste). Com `CELERY_TASK_EAGER_PROPAGATES=True`, a configuração dos testes, o
  Celery relança a exceção antes de tentar de novo e antes de chamar `on_failure`; a configuração de teste não foi
  alterada. Fica sem teste o intervalo real entre as tentativas (60 s, dobrando, até 1 h): o modo imediato o ignora.
- Nova tentativa: `OSError` e `smtplib.SMTPException`, espera inicial de 60 s e crescente, 4 novas tentativas (5 no
  total); `on_failure` grava `FALHOU` também para um erro que não se repete.

### Checkpoint 4 — Tratadores dos quatro eventos (2026-11-13)

- `uv run poe verify` em `backend/`: saída 0, 523 testes (499 + 24 novos), cobertura 97,58%, contratos do
  import-linter 1 mantido, 0 quebrados; `test_architecture.py` verde (`acesso` e `permissoes` não importam
  `notificacoes`).
- Nenhum teste existente alterado neste checkpoint: com os tratadores ativos no `ready`, toda a suíte do M2 e do M3
  continua verde.
- `permissoes.public` ganhou `nome_da_permissao(codigo)`. O plano pede o texto "com o nome da permissão (do
  catálogo)", mas `notificacoes` só pode importar a API pública de `permissoes`, que não expunha o nome. É uma
  função de consulta, sem regra nova, com teste próprio.
- A chave das notificações de classificação, papel de admin e concessão leva o ID do usuário e um UUID 7 (que
  carrega o instante), no lugar do instante em texto: duas mudanças no mesmo instante não podem colidir e perder
  uma notificação. A do cadastro concluído é determinística (`cadastro-concluido:<id>`), para o mesmo fato não
  duplicar.
- Os testes dos tratadores acionam as ações pela API HTTP de `acesso` e `permissoes`, porque os testes de um módulo
  não importam os internos de outro; os fluxos de CA-20 por senha e pelo Google, que cruzam três módulos, ficam em
  `backend/tests/test_notificacoes_de_ponta_a_ponta.py`.

### Checkpoint 5 — Rotas da caixa e das preferências (2026-11-13)

- `uv run poe verify` em `backend/`: saída 0, 563 testes (523 + 40 novos), cobertura 97,61%, contratos do
  import-linter 1 mantido, 0 quebrados.
- Nenhum teste existente alterado neste checkpoint.
- Toda consulta e toda escrita filtram por `destinatario_id` do usuário logado; a notificação de outro responde
  404 `NOT_FOUND`, inclusive para o admin. Não existe rota DELETE (o DELETE na raiz responde 405, e nos itens, 404).
- Ordem da caixa: `criada_em` e `id`, decrescentes (usa o índice `destinatario_id, criada_em`). `antes` é o ID da
  última recebida; um `antes` que não é do usuário ou não existe responde 400 `VALIDATION_ERROR`, sem revelar a
  existência. `mais_recente_id` do resumo é a última que chegou, lida ou não.
- `limite=` vazio é tratado pelo DRF como não informado (usa o padrão 20); a spec só manda recusar `limite` fora de
  1 a 50 e texto, o que está coberto.
- As preferências aceitam só `true` ou `false` (`"sim"`, `1` e `null` dão 400) e só as chaves enviadas mudam. Ler e
  marcar como lida não registram auditoria: a spec não pede, e a leitura fica na própria `lida_em`.

### Checkpoint 6 — Site (2026-11-13)

- `npm run verify` em `frontend/`: saída 0 (oxlint, `tsc`, 123 testes, cobertura de 92,6% das instruções e 94,97% das linhas, build). Os
  83 testes do ponto de partida continuam, e 40 são novos (`frontend/src/notificacoes.test.tsx`). Os testes
  novos foram escritos e vistos falhar (nenhum elemento existia) antes das telas.
- Estrutura: `Moldura.tsx` é uma rota de layout que envolve todas as rotas protegidas (cabeçalho com "Olá, nome",
  menu, "Preferências", sino e "Sair"); `Sino.tsx` e `useCaixa.ts` (sino, aviso flutuante e caixa);
  `paginas/Preferencias.tsx`; `api/notificacoes.ts`. `Inicio.tsx` perdeu o menu, o "Sair" e a saudação, que
  passaram para a moldura. A moldura consulta `permissoes/minhas/` uma vez (só com cargo, como antes) e a página
  inicial reaproveita a resposta por contexto (`useMinhasDaMoldura`).
- Teste existente alterado, com autorização do dono nesta sessão (2026-11-13):
  `frontend/src/App.test.tsx`, "entra com a credencial devolvida pelo Google". A asserção `chamadas.at(-1)` passou a
  `chamadas.find((c) => c.metodo === 'POST')`, com o mesmo caminho e corpo. Motivo: depois do login a moldura monta o
  sino, que consulta `resumo/` ao montar (CA-23), e o POST deixou de ser a última chamada.
- O sino consulta ao montar sempre e, a cada 60 s, só com a aba visível; ao voltar a ficar visível consulta na hora.
  O aviso flutuante busca a preferência e a notificação mais recente só quando `mais_recente_id` muda (a primeira
  consulta só marca o ponto de partida). Falha de consulta do sino não vira alerta.
- "Carregar mais" é um botão (o plano pede assim; a spec técnica fala em "ao chegar ao fim"). O `caminho` de uma
  notificação só é aberto se for um caminho do próprio site; caso contrário a notificação é marcada como lida e a
  caixa fecha, sem sair do site.
- No Windows, a suíte do site só roda num terminal aberto em `C:\` com letra maiúscula: de uma sessão com `c:\`
  minúsculo, o Vitest falha com "failed to find the current suite" em todos os arquivos (não é defeito do código).
- Não validado aqui: o intervalo real de 60 s e a aparência no navegador (os testes usam o relógio simulado); o
  checkpoint 7 confere isso com o sistema no ar.

### Checkpoint 7 — Mailpit e validação final (2026-11-13)

- `uv run poe verify` em `backend/`: saída 0, 576 testes (563 + 13 novos de `EMAIL_URL`), cobertura 97,85%, contratos
  do import-linter 1 mantido, 0 quebrados. `npm run verify` em `frontend/`: saída 0, 123 testes, cobertura de 92,6% das instruções,
  build. Rodados um depois do outro.
- Mailpit: imagem `axllent/mailpit:v1.33.1` (a versão atual em 2026-11-13: publicada em 2026-11-07; a tag existe
  no Docker Hub), só no `compose.override.yaml`, página em `127.0.0.1:8025`, SMTP só na rede interna. A `api` e o
  `worker` apontam para `smtp://mailpit:1025?tls=0`. `docker compose config` mostra o Mailpit e o `EMAIL_URL` só no
  desenvolvimento; `docker compose -f compose.yaml config --services` não lista o Mailpit e o `EMAIL_URL` vem do
  ambiente, como antes. O `compose.yaml` não mudou.
- `EMAIL_URL` aceita `smtp://host:porta?tls=0` (sem STARTTLS); qualquer outra opção na consulta, ou `?tls=0` em
  `smtps://`, levanta `ImproperlyConfigured` sem repetir a senha (`backend/tests/test_email_url.py`).
- Sistema no ar (`docker compose up -d --build`): `docker compose ps` com os seis serviços `Up` e `db`, `redis`, `api`
  e `mailpit` saudáveis; a migração `notificacoes.0001_notificacao_e_preferencia` aplicada na subida; o worker lista
  `notificacoes.enviar_email`. Roteiro N1 a N10 de `docs/api/manual-testing.md`: ver o que foi e o que não foi
  executado lá. Resultados: o admin recebeu a notificação "Novo diretor para classificar" (pede ação, com o nome do
  diretor e o caminho `/admin/usuarios/<id>`) e o e-mail correspondente no Mailpit; nenhum e-mail "Novo diretor
  aguardando classificação" (zero no Mailpit); depois de classificado, o diretor recebeu a notificação e o e-mail
  "Sua classificação mudou"; o admin tentando abrir a notificação do diretor recebeu 404 `NOT_FOUND`; no Chrome, com
  o diretor logado, o sino subiu de 1 para 2 sozinho (o admin reclassificou às 15:58:51 e o sino já mostrava 2 menos
  de um minuto depois), a caixa mostrou as duas como "Nova", e clicar na mais recente a marcou como lida e baixou o
  contador para 1.
- Defeito visto no roteiro e corrigido: o cabeçalho ficava cortado, porque `.pagina` (com `padding`) passava de
  `100vh`; `box-sizing: border-box` em `.cabecalho + .pagina` (`frontend/src/index.css`). Conferido no Chrome depois
  de refazer a imagem do site.
- Observado, não corrigido (fora do plano): depois de abrir uma notificação que leva à página inicial, o cargo
  mostrado ali continua o de antes até recarregar, porque a página inicial não consulta de novo as permissões ao
  voltar para a mesma rota.
- Documentação atualizada: `docs/api/README.md`, `docs/api/manual-testing.md`, `docs/setup/local.md`,
  `docs/setup/configuration.md`, `.env.example`, `docs/architecture/stack-profile.md` e `project-structure.md`,
  `docs/domain/domain-events.md`, `docs/security/threat-model.md` (seção do M4), registro de requisitos (coluna da
  feature; os status continuam `Aprovado`) e risco 10 (continua `Mitigado`). O contrato OpenAPI é gerado pela
  aplicação (`/api/v1/schema/`) e não há arquivo dele no repositório. Não foram tocados a spec funcional, a
  técnica, as ADRs nem os status de aprovação, de implementação e a Definition of Done.
- Não validado: a falha real de um servidor SMTP (só o fake nos testes); o N9; o aviso flutuante no navegador; a
  espera real entre as tentativas de e-mail; o CI (ver o pull request).

### Ajuste da revisão do PR #3: dados atuais depois de abrir uma notificação (2026-11-13)

- Problema: o diretor recém-classificado abria "Sua classificação mudou", caía na página inicial e continuava vendo
  "aguarda a classificação" (ou o cargo antigo) até recarregar. Era a observação "não corrigida" do checkpoint 7.
- Correção só no site, sem mudar a API: a sessão (`sessao.tsx`) expõe `recarregar()` e uma `versao`; abrir uma
  notificação com sucesso chama `recarregar()` (`Sino.tsx`); `useMinhas` refaz `permissoes/minhas/` quando a `versao`
  muda e esvazia o `detalhe` quando o usuário fica sem cargo (`useMinhas.ts`, `Moldura.tsx`). A página inicial e o
  menu da moldura refletem a mudança sem recarregar. Se a sessão não puder ser recarregada, nada quebra.
- Testes novos (`frontend/src/notificacoes.test.tsx` > "dados atuais depois de abrir uma notificação"), escritos antes
  do código e vistos falhar (5 de 6; o de erro da sessão já passava e guarda o caminho de falha): diretor sem cargo
  passa a ver cargo e setores; diretor que perdeu o cargo deixa de vê-los; reclassificado com cargo vê o cargo novo;
  o atalho Convites some quando a permissão é revogada; quem ganhou o papel de admin vê os atalhos de administração;
  falha ao recarregar a sessão.
- `npm run verify` em `frontend/`: saída 0, 129 testes (123 + 6), cobertura de 92,56% das instruções e
  95,06% das linhas, build. Nenhum teste existente alterado; o backend não mudou.

## Rollback ou recuperação

A migração reverte com `python manage.py migrate notificacoes zero`. A versão anterior é o commit de merge do M3 na `dev` (`f957859`).
