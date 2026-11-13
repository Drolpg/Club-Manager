# Especificação Funcional: Eventos e calendário

| Campo | Valor |
| --- | --- |
| Feature | `eventos/eventos-e-calendario` |
| Status | Draft |
| Responsável | Leandro Nascimento |
| Atualizado em | 2026-11-13 |
| Aprovado por | — |
| Aprovado em | — |
| Requisitos | RF-084 a RF-093, RF-129 a RF-131; RN-013, RN-018, RN-020, RN-021; INV-EVT-01 a 07 |
| Referências | Marco M8; canvas `docs/domain/aggregates/evento.md`; `docs/domain/domain-events.md` (situação do evento); histórias 8 e 9 da descoberta; hotspots H20, H22, H24, H25, H27, H28; features `aprovacoes/motor-de-solicitacoes` e `financeiro/gastos-e-prestacao-de-contas` |

## Problema e resultado esperado

Os eventos do clube (jogos, reuniões, festas) são combinados de boca. Não há um lugar que diga o que está marcado,
quem aprovou, quanto vai custar e se aconteceu.

Depois desta feature:

- um diretor propõe um evento, e quem responde por eventos o aprova, contesta ou recusa;
- se o evento tem custo, o orçamento passa pelo financeiro, como uma solicitação de gasto ligada ao evento;
- só entra no calendário o evento com todas as aprovações, e todos os diretores são avisados;
- os diretores confirmam presença;
- no dia, alguém confirma que aconteceu, ou cancela com motivo.

## Atores e cenários

Atores: proponente (diretor com a permissão de propor); aprovador de eventos; aprovador de gastos (do M7); todo
diretor ativo com cargo; admin; o agendador.

### 1. Preparar: categorias de evento

O admin mantém as categorias. O sistema nasce com Jogo, Reunião, Festa e Outros. Categoria usada é desativada, nunca
apagada.

### 2. Propor e aprovar um evento sem custo

1. O proponente informa título, descrição, data e hora, local, categoria, e marca que não envolve custo.
2. O sistema envia a solicitação do evento ao motor de aprovações.
3. Um aprovador de eventos aprova (ou contesta, ou recusa), pelo ciclo do motor.
4. Aprovado, o evento é publicado no calendário, e todos os diretores ativos com cargo são notificados.

### 3. Evento com custo: duas solicitações

1. O proponente propõe o evento, marcando que envolve custo. O evento não guarda valor.
2. O aprovador de eventos avalia data e disponibilidade e decide a solicitação do evento.
3. Um aprovador de eventos monta o orçamento e o envia: é uma solicitação de gasto, com itens e valores, ligada ao
   evento.
4. O aprovador de gastos decide o orçamento: aprova, recusa, ou contesta com um teto sugerido, e o orçamento volta
   ajustado em outra rodada.
5. Com as duas solicitações aprovadas, o evento é publicado. O orçamento segue o caminho de qualquer gasto: envio do
   recurso, prestação de contas e liquidação.

A ordem entre as duas aprovações é livre; o que vale é as duas estarem aprovadas.

### 4. Calendário e detalhe

- O calendário mostra, mês a mês, só os eventos publicados e os realizados. Cada um é um card com título, data,
  hora, local e categoria; clicar abre o detalhe.
- O detalhe mostra os dados do evento, quem propôs, as solicitações ligadas com as decisões e os motivos, o
  orçamento (quando há), as presenças e o histórico.

### 5. Confirmar presença

Num evento publicado, cada diretor ativo com cargo marca "vou" ou "não vou", e pode mudar de ideia até o evento ser
realizado ou cancelado. O detalhe mostra quem vai, quem não vai e quem não respondeu.

### 6. Editar

O proponente (ou um aprovador de eventos) edita um evento que ainda não foi realizado nem cancelado. Se ele estava
publicado, sai do calendário, a solicitação do evento volta à análise como nova versão, e ele só reaparece depois de
aprovado de novo. Se a data mudou, as presenças são zeradas e todos são avisados da nova data na republicação.

O orçamento é uma solicitação à parte: mudar o custo é editar o orçamento, pelo ciclo de gastos.

### 7. No dia e depois

1. Na data do evento, o sistema notifica quem pode confirmar a realização: o proponente, os aprovadores de eventos
   e os admins.
