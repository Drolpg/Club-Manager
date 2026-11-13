# Especificação Funcional: Gastos e prestação de contas

| Campo | Valor |
| --- | --- |
| Feature | `financeiro/gastos-e-prestacao-de-contas` |
| Status | Approved |
| Responsável | Leandro Nascimento |
| Atualizado em | 2026-11-13 |
| Aprovado por | Leandro Nascimento |
| Aprovado em | 2026-11-13 |
| Requisitos | RF-073 a RF-083, RF-126 a RF-128; RN-012, RN-013, RN-015, RN-019, RN-023; INV-SAI-01 a 09, INV-ENT-03 e 04 |
| Referências | Marco M7; canvas `docs/domain/aggregates/saida.md`; histórias 5 e 6 da descoberta; hotspots H13 a H15; AD-010, AD-011; features `aprovacoes/motor-de-solicitacoes` e `financeiro/cobrancas-e-recebimentos` |

## Problema e resultado esperado

Quando o clube gasta (uma taxa de campeonato, uma arbitragem, material), o dinheiro sai da conta do titular, passa
por quem vai gastar e some. Não fica registrado quem pediu, quem autorizou, quanto foi enviado, quanto foi gasto de
verdade e o que aconteceu com a diferença.

Depois desta feature, cada gasto percorre um caminho só, do pedido ao encerramento:

- o diretor pede, item a item; alguém do financeiro aprova, contesta ou recusa;
- o financeiro envia o recurso e anexa o comprovante;
- quem gastou presta contas, com comprovante ou justificativa;
- a diferença é acertada: devolução, se gastou menos; complemento, se gastou mais;
- o financeiro confere e liquida, e a saída não muda mais.

## Atores e cenários

Atores: solicitante (qualquer diretor com cargo); aprovador de gastos; quem opera o financeiro (envia o recurso,
confere e liquida); admin; o agendador.

### 1. Pedir (solicitação de gasto)

1. O solicitante informa a descrição, a categoria de saída, o setor do clube a que o gasto pertence e os itens, cada
   um com descrição e valor. Pode anexar uma cotação.
2. O sistema soma o total e envia a solicitação ao motor de aprovações.

Daí em diante vale o ciclo do motor: aprovar, contestar (com teto sugerido), recusar, retirar, reenviar, reabrir,
editar e cancelar.

### 2. Decidir, vendo o caixa

Ao abrir uma solicitação de gasto para decidir, o aprovador vê a situação do caixa: quanto entrou e foi validado,
quanto saiu e foi liquidado, e quanto está comprometido em saídas aprovadas e ainda não liquidadas.

### 3. Enviar o recurso

1. Aprovada a solicitação, o sistema abre a saída, que fica aguardando o envio. O valor aprovado passa a contar
   como comprometido.
2. Quem opera o financeiro transfere o dinheiro por fora (ele mesmo, ou pedindo ao titular da conta) e registra o
   envio, com o valor e o comprovante.
3. A saída fica com o recurso enviado, o solicitante é notificado, e a solicitação não pode mais ser editada nem
   cancelada.

### 4. Prestar contas

1. O solicitante tem 7 dias, contados do envio, para prestar contas. O sistema o lembra aos 5 dias; vencido o
   prazo, lembra de novo e avisa o financeiro. Atrasada, a prestação continua podendo ser feita.
2. O solicitante informa o valor gasto e anexa os comprovantes, ou escreve uma justificativa quando o gasto não
   gera comprovante.
3. A saída fica em conferência, e quem liquida é notificado.

### 5. Acertar a diferença

- **Gastou menos:** o solicitante devolve o dinheiro por fora e registra a devolução, com evidência. A devolução é
  uma entrada ligada à saída, validada por quem valida entradas (e que não é o solicitante).
- **Gastou mais:** o solicitante pede um complemento, que é uma nova solicitação de gasto ligada à saída, só com a
  diferença. Aprovado, o financeiro envia a diferença e registra esse envio na mesma saída. Recusado, o financeiro
  liquida a saída pelo valor enviado, e a diferença fica registrada como gasto não reembolsado.

