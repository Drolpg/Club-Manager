# Requisitos

| Campo | Valor |
| --- | --- |
| Status | Approved |
| Atualizado em | 2026-11-13 |
| Aprovado por / em | Leandro Nascimento / 2026-11-11 |
| Fontes | `docs/challenge/`, `docs/domain/` |

Este é o único registro de IDs de requisito. Board, tracker e specs citam estes IDs; nenhum deles cria IDs.

- `RF-NNN`: requisito funcional, no tamanho de uma ação.
- `RN-NNN`: regra de negócio que vale para mais de um requisito.
- `RNF-NN`: requisito não funcional.
- `INV-XXX-NN`: invariante de um aggregate, definida no canvas dele em `docs/domain/aggregates/`. As invariantes são
  regras de negócio com ID próprio e não são repetidas aqui.

Todos os requisitos são da fase 1. A coluna "Origem" cita o ID do enunciado (por exemplo, FIN-05), o hotspot da
descoberta (H01 a H30) ou a decisão (AD-NNN). Origem com **(novo)** não estava no enunciado; com **(alterado)**, muda
o que o enunciado dizia.

## Atores

| Ator | Papel | Tipo |
| --- | --- | --- |
| Admin | Gestor do sistema, com todas as permissões; gerencia usuários, cargos, setores, categorias, motivos de decisão e concessões | Humano |
| Diretor sem cargo | Recém-cadastrado, ainda não classificado; só vê o dashboard básico | Humano |
| Diretor com cargo | Lê os dados de gestão; age conforme as permissões que tem | Humano |
| Solicitante | Diretor que enviou uma solicitação | Humano (papel) |
| Aprovador | Diretor que decide uma solicitação: tem a permissão para o tipo, ou foi indicado para aquele pedido | Humano (papel) |
| Devedor | Diretor de quem uma cobrança é esperada | Humano (papel) |
| Responsável por algo | Qualquer usuário com a permissão correspondente (validar pagamento, liquidar saída, aprovar evento) | Humano (papel) |
| Agendador | Dispara as tarefas periódicas | Técnico |
| Google | Valida o login social | Sistema externo |
| Provedor de e-mail | Entrega os e-mails | Sistema externo |
| Titular da conta e banco | Movimentam o dinheiro real, fora do sistema | Fora do sistema |

## Requisitos funcionais

Status: `Proposto`, `Aprovado`, `Em implementação`, `Implementado`, `Removido (<motivo>)`.

### Identidade e Permissões — acesso (M2)

| ID | Requisito | Origem | Status | Feature |
| --- | --- | --- | --- | --- |
| RF-001 | O admin, ou quem tem a permissão de convidar, gera um convite de uso único, válido por 24 horas, sem cargo nem setor | ACE-05 | Implementado | `acesso/identidade-e-acesso` |
| RF-002 | Quem tem a permissão regenera ou revoga um convite | ACE-05 | Implementado | `acesso/identidade-e-acesso` |
| RF-003 | O sistema expira o convite depois de 24 horas | ACE-05, NOT-07 | Implementado | `acesso/identidade-e-acesso` |
| RF-004 | O convidado se cadastra pelo convite informando nome, nome de usuário único, telefone, e-mail e senha | ACE-06, ACE-09 | Implementado | `acesso/identidade-e-acesso` |
| RF-005 | O sistema envia um link de verificação e só libera o acesso depois de o e-mail ser verificado | ACE-04 | Implementado | `acesso/identidade-e-acesso` |
| RF-006 | O usuário entra com nome de usuário e senha | ACE-02 | Implementado | `acesso/identidade-e-acesso` |
| RF-007 | O usuário entra com o Google, na mesma conta do seu e-mail | ACE-01, ACE-02 | Implementado | `acesso/identidade-e-acesso` |
| RF-008 | O convidado aceita o convite pelo Google e completa o cadastro com nome de usuário e senha, sem link de verificação | ACE-03 | Implementado | `acesso/identidade-e-acesso` |
| RF-009 | O sistema recusa o login pelo Google de quem não foi convidado | ACE-12 | Implementado | `acesso/identidade-e-acesso` |
| RF-010 | O usuário recupera a senha pelo e-mail verificado | ACE-11 | Implementado | `acesso/identidade-e-acesso` |
| RF-011 | O usuário encerra a própria sessão | ACE-13 (derivado) | Implementado | `acesso/identidade-e-acesso` |
| RF-012 | O admin desativa e reativa um usuário; o desativado não entra | ACE-10 | Implementado | `acesso/identidade-e-acesso` |
| RF-013 | O sistema avisa o admin quando um diretor conclui o cadastro | ACE-07 | Implementado | `acesso/identidade-e-acesso` |
| RF-014 | O primeiro admin é criado por um procedimento seguro, sem senha padrão | Seção 16, AD-019 | Implementado | `acesso/identidade-e-acesso` |
| RF-116 | O admin dá e tira o papel de admin de outro usuário | Spec `acesso/identidade-e-acesso` **(novo)** | Implementado | `acesso/identidade-e-acesso` |
| RF-117 | O admin consulta os convites e os usuários, com a situação de cada um | Spec `acesso/identidade-e-acesso` **(novo)** | Implementado | `acesso/identidade-e-acesso` |