2. Qualquer um deles confirma que o evento aconteceu. Se aconteceu numa data diferente da marcada, informa a data
   real e o motivo. O evento fica realizado e não muda mais.
3. Se ninguém confirma nem cancela, o sistema lembra de novo 1 dia e 3 dias depois da data.

O evento realizado e o orçamento encerram separadamente: o evento pode estar realizado com a prestação de contas
ainda em andamento.

### 8. Cancelar

O proponente, o admin ou quem tem a permissão de cancelar eventos cancela, com motivo, um evento ainda não
realizado. Ele sai do calendário, todos os diretores são notificados, e ele continua no histórico.

- Se o orçamento ainda não teve recurso enviado, a solicitação orçamentária é cancelada junto.
- Se o recurso já foi enviado, a saída segue o caminho dela (prestação de contas e devolução), e quem liquida é
  avisado de que o evento foi cancelado.

### 9. Evento que não foi aprovado a tempo

Se a data do evento passa e ele ainda não foi publicado (a solicitação do evento ou o orçamento não foi aprovado),
o sistema o cancela, com o motivo "a data passou sem aprovação", e notifica o proponente.

### 10. Histórico

Todo diretor com cargo lista todos os eventos, em qualquer situação, com filtro por situação, categoria e período.

## Regras de negócio

As invariantes estão em `docs/domain/aggregates/evento.md`. A situação do evento é calculada pela regra de
precedência de `docs/domain/domain-events.md`.

| # | Regra | Requisito |
| --- | --- | --- |
| 1 | Todo evento passa pela aprovação de um aprovador de eventos, com ou sem custo | Decisão 1; H27 |
| 2 | O evento só é publicado com a solicitação do evento aprovada e, se envolve custo, com a solicitação orçamentária também aprovada | INV-EVT-01, RN-020 |
| 3 | O evento não guarda valor: o custo existe só na solicitação orçamentária ligada a ele; um evento tem no máximo um orçamento | INV-EVT-02, INV-EVT-07 |
| 4 | O orçamento é aberto por um aprovador de eventos, e só para evento que envolve custo, não realizado nem cancelado | H22; RF-086 |
| 5 | Quem decide a solicitação do evento e o orçamento segue as regras do motor: ninguém decide o próprio pedido sem auto-aprovação | RN-012 |
| 6 | O calendário mostra só eventos publicados e realizados; o histórico mostra todos | RN-021 |
| 7 | Editar um evento publicado o tira do calendário até nova aprovação | INV-EVT-03 |
| 8 | Só se confirma a realização de evento publicado, com data que não é futura; data diferente da marcada exige motivo e não reabre a aprovação | INV-EVT-05; EVT-07 |
| 9 | Realizado ou cancelado, o evento não muda mais | INV-EVT-04, RN-013 |
| 10 | Cancelar exige motivo | INV-EVT-06 |
| 11 | Confirmam a realização: o proponente, quem aprova eventos e o admin; o primeiro que fizer encerra | H22 |
| 12 | Só diretor ativo com cargo confirma presença, e só em evento publicado; a presença pode mudar até o evento encerrar; mudar a data zera as presenças | Decisão 2 |
| 13 | Evento não publicado cuja data passou é cancelado pelo sistema | H28; proposta P2 |
| 14 | Realizar o evento encerra a solicitação do evento; o orçamento encerra pelo ciclo de gastos, de forma independente | Desenho tático |
| 15 | Categoria de evento usada é desativada, nunca apagada; só o admin as mantém | RN-018 |
| 16 | Toda ação desta feature gera registro de auditoria | RF-026 |

Situações do evento: `EM_APROVACAO`, `PUBLICADO`, `RECUSADO`, `REALIZADO`, `CANCELADO`.

### Permissões

| Permissão | O que permite | Concedida de início a |
| --- | --- | --- |
| Propor eventos | Propor e editar os próprios eventos | Os quatro setores iniciais |
| Aprovar eventos | Decidir solicitações de evento, abrir o orçamento, editar eventos e confirmar a realização | Setor Eventos |
| Cancelar eventos | Cancelar evento de outra pessoa | Ninguém (o proponente e o admin já podem) |

### Notificações

