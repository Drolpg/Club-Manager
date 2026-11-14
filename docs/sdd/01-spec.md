# Especificação

Requisitos, contrato da API, dados e critérios de aceite da etapa 1 (diretores, no site). Este é o único registro de
IDs de requisito: tarefas, plano e PRs citam estes IDs e não criam outros.

- `RF-NNN`: requisito funcional, no tamanho de uma ação.
- `RN-NNN`: regra de negócio que vale para mais de um requisito.
- `RNF-NN`: requisito não funcional.
- `INV-XXX-NN`: invariante de um aggregate, definida no desenho do próprio aggregate.

A coluna "Origem" cita o ID do enunciado (por exemplo, FIN-05), o ponto de refinamento (H01 a H30) ou a decisão
(AD-NNN). Origem com **(novo)** não estava no enunciado; com **(alterado)**, muda o que o enunciado dizia.
Status do requisito: `Proposto`, `Aprovado`, `Em implementação`, `Implementado`, `Removido (<motivo>)`.

## 1. Requisitos

### Atores

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

### Requisitos funcionais

Status: `Proposto`, `Aprovado`, `Em implementação`, `Implementado`, `Removido (<motivo>)`.

##### Identidade e Permissões — acesso (M2)

| ID | Requisito | Origem | Status |
| --- | --- | --- | --- |
| RF-001 | O admin, ou quem tem a permissão de convidar, gera um convite de uso único, válido por 24 horas, sem cargo nem setor | ACE-05 | Implementado |
| RF-002 | Quem tem a permissão regenera ou revoga um convite | ACE-05 | Implementado |
| RF-003 | O sistema expira o convite depois de 24 horas | ACE-05, NOT-07 | Implementado |
| RF-004 | O convidado se cadastra pelo convite informando nome, nome de usuário único, telefone, e-mail e senha | ACE-06, ACE-09 | Implementado |
| RF-005 | O sistema envia um link de verificação e só libera o acesso depois de o e-mail ser verificado | ACE-04 | Implementado |
| RF-006 | O usuário entra com nome de usuário e senha | ACE-02 | Implementado |
| RF-007 | O usuário entra com o Google, na mesma conta do seu e-mail | ACE-01, ACE-02 | Implementado |
| RF-008 | O convidado aceita o convite pelo Google e completa o cadastro com nome de usuário e senha, sem link de verificação | ACE-03 | Implementado |
| RF-009 | O sistema recusa o login pelo Google de quem não foi convidado | ACE-12 | Implementado |
| RF-010 | O usuário recupera a senha pelo e-mail verificado | ACE-11 | Implementado |
| RF-011 | O usuário encerra a própria sessão | ACE-13 (derivado) | Implementado |
| RF-012 | O admin desativa e reativa um usuário; o desativado não entra | ACE-10 | Implementado |
| RF-013 | O sistema avisa o admin quando um diretor conclui o cadastro | ACE-07 | Implementado |
| RF-014 | O primeiro admin é criado por um procedimento seguro, sem senha padrão | Seção 16, AD-019 | Implementado |
| RF-116 | O admin dá e tira o papel de admin de outro usuário | Feature `acesso/identidade-e-acesso` **(novo)** | Implementado |
| RF-117 | O admin consulta os convites e os usuários, com a situação de cada um | Feature `acesso/identidade-e-acesso` **(novo)** | Implementado |

##### Identidade e Permissões — permissões; Auditoria (M3)

| ID | Requisito | Origem | Status |
| --- | --- | --- | --- |
| RF-015 | O admin cria, renomeia e desativa cargos | PER-04 | Implementado |
| RF-016 | O admin cria, renomeia e desativa setores | PER-04, seção 4 | Implementado |
| RF-017 | O admin classifica um diretor, atribuindo um cargo e um ou mais setores | ACE-07, seção 4 | Implementado |
| RF-018 | O admin concede e revoga uma permissão a um cargo | PER-03 | Implementado |
| RF-019 | O admin concede e revoga uma permissão a um setor | PER-03 | Implementado |
| RF-020 | O admin concede e revoga uma permissão a um usuário, inclusive de um setor a que ele não pertence | PER-03 | Implementado |
| RF-021 | O sistema calcula as permissões de um usuário como a união das concessões do cargo, dos setores e das individuais | PER-03 | Implementado |
| RF-022 | O admin vê, para cada usuário, as permissões que ele tem e de onde vem cada uma | PER-05 | Implementado |
| RF-023 | O admin concede e revoga acesso total a um usuário | PER-06 | Implementado |
| RF-024 | O diretor sem cargo acessa só o dashboard básico | ACE-08, PER-01 | Implementado |
| RF-025 | O diretor com cargo lê os dados de gestão (financeiro, eventos, feed, documentos) | PER-01 | Implementado |
| RF-026 | O sistema registra, de forma imutável, quem fez o quê, quando, sobre qual item e com que justificativa, em toda ação relevante | AUD-01, AUD-02 | Implementado |
| RF-027 | Quem pode ver um item consulta o histórico dele no próprio detalhe | AUD-03 | Implementado |
| RF-118 | O diretor consulta o próprio cargo, os próprios setores e as próprias permissões | Feature `permissoes/catalogo-e-classificacao` **(novo)** | Implementado |

##### Notificações (M4)

