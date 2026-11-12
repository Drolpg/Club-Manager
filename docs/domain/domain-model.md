# Modelo de domínio

| Campo | Valor |
| --- | --- |
| Status | Approved |
| Atualizado em | 2026-11-11 |
| Aprovado por / em | Leandro Nascimento / 2026-11-11 |
| Auditado contra o código em | Ainda não implementado |

Antes da implementação, este diagrama é o alvo. Depois, o código é a fonte da verdade e o diagrama é auditado contra
ele a cada marco. Cobre só os três contextos core; os contextos de apoio ficam em camadas, sem modelo tático
(ADR-001).

```mermaid
classDiagram
  direction LR
  namespace Aprovacoes {
    class Solicitacao {
      <<Aggregate Root>>
      +UUID id
      +TipoDeSolicitacao tipo
      +UUID solicitante_id
      +UUID aprovador_indicado_id
      +EstadoDaSolicitacao estado
      +enviar()
      +aprovar()
      +contestar()
      +recusar()
      +reenviar()
      +reabrir()
      +editar()
      +iniciar_execucao()
      +encerrar()
      +cancelar()
    }
    class Versao {
      <<Entity>>
      +int numero
      +Conteudo conteudo
      +Dinheiro valor
      +UUID autor_id
      +String justificativa
    }
    class Decisao {
      <<Entity>>
      +TipoDeDecisao tipo
      +UUID aprovador_id
      +MotivoAplicado motivo
      +String mensagem
      +Dinheiro teto_sugerido
      +bool aprovacao_propria
    }
    class MotivoAplicado {
      <<Value Object>>
      +UUID motivo_id
      +String texto
      +String complemento
    }
    class EstadoDaSolicitacao {
      <<enumeration>>
      EM_ANALISE
      CONTESTADA
      RECUSADA
      APROVADA
      EM_EXECUCAO
      ENCERRADA
      CANCELADA
    }
  }
  namespace Financeiro {
    class Cobranca {
      <<Aggregate Root>>
      +UUID id
      +UUID devedor_id
      +Dinheiro valor
      +Date vencimento
      +int limite_de_inadimplencia
      +PixCopiaECola pix
      +EstadoDaCobranca estado
      +UUID cobranca_origem_id
      +registrar_pagamento()
      +validar_pagamento()
      +rejeitar_pagamento()
      +marcar_atraso()
      +questionar()
      +decidir_questionamento()
      +isentar()
      +cancelar()
      +convocar()
      +justificar_divida()
      +perdoar()
      +renegociar()
      +manter_divida()
    }
    class Pagamento {
      <<Entity>>
      +FormaDePagamento forma
      +UUID comprovante_id
      +UUID recebedor_id
      +MotivoAplicado decisao
    }
    class Questionamento {
      <<Entity>>
      +String texto
      +MotivoAplicado decisao
    }
    class Convocacao {
      <<Entity>>
      +String justificativa_do_devedor
      +MotivoAplicado decisao
    }
    class EstadoDaCobranca {
      <<enumeration>>
      ABERTA
      EM_VALIDACAO
      ATRASADA
      PAGA
      ISENTA
      CANCELADA
      PERDOADA
      RENEGOCIADA
    }
    class Recorrencia {
      <<Aggregate Root>>
      +UUID id
      +UUID devedor_id
      +Dinheiro valor
      +Periodicidade periodicidade
      +bool ativa
      +alterar()
      +desativar()
    }
    class Suspensao {
      <<Aggregate Root>>
      +UUID id
      +UUID diretor_id
      +Periodo periodo
      +String justificativa
      +encerrar()
    }
    class Renegociacao {
      <<Aggregate Root>>
      +UUID id
      +UUID cobranca_original_id
      +Dinheiro valor_acordado
      +MotivoAplicado motivo
    }
    class Entrada {
      <<Aggregate Root>>
      +UUID id
      +TipoDeEntrada tipo
      +Dinheiro valor
      +UUID saida_id
      +EstadoDaEntrada estado
      +validar()
      +rejeitar()
      +estornar()
    }
    class Saida {
      <<Aggregate Root>>
      +UUID id
      +UUID solicitacao_id
      +UUID solicitante_id
      +Dinheiro valor_aprovado
      +EstadoDaSaida estado
      +registrar_envio()
      +prestar_contas()
      +devolver_prestacao()
      +liquidar()
      +cancelar()
      +estornar()
    }
    class Envio {
      <<Entity>>
      +Dinheiro valor_enviado
      +UUID comprovante_de_envio_id
    }
    class PrestacaoDeContas {
      <<Entity>>
      +Dinheiro valor_gasto
      +UUID comprovante_de_gasto_id
      +String justificativa
    }
    class EstadoDaSaida {
      <<enumeration>>
      AGUARDANDO_ENVIO
      RECURSO_ENVIADO
      EM_CONFERENCIA
      LIQUIDADA
      CANCELADA
      ESTORNADA
    }
    class Dinheiro {
      <<Value Object>>
      +Decimal valor
    }
    class PixCopiaECola {
      <<Value Object>>
      +String codigo
    }
    class Periodo {
      <<Value Object>>
      +Date inicio
      +Date fim
    }
    class Competencia {
      <<Value Object>>
      +int ano
      +int numero
    }
  }
  namespace Eventos {
    class Evento {
      <<Aggregate Root>>
      +UUID id
      +String titulo
      +Date data
      +UUID proponente_id
      +bool envolve_custo
      +UUID solicitacao_do_evento_id
      +UUID solicitacao_orcamentaria_id
      +EstadoDoEvento estado
      +vincular_orcamento()
      +editar()
      +atualizar_situacao()
      +confirmar_realizacao()
      +cancelar()
    }
    class Realizacao {
      <<Value Object>>
      +Date data
      +UUID confirmado_por
      +String motivo_da_mudanca_de_data
    }
    class EstadoDoEvento {
      <<enumeration>>
      EM_APROVACAO
      PUBLICADO
      RECUSADO
      REALIZADO
      CANCELADO
    }
  }

  Solicitacao "1" *-- "1..*" Versao : versões
  Solicitacao "1" *-- "0..*" Decisao : decisões
  Decisao "1" *-- "1" MotivoAplicado : motivo
  Cobranca "1" *-- "0..*" Pagamento : pagamentos
  Cobranca "1" *-- "0..*" Questionamento : questionamentos
  Cobranca "1" *-- "0..1" Convocacao : convocação
  Cobranca "1" *-- "1" PixCopiaECola : pix
  Saida "1" *-- "0..1" Envio : envio
  Saida "1" *-- "0..*" PrestacaoDeContas : prestações
  Suspensao "1" *-- "1" Periodo : período
  Evento "1" *-- "0..1" Realizacao : realização

  Cobranca ..> Recorrencia : recorrencia_id (por ID)
  Cobranca ..> Cobranca : cobranca_origem_id (por ID)
  Renegociacao ..> Cobranca : cobranca_original_id (por ID)
  Saida ..> Solicitacao : solicitacao_id (por ID)
  Entrada ..> Saida : saida_id (por ID, devolução)
  Evento ..> Solicitacao : solicitacao_do_evento_id (por ID)
  Evento ..> Solicitacao : solicitacao_orcamentaria_id (por ID)
```