### Identidade e Permissões — permissões; Auditoria (M3)

| ID | Requisito | Origem | Status | Feature |
| --- | --- | --- | --- | --- |
| RF-015 | O admin cria, renomeia e desativa cargos | PER-04 | Implementado | `permissoes/catalogo-e-classificacao` |
| RF-016 | O admin cria, renomeia e desativa setores | PER-04, seção 4 | Implementado | `permissoes/catalogo-e-classificacao` |
| RF-017 | O admin classifica um diretor, atribuindo um cargo e um ou mais setores | ACE-07, seção 4 | Implementado | `permissoes/catalogo-e-classificacao` |
| RF-018 | O admin concede e revoga uma permissão a um cargo | PER-03 | Implementado | `permissoes/catalogo-e-classificacao` |
| RF-019 | O admin concede e revoga uma permissão a um setor | PER-03 | Implementado | `permissoes/catalogo-e-classificacao` |
| RF-020 | O admin concede e revoga uma permissão a um usuário, inclusive de um setor a que ele não pertence | PER-03 | Implementado | `permissoes/catalogo-e-classificacao` |
| RF-021 | O sistema calcula as permissões de um usuário como a união das concessões do cargo, dos setores e das individuais | PER-03 | Implementado | `permissoes/catalogo-e-classificacao` |
| RF-022 | O admin vê, para cada usuário, as permissões que ele tem e de onde vem cada uma | PER-05 | Implementado | `permissoes/catalogo-e-classificacao` |
| RF-023 | O admin concede e revoga acesso total a um usuário | PER-06 | Implementado | `permissoes/catalogo-e-classificacao` |
| RF-024 | O diretor sem cargo acessa só o dashboard básico | ACE-08, PER-01 | Implementado | `permissoes/catalogo-e-classificacao` |
| RF-025 | O diretor com cargo lê os dados de gestão (financeiro, eventos, feed, documentos) | PER-01 | Implementado | `permissoes/catalogo-e-classificacao` |
| RF-026 | O sistema registra, de forma imutável, quem fez o quê, quando, sobre qual item e com que justificativa, em toda ação relevante | AUD-01, AUD-02 | Implementado | `permissoes/catalogo-e-classificacao` |
| RF-027 | Quem pode ver um item consulta o histórico dele no próprio detalhe | AUD-03 | Implementado | `permissoes/catalogo-e-classificacao` |
| RF-118 | O diretor consulta o próprio cargo, os próprios setores e as próprias permissões | Spec `permissoes/catalogo-e-classificacao` **(novo)** | Implementado | `permissoes/catalogo-e-classificacao` |

### Notificações (M4)

| ID | Requisito | Origem | Status | Feature |
| --- | --- | --- | --- | --- |
| RF-028 | O sistema registra toda notificação com destinatário, item relacionado e data e hora de envio e de leitura | NOT-03 | Aprovado | — |
| RF-029 | O sistema envia a notificação por e-mail ao endereço cadastrado | NOT-01 | Aprovado | — |
| RF-030 | O usuário abre a caixa de entrada no site, com indicador de notificações novas | NOT-01 | Aprovado | — |
| RF-031 | O usuário marca uma notificação como lida e vai dela para o item relacionado | NOT-03 | Aprovado | — |
| RF-032 | O usuário ajusta como é alertado, sem desligar o registro da notificação | NOT-04 | Aprovado | — |
| RF-119 | O sistema notifica o usuário quando mudam a classificação, o papel de admin ou as permissões individuais dele | Spec `notificacoes/caixa-e-email` **(novo)** | Aprovado | — |

### Aprovações (M5)