| ID | Requisito | Origem | Status |
| --- | --- | --- | --- |
| RF-028 | O sistema registra toda notificação com destinatário, item relacionado e data e hora de envio e de leitura | NOT-03 | Implementado |
| RF-029 | O sistema envia a notificação por e-mail ao endereço cadastrado | NOT-01 | Implementado |
| RF-030 | O usuário abre a caixa de entrada no site, com indicador de notificações novas | NOT-01 | Implementado |
| RF-031 | O usuário marca uma notificação como lida e vai dela para o item relacionado | NOT-03 | Implementado |
| RF-032 | O usuário ajusta como é alertado, sem desligar o registro da notificação | NOT-04 | Implementado |
| RF-119 | O sistema notifica o usuário quando mudam a classificação, o papel de admin ou as permissões individuais dele | Feature `notificacoes/caixa-e-email` **(novo)** | Implementado |

##### Aprovações (M5)

| ID | Requisito | Origem | Status |
| --- | --- | --- | --- |
| RF-033 | O admin cadastra e desativa motivos de decisão, por tipo de decisão | H04, H07 **(novo)** | Implementado |
| RF-034 | O solicitante envia uma solicitação de um tipo registrado | APR-01 | Implementado |
| RF-035 | O solicitante que poderia decidir o próprio pedido indica outro diretor como aprovador daquele pedido; a indicação fica no histórico e o admin é notificado | H19, H26 **(alterado: APR-02)** | Implementado |
| RF-036 | O aprovador aprova a solicitação, com um motivo de decisão e texto opcional | APR-01, APR-05, H07 **(alterado)** | Implementado |
| RF-037 | O aprovador contesta a solicitação para ajustes, com motivo, mensagem e, se houver custo, um teto sugerido | H12, H21 **(novo)** | Implementado |
| RF-038 | O aprovador recusa a solicitação, com um motivo de decisão e texto opcional | APR-04, APR-05 | Implementado |
| RF-039 | O solicitante corrige e reenvia uma solicitação contestada, criando nova versão | H12, APR-08 **(novo)** | Implementado |
| RF-040 | O solicitante, o admin ou quem tem a permissão reabre uma solicitação recusada, com justificativa, criando nova versão | APR-06 | Implementado |
| RF-041 | O solicitante edita uma solicitação aprovada, que volta à análise como nova versão | APR-07 | Implementado |
| RF-042 | O solicitante, o admin ou quem tem a permissão cancela uma solicitação, com motivo | APR-10 | Implementado |
| RF-043 | Quem pode ver a solicitação consulta todas as versões, decisões, motivos e mensagens | APR-08 | Implementado |
| RF-044 | O aprovador consulta a fila das solicitações que pode decidir | APR-11 | Implementado |
| RF-045 | O sistema notifica quem pode decidir quando uma solicitação é enviada ou reenviada, e notifica o solicitante de cada decisão, com um texto padrão e a mensagem do aprovador | NOT-06, H12 | Implementado |
| RF-120 | O solicitante retira da análise a própria solicitação, para corrigir e reenviar | Feature `aprovacoes/motor-de-solicitacoes` **(novo)** | Implementado |
| RF-121 | O sistema lembra quem pode decidir depois de 3 dias sem decisão, e avisa o admin depois de 7 | Feature `aprovacoes/motor-de-solicitacoes` **(novo)** | Implementado |
| RF-122 | O diretor com cargo lista as solicitações, com filtro por tipo, por situação e pelas próprias | Feature `aprovacoes/motor-de-solicitacoes` **(novo)** | Implementado |

##### Financeiro — cobrança e recebimento (M6)

