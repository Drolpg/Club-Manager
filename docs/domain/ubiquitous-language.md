# Linguagem ubíqua

| Campo | Valor |
| --- | --- |
| Status | Approved |
| Atualizado em | 2026-11-11 |
| Aprovado por / em | Leandro Nascimento / 2026-11-11 |

Vocabulário oficial do projeto. Specs, código, testes, telas e documentação usam estes termos. Os nomes aqui são
definitivos; mudar um deles é uma decisão registrada. No código, os nomes de domínio ficam em português, sem acento.

## Glossário

### Identidade e Permissões

| Termo | Definição | Nome no código | Não usar |
| --- | --- | --- | --- |
| Usuário | Pessoa com conta no sistema. Na etapa 1, todo usuário é um diretor | `Usuario` | conta, membro |
| Admin | Usuário gestor do sistema, com todas as permissões; o único que gerencia usuários, cargos, setores, categorias e concessões | `admin` | superusuário, root |
| Diretor | Usuário comum da etapa 1; o que o diferencia são o cargo, os setores e as permissões | `Diretor` | sócio |
| Convite | Link de uso único, válido por 24 horas, pelo qual um diretor se cadastra | `Convite` | token de cadastro |
| Classificação | Ato de o admin atribuir cargo e setores a um diretor recém-cadastrado | `classificar` | aprovação de cadastro |
| Cargo | Função do diretor no clube (por exemplo, presidente), que traz um pacote de permissões | `Cargo` | papel, role |
| Setor | Área do clube (Financeiro, Futebol, Eventos, Operacional), que traz um pacote de permissões; um usuário pode estar em vários | `Setor` | departamento, grupo |
| Permissão | Combinação de ação e tipo de recurso que um usuário pode executar | `Permissao` | regra, role, privilégio |
| Concessão | Atribuição de uma permissão a um cargo, a um setor ou a um usuário | `Concessao` | regra avulsa |
| Responsável (por algo) | Qualquer usuário que tem a permissão correspondente; não é um cargo nem um campo | — | — |

### Aprovações

| Termo | Definição | Nome no código | Não usar |
| --- | --- | --- | --- |
| Solicitação | Pedido que passa por decisão formal. Tem tipo, versões e decisões | `Solicitacao` | requisição, pedido, proposta |
| Tipo de solicitação | O que está sendo pedido (gasto, orçamento de evento, evento), registrado pelo contexto que usa o motor | `TipoDeSolicitacao` | categoria de solicitação |
| Solicitante | Usuário que enviou a solicitação | `solicitante` | requerente, autor |
| Aprovador | Usuário que decide uma solicitação: quem tem a permissão para aquele tipo, ou o diretor indicado para aquele pedido | `aprovador` | validador, avaliador |
| Indicar aprovador | Ato de o solicitante, quando ele mesmo decidiria o pedido, escolher outro diretor para decidir só aquele pedido | `indicar_aprovador` | delegar |
| Decisão | Registro de aprovar, contestar ou recusar uma versão, com aprovador, motivo e momento | `Decisao` | parecer, voto |
| Aprovar | Aceitar a solicitação como está | `aprovar` | validar, confirmar |
| Contestar | Devolver a solicitação ao solicitante para ajustes, com mensagem e, se houver custo, um teto sugerido | `contestar` | questionar, devolver |
| Recusar | Negar a solicitação | `recusar` | reprovar, negar, rejeitar |
| Teto sugerido | Valor máximo que o aprovador propõe ao contestar uma solicitação com custo | `teto_sugerido` | limite |
| Reenviar | Corrigir uma solicitação contestada e mandá-la de volta, criando nova versão | `reenviar` | resubmeter |
| Retirar | Tirar da análise a própria solicitação para corrigi-la; ela sai da fila e volta por reenvio | `retirar` | cancelar, desistir |
| Reabrir | Voltar a pôr em decisão uma solicitação recusada, com justificativa, criando nova versão | `reabrir` | — |
| Versão | Cada estado do corpo da solicitação; nenhuma versão é sobrescrita | `Versao` | revisão |
| Motivo de decisão | Opção de uma lista cadastrada pelo admin, por tipo de decisão, que justifica uma decisão; pode vir com texto livre | `MotivoDeDecisao` | justificativa padrão |
| Fila de pendências | O que um aprovador tem para decidir | `fila_de_pendencias` | inbox de aprovação |