| Quando | Quem é avisado | Pede ação? |
| --- | --- | --- |
| Solicitação do evento e orçamento: enviados, decididos, contestados | As do motor de aprovações e de gastos | — |
| Evento aprovado e com custo, ainda sem orçamento | Quem aprova eventos | Sim (montar o orçamento) |
| Evento publicado | Todos os diretores ativos com cargo | Não |
| Evento saiu do calendário por edição | Quem tinha confirmado presença | Não |
| Data do evento chegou; e 1 e 3 dias depois, sem confirmação | O proponente, quem aprova eventos e os admins | Sim |
| Evento realizado | O proponente | Não |
| Evento cancelado | Todos os diretores ativos com cargo; e quem liquida, se havia recurso enviado | Não |
| Evento cancelado pelo sistema por falta de aprovação | O proponente | Não |

## Fora de escopo

| Item | Onde está |
| --- | --- |
| Lista de presença marcada pelo organizador depois do evento | Backlog |
| Evento recorrente (toda semana, todo mês) | Não pedido; backlog |
| Aprovação diferente por categoria de evento | Backlog (CB-03): quem aprova é quem tem a permissão de aprovar eventos |
| Convidados de fora, torcedores e jogadores | Etapas futuras |
| Lembrete de evento para quem confirmou presença | Não pedido; backlog |
| Eventos no perfil do diretor | M9 |
| Relatório de eventos | M10 |

## Critérios de aceite

Categorias e proposta:

- [ ] CA-01 Dado um sistema recém-instalado, então existem as quatro categorias de evento; o admin as mantém, e quem
      não é admin é negado.
- [ ] CA-02 Dado quem pode propor, quando propõe um evento válido, então o evento fica em aprovação, existe a
      solicitação do evento em análise, e quem aprova eventos é notificado.
- [ ] CA-03 Dado um evento sem título, com data no passado ou com categoria inativa, então o sistema recusa; quem
      não tem a permissão de propor é negado.

Aprovação e publicação:

- [ ] CA-04 Dado um evento sem custo, quando a solicitação do evento é aprovada, então ele fica publicado, aparece
      no calendário, e todos os diretores ativos com cargo são notificados uma vez.
- [ ] CA-05 Dado um evento com custo e só a solicitação do evento aprovada, então ele não está no calendário, e quem
      aprova eventos é avisado para montar o orçamento.
- [ ] CA-06 Dado um evento com custo, quando um aprovador de eventos abre o orçamento com itens, então nasce uma
      solicitação de gasto ligada ao evento; um segundo orçamento é recusado; orçamento para evento sem custo é
      recusado.
- [ ] CA-07 Dado um evento com custo, quando as duas solicitações estão aprovadas, em qualquer ordem, então ele é
      publicado. (Critério de aceite do marco: evento com custo exige o Financeiro.)
- [ ] CA-08 Dado um orçamento contestado com teto sugerido, quando ele é reenviado ajustado e aprovado, então o
      evento é publicado.
- [ ] CA-09 Dada a solicitação do evento recusada, então o evento fica recusado; reaberta e aprovada, ele segue o
      caminho normal.
- [ ] CA-10 Dado o proponente com a permissão de aprovar eventos e sem auto-aprovação, então ele não decide o
      próprio evento.

Calendário, detalhe e presença:

- [ ] CA-11 Dado o calendário de um mês, então ele mostra só os eventos publicados e realizados daquele mês; os em
      aprovação, recusados e cancelados não aparecem. (Critério de aceite do marco.)
- [ ] CA-12 Dado o detalhe de um evento, então ele mostra os dados, o proponente, as solicitações ligadas com
      decisões e motivos, o orçamento quando há, as presenças e o histórico.
- [ ] CA-13 Dado um diretor ativo com cargo e um evento publicado, quando marca "vou" e depois "não vou", então vale
      a última resposta, e o detalhe lista quem vai, quem não vai e quem não respondeu.
- [ ] CA-14 Dado um evento que não está publicado, ou um diretor sem cargo, então a presença é recusada.

Edição:

- [ ] CA-15 Dado um evento publicado, quando é editado, então ele sai do calendário, a solicitação do evento volta à
      análise como nova versão, e ele só volta ao calendário depois de aprovado de novo. (Critério de aceite do
      marco.)
- [ ] CA-16 Dada uma edição que muda a data, então as presenças são zeradas, e quem tinha confirmado é avisado.
- [ ] CA-17 Dado um evento realizado ou cancelado, quando alguém tenta editá-lo, então o sistema recusa.