| ID | Requisito | Origem | Status |
| --- | --- | --- | --- |
| RF-046 | O admin cria e desativa categorias de entrada e de saída | FIN-01 | Aprovado |
| RF-047 | O admin cadastra e desativa chaves Pix de destino | H01 **(novo)** | Aprovado |
| RF-048 | Quem tem a permissão cria uma cobrança avulsa para um diretor, com valor, vencimento, categoria, limite de inadimplência e chave Pix | FIN-02, H11 | Aprovado |
| RF-049 | Quem tem a permissão cria a mesma cobrança avulsa para vários diretores de uma vez | AD-016 **(novo)** | Aprovado |
| RF-050 | Quem tem a permissão cria, altera e desativa a recorrência de um diretor (por exemplo, a mensalidade, com o valor dele) | FIN-02, FIN-03 | Aprovado |
| RF-051 | O sistema gera automaticamente as cobranças das recorrências, uma por competência | FIN-02 | Aprovado |
| RF-052 | O sistema gera, para cada cobrança, o Pix copia e cola e o QR Code com o valor | H01 **(novo)** | Aprovado |
| RF-053 | O sistema notifica o devedor quando a cobrança é criada e no dia do vencimento | FIN-04 | Aprovado |
| RF-054 | O devedor registra o pagamento de uma cobrança, anexando o comprovante | FIN-05 | Aprovado |
| RF-055 | O devedor registra um pagamento feito em dinheiro, indicando o usuário que recebeu | H05 **(novo)** | Aprovado |
| RF-056 | O sistema notifica quem pode validar pagamentos quando um pagamento é registrado | FIN-05 | Aprovado |
| RF-057 | Quem tem a permissão valida o pagamento, com motivo de decisão; a cobrança fica paga e o devedor é notificado | FIN-05, H04 | Aprovado |
| RF-058 | Quem tem a permissão rejeita o pagamento, com motivo de decisão; o devedor é notificado para refazer | FIN-08 | Aprovado |
| RF-059 | O devedor baixa o recibo em PDF de uma cobrança paga | H03 **(novo)** | Aprovado |
| RF-060 | O sistema marca como atrasada a cobrança vencida sem pagamento validado e notifica o devedor e quem responde pelo financeiro | FIN-09 | Aprovado |
| RF-061 | O devedor questiona uma cobrança, com texto | FIN-10 | Aprovado |
| RF-062 | Quem tem a permissão decide o questionamento (isentar, cancelar ou manter), com motivo; o devedor é notificado | FIN-10, H18 | Aprovado |
| RF-063 | Quem tem a permissão de isentar isenta uma cobrança, com justificativa | FIN-11 | Aprovado |
| RF-064 | Quem tem a permissão suspende, por um período e com justificativa, a geração das cobranças recorrentes de um diretor, e encerra a suspensão | H17 **(novo)** | Aprovado |
| RF-065 | Quem tem a permissão cancela uma cobrança, com motivo | Seção 7 (estados) | Aprovado |
| RF-066 | O sistema convoca o devedor quando o limite de inadimplência da cobrança acaba, e notifica quem responde pelo financeiro | H11 **(novo)** | Aprovado |
| RF-067 | O devedor convocado registra a justificativa da dívida | H10 **(novo)** | Aprovado |
| RF-068 | Quem tem a permissão perdoa uma dívida atrasada, com motivo | H08 **(novo)** | Aprovado |
| RF-069 | Quem tem a permissão renegocia uma dívida atrasada em parcelas, com motivo | H09 **(novo)** | Aprovado |
| RF-070 | Quem tem a permissão mantém a dívida depois da convocação, com motivo | H10 **(novo)** | Aprovado |
| RF-071 | Quem tem a permissão registra uma entrada sem devedor (patrocínio, rifa, ajuda), com comprovante ou evidência em texto | FIN-06, FIN-07 | Aprovado |
| RF-072 | Quem tem a permissão valida ou rejeita uma entrada, com motivo | FIN-06 | Aprovado |
| RF-123 | O sistema lembra o devedor 3 dias antes do vencimento, se ele ainda não registrou o pagamento | Feature `financeiro/cobrancas-e-recebimentos` **(novo)** | Aprovado |
| RF-124 | O devedor consulta as próprias cobranças, mesmo sem cargo | Feature `financeiro/cobrancas-e-recebimentos` **(novo)** | Aprovado |
| RF-125 | O sistema avisa quem opera o financeiro quando um diretor com cobranças em aberto é desativado | Feature `financeiro/cobrancas-e-recebimentos` **(novo)** | Aprovado |

##### Financeiro — gasto e prestação de contas (M7)

| ID | Requisito | Origem | Status |
| --- | --- | --- | --- |
| RF-073 | O solicitante envia uma solicitação de gasto com descrição, categoria, setor, itens (descrição e valor) e, se houver, cotação anexa | FIN-13, H14 | Aprovado |
| RF-074 | O sistema abre a saída quando a solicitação de gasto é aprovada, e o valor passa a constar como comprometido | FIN-14 | Aprovado |
| RF-075 | Quem tem a permissão registra o envio do recurso, anexando o comprovante de envio | FIN-15 | Aprovado |
| RF-076 | O solicitante presta contas, informando o valor gasto e anexando o comprovante de gasto ou uma justificativa em texto | FIN-16 | Aprovado |
| RF-077 | Quem responde pelo financeiro consulta as prestações de contas pendentes | FIN-16 | Aprovado |
| RF-078 | O solicitante registra a devolução da diferença, ligada à saída, quando gastou menos do que recebeu | H13 **(novo)** | Aprovado |
| RF-079 | O solicitante envia uma solicitação de complemento, ligada à saída, quando gastou mais do que recebeu | H13 **(novo)** | Aprovado |
| RF-080 | Quem tem a permissão devolve uma prestação de contas ao solicitante para correção, com motivo | Canvas Saída **(novo)** | Aprovado |
| RF-081 | Quem tem a permissão liquida a saída depois de conferir a prestação de contas | FIN-17, H15 | Aprovado |
| RF-082 | Quem tem a permissão cancela uma saída antes do envio do recurso, com motivo | FIN-18 | Aprovado |
| RF-083 | Quem tem a permissão estorna um registro liquidado (saída, entrada ou cobrança paga), com justificativa, gerando um lançamento ligado ao original | FIN-18, APR-09 | Aprovado |
| RF-126 | O sistema lembra o solicitante da prestação de contas aos 5 dias do envio e, vencido o prazo de 7 dias, avisa também quem liquida | Feature `financeiro/gastos-e-prestacao-de-contas` **(novo)** | Aprovado |
| RF-127 | O aprovador de um gasto vê o total validado de entradas, o liquidado de saídas e o comprometido | Feature `financeiro/gastos-e-prestacao-de-contas` **(novo)** | Aprovado |
| RF-128 | Quem envia recursos registra, na mesma saída, o envio da diferença de um complemento aprovado | Feature `financeiro/gastos-e-prestacao-de-contas` **(novo)** | Aprovado |

##### Eventos (M8)