| ID | Requisito | Origem | Status | Feature |
| --- | --- | --- | --- | --- |
| RF-033 | O admin cadastra e desativa motivos de decisão, por tipo de decisão | H04, H07 **(novo)** | Aprovado | — |
| RF-034 | O solicitante envia uma solicitação de um tipo registrado | APR-01 | Aprovado | — |
| RF-035 | O solicitante que poderia decidir o próprio pedido indica outro diretor como aprovador daquele pedido; a indicação fica no histórico e o admin é notificado | H19, H26 **(alterado: APR-02)** | Aprovado | — |
| RF-036 | O aprovador aprova a solicitação, com um motivo de decisão e texto opcional | APR-01, APR-05, H07 **(alterado)** | Aprovado | — |
| RF-037 | O aprovador contesta a solicitação para ajustes, com motivo, mensagem e, se houver custo, um teto sugerido | H12, H21 **(novo)** | Aprovado | — |
| RF-038 | O aprovador recusa a solicitação, com um motivo de decisão e texto opcional | APR-04, APR-05 | Aprovado | — |
| RF-039 | O solicitante corrige e reenvia uma solicitação contestada, criando nova versão | H12, APR-08 **(novo)** | Aprovado | — |
| RF-040 | O solicitante, o admin ou quem tem a permissão reabre uma solicitação recusada, com justificativa, criando nova versão | APR-06 | Aprovado | — |
| RF-041 | O solicitante edita uma solicitação aprovada, que volta à análise como nova versão | APR-07 | Aprovado | — |
| RF-042 | O solicitante, o admin ou quem tem a permissão cancela uma solicitação, com motivo | APR-10 | Aprovado | — |
| RF-043 | Quem pode ver a solicitação consulta todas as versões, decisões, motivos e mensagens | APR-08 | Aprovado | — |
| RF-044 | O aprovador consulta a fila das solicitações que pode decidir | APR-11 | Aprovado | — |
| RF-045 | O sistema notifica quem pode decidir quando uma solicitação é enviada ou reenviada, e notifica o solicitante de cada decisão, com um texto padrão e a mensagem do aprovador | NOT-06, H12 | Aprovado | — |
| RF-120 | O solicitante retira da análise a própria solicitação, para corrigir e reenviar | Spec `aprovacoes/motor-de-solicitacoes` **(novo)** | Aprovado | — |
| RF-121 | O sistema lembra quem pode decidir depois de 3 dias sem decisão, e avisa o admin depois de 7 | Spec `aprovacoes/motor-de-solicitacoes` **(novo)** | Aprovado | — |
| RF-122 | O diretor com cargo lista as solicitações, com filtro por tipo, por situação e pelas próprias | Spec `aprovacoes/motor-de-solicitacoes` **(novo)** | Aprovado | — |

### Financeiro — cobrança e recebimento (M6)