### Financeiro

| Termo | Definição | Nome no código | Não usar |
| --- | --- | --- | --- |
| Cobrança | Valor esperado de um diretor, com vencimento; única ou gerada por recorrência | `Cobranca` | débito, fatura, boleto |
| Devedor | O diretor de quem a cobrança é esperada | `devedor` | pagador, inadimplente (antes do atraso) |
| Recorrência | Regra que gera cobranças periódicas automaticamente | `Recorrencia` | assinatura |
| Mensalidade | Cobrança recorrente mensal de um diretor, com valor próprio | categoria | — |
| Vencimento | Data até a qual a cobrança deve ser paga | `vencimento` | prazo |
| Atrasada | Estado da cobrança vencida sem pagamento validado | `ATRASADA` | em atraso, vencida |
| Limite de inadimplência | Prazo, definido na criação da cobrança, depois do qual o devedor em atraso é convocado | `limite_de_inadimplencia` | carência |
| Convocação | Chamada ao devedor para justificar a dívida, quando o limite de inadimplência acaba | `Convocacao` | notificação de dívida |
| Perdão | Desfecho em que a dívida é extinta por decisão dos responsáveis; estado próprio da cobrança | `PERDOADA` | isenção, cancelamento |
| Renegociação | Desfecho em que a cobrança original é encerrada e substituída por parcelas | `Renegociacao` | acordo, parcelamento |
| Parcela | Cobrança gerada por uma renegociação, ligada à cobrança original | `Cobranca` com origem | prestação |
| Pagamento | Registro, feito pelo devedor, de que pagou por fora; leva comprovante, ou o recebedor quando foi em mão | `Pagamento` | baixa |
| Recebedor | Usuário que recebeu o dinheiro em mão, indicado pelo devedor | `recebedor` | — |
| Em validação | Estado da cobrança com pagamento registrado e ainda não conferido | `EM_VALIDACAO` | em processamento, pendente de validação |
| Validar (pagamento) | Conferir que o valor entrou e aceitar o pagamento, com motivo | `validar_pagamento` | aprovar, confirmar |
| Rejeitar (pagamento) | Não aceitar o pagamento, com motivo; o devedor refaz o registro | `rejeitar_pagamento` | reprovar, recusar |
| Paga | Estado final da cobrança com pagamento validado | `PAGA` | liquidada, quitada |
| Recibo | PDF emitido ao devedor a partir de uma cobrança paga | `Recibo` | comprovante |
| Chave Pix | Chave de destino cadastrada pelo admin; cada cobrança aponta para uma | `ChavePix` | conta |
| Pix copia e cola | Código de pagamento gerado para a cobrança, com o valor; o QR Code é a imagem dele | `pix_copia_e_cola` | — |
| Questionamento | Pedido do devedor para que uma cobrança seja revista, com texto | `Questionamento` | contestação (de cobrança) |
| Isenção | Dispensa de uma cobrança já gerada, com justificativa | `ISENTA` | suspensão, perdão |
| Suspensão | Regra, com período, que impede gerar as próximas cobranças recorrentes de um diretor | `Suspensao` | isenção |
| Entrada | Dinheiro que entrou, sempre validado: uma cobrança paga, uma devolução ou uma entrada sem devedor (patrocínio, rifa) | `Entrada` | receita |
| Saída | Dinheiro que sai, nascido de uma solicitação de gasto aprovada | `Saida` | despesa |
| Solicitação de gasto | Solicitação cujo tipo é um gasto, com itens e valores | tipo de solicitação | solicitação de recurso, pedido de verba |
| Solicitação orçamentária | Solicitação de gasto aberta para o orçamento de um evento | tipo de solicitação | — |
| Item | Linha de uma solicitação de gasto, com descrição e valor | `Item` | — |
| Recurso enviado | Estado da saída depois que o financeiro mandou o dinheiro ao solicitante | `RECURSO_ENVIADO` | pago |
| Comprovante de envio | Arquivo que prova a transferência ao solicitante | `comprovante_de_envio` | — |
| Prestação de contas | Comprovação do gasto pelo solicitante: comprovante de gasto ou justificativa em texto, com o valor gasto | `PrestacaoDeContas` | — |
| Devolução | Entrada ligada a uma saída, quando o gasto foi menor que o valor enviado | `Devolucao` | troco, ajuste |
| Complemento | Nova solicitação de gasto ligada à original, quando o gasto foi maior | `complemento` | ajuste |
| Liquidar | Encerrar a saída depois de conferir a prestação de contas; liquidada, ela não muda mais | `liquidar` | fechar, quitar |
| Estorno | Novo lançamento que desfaz um registro liquidado, ligado ao original | `Estorno` | cancelamento, reversão |
| Categoria | Classificação de entradas e de saídas, gerida pelo admin | `Categoria` | tipo |
| Titular | Dono da conta bancária real do clube; está fora do sistema | — | — |
| Escritural | Qualidade de todo valor do sistema: é registro, não movimentação bancária | — | — |