| ID | Requisito | Origem | Status |
| --- | --- | --- | --- |
| RF-084 | O admin cria e desativa categorias de evento | EVT-10 | Aprovado |
| RF-085 | O diretor com a permissão propõe um evento com título, descrição, data, categoria e a marca "envolve custo" | EVT-01 | Aprovado |
| RF-086 | Quem responde por eventos abre a solicitação orçamentária do evento, vinculada a ele | H16 **(alterado: EVT-02, EVT-03)** | Aprovado |
| RF-087 | O sistema publica o evento no calendário quando as aprovações exigidas estão concluídas, e notifica todos os diretores | EVT-04, H20, H25 | Aprovado |
| RF-088 | O diretor consulta o calendário, em que cada evento publicado é um card que abre o detalhe | EVT-04 | Aprovado |
| RF-089 | O proponente, ou quem tem a permissão, edita um evento; se estava publicado, ele sai do calendário até nova aprovação | EVT-05, H24 | Aprovado |
| RF-090 | O diretor consulta o histórico de eventos (publicados, recusados, cancelados e realizados), com as decisões e os motivos | EVT-06 | Aprovado |
| RF-091 | O sistema notifica, na data do evento, quem pode confirmar a realização | EVT-07 | Aprovado |
| RF-092 | O proponente, quem responde por eventos ou o admin confirma que o evento aconteceu; se foi antes da data, informa a data e o motivo | EVT-07, H22 | Aprovado |
| RF-093 | O proponente, o admin ou quem tem a permissão cancela um evento, com motivo; ele sai do calendário e todos os diretores são notificados | EVT-08, H25 | Aprovado |
| RF-129 | O diretor ativo com cargo confirma se vai ou não a um evento publicado, e o evento mostra as respostas | Feature `eventos/eventos-e-calendario` **(novo)** | Aprovado |
| RF-130 | O sistema cancela o evento que não foi publicado até a data dele, e avisa o proponente | Feature `eventos/eventos-e-calendario` **(novo)** | Aprovado |
| RF-131 | O sistema lembra quem pode confirmar a realização 1 e 3 dias depois da data, se ninguém confirmou nem cancelou | Feature `eventos/eventos-e-calendario` **(novo)** | Aprovado |

##### Comunicação e perfil (M9)

| ID | Requisito | Origem | Status |
| --- | --- | --- | --- |
| RF-094 | O usuário com a permissão publica um comunicado ou uma pauta no feed | COM-01 | Aprovado |
| RF-095 | O autor vincula documentos da aba de documentos a um comunicado | COM-02 | Aprovado |
| RF-096 | O usuário com a permissão fixa e desafixa um comunicado no topo do feed | AD-016 **(novo)** | Aprovado |
| RF-097 | O sistema notifica os diretores de um novo comunicado | COM-03 (hipótese) | Aprovado |
| RF-098 | O usuário com a permissão envia um documento; os diretores o consultam e baixam | DOC-01 | Aprovado |
| RF-099 | O usuário com a permissão registra uma ata de reunião como documento | AD-016 **(novo)** | Aprovado |
| RF-100 | O usuário consulta o próprio perfil: seus dados, histórico de pagamentos, eventos relacionados, notificações e preferências | PRF-01 | Aprovado |
| RF-101 | O admin consulta o perfil de qualquer usuário | PRF-02 | Aprovado |

##### Relatórios (M10)

| ID | Requisito | Origem | Status |
| --- | --- | --- | --- |
| RF-102 | O diretor com cargo vê o dashboard financeiro: totais do período, saldo, pendências de aprovação e de validação, inadimplência, próximos eventos e últimos comunicados | DSH-01, DSH-02 | Aprovado |
| RF-103 | O diretor sem cargo vê o dashboard básico | DSH-03 | Aprovado |
| RF-104 | O diretor lista as transações com filtros por período, categoria, tipo e estado, e abre o detalhe de cada uma | DSH-06 | Aprovado |
| RF-105 | O usuário gera o extrato do mês ou de um período, em PDF e em CSV | REL-01, REL-02 | Aprovado |
| RF-106 | O usuário gera o balancete, em PDF e em CSV | REL-02 | Aprovado |
| RF-107 | O usuário gera o relatório de inadimplência, em PDF e em CSV | REL-02 | Aprovado |
| RF-108 | O usuário gera o relatório de eventos, em PDF e em CSV | REL-02 | Aprovado |
| RF-109 | O usuário gera o relatório de prestação de contas, em PDF e em CSV | REL-02 | Aprovado |
| RF-110 | O usuário gera o fluxo de caixa com o previsto, o realizado e a inadimplência, em PDF e em CSV | AD-016 **(novo)** | Aprovado |
| RF-111 | O sistema gera em segundo plano os relatórios pesados e avisa o usuário quando ficam prontos | REL-03 | Aprovado |

##### Marca (M11)

| ID | Requisito | Origem | Status |
| --- | --- | --- | --- |
| RF-112 | Quem tem a permissão cadastra o escudo e as cores base do clube | BRD-01 | Aprovado |
| RF-113 | O sistema aplica a marca em toda a interface e oferece opções de tema derivadas das cores base | BRD-02 | Aprovado |
| RF-114 | Quem tem a permissão substitui os ícones e símbolos padrão | BRD-03 | Aprovado |
| RF-115 | A API entrega a configuração de marca ao site, e os PDFs levam o escudo e as cores | BRD-04, REL-04 | Aprovado |