### 6. Conferir e liquidar

1. Quem liquida confere a prestação de contas e a diferença acertada.
2. Se algo está errado, devolve a prestação ao solicitante, com motivo; a saída volta a aguardar a prestação.
3. Se está certo, liquida. A saída fica liquidada e não muda mais, e a solicitação é encerrada.

Quem liquida não pode ser o solicitante daquela saída.

### 7. Cancelar antes do envio

Enquanto o recurso não foi enviado, cancelar ou editar a solicitação (pelo motor) cancela a saída. Uma nova saída
nasce se a solicitação for aprovada de novo.

### 8. Estornar

Um registro encerrado não é editado. Para desfazê-lo, quem tem a permissão de estornar registra um estorno, com
motivo e justificativa, ligado ao original:

| Original | Efeito do estorno |
| --- | --- |
| Saída liquidada | A saída fica estornada; o valor deixa de contar como saído |
| Entrada validada | A entrada fica estornada; o valor deixa de contar como recebido |
| Cobrança paga | A cobrança fica estornada; o valor deixa de contar como recebido. A dívida não reabre: para cobrar de novo, cria-se outra cobrança |

O estorno é definitivo: não existe estorno de estorno.

### 9. Consultar

- **Todo diretor com cargo** lista as saídas, com filtro por situação, categoria, setor, solicitante e período, e
  abre o detalhe: itens, valores (aprovado, enviado, gasto, devolvido), envios, prestações, devoluções, complementos,
  estorno e histórico.
- **Quem opera o financeiro** tem duas listas de trabalho: saídas aguardando envio, e prestações de contas
  pendentes (com as atrasadas em destaque).
- **Os anexos de um gasto** (cotação, comprovante de envio, comprovantes de gasto) são vistos por todo diretor com
  cargo.

## Regras de negócio

As invariantes estão em `docs/domain/aggregates/saida.md` e `financeiro-menores.md`. Esta spec as mantém, com as
mudanças do adendo descrito na proposta P1.

| # | Regra | Requisito |
| --- | --- | --- |
| 1 | Uma saída só nasce de uma solicitação de gasto aprovada, uma por solicitação | INV-SAI-01, RN-019 |
| 2 | A solicitação de gasto tem ao menos um item; cada item tem descrição e valor maior que zero; o total é a soma | RF-073 |
| 3 | Quem decide um gasto é quem tem a permissão de aprovar gastos, pelas regras do motor: nunca o próprio solicitante sem auto-aprovação | RN-010, RN-012 |
| 4 | O total enviado (envio inicial mais complementos) nunca passa do total aprovado (solicitação original mais complementos aprovados) | INV-SAI-02 |
| 5 | Todo envio tem comprovante | INV-SAI-03 |
| 6 | A prestação de contas tem o valor gasto e uma evidência: comprovante ou justificativa em texto | INV-SAI-04 |
| 7 | A saída só é liquidada com a diferença acertada: devoluções validadas cobrindo o que sobrou; ou complemento aprovado e enviado; ou, com complemento recusado ou não pedido, liquidação pelo valor enviado com justificativa | INV-SAI-05; decisão 2 |
| 8 | Quem liquida não é o solicitante; quem valida a devolução não é quem a registrou | INV-SAI-06, INV-ENT-04 |
| 9 | Depois do envio, a solicitação não é editada nem cancelada; a correção é por devolução ou complemento | INV-SOL-09 |
| 10 | Liquidada, cancelada ou estornada, a saída não muda mais | INV-SAI-07, RN-013 |
| 11 | O complemento é uma solicitação de gasto ligada à saída; só existe para saída com prestação de contas em que o gasto passou do enviado; no máximo um complemento em andamento por vez | RF-079 |
| 12 | A soma das devoluções de uma saída não passa do valor enviado | INV-ENT-03 |
| 13 | O estorno cria um registro novo, ligado ao original, com motivo e justificativa; o original fica marcado como estornado e não muda em mais nada | INV-SAI-09, RF-083 |
| 14 | Só se estorna o que está encerrado: saída liquidada, entrada validada, cobrança paga | RF-083 |
| 15 | Valor aprovado e não liquidado conta como comprometido; liquidado, conta como saído pelo valor gasto reembolsado (o enviado menos o devolvido) | FIN-14, RN-015 |
| 16 | O prazo da prestação de contas é de 7 dias depois do envio; o atraso gera avisos, não bloqueio | Decisão 1 |
| 17 | Categoria de saída usada é desativada, nunca apagada; só o admin as mantém | RN-018 |
| 18 | Toda ação desta feature gera registro de auditoria | RF-026 |