## Legenda

| Notação | Significado |
| --- | --- |
| `*--` | Faz parte do aggregate (mesma transação) |
| `..>` | Referência por ID a outro aggregate |
| `<<Value Object>>` | Imutável, validado na criação, sem identidade |

## Value objects

| Value object | Regra de formação | Usado em |
| --- | --- | --- |
| `Dinheiro` | Decimal com duas casas, em reais; nunca ponto flutuante; não negativo | Todos os valores |
| `MotivoAplicado` | ID do motivo de decisão, texto do motivo no momento da decisão e texto livre opcional | Toda decisão |
| `PixCopiaECola` | Código de pagamento gerado a partir da chave Pix, do valor e do identificador da cobrança | Cobrança |
| `Periodo` | Início e fim opcional; o fim não é anterior ao início | Suspensão |
| `Competencia` | Período de referência de uma cobrança recorrente, calculado da periodicidade e da data | Recorrência, Cobrança |
| `Realizacao` | Data em que o evento aconteceu, quem confirmou e, se a data difere da planejada, o motivo | Evento |

## Observações de implementação

- Pela ADR-001, o aggregate é o modelo persistido: não há entidade de domínio separada nem mapper. O que este
  diagrama chama de método é o método do modelo; as decisões (transições permitidas, `situacao_do_evento`,
  `estado_sem_pagamento`, cálculo de competência) são funções puras, sem import do framework.
- As permissões ("quem tem a permissão") não aparecem no modelo: são verificadas pelo serviço antes de chamar o
  aggregate, e o aggregate protege só as regras que dependem do próprio estado e de quem é o ator.

## Divergências conhecidas código × diagrama

| Elemento | Diagrama | Código | Motivo | Registro |
| --- | --- | --- | --- | --- |
| — | — | Ainda não implementado | — | — |