### Regras de negócio

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
| RN-024 | Ninguém desativa a si mesmo nem tira o próprio papel de admin; sempre existe ao menos um admin ativo | Identidade e Permissões | Feature `acesso/identidade-e-acesso` **(novo)** |
| RN-025 | As respostas de login, de recuperação de senha e de convite inválido não revelam se uma conta, um e-mail ou um convite existe | Identidade e Permissões | Feature `acesso/identidade-e-acesso` **(novo)** |

### Requisitos não funcionais

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

### Casos de borda fechados

Os casos fechados na descoberta do domínio têm IDs H01 a H30; os fechados no refinamento dos
requisitos são os abaixo:

#### CB-01 — Quais itens do protótipo, fora do enunciado, entram na etapa 1?

**Decisão:** todos: cobranças em lote, fluxo de caixa previsto e realizado, atas de reunião e postagem fixada, além de
Pix copia e cola, QR Code e recibo, confirmados na descoberta.
**Data / quem decidiu:** 2026-11-11 / o dono do projeto
**Afeta:** RF-047, RF-049, RF-052, RF-059, RF-096, RF-099, RF-110; AD-016

#### CB-02 — O que o sistema faz quando o solicitante indica o próprio aprovador?

**Decisão:** a indicação fica explícita no histórico da solicitação e o admin recebe uma notificação. O admin não
precisa confirmar.
**Data / quem decidiu:** 2026-11-11 / o dono do projeto
**Afeta:** RF-035, aggregate Solicitação (INV-SOL-10, INV-SOL-11); hotspot H26

#### CB-03 — O admin define quais setores aprovam cada tipo de solicitação (APR-03)?

**Decisão:** não há regra de vários setores. Quem aprova um tipo de solicitação é quem tem a permissão de aprovar
aquele tipo, e essa permissão é concedida como qualquer outra (por cargo, setor ou usuário). Se a aprovação de eventos
varia por categoria de evento é pergunta do refinamento do M8.
**Data / quem decidiu:** 2026-11-11 / o dono do projeto (na descoberta, história 8)
**Afeta:** RN-010; APR-03 e APR-04 do enunciado deixam de valer como escritos

#### CB-04 — O que do enunciado foi removido ou substituído?

**Decisão:** aprovação de uma solicitação por vários setores (APR-03, APR-04, EVT-02) foi substituída por
solicitações ligadas; "liquidado" como estado único (APR-09) virou três termos (paga, liquidada, realizado), com a
mesma regra de imutabilidade; "questionada" deixou de ser estado da cobrança.
**Data / quem decidiu:** 2026-11-11 / o dono do projeto
**Afeta:** RN-010, RN-013, RN-020; glossário



## 2. Contrato da API

O contrato completo, rota a rota, é o gerado pela aplicação: com o sistema no ar e um admin logado, abra
`/api/v1/docs/` (navegável) ou `/api/v1/schema/` (OpenAPI). Todas as rotas ficam sob `/api/v1/`, falam JSON e usam
nomes de recursos e campos em português.

### Autenticação

Sessão no servidor, em cookie (ADR-008). Não há token no corpo das respostas.

1. `GET /api/v1/acesso/sessao/` devolve quem está logado (`{"usuario": null}` se ninguém) e entrega o cookie
   `csrftoken`.
2. `POST /api/v1/acesso/sessao/` com `identificador` (nome de usuário ou e-mail) e `senha` abre a sessão: a resposta
   traz o cookie `sessionid`, que é `HttpOnly`.
3. Toda escrita (`POST`, `PUT`, `DELETE`) precisa do cabeçalho `X-CSRFToken` com o valor do cookie `csrftoken`. Sem ele, a
   resposta é 403 `CSRF_FAILED`.
4. `DELETE /api/v1/acesso/sessao/` encerra a sessão.

A sessão acaba depois de 7 dias sem uso. Desativar o usuário ou trocar a senha encerra as sessões na requisição
seguinte.

Os cookies são marcados como `Secure` quando `DJANGO_DEBUG=0`. Navegadores aceitam isso em `http://localhost`;
ferramentas como o `curl` também. Bibliotecas que não enviam cookie `Secure` por HTTP precisam ser configuradas.

O login com o Google usa `POST /api/v1/acesso/sessao/google/` com a `credencial` devolvida pelo botão do Google.

### Erros

Toda resposta de erro tem o mesmo envelope, com um código estável:

```json
{"error": {"code": "CREDENCIAIS_INVALIDAS", "message": "Usuário ou senha inválidos.", "details": null}}
```

Em `VALIDATION_ERROR`, `details` traz os motivos por campo.