Situações da saída: `AGUARDANDO_ENVIO`, `RECURSO_ENVIADO`, `EM_CONFERENCIA`, `LIQUIDADA`, `CANCELADA`, `ESTORNADA`.

### Permissões

| Permissão | O que permite | Concedida de início a |
| --- | --- | --- |
| Aprovar gastos | Decidir solicitações de gasto e complementos | Setor Financeiro |
| Enviar recursos | Registrar o envio do recurso | Setor Financeiro |
| Liquidar saídas | Conferir a prestação de contas, devolvê-la e liquidar | Setor Financeiro |
| Estornar | Estornar saída, entrada ou cobrança encerrada | Ninguém (só o admin) |

Pedir um gasto não exige permissão: todo diretor com cargo pode. A validação da devolução usa a permissão de
validar entradas, do M6.

### Notificações

| Quando | Quem é avisado | Pede ação? |
| --- | --- | --- |
| Solicitação de gasto enviada, decidida, contestada etc. | As do motor de aprovações | — |
| Solicitação aprovada: saída aguardando envio | Quem envia recursos | Sim |
| Recurso enviado | O solicitante | Sim (prestar contas) |
| 5 dias depois do envio, sem prestação | O solicitante | Sim |
| Prazo de 7 dias vencido, sem prestação | O solicitante (pede ação) e quem liquida (informativa) | — |
| Prestação de contas registrada | Quem liquida, menos o solicitante | Sim |
| Prestação devolvida para correção | O solicitante | Sim |
| Devolução registrada | Quem valida entradas, menos quem registrou | Sim |
| Complemento aprovado: diferença a enviar | Quem envia recursos | Sim |
| Saída liquidada | O solicitante | Não |
| Estorno registrado | O solicitante ou o devedor do registro original, e os admins | Não |

## Fora de escopo

| Item | Onde está |
| --- | --- |
| Orçamento de evento (a mesma solicitação de gasto, aberta a partir de um evento) | M8 |
| Envio do recurso em parcelas, fora do caso do complemento | Backlog |
| Adiantamento sem solicitação, e reembolso de gasto já feito sem pedido prévio | Não pedido; backlog |
| Bloquear novos pedidos de quem tem prestação atrasada | Não pedido; backlog |
| Extrato, balancete e relatório de prestação de contas | M10 |
| Conferência automática com o banco | Etapa futura |

## Critérios de aceite

Pedido e decisão:

- [ ] CA-01 Dado um diretor com cargo, quando envia uma solicitação de gasto com dois itens, então ela entra em
      análise com o total igual à soma, e quem aprova gastos é notificado.
- [ ] CA-02 Dada uma solicitação sem itens, com item sem descrição ou de valor zero, com categoria ou setor inativo,
      então o sistema recusa, apontando o campo.
- [ ] CA-03 Dado o aprovador, quando abre a solicitação, então vê o total validado de entradas, o total liquidado de
      saídas e o total comprometido.
- [ ] CA-04 Dado um solicitante que tem a permissão de aprovar gastos e não tem auto-aprovação, então ele não decide
      o próprio pedido e precisa indicar um aprovador.
- [ ] CA-05 Dada uma contestação com teto sugerido, quando o solicitante reenvia com os itens ajustados, então a
      nova versão tem o novo total e a anterior continua visível.

Saída e envio:

