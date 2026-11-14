# Eventos de domínio e policies

| Campo | Valor |
| --- | --- |
| Status | Approved |
| Atualizado em | 2026-11-11 |
| Aprovado por / em | Leandro Nascimento / 2026-11-11 |

A materialização segue a ADR-003: entre contextos, só existem eventos de integração onde o context map tem seta para
baixo, e eles são tratados em processo, de forma síncrona, na mesma transação. Dentro de um contexto, a reação a um
evento é uma chamada direta no serviço. E-mail e trabalho pesado são enfileirados depois do commit.

## Catálogo de eventos

### Publicados entre contextos (contrato)

| Evento (passado) | Emitido por | Payload mínimo | Consumidores | Alcance |
| --- | --- | --- | --- | --- |
| `SolicitacaoAprovada` | Solicitação | ID, tipo, versão, valor, aprovador | Financeiro, Eventos | Publicado |
| `SolicitacaoContestada` | Solicitação | ID, tipo, versão, teto sugerido | Financeiro, Eventos | Publicado |
| `SolicitacaoRecusada` | Solicitação | ID, tipo, versão | Financeiro, Eventos | Publicado |
| `SolicitacaoEditada` | Solicitação | ID, tipo, versão nova | Financeiro, Eventos | Publicado |
| `SolicitacaoReaberta` | Solicitação | ID, tipo, versão nova | Eventos | Publicado |
| `SolicitacaoCancelada` | Solicitação | ID, tipo | Financeiro, Eventos | Publicado |
| `CadastroConcluido` | Identidade e Permissões | ID do usuário | Notificações | Publicado |
| `PapelDeAdminAlterado` | Identidade e Permissões | ID do usuário, se agora é admin | Notificações | Publicado |
| `ClassificacaoAlterada` | Identidade e Permissões | ID do usuário | Notificações | Publicado |
| `ConcessaoIndividualAlterada` | Identidade e Permissões | ID do usuário, código da permissão, se foi concedida | Notificações | Publicado |

Os três últimos foram acrescentados em 2026-11-13 pela feature `notificacoes/caixa-e-email` (technical-spec aprovada).
`CadastroConcluido` e `PapelDeAdminAlterado` saem de `acesso`; `ClassificacaoAlterada` e `ConcessaoIndividualAlterada`
saem de `permissoes`. `ConcessaoIndividualAlterada` só existe para concessão a uma pessoa; a de cargo ou setor não
tem um destinatário só.

Mudar o payload de um evento publicado exige decisão registrada.

### Internos ao contexto

| Evento (passado) | Emitido por | Consumidores |
| --- | --- | --- |
| `SolicitacaoEnviada`, `SolicitacaoReenviada`, `SolicitacaoEmExecucao`, `SolicitacaoEncerrada` | Solicitação | Serviço de Aprovações (notificação, auditoria) |
| `CobrancaCriada`, `PagamentoRegistrado`, `PagamentoValidado`, `PagamentoRejeitado`, `CobrancaAtrasada`, `CobrancaQuestionada`, `QuestionamentoDecidido`, `CobrancaIsenta`, `CobrancaCancelada`, `DevedorConvocado`, `DividaJustificada`, `DividaPerdoada`, `DividaRenegociada`, `DividaMantida`, `ParcelasGeradas` | Cobrança, Renegociação | Serviço financeiro |
| `RecorrenciaCriada`, `RecorrenciaAlterada`, `RecorrenciaDesativada`, `CobrancasSuspensas`, `SuspensaoEncerrada` | Recorrência, Suspensão | Serviço financeiro |
| `EntradaRegistrada`, `EntradaValidada`, `EntradaRejeitada`, `EntradaEstornada` | Entrada | Serviço financeiro |
| `SaidaAberta`, `RecursoEnviado`, `PrestacaoDeContasRegistrada`, `PrestacaoDevolvida`, `SaidaLiquidada`, `SaidaCancelada`, `SaidaEstornada` | Saída | Serviço financeiro |
| `EventoProposto`, `OrcamentoVinculado`, `EventoEditado`, `EventoPublicado`, `EventoDespublicado`, `EventoRecusado`, `EventoRealizado`, `EventoCancelado` | Evento | Serviço de eventos |