| ID | Requisito | Origem | Status | Feature |
| --- | --- | --- | --- | --- |
| RF-046 | O admin cria e desativa categorias de entrada e de saída | FIN-01 | Aprovado | — |
| RF-047 | O admin cadastra e desativa chaves Pix de destino | H01 **(novo)** | Aprovado | — |
| RF-048 | Quem tem a permissão cria uma cobrança avulsa para um diretor, com valor, vencimento, categoria, limite de inadimplência e chave Pix | FIN-02, H11 | Aprovado | — |
| RF-049 | Quem tem a permissão cria a mesma cobrança avulsa para vários diretores de uma vez | AD-016 **(novo)** | Aprovado | — |
| RF-050 | Quem tem a permissão cria, altera e desativa a recorrência de um diretor (por exemplo, a mensalidade, com o valor dele) | FIN-02, FIN-03 | Aprovado | — |
| RF-051 | O sistema gera automaticamente as cobranças das recorrências, uma por competência | FIN-02 | Aprovado | — |
| RF-052 | O sistema gera, para cada cobrança, o Pix copia e cola e o QR Code com o valor | H01 **(novo)** | Aprovado | — |
| RF-053 | O sistema notifica o devedor quando a cobrança é criada e no dia do vencimento | FIN-04 | Aprovado | — |
| RF-054 | O devedor registra o pagamento de uma cobrança, anexando o comprovante | FIN-05 | Aprovado | — |
| RF-055 | O devedor registra um pagamento feito em dinheiro, indicando o usuário que recebeu | H05 **(novo)** | Aprovado | — |
| RF-056 | O sistema notifica quem pode validar pagamentos quando um pagamento é registrado | FIN-05 | Aprovado | — |
| RF-057 | Quem tem a permissão valida o pagamento, com motivo de decisão; a cobrança fica paga e o devedor é notificado | FIN-05, H04 | Aprovado | — |
| RF-058 | Quem tem a permissão rejeita o pagamento, com motivo de decisão; o devedor é notificado para refazer | FIN-08 | Aprovado | — |
| RF-059 | O devedor baixa o recibo em PDF de uma cobrança paga | H03 **(novo)** | Aprovado | — |
| RF-060 | O sistema marca como atrasada a cobrança vencida sem pagamento validado e notifica o devedor e quem responde pelo financeiro | FIN-09 | Aprovado | — |
| RF-061 | O devedor questiona uma cobrança, com texto | FIN-10 | Aprovado | — |
| RF-062 | Quem tem a permissão decide o questionamento (isentar, cancelar ou manter), com motivo; o devedor é notificado | FIN-10, H18 | Aprovado | — |
| RF-063 | Quem tem a permissão de isentar isenta uma cobrança, com justificativa | FIN-11 | Aprovado | — |
| RF-064 | Quem tem a permissão suspende, por um período e com justificativa, a geração das cobranças recorrentes de um diretor, e encerra a suspensão | H17 **(novo)** | Aprovado | — |
| RF-065 | Quem tem a permissão cancela uma cobrança, com motivo | Seção 7 (estados) | Aprovado | — |
| RF-066 | O sistema convoca o devedor quando o limite de inadimplência da cobrança acaba, e notifica quem responde pelo financeiro | H11 **(novo)** | Aprovado | — |
| RF-067 | O devedor convocado registra a justificativa da dívida | H10 **(novo)** | Aprovado | — |
| RF-068 | Quem tem a permissão perdoa uma dívida atrasada, com motivo | H08 **(novo)** | Aprovado | — |
| RF-069 | Quem tem a permissão renegocia uma dívida atrasada em parcelas, com motivo | H09 **(novo)** | Aprovado | — |
| RF-070 | Quem tem a permissão mantém a dívida depois da convocação, com motivo | H10 **(novo)** | Aprovado | — |
| RF-071 | Quem tem a permissão registra uma entrada sem devedor (patrocínio, rifa, ajuda), com comprovante ou evidência em texto | FIN-06, FIN-07 | Aprovado | — |
| RF-072 | Quem tem a permissão valida ou rejeita uma entrada, com motivo | FIN-06 | Aprovado | — |
| RF-123 | O sistema lembra o devedor 3 dias antes do vencimento, se ele ainda não registrou o pagamento | Spec `financeiro/cobrancas-e-recebimentos` **(novo)** | Aprovado | — |
| RF-124 | O devedor consulta as próprias cobranças, mesmo sem cargo | Spec `financeiro/cobrancas-e-recebimentos` **(novo)** | Aprovado | — |
| RF-125 | O sistema avisa quem opera o financeiro quando um diretor com cobranças em aberto é desativado | Spec `financeiro/cobrancas-e-recebimentos` **(novo)** | Aprovado | — |

### Financeiro — gasto e prestação de contas (M7)

