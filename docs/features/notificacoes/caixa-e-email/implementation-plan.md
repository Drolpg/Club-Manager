# Plano de Implementação: Notificações, com caixa de entrada e e-mail

| Campo | Valor |
| --- | --- |
| Feature | `notificacoes/caixa-e-email` |
| Status | In Progress |
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
| ADR-003 (despachante) | `tests/test_events.py` (entrega, ordem, tipos que não se misturam, exceção que propaga, transação desfeita) |

## Revisão de segurança

Preenchida no checkpoint 7.

| Item | Achado | Mitigação | Status |
| --- | --- | --- | --- |

## Definition of Done

- [ ] Checkpoints concluídos, com evidência.
- [ ] Todo CA com ao menos um teste.
- [ ] Verificação completa com saída 0; cobertura dentro da meta.
- [ ] Fronteiras de módulo verificadas.
- [ ] Revisão de segurança registrada, sem achado crítico ou alto aberto.
- [ ] Migration reversível; nenhum seed.
- [ ] Contrato, `docs/api/` e guia de teste manual atualizados.
- [ ] Registro de requisitos, decisões e riscos atualizados.
- [ ] CI verde no GitHub.
- [ ] Critérios de aceite validados e aprovados pelo dono.

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

## Rollback ou recuperação

A migração reverte com `python manage.py migrate notificacoes zero`. A versão anterior é o commit de merge do M3 na `dev` (`f957859`).