| Código | HTTP | Quando |
| --- | --- | --- |
| `NOT_AUTHENTICATED` | 401 | Rota protegida sem sessão |
| `PERMISSION_DENIED` | 403 | Logado, sem permissão (por exemplo, sem ser admin) |
| `CSRF_FAILED` | 403 | Escrita sem o token CSRF válido |
| `VALIDATION_ERROR` | 400 | Campo ausente, mal formatado ou senha fora da política |
| `NOT_FOUND` | 404 | Recurso ou rota inexistente |
| `MUITAS_TENTATIVAS` | 429 | Limite de tentativas de login ou de requisições por IP |
| `CREDENCIAIS_INVALIDAS` | 401 | Identificador ou senha errados, conta inexistente ou inativa |
| `EMAIL_NAO_VERIFICADO` | 403 | Senha certa numa conta que aguarda verificação |
| `CONVITE_INVALIDO` | 404 | Convite usado, expirado, revogado ou inexistente |
| `NOME_DE_USUARIO_EM_USO`, `EMAIL_EM_USO` | 409 | Cadastro com dado já usado |
| `LINK_INVALIDO` | 400 | Link de verificação ou de recuperação inválido ou vencido |
| `GOOGLE_INVALIDO` | 401 | Credencial do Google recusada, ou login com Google não configurado |
| `ACESSO_SO_POR_CONVITE` | 403 | Login com Google de quem não tem conta |
| `CONTA_JA_EXISTE` | 409 | Cadastro com Google de um e-mail que já tem conta |
| `NAO_PODE_ALTERAR_A_SI_MESMO` | 422 | Desativar a si mesmo ou tirar o próprio papel de admin |
| `CONVITE_NAO_ESTA_ATIVO`, `CONVITE_NAO_PODE_SER_REGENERADO` | 422 | Ação fora da situação do convite |
| `USUARIO_NAO_ESTA_ATIVO`, `USUARIO_NAO_ESTA_INATIVO`, `USUARIO_JA_E_ADMIN`, `USUARIO_NAO_E_ADMIN` | 422 | Ação fora da situação do usuário |
| `NOME_EM_USO` | 409 | Cargo ou setor com nome já usado (sem diferenciar maiúsculas) |
| `CARGO_EM_USO`, `SETOR_EM_USO` | 422 | Desativar cargo ou setor que usuários ativos têm; `details.usuarios` traz a quantidade |
| `CARGO_INATIVO`, `SETOR_INATIVO` | 422 | Classificar com cargo ou setor inativo |
| `JA_ESTA_ATIVO`, `JA_ESTA_INATIVO` | 422 | Reativar o que está ativo, ou desativar o que está inativo |
| `USUARIO_NAO_ESTA_ATIVO` | 422 | Também ao classificar usuário que não está ativo |
| `ACESSO_TOTAL_SO_PARA_USUARIO` | 422 | Conceder o acesso total a cargo ou setor |
| `CONCESSAO_JA_REVOGADA` | 422 | Revogar uma concessão já revogada |
| `SO_O_SOLICITANTE` | 403 | Retirar, reenviar ou editar a solicitação de outra pessoa |
| `SOLICITANTE_NAO_DECIDE` | 403 | O solicitante tenta decidir o próprio pedido sem a auto-aprovação |
| `APROVADOR_NAO_INDICADO` | 422 | Quem aprovaria o próprio pedido envia sem indicar outro aprovador |
| `APROVADOR_INVALIDO` | 422 | O indicado é o próprio solicitante, inativo, sem cargo ou inexistente; ou indica quem não precisa indicar |
| `NAO_ESTA_EM_ANALISE` | 422 | Retirar, aprovar, contestar ou recusar fora da análise |
| `NAO_ESTA_CONTESTADA_NEM_RETIRADA`, `NAO_ESTA_RECUSADA`, `NAO_PODE_EDITAR`, `NAO_PODE_CANCELAR` | 422 | Reenviar, reabrir, editar ou cancelar fora da situação certa |
| `TETO_SEM_VALOR` | 422 | Teto sugerido numa solicitação cujo tipo não tem valor |
| `MOTIVO_JA_EXISTE` | 409 | Motivo com o texto de outro do mesmo tipo de decisão, ativo ou inativo (sem diferenciar maiúsculas) |
| `INTERNAL_ERROR` | 500 | Erro inesperado; o detalhe fica só no log, com o `X-Request-ID` da resposta |

Login, recuperação de senha, reenvio de verificação e convite inválido respondem do mesmo jeito exista a conta (ou o
convite) ou não.

### Recursos