| ID | Requisito | Origem | Status | Feature |
| --- | --- | --- | --- | --- |
| RF-073 | O solicitante envia uma solicitação de gasto com descrição, categoria, setor, itens (descrição e valor) e, se houver, cotação anexa | FIN-13, H14 | Aprovado | — |
| RF-074 | O sistema abre a saída quando a solicitação de gasto é aprovada, e o valor passa a constar como comprometido | FIN-14 | Aprovado | — |
| RF-075 | Quem tem a permissão registra o envio do recurso, anexando o comprovante de envio | FIN-15 | Aprovado | — |
| RF-076 | O solicitante presta contas, informando o valor gasto e anexando o comprovante de gasto ou uma justificativa em texto | FIN-16 | Aprovado | — |
| RF-077 | Quem responde pelo financeiro consulta as prestações de contas pendentes | FIN-16 | Aprovado | — |
| RF-078 | O solicitante registra a devolução da diferença, ligada à saída, quando gastou menos do que recebeu | H13 **(novo)** | Aprovado | — |
| RF-079 | O solicitante envia uma solicitação de complemento, ligada à saída, quando gastou mais do que recebeu | H13 **(novo)** | Aprovado | — |
| RF-080 | Quem tem a permissão devolve uma prestação de contas ao solicitante para correção, com motivo | Canvas Saída **(novo)** | Aprovado | — |
| RF-081 | Quem tem a permissão liquida a saída depois de conferir a prestação de contas | FIN-17, H15 | Aprovado | — |
| RF-082 | Quem tem a permissão cancela uma saída antes do envio do recurso, com motivo | FIN-18 | Aprovado | — |
| RF-083 | Quem tem a permissão estorna um registro liquidado (saída, entrada ou cobrança paga), com justificativa, gerando um lançamento ligado ao original | FIN-18, APR-09 | Aprovado | — |
| RF-126 | O sistema lembra o solicitante da prestação de contas aos 5 dias do envio e, vencido o prazo de 7 dias, avisa também quem liquida | Spec `financeiro/gastos-e-prestacao-de-contas` **(novo)** | Aprovado | — |
| RF-127 | O aprovador de um gasto vê o total validado de entradas, o liquidado de saídas e o comprometido | Spec `financeiro/gastos-e-prestacao-de-contas` **(novo)** | Aprovado | — |
| RF-128 | Quem envia recursos registra, na mesma saída, o envio da diferença de um complemento aprovado | Spec `financeiro/gastos-e-prestacao-de-contas` **(novo)** | Aprovado | — |

### Eventos (M8)

| ID | Requisito | Origem | Status | Feature |
| --- | --- | --- | --- | --- |
| RF-084 | O admin cria e desativa categorias de evento | EVT-10 | Aprovado | — |
| RF-085 | O diretor com a permissão propõe um evento com título, descrição, data, categoria e a marca "envolve custo" | EVT-01 | Aprovado | — |
| RF-086 | Quem responde por eventos abre a solicitação orçamentária do evento, vinculada a ele | H16 **(alterado: EVT-02, EVT-03)** | Aprovado | — |
| RF-087 | O sistema publica o evento no calendário quando as aprovações exigidas estão concluídas, e notifica todos os diretores | EVT-04, H20, H25 | Aprovado | — |
| RF-088 | O diretor consulta o calendário, em que cada evento publicado é um card que abre o detalhe | EVT-04 | Aprovado | — |
| RF-089 | O proponente, ou quem tem a permissão, edita um evento; se estava publicado, ele sai do calendário até nova aprovação | EVT-05, H24 | Aprovado | — |
| RF-090 | O diretor consulta o histórico de eventos (publicados, recusados, cancelados e realizados), com as decisões e os motivos | EVT-06 | Aprovado | — |
| RF-091 | O sistema notifica, na data do evento, quem pode confirmar a realização | EVT-07 | Aprovado | — |
| RF-092 | O proponente, quem responde por eventos ou o admin confirma que o evento aconteceu; se foi antes da data, informa a data e o motivo | EVT-07, H22 | Aprovado | — |
| RF-093 | O proponente, o admin ou quem tem a permissão cancela um evento, com motivo; ele sai do calendário e todos os diretores são notificados | EVT-08, H25 | Aprovado | — |
| RF-129 | O diretor ativo com cargo confirma se vai ou não a um evento publicado, e o evento mostra as respostas | Spec `eventos/eventos-e-calendario` **(novo)** | Aprovado | — |
| RF-130 | O sistema cancela o evento que não foi publicado até a data dele, e avisa o proponente | Spec `eventos/eventos-e-calendario` **(novo)** | Aprovado | — |
| RF-131 | O sistema lembra quem pode confirmar a realização 1 e 3 dias depois da data, se ninguém confirmou nem cancelou | Spec `eventos/eventos-e-calendario` **(novo)** | Aprovado | — |

### Comunicação e perfil (M9)

| ID | Requisito | Origem | Status | Feature |
| --- | --- | --- | --- | --- |
| RF-094 | O usuário com a permissão publica um comunicado ou uma pauta no feed | COM-01 | Aprovado | — |
| RF-095 | O autor vincula documentos da aba de documentos a um comunicado | COM-02 | Aprovado | — |
| RF-096 | O usuário com a permissão fixa e desafixa um comunicado no topo do feed | AD-016 **(novo)** | Aprovado | — |
| RF-097 | O sistema notifica os diretores de um novo comunicado | COM-03 (hipótese) | Aprovado | — |
| RF-098 | O usuário com a permissão envia um documento; os diretores o consultam e baixam | DOC-01 | Aprovado | — |
| RF-099 | O usuário com a permissão registra uma ata de reunião como documento | AD-016 **(novo)** | Aprovado | — |
| RF-100 | O usuário consulta o próprio perfil: seus dados, histórico de pagamentos, eventos relacionados, notificações e preferências | PRF-01 | Aprovado | — |
| RF-101 | O admin consulta o perfil de qualquer usuário | PRF-02 | Aprovado | — |