- [ ] CA-06 Dada uma solicitação de gasto aprovada, então existe uma saída aguardando envio, com o valor aprovado, e
      quem envia recursos é notificado; aprovar não cria duas saídas.
- [ ] CA-07 Dada uma saída aguardando envio, quando a solicitação é editada ou cancelada, então a saída é cancelada;
      aprovada de novo, nasce outra.
- [ ] CA-08 Dado quem envia recursos, quando registra o envio com comprovante e valor até o aprovado, então a saída
      fica com o recurso enviado, a solicitação entra em execução, e o solicitante é notificado.
- [ ] CA-09 Dado um envio sem comprovante, ou com valor zero ou acima do aprovado, então o sistema recusa.
- [ ] CA-10 Dada uma solicitação com o recurso enviado, quando alguém tenta editá-la ou cancelá-la, então o sistema
      recusa.
- [ ] CA-11 Dado quem não tem a permissão de enviar recursos, quando tenta registrar o envio, então é negado.

Prestação de contas:

- [ ] CA-12 Dado o solicitante de uma saída com o recurso enviado, quando presta contas com valor gasto e
      comprovante, ou com justificativa em texto, então a saída fica em conferência e quem liquida é notificado.
- [ ] CA-13 Dada uma prestação sem comprovante e sem justificativa, ou feita por quem não é o solicitante, então o
      sistema recusa.
- [ ] CA-14 Dada uma saída há 5 dias com o recurso enviado e sem prestação, então o solicitante é lembrado; aos 7
      dias, é lembrado de novo e quem liquida é avisado; rodar a tarefa de novo não repete; a prestação ainda pode ser
      feita.
- [ ] CA-15 Dado quem liquida, quando devolve a prestação com motivo, então a saída volta a aguardar a prestação, a
      prestação devolvida fica no histórico, e o solicitante é notificado.

Diferença:

- [ ] CA-16 Dado um gasto menor que o enviado, quando o solicitante registra a devolução da diferença com evidência,
      então ela fica em validação como entrada ligada à saída; o solicitante não consegue validá-la.
- [ ] CA-17 Dada uma devolução que faria a soma das devoluções passar do valor enviado, então o sistema recusa.
- [ ] CA-18 Dado um gasto maior que o enviado, quando o solicitante pede o complemento da diferença, então nasce uma
      solicitação de gasto ligada à saída; um segundo complemento com o primeiro em andamento é recusado.
- [ ] CA-19 Dado um complemento aprovado, quando quem envia recursos registra o envio da diferença com comprovante,
      então a saída passa a ter dois envios e o total enviado não passa do total aprovado.
- [ ] CA-20 Dado um gasto igual ao enviado, então nem devolução nem complemento são pedidos.

Liquidação:

- [ ] CA-21 Dada uma saída em conferência com gasto menor e a devolução ainda não validada, quando alguém tenta
      liquidar, então o sistema recusa; validada a devolução, a liquidação é aceita.
- [ ] CA-22 Dada uma saída em conferência com gasto maior e complemento aprovado e enviado, então a liquidação é
      aceita.
- [ ] CA-23 Dada uma saída em conferência com gasto maior e complemento recusado, ou não pedido, quando quem liquida
      liquida pelo valor enviado com justificativa, então a liquidação é aceita e a diferença fica registrada como
      não reembolsada; sem justificativa, o sistema recusa.
- [ ] CA-24 Dado o solicitante de uma saída, com a permissão de liquidar, quando tenta liquidá-la, então o sistema
      recusa.
- [ ] CA-25 Dada uma saída liquidada, então a solicitação está encerrada, e nenhuma ação altera a saída além do
      estorno.
- [ ] CA-26 Dado o ciclo completo: pedido, aprovação, envio, prestação, liquidação, então cada passo aparece no
      histórico da saída. (Critério de aceite do marco no enunciado.)

Estorno:

- [ ] CA-27 Dado quem pode estornar, quando estorna com motivo e justificativa uma saída liquidada, uma entrada
      validada ou uma cobrança paga, então o original fica estornado, existe um estorno ligado a ele, e o valor deixa
      de contar nos totais.