| Recurso | Rotas | Quem |
| --- | --- | --- |
| Saúde | `GET health/` | Aberta |
| Sessão | `GET`, `POST`, `DELETE acesso/sessao/`; `POST acesso/sessao/google/` | Aberta (sair exige sessão) |
| Configuração pública | `GET acesso/configuracao/` | Aberta |
| Convites | `GET`, `POST acesso/convites/`; `POST acesso/convites/{id}/regenerar/`, `…/revogar/`; `GET acesso/convites/{id}/historico/` | Admin, ou quem tem a permissão `convites.gerenciar` |
| Consulta de convite | `POST acesso/convites/consultar/` | Aberta |
| Cadastro | `POST acesso/cadastros/`, `POST acesso/cadastros/google/` | Aberta, com convite |
| Verificação de e-mail | `POST acesso/verificacoes/`, `POST acesso/verificacoes/reenviar/` | Aberta |
| Senha | `POST acesso/senhas/recuperar/`, `POST acesso/senhas/redefinir/` | Aberta |
| Usuários | `GET acesso/usuarios/`; `POST acesso/usuarios/{id}/desativar/`, `…/reativar/`, `…/tornar-admin/`, `…/remover-admin/`; `GET acesso/usuarios/{id}/historico/` | Admin |
| Cargos e setores | `GET permissoes/cargos/`, `GET permissoes/setores/` | Admin ou diretor ativo com cargo |
| | `POST permissoes/cargos/` (e `setores/`); `POST …/{id}/renomear/`, `…/desativar/`, `…/reativar/`; `GET …/{id}/historico/` | Admin |
| Catálogo e concessões | `GET permissoes/catalogo/`; `GET`, `POST permissoes/concessoes/` (201 se criou, 200 se já existia); `POST permissoes/concessoes/{id}/revogar/` | Admin |
| Classificação e permissões de um usuário | `GET permissoes/usuarios/{id}/`; `PUT permissoes/usuarios/{id}/classificacao/` (`cargo_id` nulo tira o cargo e os setores) | Admin |
| Minhas permissões | `GET permissoes/minhas/` | Logado: só as próprias |
| Caixa de notificações | `GET notificacoes/` (`?antes=<id da última recebida>&limite=20`, de 1 a 50), `GET notificacoes/resumo/` (`nao_lidas` e `mais_recente_id`), `POST notificacoes/{id}/ler/`, `POST notificacoes/ler-todas/` (`marcadas`) | Logado: só as próprias. A de outro usuário responde 404 `NOT_FOUND`, inclusive para o admin |
| Preferências de alerta | `GET`, `PUT notificacoes/preferencias/` (`aviso_na_tela`, `email_informativos`; só as chaves enviadas mudam, e só `true` ou `false`) | Logado: só as próprias |
| Tipos de solicitação | `GET aprovacoes/tipos/` (`codigo`, `nome`, `tem_valor`) | Admin ou diretor ativo com cargo |
| Solicitações | `GET aprovacoes/solicitacoes/` (`?tipo=`, `?situacao=`, `?minhas=1`, `?antes=<id>`, `?limite=` de 1 a 50); `GET aprovacoes/solicitacoes/{id}/` (versões, decisões, indicação e `acoes`); `GET …/{id}/historico/` | Admin ou diretor ativo com cargo |
| Enviar | `POST aprovacoes/solicitacoes/` (`tipo`, `conteudo`, `aprovador_indicado_id`) | Quem lê gestão e, se o tipo pede, tem a permissão de enviar |
| Comandos do solicitante | `POST aprovacoes/solicitacoes/{id}/retirar/`, `…/reenviar/` (`conteudo`), `…/editar/` (`conteudo`, `justificativa`) | O solicitante |
| Reabrir e cancelar | `POST …/{id}/reabrir/` (`justificativa`, `conteudo` opcional), `…/cancelar/` (`motivo`) | O solicitante, o admin ou quem tem `solicitacoes.reabrir` ou `solicitacoes.cancelar` |
| Decisões | `POST …/{id}/aprovar/`, `…/recusar/` (`motivo_id`, `texto`); `…/contestar/` (`motivo_id`, `mensagem`, `texto`, `teto_sugerido`) | Quem lê gestão e tem a permissão de aprovar o tipo, ou o indicado; o solicitante só com `solicitacoes.auto_aprovar` |
| Fila de pendências | `GET aprovacoes/fila/` | Admin ou diretor ativo com cargo: só o que ele pode decidir |
| Motivos de decisão | `GET aprovacoes/motivos/` (`?tipo_de_decisao=`; `?todos=1` traz os inativos, só para o admin) | Admin ou diretor ativo com cargo |
| | `POST aprovacoes/motivos/`; `POST …/{id}/editar/`, `…/desativar/`, `…/reativar/`; `GET aprovacoes/tipos-de-decisao/` | Admin |
| Contrato | `GET schema/`, `GET docs/` | Admin |

Notificação nunca é alterada nem apagada: não há rota `DELETE` nem preferência que desligue o registro; a rota `ler`
só preenche `lida_em` na primeira leitura. A caixa vem da mais recente para a mais antiga, e `tem_mais` diz se há
outras depois da última página; um `antes` que não é do usuário responde 400 `VALIDATION_ERROR`. Um item traz
`id`, `tipo`, `pede_acao`, `titulo`, `texto`, `caminho`, `criada_em` e `lida_em`; o texto é sempre texto, nunca HTML.

Cargo, setor e concessão nunca são apagados: não há rota `DELETE` para eles; só desativar ou revogar. O histórico
de um item (`…/historico/`) vem do mais recente para o mais antigo, com `acao`, `ator` (`id` e `nome`, ou nulo
para o sistema), `justificativa` e `criado_em`.

O token de convite, de verificação e de recuperação vai sempre no corpo, nunca na URL da API.

Solicitação, versão, decisão e motivo nunca são apagados, e versão e decisão nunca mudam (também no banco). A ordem das conferências em toda rota de solicitação é: leitura de gestão (403), entrada (400), existência (404), quem pode (403) e situação (422); quem não lê gestão recebe 403 sem saber se o ID existe. Dinheiro vai e volta como texto com duas casas (`"150.00"`). O `conteudo` de cada versão é do módulo dono do tipo (um objeto JSON de até 64 KB) e o site o mostra como texto. O campo `acoes` do detalhe diz o que quem pergunta pode fazer agora; ele é conveniência do site, e a API confere de novo em cada comando. Não há rota para pôr em execução nem encerrar: isso é do módulo dono do tipo, pela API pública em processo.

## 3. Dados

### Convenções