### Relatórios (M10)

| ID | Requisito | Origem | Status | Feature |
| --- | --- | --- | --- | --- |
| RF-102 | O diretor com cargo vê o dashboard financeiro: totais do período, saldo, pendências de aprovação e de validação, inadimplência, próximos eventos e últimos comunicados | DSH-01, DSH-02 | Aprovado | — |
| RF-103 | O diretor sem cargo vê o dashboard básico | DSH-03 | Aprovado | — |
| RF-104 | O diretor lista as transações com filtros por período, categoria, tipo e estado, e abre o detalhe de cada uma | DSH-06 | Aprovado | — |
| RF-105 | O usuário gera o extrato do mês ou de um período, em PDF e em CSV | REL-01, REL-02 | Aprovado | — |
| RF-106 | O usuário gera o balancete, em PDF e em CSV | REL-02 | Aprovado | — |
| RF-107 | O usuário gera o relatório de inadimplência, em PDF e em CSV | REL-02 | Aprovado | — |
| RF-108 | O usuário gera o relatório de eventos, em PDF e em CSV | REL-02 | Aprovado | — |
| RF-109 | O usuário gera o relatório de prestação de contas, em PDF e em CSV | REL-02 | Aprovado | — |
| RF-110 | O usuário gera o fluxo de caixa com o previsto, o realizado e a inadimplência, em PDF e em CSV | AD-016 **(novo)** | Aprovado | — |
| RF-111 | O sistema gera em segundo plano os relatórios pesados e avisa o usuário quando ficam prontos | REL-03 | Aprovado | — |

### Marca (M11)

| ID | Requisito | Origem | Status | Feature |
| --- | --- | --- | --- | --- |
| RF-112 | Quem tem a permissão cadastra o escudo e as cores base do clube | BRD-01 | Aprovado | — |
| RF-113 | O sistema aplica a marca em toda a interface e oferece opções de tema derivadas das cores base | BRD-02 | Aprovado | — |
| RF-114 | Quem tem a permissão substitui os ícones e símbolos padrão | BRD-03 | Aprovado | — |
| RF-115 | A API entrega a configuração de marca ao site, e os PDFs levam o escudo e as cores | BRD-04, REL-04 | Aprovado | — |

## Regras de negócio

