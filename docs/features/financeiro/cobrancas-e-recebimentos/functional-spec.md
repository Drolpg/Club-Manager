# Especificação Funcional: Cobranças e recebimentos

| Campo | Valor |
| --- | --- |
| Feature | `financeiro/cobrancas-e-recebimentos` |
| Status | Draft |
| Responsável | Leandro Nascimento |
| Atualizado em | 2026-11-13 |
| Aprovado por | — |
| Aprovado em | — |
| Requisitos | RF-046 a RF-072, RF-123 a RF-125; RN-011, RN-012, RN-013, RN-015 a RN-018, RN-023; INV-COB-01 a 13, INV-REC, INV-SUS, INV-ENT, INV-REN |
| Referências | Marco M6; canvases `docs/domain/aggregates/cobranca.md` e `financeiro-menores.md`; histórias 1 a 4 e 7 da descoberta; hotspots H01 a H10, H17, H18; AD-011 |

## Problema e resultado esperado

O clube vive de mensalidades, cotas, patrocínios e rifas, e hoje não tem um registro confiável de quem deve, quem
pagou e o que de fato entrou na conta. O dinheiro passa por fora do sistema, por Pix ou em mão.

Depois desta feature:

- o financeiro cria cobranças, avulsas ou recorrentes, e cada diretor vê o que deve e como pagar;
- o devedor registra o pagamento, e a cobrança só conta como recebida depois que outra pessoa confere e valida;
- quem atrasa é avisado, convocado e tem a dívida decidida: perdoada, renegociada ou mantida;
- entradas sem devedor (patrocínio, rifa, ajuda) também passam por validação;
- tudo fica auditado, e nada é apagado.

Esta feature é grande e é entregue em seis partes, na ordem da seção "Entregas".

## Atores e cenários

Atores: admin; quem opera o financeiro (usuário com as permissões da tabela "Permissões"); devedor (o diretor de
quem a cobrança é esperada); recebedor (usuário que recebeu dinheiro em mão); o agendador.

### 1. Preparar: categorias e chaves Pix

- O admin mantém as categorias de entrada e de saída. O sistema nasce com as de entrada: Mensalidade, Patrocínio,
  Ajuda, Rifa e Diversos. Categoria já usada é desativada, nunca apagada.
- O admin cadastra as chaves Pix de destino, com o tipo da chave, o nome do recebedor e a cidade, e marca uma como
  padrão do clube. Chave usada é desativada, nunca apagada.

### 2. Cobrança avulsa, para um ou vários diretores

1. Quem pode criar cobranças informa a descrição, a categoria, o valor, o vencimento, o limite de inadimplência (em
   dias depois do vencimento) e a chave Pix (já vem a padrão).
2. Escolhe um diretor, vários, ou todos os diretores ativos com cargo.
3. O sistema cria uma cobrança para cada um, com o Pix copia e cola e o QR Code já com o valor, e notifica cada
   devedor.

### 3. Recorrência (a mensalidade)

1. Quem pode criar cobranças cria uma recorrência para um diretor: categoria, valor, periodicidade (mensal, semanal
   ou anual), quando vence, com quantos dias de antecedência a cobrança é gerada (padrão: 10), limite de
   inadimplência e chave Pix.
2. Todo dia, o sistema gera as cobranças que chegaram na antecedência, uma por diretor e por período, e notifica.
3. Alterar a recorrência vale para as próximas cobranças; as já geradas não mudam. Desativá-la para a geração.

A mensalidade de cada diretor é uma recorrência mensal com o valor dele.

### 4. Pagar e validar (caminho feliz)