### Eventos

| Termo | Definição | Nome no código | Não usar |
| --- | --- | --- | --- |
| Evento | Algo que o clube organiza, com título, data e categoria | `Evento` | atividade |
| Proponente | Diretor que propôs o evento | `proponente` | organizador |
| Categoria de evento | Classificação do evento, gerida pelo admin | `CategoriaDeEvento` | tipo de evento |
| Orçamento do evento | O custo do evento, que existe como solicitação orçamentária no Financeiro | vínculo | — |
| Publicado | Estado do evento que está no calendário, com todas as solicitações exigidas aprovadas | `PUBLICADO` | aprovado (como estado do evento) |
| Calendário | Lista dos eventos publicados, vista por todos os diretores | consulta | agenda |
| Realizado | Estado final do evento que aconteceu, confirmado pelo proponente, por um responsável de eventos ou pelo admin | `REALIZADO` | liquidado, concluído |
| Cancelado | Estado final do evento que não vai acontecer, com motivo | `CANCELADO` | — |

### Demais contextos

| Termo | Definição | Contexto | Nome no código | Não usar |
| --- | --- | --- | --- | --- |
| Notificação | Registro de que um usuário foi avisado de algo, com vínculo ao item | Notificações | `Notificacao` | alerta, mensagem |
| Caixa de entrada | Lista das notificações de um usuário no site | Notificações | consulta | inbox |
| Preferência de alerta | Como o usuário quer ser alertado; nunca desliga o registro | Notificações | `PreferenciaDeAlerta` | — |
| Registro de auditoria | Linha imutável: quem, o quê, quando, sobre qual item, por quê | Auditoria | `RegistroDeAuditoria` | log |
| Comunicado | Postagem do feed; pode indexar documentos | Comunicação | `Comunicado` | post, notícia |
| Documento | Arquivo guardado na aba de documentos | Comunicação | `Documento` | anexo |
| Anexo | Arquivo preso a um item (comprovante, orçamento) | Transversal | `Anexo` | documento |
| Marca | Escudo e cores do clube | Marca | `Marca` | branding, tema |
| Tema | Variação visual derivada das cores base | Marca | `Tema` | skin |
| Realizado | Em relatórios: valor que já foi validado | Relatórios | — | — |