| ID | Regra | Contexto | Origem |
| --- | --- | --- | --- |
| RN-001 | O acesso é só por convite | Identidade e Permissões | Seção 5 |
| RN-002 | O mesmo e-mail nunca resulta em dois usuários | Identidade e Permissões | ACE-02 |
| RN-003 | O sistema não coleta CPF | Identidade e Permissões | ACE-09 |
| RN-004 | Um usuário é desativado, nunca apagado | Identidade e Permissões | ACE-10 |
| RN-005 | Só o admin gerencia usuários, cargos, setores, categorias, motivos de decisão e concessões | Identidade e Permissões | PER-04 |
| RN-006 | Presidente é um cargo como os outros, sem poder especial | Identidade e Permissões | Seção 4 |
| RN-007 | Acesso total não inclui a permissão de auto-aprovação | Identidade e Permissões | PER-06 |
| RN-008 | O perfil de um usuário só é visto por ele e pelo admin | Identidade e Permissões | PRF-02 |
| RN-009 | Toda notificação é registrada e o usuário não desliga o registro; cada usuário só vê as suas | Notificações | Seção 9, NOT-05 |
| RN-010 | Cada solicitação tem um só aprovador por versão; o que precisa de duas decisões são duas solicitações ligadas | Aprovações | H16 **(alterado: APR-03, APR-04)** |
| RN-011 | Toda decisão (de solicitação, de pagamento, de questionamento, de dívida, de entrada) tem um motivo de decisão da lista, com texto opcional | Todos | H04, H07 **(alterado: APR-05)** |
| RN-012 | Ninguém decide em causa própria: o solicitante não decide o próprio pedido, o devedor não valida o próprio pagamento, o solicitante não liquida a própria saída. A exceção é a permissão de auto-aprovação, que fica marcada no histórico | Aprovações, Financeiro | APR-02; canvases |
| RN-013 | Todo estado final é imutável; corrigir é criar um registro novo, justificado e ligado ao original | Todos | APR-09 |
| RN-014 | Nada é apagado: o que é desativado, cancelado ou estornado continua no histórico | Todos | AUD-04 |
| RN-015 | Só conta como realizado o valor que foi validado | Financeiro, Relatórios | DSH-02 |
| RN-016 | Cobrança isenta, perdoada, cancelada ou renegociada não gera aviso nem conta como inadimplência | Financeiro | FIN-11, H08 |
| RN-017 | Diretor desativado não recebe cobrança nova | Financeiro | FIN-12 |
| RN-018 | Categoria já usada é desativada, e não apagada | Financeiro, Eventos | FIN-01 |
| RN-019 | Uma saída só existe a partir de uma solicitação de gasto aprovada, e o valor enviado não passa do aprovado | Financeiro | FIN-13, FIN-14 |
| RN-020 | Um evento que envolve custo só é publicado com a solicitação do evento e a solicitação orçamentária aprovadas | Eventos | H20 **(alterado: EVT-02)** |
| RN-021 | O calendário mostra só eventos publicados; o histórico mostra todos | Eventos | EVT-04, EVT-06 |
| RN-022 | Um relatório só mostra o que o usuário que o gerou pode ver | Relatórios | REL-03 |
| RN-023 | Os valores são escriturais: o sistema registra, e o dinheiro se move por fora | Financeiro | Seção 1 |
| RN-024 | Ninguém desativa a si mesmo nem tira o próprio papel de admin; sempre existe ao menos um admin ativo | Identidade e Permissões | Spec `acesso/identidade-e-acesso` **(novo)** |
| RN-025 | As respostas de login, de recuperação de senha e de convite inválido não revelam se uma conta, um e-mail ou um convite existe | Identidade e Permissões | Spec `acesso/identidade-e-acesso` **(novo)** |

## Requisitos não funcionais

| ID | Requisito | Categoria | Origem | Como verificar |
| --- | --- | --- | --- | --- |
| RNF-01 | Uma única API, versionada e documentada, serve o site e depois o app; regras de negócio, permissões e auditoria ficam só nela | Arquitetura | RNF-01 | Contrato gerado pela aplicação e teste de contrato; nenhum teste de regra no site |
| RNF-02 | O conjunto roda numa única instância AWS de custo mínimo, sem impedir separar banco ou workers depois | Operação | RNF-02 | Medição de memória no M1 e no M12; serviços separados por contêiner |
| RNF-03 | Tudo roda em contêineres, com as mesmas imagens em desenvolvimento e em produção | Entrega | RNF-03 | Um comando sobe o ambiente local; o deploy usa a imagem do CI |
| RNF-04 | O CI/CD roda no GitHub Actions dentro do plano gratuito | Entrega | RNF-04 | Pipeline verde; consumo de minutos conferido |
| RNF-05 | Há só os ambientes local e produção; migrações reversíveis, imagens versionadas e backup do banco antes de mudança com dados | Operação | RNF-05 | Teste de reversão de migração; rollback e restauração ensaiados no M12 |
| RNF-06 | Armazenamento de anexos e envio de e-mail têm custo mínimo e podem trocar de provedor por configuração | Arquitetura | RNF-06 | Testes com os fakes; troca por variável de ambiente |
| RNF-07 | Senhas com hash forte, tokens seguros, anexos acessíveis só por permissão, e tratamento de dados pessoais conforme a LGPD | Segurança | RNF-07 | Threat model no M2; revisão de segurança por marco; teste de acesso negado a anexo |
| RNF-08 | Código testado, tipado e com análise estática no CI; cobertura mínima de 80% | Qualidade | RNF-08 | Comando de verificação completa no CI |
| RNF-09 | Monólito modular: um módulo por contexto, dependências acíclicas, fronteiras verificadas por ferramenta | Arquitetura | ADR-001, ADR-003 | Teste de fronteira no CI |
| RNF-10 | As tarefas agendadas são idempotentes | Confiabilidade | NOT-07, ADR-001 | Teste que executa cada tarefa duas vezes |
| RNF-11 | Dinheiro em tipo decimal com duas casas; nunca ponto flutuante | Qualidade | ADR-001 | Value object `Dinheiro`; verificação estática |
| RNF-12 | Tipos de usuário e permissões são extensíveis, e nada impede um deploy por cliente ou um SaaS no futuro | Arquitetura | Seção 3, BRD-05 | Revisão de arquitetura por marco; nenhuma identidade de clube fixa no código |
| RNF-13 | Logs estruturados, com ID de correlação, sem dados pessoais, tokens ou segredos | Segurança | AGENTS.md | Revisão de segurança por marco |
| RNF-14 | Os fluxos críticos (aprovação, validação, permissões, recorrência) têm teste de ponta a ponta | Qualidade | RNF-05 | Suíte de ponta a ponta no CI |