1. O devedor abre a cobrança, vê o valor, o vencimento, o Pix copia e cola e o QR Code, e paga por fora.
2. O devedor registra o pagamento, anexando o comprovante.
3. A cobrança fica em validação, e quem pode validar pagamentos é notificado.
4. Um validador, que não é o devedor, confere na conta e valida, escolhendo um motivo (por exemplo, "conferido em
   conta pelo titular").
5. A cobrança fica paga; o devedor é notificado e pode baixar o recibo em PDF.

Variação, dinheiro em mão: o devedor registra o pagamento sem comprovante e indica o usuário que recebeu o dinheiro.
O validador consulta essa pessoa por fora e valida com o motivo correspondente.

### 5. Pagamento rejeitado

1. O validador não encontra o valor na conta, ou o comprovante está errado, e rejeita com um motivo.
2. A cobrança volta a aberta (ou a atrasada, se já venceu), e o devedor é notificado para refazer.

### 6. Lembretes, atraso e inadimplência

1. Três dias antes do vencimento e no dia, o sistema lembra o devedor que ainda não registrou o pagamento.
2. No dia seguinte ao vencimento, sem pagamento validado nem em validação, a cobrança fica atrasada; o devedor e
   quem opera o financeiro são notificados.
3. Quando o limite de inadimplência acaba, o sistema convoca o devedor e avisa quem decide dívidas.
4. O devedor registra a justificativa na própria cobrança.
5. Quem decide dívidas escolhe, com motivo: **perdoar** (a dívida é extinta), **renegociar** (a cobrança é
   encerrada e substituída por parcelas, cada uma com valor e vencimento) ou **manter**.

Quem decide não precisa esperar a justificativa.

### 7. Questionar uma cobrança

1. O devedor questiona uma cobrança aberta ou atrasada, com um texto.
2. Quem decide questionamentos é notificado. Enquanto o questionamento está aberto, a cobrança não gera aviso de
   atraso nem convocação, e não conta como inadimplência.
3. A decisão, com motivo, é **isentar**, **cancelar** ou **manter**. O devedor é notificado. Mantida, a cobrança
   volta a contar os prazos normalmente.

### 8. Isentar, cancelar e suspender

- **Isentar:** dispensa uma cobrança já gerada, com justificativa.
- **Cancelar:** anula uma cobrança aberta ou atrasada, com motivo (por exemplo, criada por engano).
- **Suspender:** por um período e com justificativa, impede que as próximas cobranças recorrentes de um diretor
  sejam geradas (de uma recorrência ou de todas). Não mexe nas já geradas. Os períodos pulados não são gerados depois.

### 9. Entrada sem devedor

1. Quem pode registrar entradas informa a categoria, o valor, a data, a origem (por exemplo, o nome do
   patrocinador) e a evidência: comprovante ou texto.
2. Quem pode validar entradas, e não é quem registrou, valida ou rejeita, com motivo.
3. Só a entrada validada conta como recebida.

### 10. Diretor desativado

Quando um diretor é desativado, as recorrências dele param de gerar, e ele deixa de receber avisos. As cobranças já
existentes continuam como estão, e quem opera o financeiro é notificado para decidir cada uma.

### 11. Consultar

- **O devedor** vê as próprias cobranças, com situação, pagamento, questionamento e recibo.
- **Todo diretor com cargo** lista as cobranças e as entradas do clube, com filtro por situação, categoria, devedor e
  período, e abre o detalhe com o histórico.
- **Os comprovantes** só são vistos pelo devedor, por quem valida pagamentos e pelo admin.

## Regras de negócio

As invariantes estão nos canvases dos aggregates. Esta spec as mantém e acrescenta o que segue.

| # | Regra | Requisito |
| --- | --- | --- |
| 1 | Valores são escriturais: o sistema registra, e o dinheiro se move por fora | RN-023 |
| 2 | Toda entrada precisa de validação; só o validado conta como recebido | RN-015, INV-ENT-02 |
| 3 | Ninguém valida em causa própria: o devedor não valida o próprio pagamento, e quem registrou uma entrada não a valida | RN-012, INV-COB-05; decisão 1 |
| 4 | Toda decisão (validar, rejeitar, decidir questionamento, perdoar, renegociar, manter, validar entrada) tem um motivo da lista, com texto opcional | RN-011 |
| 5 | Uma cobrança termina de um só jeito (paga, isenta, cancelada, perdoada ou renegociada) e, encerrada, não muda mais | INV-COB-02, RN-013 |
| 6 | O pagamento tem comprovante, ou a marca "em mão" com um recebedor que é usuário ativo e não é o devedor | INV-COB-04 |
| 7 | Não há pagamento parcial: o pagamento é do valor inteiro da cobrança | Backlog |
| 8 | Uma recorrência gera no máximo uma cobrança por período; rodar a geração de novo não duplica | INV-COB-11, RNF-10 |
| 9 | A cobrança guarda a chave Pix e o código copia e cola de quando foi criada | INV-COB-12 |
| 10 | A cobrança fica atrasada no dia seguinte ao vencimento, se não está paga nem em validação | RF-060 |
| 11 | Com questionamento aberto, a cobrança não gera aviso de atraso nem convocação e não conta como inadimplência; o prazo do limite de inadimplência volta a contar na decisão | Decisão 4 |
| 12 | Cobrança isenta, perdoada, cancelada ou renegociada não gera aviso nem conta como inadimplência | RN-016 |
| 13 | Isenção vale para uma cobrança já gerada e não tem período; o que tem período é a suspensão | H17 **(altera FIN-11)** |
| 14 | A suspensão não afeta cobranças já geradas, e os períodos pulados não são gerados depois | INV-SUS-03, INV-SUS-04 |
| 15 | Na renegociação, a cobrança original é encerrada e as parcelas nascem na mesma operação, ligadas a ela; o total das parcelas pode ser diferente do valor original | INV-REN-03; decisão do desenho tático |
| 16 | Uma parcela é uma cobrança como as outras e pode atrasar e ser renegociada de novo | INV-REN-04 |
| 17 | Diretor inativo não recebe cobrança nova nem aviso; as cobranças antigas dele ficam para o financeiro decidir | RN-017; decisão 3 |
| 18 | Categoria e chave Pix usadas são desativadas, nunca apagadas; só o admin as mantém | RN-005, RN-018 |
| 19 | Todo diretor com cargo lê cobranças e entradas; o comprovante só é visto pelo devedor, por quem valida pagamentos e pelo admin | RF-025, RNF-07 |
| 20 | O recibo só existe para cobrança paga, e é o mesmo toda vez que é baixado | RF-059 |
| 21 | Toda ação desta feature gera registro de auditoria; comprovantes não entram no registro, só a referência | RF-026 |

Situações da cobrança (do canvas): `ABERTA`, `EM_VALIDACAO`, `ATRASADA`, `PAGA`, `ISENTA`, `CANCELADA`, `PERDOADA`,
`RENEGOCIADA`. Questionamento e convocação são registros dentro da cobrança, não situações.

### Permissões

| Permissão | O que permite | Concedida de início a |
| --- | --- | --- |
| Criar cobranças | Cobrança avulsa, em lote e recorrências | Setor Financeiro |
| Validar pagamentos | Validar e rejeitar pagamentos de cobrança; ver comprovantes | Setor Financeiro |
| Registrar entradas | Entradas sem devedor | Setor Financeiro |
| Validar entradas | Validar e rejeitar entradas | Setor Financeiro |
| Cancelar cobranças | Cancelar cobrança aberta ou atrasada | Ninguém (só o admin) |
| Isentar cobranças | Isentar uma cobrança | Ninguém |
| Decidir questionamentos | Isentar, cancelar ou manter uma cobrança questionada | Ninguém |
| Decidir dívidas | Perdoar, renegociar ou manter | Ninguém |
| Suspender cobranças | Criar e encerrar suspensões | Ninguém |

Categorias e chaves Pix são só do admin.

### Notificações

| Quando | Quem é avisado | Pede ação? |
| --- | --- | --- |
| Cobrança criada | O devedor | Sim |
| 3 dias antes do vencimento, e no dia | O devedor que ainda não registrou pagamento | Sim |
| Pagamento registrado | Quem valida pagamentos, menos o devedor | Sim |
| Pagamento validado | O devedor | Não |
| Pagamento rejeitado | O devedor | Sim |
| Cobrança atrasada | O devedor (pede ação) e quem cria cobranças (informativa) | — |
| Cobrança questionada | Quem decide questionamentos | Sim |
| Questionamento decidido | O devedor | Não |
| Devedor convocado | O devedor (pede ação) e quem decide dívidas (informativa) | — |
| Justificativa registrada | Quem decide dívidas | Sim |
| Dívida perdoada, renegociada ou mantida | O devedor | Não |
| Entrada registrada | Quem valida entradas, menos quem registrou | Sim |
| Entrada validada ou rejeitada | Quem registrou | Não |
| Diretor com cobranças em aberto foi desativado | Quem cria cobranças | Sim |

## Entregas

A feature é implementada em seis partes, cada uma utilizável sozinha. O critério de aceite do marco no enunciado
(cobrança recorrente gerada, notificada, paga e validada) é atendido ao fim da parte 3.

| Parte | Conteúdo | Cenários |
| --- | --- | --- |
| 1 | Categorias, chaves Pix, cobrança avulsa e em lote, Pix copia e cola, cancelar | 1, 2, 8 (cancelar) |
| 2 | Pagamento, validação, rejeição, comprovante e recibo | 4, 5 |
| 3 | Recorrência, geração automática e suspensão | 3, 8 (suspender) |
| 4 | Lembretes, atraso, questionamento e isenção | 6 (passos 1 e 2), 7, 8 (isentar) |
| 5 | Inadimplência: convocação, perdão, renegociação | 6 (passos 3 a 5) |
| 6 | Entradas sem devedor e diretor desativado | 9, 10 |

## Fora de escopo

| Item | Onde está |
| --- | --- |
| Estorno de cobrança paga e de entrada validada | M7 (RF-083, AD-010) |
| Saídas, solicitações de gasto e devoluções | M7 |
| Pagamento parcial | Backlog |
| Confirmação, pelo sistema, de quem recebeu dinheiro em mão | Backlog (H05) |
| Recebimento automático por plataforma de pagamento, e conferência automática do Pix | Etapa futura; o Pix aqui é só o código de pagamento |
| Dashboard, extrato, relatório de inadimplência e fluxo de caixa | M10 |
| Escudo e cores do clube no recibo | M11 |
| Histórico de pagamentos no perfil | M9 |
| Juros, multa e correção de cobrança atrasada | Não pedido; backlog |

## Critérios de aceite

Parte 1 — preparar e cobrar:

- [ ] CA-01 Dado um sistema recém-instalado, então existem as cinco categorias de entrada, e nenhuma chave Pix.
- [ ] CA-02 Dado o admin, quando ele cria, renomeia e desativa uma categoria, então a lista muda; categoria usada
      não pode ser apagada; quem não é admin é negado.
- [ ] CA-03 Dado o admin, quando ele cadastra chaves Pix e marca uma como padrão, então só uma é a padrão; chave
      com formato inválido para o tipo é recusada; quem não é admin é negado.
- [ ] CA-04 Dado quem pode criar cobranças, quando cria uma cobrança avulsa válida para um diretor ativo, então ela
      nasce aberta, com o Pix copia e cola contendo a chave e o valor, e o devedor é notificado.
- [ ] CA-05 Dada uma cobrança com valor zero ou negativo, devedor inativo, categoria ou chave inativa, ou
      vencimento no passado, então o sistema recusa.
- [ ] CA-06 Dada uma criação em lote para vários diretores, então nasce uma cobrança por diretor, cada devedor é
      notificado uma vez, e um diretor inativo na lista faz a operação inteira ser recusada, sem criar nenhuma.
- [ ] CA-07 Dado o código copia e cola de uma cobrança, então ele segue o padrão do Pix (campos obrigatórios e
      código de verificação corretos) e o QR Code mostrado corresponde a ele.
- [ ] CA-08 Dada uma chave Pix trocada ou desativada depois, então as cobranças já criadas continuam com o código
      antigo.
- [ ] CA-09 Dado quem não tem a permissão de criar cobranças, quando tenta criar, então é negado.
- [ ] CA-10 Dado quem pode cancelar, quando cancela com motivo uma cobrança aberta ou atrasada, então ela fica
      cancelada e não aceita mais nada; sem motivo, ou em outra situação, o sistema recusa.

Parte 2 — pagar e validar:

- [ ] CA-11 Dado o devedor de uma cobrança aberta ou atrasada, quando registra o pagamento com comprovante, então a
      cobrança fica em validação e quem valida pagamentos é notificado.
- [ ] CA-12 Dado um pagamento sem comprovante e sem a marca "em mão", ou "em mão" sem recebedor, com recebedor
      inativo ou com o próprio devedor como recebedor, então o sistema recusa.
- [ ] CA-13 Dado alguém que não é o devedor, quando tenta registrar o pagamento da cobrança, então é negado.
- [ ] CA-14 Dada uma cobrança em validação, quando um validador que não é o devedor valida com motivo, então ela
      fica paga, e o devedor é notificado.
- [ ] CA-15 Dado o devedor com a permissão de validar pagamentos, quando tenta validar o próprio pagamento, então o
      sistema recusa.
- [ ] CA-16 Dada uma cobrança em validação, quando o validador rejeita com motivo, então ela volta a aberta se não
      venceu e a atrasada se venceu, a rejeição fica no histórico, e o devedor é notificado.
- [ ] CA-17 Dada uma validação ou rejeição sem motivo, ou de cobrança que não está em validação, então o sistema
      recusa.
- [ ] CA-18 Dado um comprovante, então só o devedor, quem valida pagamentos e o admin conseguem abri-lo; outro
      diretor com cargo é negado.
- [ ] CA-19 Dada uma cobrança paga, quando o devedor baixa o recibo, então recebe um PDF com devedor, descrição,
      valor, data do pagamento e data da validação; para cobrança não paga, o recibo não existe.
- [ ] CA-20 Dado um arquivo de comprovante de tipo não permitido ou maior que o limite, então o sistema recusa.

Parte 3 — recorrência:

- [ ] CA-21 Dada uma recorrência mensal que vence no dia 10 com antecedência de 10 dias, quando a geração roda no
      dia 31 do mês anterior ou depois, então existe a cobrança daquele mês, e o devedor é notificado.
- [ ] CA-22 Dada a geração rodando duas vezes no mesmo dia, ou em dias seguidos, então existe uma cobrança só por
      período.
- [ ] CA-23 Dadas recorrências semanal e anual, então cada uma gera a cobrança do período certo.
- [ ] CA-24 Dada uma recorrência alterada, então as próximas cobranças usam os dados novos e as já geradas não
      mudam.
- [ ] CA-25 Dada uma recorrência desativada, ou de devedor inativo, então nenhuma cobrança é gerada.
- [ ] CA-26 Dada uma suspensão vigente para o diretor, então a cobrança do período não é gerada, e não é gerada
      depois que a suspensão acaba; as cobranças já geradas não mudam.
- [ ] CA-27 Dada uma suspensão sem justificativa, ou com fim antes do início, então o sistema recusa.
- [ ] CA-28 Dado o ciclo completo: recorrência criada, cobrança gerada sozinha, devedor notificado, pagamento
      registrado, validado e cobrança paga, então cada passo aparece no histórico da cobrança. (Critério de aceite do
      marco no enunciado.)

Parte 4 — lembretes, atraso, questionamento:

- [ ] CA-29 Dada uma cobrança aberta, então o devedor é lembrado 3 dias antes do vencimento e no dia, uma vez cada;
      se já registrou o pagamento, não é lembrado.
- [ ] CA-30 Dada uma cobrança aberta cujo vencimento passou, quando a tarefa diária roda, então ela fica atrasada e
      o devedor e quem cria cobranças são notificados; rodar de novo não repete.
- [ ] CA-31 Dado o devedor de uma cobrança aberta ou atrasada, quando a questiona com texto, então quem decide
      questionamentos é notificado; um segundo questionamento com o primeiro aberto é recusado.
- [ ] CA-32 Dada uma cobrança com questionamento aberto, então ela não fica atrasada, não gera lembrete nem
      convocação, e não aparece na consulta de inadimplência.
- [ ] CA-33 Dado um questionamento, quando é decidido com motivo: "isentar" deixa a cobrança isenta; "cancelar", a
      cancela; "manter" a deixa como estava e os prazos voltam a contar. O devedor é notificado.
- [ ] CA-34 Dado quem pode isentar, quando isenta com justificativa uma cobrança aberta ou atrasada, então ela fica
      isenta e não gera mais avisos.

Parte 5 — inadimplência:

- [ ] CA-35 Dada uma cobrança atrasada cujo limite de inadimplência acabou, quando a tarefa diária roda, então o
      devedor é convocado uma vez só e quem decide dívidas é avisado.
- [ ] CA-36 Dado o devedor convocado, quando registra a justificativa, então quem decide dívidas é notificado.
- [ ] CA-37 Dada uma cobrança atrasada, quando quem decide dívidas a perdoa com motivo, então ela fica perdoada,
      mesmo sem justificativa do devedor.
- [ ] CA-38 Dada uma cobrança atrasada, quando é renegociada em três parcelas, então a original fica renegociada e
      existem três cobranças novas, ligadas a ela, cada uma com o seu valor, vencimento e Pix; se a criação de uma
      parcela falha, nada muda.
- [ ] CA-39 Dada uma renegociação sem parcelas, com parcela de valor zero ou com vencimento no passado, então o
      sistema recusa.
- [ ] CA-40 Dada uma parcela atrasada, então ela pode ser renegociada de novo; a cobrança original, já renegociada,
      não.
- [ ] CA-41 Dado quem não tem a permissão de decidir dívidas, quando tenta perdoar, renegociar ou manter, então é
      negado; e o devedor nunca decide a própria dívida.

Parte 6 — entradas e diretor desativado:

- [ ] CA-42 Dado quem pode registrar entradas, quando registra uma entrada com evidência, então ela fica em
      validação e quem valida entradas, menos ele, é notificado; sem evidência, o sistema recusa.
- [ ] CA-43 Dada uma entrada em validação, quando quem a registrou tenta validá-la, então o sistema recusa; outro
      validador a valida ou rejeita com motivo, e quem registrou é notificado.
- [ ] CA-44 Dado um diretor com recorrência e cobranças abertas, quando ele é desativado, então a recorrência para
      de gerar, ele não recebe mais avisos, as cobranças ficam como estavam, e quem cria cobranças é notificado.

Transversais:

- [ ] CA-45 Dado um diretor com cargo, quando lista cobranças e entradas, então vê as de todos, com os filtros
      funcionando; diretor sem cargo é negado, mas vê as próprias cobranças.
- [ ] CA-46 Dada a consulta de inadimplência (quem tem cobrança atrasada), então isentas, perdoadas, canceladas,
      renegociadas e as com questionamento aberto não aparecem.
- [ ] CA-47 Dada cada ação desta feature, então existe um registro de auditoria, e o detalhe da cobrança e da
      entrada mostra o histórico.
- [ ] CA-48 Dada qualquer cobrança, entrada, categoria ou chave Pix, então não existe caminho para apagá-la.

## Decisões registradas nesta spec

| # | Decisão | Quem decidiu | Data |
| --- | --- | --- | --- |
| 1 | Quem registra uma entrada sem devedor não a valida | Leandro Nascimento | 2026-11-13 |
| 2 | O devedor é lembrado 3 dias antes do vencimento e no dia | Leandro Nascimento | 2026-11-13 |
| 3 | As cobranças de um diretor desativado ficam para o financeiro decidir | Leandro Nascimento | 2026-11-13 |
| 4 | Questionamento aberto pausa avisos, convocação e a contagem de inadimplência | Leandro Nascimento | 2026-11-13 |
| 5 | Periodicidades: mensal, semanal e anual | Leandro Nascimento | 2026-11-13 |
| 6 | A cobrança recorrente é gerada alguns dias antes do vencimento (padrão: 10) | Leandro Nascimento | 2026-11-13 |
| 7 | Há uma chave Pix padrão do clube, e quem cria a cobrança pode escolher outra | Leandro Nascimento | 2026-11-13 |
| 8 | Só as permissões operacionais nascem com o setor Financeiro; cancelar, isentar, decidir questionamentos e dívidas e suspender ficam só com o admin até ele conceder | Leandro Nascimento | 2026-11-13 |

Propostas do agente, que passam a valer com a aprovação desta spec:

| # | Proposta | Motivo |
| --- | --- | --- |
| P1 | A isenção perde o período; o que tem período é a suspensão (regra 13) | É o que a sua resposta na descoberta descreve (H17); altera o FIN-11 do enunciado |
| P2 | A cobrança fica atrasada no dia seguinte ao vencimento (regra 10) | Pagar no dia do vencimento ainda é pagar em dia |
| P3 | Com questionamento aberto, o prazo do limite de inadimplência para e volta a contar na decisão (regra 11) | Senão o devedor seria convocado logo depois de um questionamento negado, sem tempo de pagar |
| P4 | Criação em lote é tudo ou nada (CA-06) | Um lote pela metade é difícil de conferir |
| P5 | "Todos os diretores" no lote quer dizer os ativos com cargo | Diretor sem cargo ainda não foi classificado |
| P6 | O comprovante só é visto pelo devedor, por quem valida e pelo admin (regra 19) | Comprovante bancário traz dados da conta de quem pagou |
| P7 | Cancelar cobrança e validar entradas viram permissões próprias (tabela) | Cancelar apaga uma dívida; validar entrada confirma dinheiro: as duas pedem controle |
| P8 | A chave Pix guarda também o nome do recebedor e a cidade | O código do Pix exige os dois campos |
| P9 | A chave Pix pode ser e-mail, telefone, CNPJ, CPF ou aleatória | São os tipos que existem. Se for o CPF do titular, é um dado pessoal dele guardado no sistema: vale ele saber e concordar |
| P10 | O limite de inadimplência é obrigatório em toda cobrança, com 30 dias sugeridos | A convocação depende dele |
| P11 | Quem decide dívidas não precisa esperar a justificativa do devedor (cenário 6) | O devedor pode nunca responder |
| P12 | A feature é entregue em seis partes (seção "Entregas") | São 27 requisitos; em partes, cada entrega é conferível |

## Adendos

Nenhum.