"Realizado" tem duas definições, uma por contexto: em Eventos é o estado de um evento que aconteceu; em Relatórios é
o valor validado. Não há conflito porque nunca aparecem no mesmo lugar.

## Regras de linguagem

- Um **usuário** tem **permissões** pela união das **concessões** do seu **cargo**, dos seus **setores** e das
  individuais.
- Uma **solicitação** é enviada por um **solicitante** e decidida por um **aprovador**, que a **aprova**,
  **contesta** ou **recusa**, sempre com um **motivo de decisão**.
- Uma solicitação **contestada** volta ao solicitante, que a **reenvia** como nova **versão**.
- Uma **cobrança** tem um **devedor**. O devedor registra um **pagamento**; a cobrança fica **em validação** até
  alguém **validar** ou **rejeitar** o pagamento.
- Uma cobrança termina de um só jeito: **paga**, **perdoada**, **isenta**, cancelada ou encerrada por
  **renegociação**.
- O devedor **questiona** uma cobrança; o aprovador **contesta** uma solicitação. Os dois verbos não se trocam.
- **Isenção** dispensa uma cobrança que já existe; **suspensão** impede que as próximas sejam geradas; **perdão**
  extingue uma dívida em atraso.
- Uma **solicitação de gasto** aprovada dá origem a uma **saída**. A saída passa por **recurso enviado** e
  **prestação de contas**, e é **liquidada** pelo financeiro.
- Um **evento** com custo tem duas solicitações: a do evento e a **solicitação orçamentária**. Ele só é
  **publicado** com as duas aprovadas.
- Só solicitações são **aprovadas**; só pagamentos são **validados**; só saídas são **liquidadas**; só eventos são
  **realizados**.

## Decisões de nomenclatura

### Validar vs aprovar e confirmar (pagamento)

"Validar pagamento" é o termo do enunciado e deixa "aprovar" exclusivo das solicitações. "Confirmar" ficaria ambíguo
com a confirmação de que um evento aconteceu. Escolha do dono em 2026-11-11.

### Questionar vs contestar

O dono usou "contestar" para os dois atos. Ficou separado: o devedor **questiona** a cobrança (termo do enunciado), e
o aprovador **contesta** a solicitação. Escolha do dono em 2026-11-11.

### Permissão vs regra, role e privilégio

"Permissão" é a combinação de ação e recurso; "concessão" é o ato de atribuí-la. "Regra" confundiria com regra de
negócio (RN-NN). Escolha do dono em 2026-11-11.

### Em validação vs em processamento

"Em processamento" sugere algo automático, e a conferência é manual. Escolha do dono em 2026-11-11.

### Aprovador vs validador

O dono falou em "validador" da solicitação. Como "validar" ficou reservado ao pagamento, quem decide uma solicitação
é o **aprovador**, que é o termo do enunciado.

### Liquidado só para saídas

O enunciado usa "liquidado" para cobrança paga, saída encerrada e evento encerrado. Cada um ganhou seu termo
(**paga**, **liquidada**, **realizado**), porque são fatos diferentes. A regra comum, "estado final é imutável",
continua valendo para os três.

### Publicado vs aprovado (evento)

O que é aprovado é a solicitação. O evento com custo depende de duas aprovações, então o estado dele é **publicado**
quando entra no calendário.

### Saída vs despesa; entrada vs receita

Termos do enunciado e do dono. "Solicitação de gasto" é o pedido; "saída" é o dinheiro que sai depois de aprovado.

## Histórico

| Data | Termo | Mudança | Motivo | Decisão |
| --- | --- | --- | --- | --- |
| 2026-11-11 | Todos | Primeira versão | Rito 4 | Aprovada por Leandro Nascimento |
| 2026-11-13 | Retirar | Termo novo | Spec funcional `aprovacoes/motor-de-solicitacoes` | Aprovada por Leandro Nascimento |