Encerramento:

- [ ] CA-18 Dada a data de um evento publicado, então o proponente, quem aprova eventos e os admins são notificados;
      sem confirmação nem cancelamento, são lembrados 1 e 3 dias depois, uma vez cada.
- [ ] CA-19 Dado um evento publicado cuja data chegou, quando o proponente, um aprovador de eventos ou o admin
      confirma a realização, então ele fica realizado e a solicitação do evento é encerrada; outra pessoa é negada.
- [ ] CA-20 Dada a confirmação com data diferente da marcada, então o motivo é obrigatório, a data real fica
      registrada, e a aprovação não é reaberta; data futura é recusada.
- [ ] CA-21 Dado um evento realizado com orçamento ainda em prestação de contas, então o evento está encerrado e a
      saída continua o caminho dela.

Cancelamento:

- [ ] CA-22 Dado um evento não realizado, quando o proponente o cancela com motivo, então ele sai do calendário,
      fica no histórico, e todos os diretores são notificados; sem motivo, o sistema recusa.
- [ ] CA-23 Dado um evento de outra pessoa, então só o admin ou quem tem a permissão de cancelar eventos o cancela.
- [ ] CA-24 Dado um evento cancelado com orçamento sem recurso enviado, então a solicitação orçamentária é cancelada
      junto; com recurso já enviado, a saída continua e quem liquida é avisado.
- [ ] CA-25 Dado um evento em aprovação cuja data passou, quando a tarefa diária roda, então ele é cancelado pelo
      sistema, com o motivo registrado, e o proponente é notificado; rodar de novo não repete.

Histórico e transversais:

- [ ] CA-26 Dado um diretor com cargo, quando lista os eventos, então vê todos, em qualquer situação, com os filtros
      funcionando; diretor sem cargo é negado.
- [ ] CA-27 Dada cada ação desta feature, então existe um registro de auditoria; e nenhum evento pode ser apagado.
- [ ] CA-28 Dado o módulo de eventos, então ele usa o motor de aprovações e o financeiro só pela API pública de
      cada um, e nenhum dos dois o conhece.

## Decisões registradas nesta spec

| # | Decisão | Quem decidiu | Data |
| --- | --- | --- | --- |
| 1 | Todo evento, com ou sem custo, é aprovado por quem responde por eventos | Leandro Nascimento | 2026-11-13 |
| 2 | Os diretores confirmam presença nos eventos publicados | Leandro Nascimento | 2026-11-13 |

Propostas do agente, que passam a valer com a aprovação desta spec:

| # | Proposta | Motivo |
| --- | --- | --- |
| P1 | A ordem entre a aprovação do evento e a do orçamento é livre (cenário 3) | Nas suas histórias, quem aprova o evento é quem monta o orçamento; travar a ordem só atrasaria |
| P2 | Evento não aprovado cuja data passou é cancelado pelo sistema (cenário 9) | Responde à dúvida sobre o orçamento recusado em definitivo: o evento não fica parado para sempre |
| P3 | Mudar a data zera as presenças (regra 12) | Quem disse "vou" respondeu para outra data |
| P4 | Lembretes de confirmação 1 e 3 dias depois da data (cenário 7) | Responde à pendência do enunciado sobre reenvio quando ninguém confirma |
| P5 | Quem aprova eventos também pode editar qualquer evento, abrir o orçamento e confirmar a realização (tabela de permissões) | É o "responsável por eventos" das suas histórias; uma permissão só em vez de quatro |
| P6 | A permissão de propor nasce com os quatro setores iniciais | Na sua história, qualquer diretor propõe uma festa; o admin restringe se quiser |
| P7 | O evento realizado continua no calendário, marcado como realizado (cenário 4) | O calendário serve também para ver o que já aconteceu no mês |
| P8 | Categorias iniciais: Jogo, Reunião, Festa e Outros | Ponto de partida editável pelo admin |
| P9 | Cancelado o evento com recurso já enviado, a saída continua e o financeiro é avisado (cenário 8) | O dinheiro já saiu: precisa de prestação de contas ou devolução, e não de um cancelamento que o faria sumir |
| P10 | Presença é só "vou" ou "não vou", sem lembrete para quem confirmou | O mínimo que atende ao que você escolheu; o resto fica no backlog |

## Adendos

Nenhum.