- [ ] CA-28 Dado um registro que não está encerrado, ou já estornado, quando alguém tenta estorná-lo, então o
      sistema recusa; quem não tem a permissão é negado.
- [ ] CA-29 Dada uma cobrança paga e estornada, então ela não volta a aberta, e o recibo deixa de ser emitido.

Consulta e transversais:

- [ ] CA-30 Dado um diretor com cargo, quando lista as saídas e abre uma, então vê itens, valores, envios,
      prestações, devoluções, complementos, estorno, anexos e histórico; diretor sem cargo é negado.
- [ ] CA-31 Dado quem opera o financeiro, então as listas "aguardando envio" e "prestações pendentes" mostram
      exatamente as saídas nessas situações, com as atrasadas em destaque.
- [ ] CA-32 Dados os totais do caixa, então: entradas contam quando validadas e não estornadas; saídas contam como
      comprometidas da aprovação à liquidação, e como saídas pelo valor enviado menos o devolvido depois de
      liquidadas e não estornadas.
- [ ] CA-33 Dada cada ação desta feature, então existe um registro de auditoria; e nenhuma saída, envio, prestação
      ou estorno pode ser apagado.

## Decisões registradas nesta spec

| # | Decisão | Quem decidiu | Data |
| --- | --- | --- | --- |
| 1 | A prestação de contas tem prazo de 7 dias, com lembrete aos 5 e aviso ao financeiro no vencimento | Leandro Nascimento | 2026-11-13 |
| 2 | Com complemento recusado, a saída é liquidada pelo valor enviado, e a diferença fica como não reembolsada | Leandro Nascimento | 2026-11-13 |

Propostas do agente, que passam a valer com a aprovação desta spec:

| # | Proposta | Motivo |
| --- | --- | --- |
| P1 | A saída passa a aceitar mais de um envio: o inicial e os de complemento (adendo ao canvas, que previa um só) | O complemento aprovado precisa chegar ao solicitante com comprovante, e fica mais claro na mesma saída do que numa saída à parte |
| P2 | Cancelar uma saída é cancelar a solicitação dela, antes do envio; não há cancelamento só da saída | Um caminho só para a mesma coisa; a permissão é a de cancelar solicitações, do M5 |
| P3 | O estorno de cobrança paga não reabre a dívida; cria-se outra cobrança se for o caso (cenário 8) | É a regra do enunciado: corrigir um item encerrado exige um registro novo (APR-09) |
| P4 | A cobrança ganha a situação "estornada", por adendo ao canvas | A saída e a entrada já a tinham; os três passam a se comportar igual |
| P5 | Não existe estorno de estorno | Evita uma cadeia de desfazer e refazer; o caminho é um registro novo |
| P6 | Os anexos de um gasto são vistos por todo diretor com cargo | Gasto do clube é assunto de todos os diretores; diferente do comprovante de pagamento, que traz dados da conta de quem pagou |
| P7 | Aprovar gastos, enviar recursos e liquidar nascem com o setor Financeiro; estornar, só com o admin | Segue a sua decisão do M6: o operacional com o Financeiro, o sensível com o admin. Aprovar gasto é a função central do setor nas histórias que você contou |
| P8 | Pedir um gasto não exige permissão: basta ter cargo | Nas suas histórias, qualquer responsável de área pede |
| P9 | O sistema nasce com categorias de saída: Arbitragem, Taxas e inscrições, Material esportivo, Transporte, Alimentação, Eventos e Diversos | Ponto de partida editável pelo admin |
| P10 | O aprovador vê o caixa ao decidir (cenário 2) | Você descreveu o financeiro avaliando "a saúde do caixa" antes de aprovar |
| P11 | Prestação atrasada gera avisos, mas não bloqueia nada | Bloqueio é regra nova, que você não pediu |
| P12 | Só um complemento em andamento por vez (regra 11) | Evita pedidos sobrepostos para a mesma diferença |

## Adendos

Nenhum.