## Casos de borda fechados

Os 22 casos fechados na descoberta estão em `docs/domain/discovery/hotspots.md` (H01 a H24) e nos canvases dos
aggregates. Os fechados neste rito:

### CB-01 — Quais itens do protótipo, fora do enunciado, entram na etapa 1?

**Decisão:** todos: cobranças em lote, fluxo de caixa previsto e realizado, atas de reunião e postagem fixada, além de
Pix copia e cola, QR Code e recibo, confirmados na descoberta.
**Data / quem decidiu:** 2026-11-11 / Leandro Nascimento
**Afeta:** RF-047, RF-049, RF-052, RF-059, RF-096, RF-099, RF-110; AD-016

### CB-02 — O que o sistema faz quando o solicitante indica o próprio aprovador?

**Decisão:** a indicação fica explícita no histórico da solicitação e o admin recebe uma notificação. O admin não
precisa confirmar.
**Data / quem decidiu:** 2026-11-11 / Leandro Nascimento
**Afeta:** RF-035, aggregate Solicitação (INV-SOL-10, INV-SOL-11); hotspot H26

### CB-03 — O admin define quais setores aprovam cada tipo de solicitação (APR-03)?

**Decisão:** não há regra de vários setores. Quem aprova um tipo de solicitação é quem tem a permissão de aprovar
aquele tipo, e essa permissão é concedida como qualquer outra (por cargo, setor ou usuário). Se a aprovação de eventos
varia por categoria de evento é pergunta do refinamento do M8.
**Data / quem decidiu:** 2026-11-11 / Leandro Nascimento (na descoberta, história 8)
**Afeta:** RN-010; APR-03 e APR-04 do enunciado deixam de valer como escritos

### CB-04 — O que do enunciado foi removido ou substituído?

**Decisão:** aprovação de uma solicitação por vários setores (APR-03, APR-04, EVT-02) foi substituída por
solicitações ligadas; "liquidado" como estado único (APR-09) virou três termos (paga, liquidada, realizado), com a
mesma regra de imutabilidade; "questionada" deixou de ser estado da cobrança.
**Data / quem decidiu:** 2026-11-11 / Leandro Nascimento
**Afeta:** RN-010, RN-013, RN-020; glossário

## Riscos técnicos

| # | Risco | Status | Referência |
| --- | --- | --- | --- |
| 1 | API, banco, fila e worker não cabem com folga na instância única | Pendente de análise | AD-013; medir no M1 |
| 2 | As regras do free tier da AWS para a conta do dono são diferentes do que o enunciado supõe | Pendente de análise | AD-013 |
| 3 | O Pix copia e cola gerado sem integração bancária não é aceito por algum aplicativo de banco | Pendente de análise | RF-052; testar com aplicativos reais no M6 |
| 4 | Um tratador de evento em processo com erro desfaz a operação de quem publicou | Mitigado (tratadores curtos e testados) | ADR-003 |
| 5 | A tarefa de geração de cobranças roda duas vezes e duplica cobranças | Mitigado (unicidade por recorrência, devedor e competência) | INV-COB-11, RNF-10 |
| 6 | Geração de PDF pesa na instância pequena | Pendente de análise | RF-111; escolher a biblioteca no M10 |
| 7 | E-mails caem em spam ou o provedor gratuito limita o envio | Pendente de análise | AD-012 |
| 8 | "Nada é apagado" entra em conflito com direitos do titular na LGPD | Pendente de análise | AD-015; avaliar no M2 |
| 9 | O escopo do M6 cresceu com inadimplência, renegociação, suspensão e Pix | Mitigado (dividir o marco em features menores) | `epics.md` |
| 10 | Em desenvolvimento, os links dos e-mails saem no log quebrados pela codificação, o que atrapalha o teste manual | Mitigado (documentado; avaliar um servidor de e-mail de desenvolvimento no M4) | `docs/setup/local.md` |