Todo evento desta lista gera um registro de auditoria.

## Policies

### Entre contextos

| Evento de origem | Policy ("sempre que… então…") | Comando | Aggregate alvo | Consistência | Falha e retry |
| --- | --- | --- | --- | --- | --- |
| `SolicitacaoAprovada` (gasto ou orçamento) | Sempre que uma solicitação de gasto for aprovada, abrir a saída | `abrir` | Saída | Mesma transação | A falha desfaz a aprovação; o aprovador tenta de novo |
| `SolicitacaoEditada` ou `SolicitacaoCancelada` (gasto) | Sempre que a solicitação sair de aprovada antes do envio, cancelar a saída | `cancelar` | Saída | Mesma transação | Idem |
| Qualquer decisão sobre a solicitação do evento ou a orçamentária | Sempre que uma solicitação ligada a um evento mudar, recalcular a situação do evento | `atualizar_situacao` | Evento | Mesma transação | Idem; o comando é idempotente |
| `CadastroConcluido` | Sempre que um diretor concluir o cadastro, notificar o admin para classificá-lo | Notificar | Notificação | Mesma transação para o registro; e-mail depois do commit | O registro não se perde; o e-mail é tentado de novo até 5 vezes e, esgotadas, fica `FALHOU` |
| `ClassificacaoAlterada` | Sempre que o diretor for classificado, reclassificado ou ficar sem cargo, avisá-lo (informativa) | Notificar | Notificação | Idem | Idem |
| `PapelDeAdminAlterado` | Sempre que alguém ganhar ou perder o papel de admin, avisá-lo (informativa) | Notificar | Notificação | Idem | Idem |
| `ConcessaoIndividualAlterada` | Sempre que alguém ganhar ou perder uma permissão concedida a ele, avisá-lo (informativa) | Notificar | Notificação | Idem | Idem |

### Dentro do Financeiro

| Evento de origem | Policy | Comando | Aggregate alvo | Consistência | Falha e retry |
| --- | --- | --- | --- | --- | --- |
| `RecursoEnviado` | Sempre que o recurso for enviado, pôr a solicitação em execução | `iniciar_execucao` | Solicitação (Aprovações, chamada direta) | Mesma transação | Desfaz o registro do envio |
| `SaidaLiquidada` | Sempre que a saída for liquidada, encerrar a solicitação | `encerrar` | Solicitação | Mesma transação | Desfaz a liquidação |
| `PrestacaoDeContasRegistrada` com gasto menor | Sempre que o gasto for menor que o enviado, pedir a devolução ao solicitante | Notificar | — | Depois do commit | Reenfileira |
| `PrestacaoDeContasRegistrada` com gasto maior | Sempre que o gasto for maior, pedir ao solicitante uma solicitação de complemento | Notificar | — | Depois do commit | Reenfileira |
| `DividaRenegociada` | Sempre que uma dívida for renegociada, gerar as parcelas | `criar` | Cobrança (parcelas) | Mesma transação | Desfaz a renegociação |
| `QuestionamentoDecidido` (isentar ou cancelar) | Sempre que o questionamento for aceito, encerrar a cobrança conforme a decisão | `isentar` ou `cancelar` | Cobrança (o mesmo aggregate) | Mesma transação | — |

### Dentro de Eventos

| Evento de origem | Policy | Comando | Aggregate alvo | Consistência | Falha e retry |
| --- | --- | --- | --- | --- | --- |
| `EventoPublicado` | Sempre que um evento for publicado, notificar todos os diretores | Notificar | — | Registro na transação; e-mail depois | Reenfileira |
| `EventoCancelado` | Sempre que um evento for cancelado, notificar todos os diretores e cancelar a solicitação orçamentária que ainda não teve envio | Notificar; `cancelar` | Solicitação | Mesma transação | Desfaz o cancelamento |
| `EventoRealizado` | Sempre que um evento for realizado, encerrar a solicitação do evento | `encerrar` | Solicitação | Mesma transação | Desfaz |
| `EventoEditado` | Sempre que um evento publicado for editado, criar nova versão da solicitação do evento | `editar` | Solicitação | Mesma transação | Desfaz |