- Chaves primárias: UUID versão 7, em todos os modelos.
- Referência entre módulos: por ID (campo UUID), sem chave estrangeira; dentro do módulo, chave estrangeira normal.
  A auditoria guarda só IDs.
- Dinheiro: `Decimal` com duas casas no value object `Dinheiro`; `DecimalField` no banco; texto na API (`"150.00"`).
- Nada é apagado: usuário, cargo, setor, concessão, solicitação, versão, decisão, motivo e notificação só se
  desativam, revogam ou cancelam. A trilha de auditoria é só de inserção, recusada também por gatilho no banco.
- Migrações do Django, versionadas e reversíveis, em `<modulo>/migrations/`.

### Aggregates e estados

| Módulo | Aggregate | Estados |
| --- | --- | --- |
| `aprovacoes` | Solicitação (com Versão e Decisão) | `EM_ANALISE`, `RETIRADA`, `CONTESTADA`, `RECUSADA`, `APROVADA`, `EM_EXECUCAO`, `ENCERRADA`, `CANCELADA` |
| `financeiro` | Cobrança | `ABERTA`, `EM_VALIDACAO`, `ATRASADA`, `PAGA`, `ISENTA`, `CANCELADA`, `PERDOADA`, `RENEGOCIADA` |
| `financeiro` | Saída | `AGUARDANDO_ENVIO`, `RECURSO_ENVIADO`, `EM_CONFERENCIA`, `LIQUIDADA`, `CANCELADA`, `ESTORNADA` |
| `financeiro` | Entrada, Recorrência, Suspensão, Renegociação | Definidos na spec técnica de cada feature do M6 |
| `eventos` | Evento | `EM_APROVACAO`, `PUBLICADO`, `RECUSADO`, `REALIZADO`, `CANCELADO` (derivado das duas solicitações por uma função só, `situacao_do_evento`) |

Os módulos de apoio (`acesso`, `permissoes`, `notificacoes`, `auditoria`, `comunicacao`, `marca`, `relatorios`) usam
camadas, sem modelo tático. Dados pessoais tratados: nome, nome de usuário, telefone, e-mail e senha (em hash
Argon2); convites, verificações e recuperações guardam só o hash do token. Detalhes e pendências de LGPD em
[04-seguranca](04-seguranca.md).

## 4. Critérios de aceite por marco

| Marco | Entregável | Critério de aceite |
| --- | --- | --- |
| M0 | Arquitetura: avaliação do enunciado e proposta de arquitetura, stack, estrutura e repositório, com decisões registradas | Decisões aprovadas pelo dono e especificações dos marcos seguintes geradas |
| M1 | Fundação: projeto, Docker, banco, CI no GitHub Actions, configuração por ambiente, esqueleto da API e do site | Subir tudo com um comando local e pipeline verde |
| M2 | Identidade e acesso: login Google e usuário/senha, verificação de e-mail, convite de 24 horas, cadastro, desativação | Diretor convidado se cadastra, valida o e-mail e entra pelos dois modos |
| M3 | Permissões e auditoria: catálogo, três origens, cargos, setores, categorias, painel do admin, trilha de auditoria | Admin atribui permissões por cargo, setor e individual, e cada concessão fica auditada |
| M4 | Notificações: tarefas agendadas, e-mail, caixa de notificações no site, preferências de alerta | Evento de teste gera registro, e-mail e item na caixa; usuário não desliga o registro |
| M5 | Motor de aprovações: solicitação genérica com versões, regras por setor, justificativas, reabertura, cancelamento e liquidação | Fluxos de aprovar, recusar, reabrir e editar aprovada passam nos testes, com solicitante nunca aprovando o próprio pedido sem permissão |
| M6 | Financeiro, entradas: categorias, cobranças únicas e recorrentes, mensalidade por diretor, validação, questionamento, isenção, atraso | Cobrança recorrente é gerada sozinha, notificada, paga, validada e liquidada |
| M7 | Financeiro, saídas: solicitação de recurso, envio com comprovante, prestação de contas, estorno e cancelamento | Ciclo completo de uma saída, da solicitação à liquidação, com histórico |
| M8 | Eventos: proposta, regras por tipo, calendário, histórico, encerramento e cancelamento | Evento com custo exige o Financeiro, só aprovado aparece no calendário, editar o tira de lá |
| M9 | Feed, documentos e perfil: comunicados, aba de documentos, perfil privado | Perfil só visível ao dono e ao admin; documentos acessíveis pelo feed |
| M10 | Dashboard e relatórios: dashboard completo e básico, listas e detalhes, relatórios em PDF e CSV | Números batem com os lançamentos validados e relatórios respeitam permissões |
| M11 | Personalização: cadastro de escudo e cores, temas derivados, ícones customizáveis | Sistema nasce em branco e assume a identidade configurada em todas as telas e no PDF |
| M12 | Produção: deploy na AWS, backups, rollback, segurança, testes ponta a ponta, documentação, limpeza do protótipo antigo | Sistema no ar na instância única, backup e rollback testados, resquícios do protótipo removidos |
| — | Etapas futuras "só documentadas" (mobile, torcedor e jogador, gestão do time, multi-cliente) | Seção de etapas futuras na documentação, sem implementação |

Critério de aceite de cada requisito: o teste automatizado que o cobre. A matriz requisito → teste é mantida junto
do plano de cada feature e atualizada a cada marco; todo requisito tem pelo menos um teste.