### Disparadas pelo agendador

Todos os comandos abaixo são idempotentes: rodar duas vezes no mesmo dia não muda nada na segunda vez.

| Gatilho | Policy | Comando | Aggregate alvo |
| --- | --- | --- | --- |
| Diário | Para cada recorrência ativa, sem suspensão vigente e com devedor ativo, gerar a cobrança da competência | `criar` | Cobrança |
| Diário | Para cada cobrança `ABERTA` com vencimento passado, marcar atraso e notificar o devedor e quem tem a permissão | `marcar_atraso` | Cobrança |
| Diário | No dia do vencimento, notificar o devedor (FIN-04) | Notificar | — |
| Diário | Para cada cobrança `ATRASADA` com o limite de inadimplência esgotado, convocar o devedor e notificar o financeiro | `convocar` | Cobrança |
| Diário | Para cada suspensão cujo período acabou, encerrar | `encerrar` | Suspensão |
| Diário | No dia do evento, notificar quem pode confirmar a realização | Notificar | — |
| A cada hora | Expirar convites com mais de 24 horas | Expirar | Convite (Identidade) |

### Notificações

Toda decisão notifica o interessado: o solicitante (decisão da solicitação), o devedor (pagamento validado ou
rejeitado, questionamento decidido, convocação, decisão da dívida) e quem tem a permissão de agir (solicitação
enviada, pagamento registrado, prestação de contas registrada). A lista completa, por evento, entra na especificação
do M4.

## Status derivado

### Situação do evento

O estado do evento é calculado por uma função pura, `situacao_do_evento`, nesta ordem (o primeiro que casar vence):

1. `CANCELADO` — o evento foi cancelado por comando.
2. `REALIZADO` — a realização foi confirmada por comando.
3. `RECUSADO` — a solicitação do evento está `RECUSADA`.
4. `PUBLICADO` — a solicitação do evento está `APROVADA`, `EM_EXECUCAO` ou `ENCERRADA` e, se o evento envolve custo,
   a solicitação orçamentária também.
5. `EM_APROVACAO` — qualquer outro caso.

Recalculado em: todo evento de integração de uma solicitação ligada ao evento, e em `vincular_orcamento`. O resultado
é gravado no evento; o calendário lê o estado gravado.

### Estado da cobrança sem pagamento

Quando um pagamento é rejeitado, a cobrança volta ao estado dado por `estado_sem_pagamento`:

1. `ATRASADA` — o vencimento já passou.
2. `ABERTA` — caso contrário.

Recalculado em: `rejeitar_pagamento`.

### Inadimplência

"Inadimplente" não é um estado gravado: é a consulta das cobranças `ATRASADA` de um diretor. Cobranças `ISENTA`,
`PERDOADA`, `CANCELADA` e `RENEGOCIADA` não contam. Se a cobrança com questionamento aberto conta ou não é pendência
do M6 (hipótese do enunciado: não conta).

## Como o motor de aprovações entrega as mudanças (M5)

Os eventos `Solicitacao…` das tabelas acima não são classes separadas no código. O motor entrega um
`MudancaDeSolicitacao` (em `aprovacoes.public`) ao `ao_mudar` do tipo de solicitação, na mesma transação, com o
acontecimento: `APROVADA`, `CONTESTADA`, `RECUSADA`, `EDITADA`, `REABERTA`, `RETIRADA` ou `CANCELADA`. Cada tipo
tem um só `ao_mudar`, que é do módulo dono do tipo.

Limite conhecido, registrado no adendo 1 da especificação técnica do motor: o orçamento de um evento é um tipo do
Financeiro, então só o Financeiro é avisado, e o Eventos precisa de um caminho para saber da mudança. O envio e o
reenvio também não avisam o dono do tipo. Os dois pontos são resolvidos no refinamento do M7 e do M8.

