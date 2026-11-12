# Desenho estratégico

| Campo | Valor |
| --- | --- |
| Status | Approved |
| Atualizado em | 2026-11-11 |
| Aprovado por / em | Leandro Nascimento / 2026-11-11 |
| Fontes | `docs/domain/discovery/`, `docs/challenge/phase-1-enunciado.md` |

## Domínio

Governança financeira e institucional de um clube de futebol, exercida pelos diretores.

## Subdomínios

| Subdomínio | Tipo | Por quê | Estratégia |
| --- | --- | --- | --- |
| Aprovação de solicitações | Core | É o que dá formalidade às decisões: quem pediu, quem decidiu, por quê, em que versão | Construir |
| Cobrança e recebimento | Core | É onde o dinheiro entra e onde a inadimplência é tratada; cada valor precisa de validação rastreável | Construir |
| Gasto e prestação de contas | Core | É onde o dinheiro sai; liga a aprovação ao envio, à comprovação e ao encerramento | Construir |
| Eventos institucionais | Core | Usa a aprovação e o financeiro para decidir o que o clube faz; o calendário é a face visível da governança | Construir |
| Identidade e permissões | Supporting | Necessário e específico (três origens de permissão), mas não é o diferencial | Construir, reutilizando a autenticação do framework |
| Comunicação e documentos | Supporting | Feed e arquivos com pouca regra | Construir, mínimo |
| Dashboard e relatórios | Supporting | Leitura do que os outros subdomínios produzem | Construir |
| Notificações | Generic | Aviso por e-mail e caixa de entrada é um problema resolvido | Construir fino sobre e-mail e fila prontos |
| Auditoria | Generic | Trilha de inserção é um padrão conhecido | Construir fino |
| Marca | Generic | Configuração de escudo e cores | Construir fino |

### Core domain

O diferencial não é lançar receitas e despesas, e sim dar aos diretores aprovação formal e rastreabilidade completa de
cada valor e de cada decisão.

Pilares: decisão formal e justificada; rastreabilidade de quem fez o quê e quando; registros encerrados que não mudam.

Consequência de modelagem: o estado de cada cobrança, solicitação, saída e evento é o produto. As transições são
poucas, nomeadas e protegidas; toda decisão carrega decisor, motivo e momento; nada é sobrescrito nem apagado, e a
correção de algo encerrado é sempre um registro novo ligado ao original.

## Princípios de fronteira

1. Uma transação altera um aggregate. Exceções registradas na ADR-003: o registro de auditoria entra na mesma
   transação, e a reação à decisão de uma solicitação (por exemplo, criar a saída quando a solicitação é aprovada)
   também, porque aprovação e dinheiro não podem divergir.
2. Referência entre aggregates só por ID.
3. Um contexto só conhece os que estão abaixo dele no context map. Quando o de baixo precisa provocar algo no de
   cima, ele publica um evento em processo e o de cima reage (ADR-003).
4. Dado de outro contexto entra como snapshot no momento do registro: o texto do motivo de decisão, o nome da
   categoria, o valor aprovado.
5. Todo estado final é imutável. Corrigir é criar um registro novo ligado ao original.

## Mapeamento

| Subdomínio | Bounded context | Módulo (rito 7) |
| --- | --- | --- |
| Identidade e permissões | Identidade e Permissões | `acesso`, `permissoes` |
| Auditoria | Auditoria | `auditoria` |
| Notificações | Notificações | `notificacoes` |
| Aprovação de solicitações | Aprovações | `aprovacoes` |
| Cobrança e recebimento; gasto e prestação de contas | Financeiro | `financeiro` |
| Eventos institucionais | Eventos | `eventos` |
| Comunicação e documentos | Comunicação | `comunicacao` |
| Marca | Marca | `marca` |
| Dashboard e relatórios | Relatórios | `relatorios` |

Dois subdomínios financeiros ficam num contexto só, porque compartilham categorias, a validação de entradas (a
devolução de um gasto é uma entrada) e o saldo. Dividir é o gatilho registrado abaixo. Identidade e Permissões é um
contexto com dois módulos, porque autenticar e autorizar mudam por motivos diferentes mas falam do mesmo usuário.

## Canvas: Identidade e Permissões

| Campo | Conteúdo |
| --- | --- |
| Propósito | Saber quem é cada diretor, como ele entra e o que ele pode fazer |
| Classificação | Supporting |
| Papel | Cadastro e autorização |
| Linguagem (termos-chave) | Usuário, admin, diretor, convite, cargo, setor, permissão, concessão, classificação |
| Regras de negócio centrais | Acesso só por convite, de uso único, com 24 horas; e-mail verificado; usuário é desativado, nunca apagado; as permissões de um usuário são a união das concessões por cargo, por setor e individuais; diretor sem cargo só vê o dashboard básico |
| Entrada | Do site: comandos de cadastro, login e administração. Dos demais contextos: consulta "este usuário pode fazer esta ação neste recurso?" e "quem pode fazer esta ação?" |
| Saída | Para Notificações: evento "cadastro concluído". Para Auditoria: registros |
| Aggregates candidatos | Nenhum formal (camadas); a resolução de permissões é função pura |
| Premissas | O admin é um perfil de gestão; presidente é um cargo como os outros |
| Perguntas em aberto | AD-006 (autenticação e tokens), AD-007 (modelagem das permissões), AD-014 (painel do admin), AD-019 (primeiro admin) |

## Canvas: Auditoria

| Campo | Conteúdo |
| --- | --- |
| Propósito | Guardar, de forma imutável, quem fez o quê, quando, sobre qual item e por quê |
| Classificação | Generic |
| Papel | Registro |
| Linguagem (termos-chave) | Registro de auditoria, ator, ação, item, justificativa |
| Regras de negócio centrais | Só inserção; nada é alterado nem apagado; o histórico de um item é visível a quem pode ver o item |
| Entrada | De todos os contextos: "registrar ação" |
| Saída | Para os detalhes de cada item e para Relatórios: consulta do histórico |
| Aggregates candidatos | Nenhum |
| Premissas | A auditoria guarda o ID do ator e do item, não cópias dos dados pessoais |
| Perguntas em aberto | AD-009 (modelagem), AD-015 (LGPD e o que nunca é apagado) |

## Canvas: Notificações

| Campo | Conteúdo |
| --- | --- |
| Propósito | Avisar um usuário e guardar a prova de que ele foi avisado |
| Classificação | Generic |
| Papel | Entrega e registro |
| Linguagem (termos-chave) | Notificação, caixa de entrada, canal, lida, preferência de alerta |
| Regras de negócio centrais | Toda notificação é registrada, e o usuário não desliga o registro; cada usuário só vê as suas; a notificação aponta para o item relacionado |
| Entrada | Dos contextos acima: "notificar estes usuários sobre este item". De Identidade e Permissões: evento "cadastro concluído" |
| Saída | Para o usuário: e-mail e caixa no site. Para o provedor de e-mail: envio |
| Aggregates candidatos | Nenhum |
| Premissas | Os e-mails transacionais de acesso (verificação, recuperação de senha) não são notificações: saem direto de Identidade e Permissões |
| Perguntas em aberto | AD-012 (provedor de e-mail); pendências do M4 |

## Canvas: Aprovações

| Campo | Conteúdo |
| --- | --- |
| Propósito | Fazer um pedido passar por decisão formal, versionada e justificada, sem saber do que o pedido trata |
| Classificação | Core |
| Papel | Execução (motor) |
| Linguagem (termos-chave) | Solicitação, tipo de solicitação, versão, solicitante, aprovador, decisão, aprovar, contestar, recusar, reenviar, reabrir, cancelar, motivo de decisão, teto sugerido, fila de pendências |
| Regras de negócio centrais | Uma solicitação tem um só aprovador por versão; o solicitante não decide o próprio pedido, e quem decidiria indica outro diretor; toda decisão tem motivo; contestar devolve para ajustes; cada reenvio é uma versão nova e as decisões valem só para a versão em que foram tomadas |
| Entrada | De Financeiro e Eventos: "abrir solicitação deste tipo". Do site: comandos de decisão. De Identidade e Permissões: quem pode decidir |
| Saída | Para Financeiro e Eventos: eventos "solicitação aprovada, contestada, recusada, cancelada". Para Notificações e Auditoria |
| Aggregates candidatos | Solicitação |
| Premissas | Os tipos de solicitação são registrados pelos contextos que usam o motor; o catálogo de motivos de decisão vive aqui e é usado por todos os contextos |
| Perguntas em aberto | AD-008 (modelagem); H26 (risco da indicação de aprovador); reabertura e cancelamento são hipóteses do enunciado |

## Canvas: Financeiro

| Campo | Conteúdo |
| --- | --- |
| Propósito | Registrar o dinheiro que se espera, o que entrou e o que saiu, sempre validado e comprovado |
| Classificação | Core |
| Papel | Execução |
| Linguagem (termos-chave) | Cobrança, devedor, vencimento, limite de inadimplência, pagamento, validar, rejeitar, em validação, recibo, chave Pix, questionamento, isenção, suspensão, convocação, perdão, renegociação, parcela, entrada, saída, recurso enviado, prestação de contas, devolução, complemento, liquidar, estorno, categoria |
| Regras de negócio centrais | Toda entrada precisa de validação; a cobrança tem um só desfecho; liquidado é imutável; a saída só nasce de solicitação aprovada e só é liquidada com a prestação de contas conferida; gasto maior exige nova aprovação e gasto menor exige devolução; tarefas agendadas não geram a mesma cobrança duas vezes |
| Entrada | Do site: comandos. Do agendador: gerar cobranças, marcar atrasos, esgotar limites. De Aprovações: decisão das solicitações de gasto e de orçamento. De Eventos: "abrir solicitação orçamentária para este evento" |
| Saída | Para Aprovações: abrir solicitação. Para Notificações, Auditoria e Relatórios |
| Aggregates candidatos | Cobrança, Renegociação, Suspensão de cobranças, Saída |
| Premissas | Os valores são escriturais; a transferência real acontece por fora |
| Perguntas em aberto | AD-010 (estornos), AD-011 (anexos); pendências do M6 e do M7 |

## Canvas: Eventos

| Campo | Conteúdo |
| --- | --- |
| Propósito | Decidir, divulgar e encerrar o que o clube organiza |
| Classificação | Core |
| Papel | Execução |
| Linguagem (termos-chave) | Evento, proponente, proposta, categoria de evento, orçamento do evento, calendário, publicar, realizado, cancelado |
| Regras de negócio centrais | O evento só está no calendário com todas as solicitações exigidas aprovadas (a do evento e, se houver custo, a orçamentária); editar um evento aprovado o tira do calendário; realizado é imutável |
| Entrada | Do site: comandos. De Aprovações: decisão das solicitações de evento e de orçamento. Do agendador: dia do evento |
| Saída | Para Aprovações: abrir a solicitação do evento. Para Financeiro: abrir a solicitação orçamentária. Para Notificações (todos os diretores), Auditoria e Relatórios |
| Aggregates candidatos | Evento |
| Premissas | O custo do evento existe uma vez só, na solicitação orçamentária; o evento guarda o vínculo |
| Perguntas em aberto | H27 (evento sem custo), H28 (orçamento negado em definitivo); participação em eventos (pendência do M8) |

## Canvas: Comunicação

| Campo | Conteúdo |
| --- | --- |
| Propósito | Publicar comunicados e pautas e guardar os documentos do clube |
| Classificação | Supporting |
| Papel | Cadastro e publicação |
| Linguagem (termos-chave) | Comunicado, pauta, feed, documento |
| Regras de negócio centrais | Todos os diretores leem; publicar depende de permissão; os documentos do feed e os da aba são os mesmos |
| Entrada | Do site: comandos |
| Saída | Para Notificações (hipótese, COM-03), Auditoria e Relatórios |
| Aggregates candidatos | Nenhum |
| Premissas | Desenho mínimo |
| Perguntas em aberto | Pendências do M9; atas e postagem fixada (AD-016) |

## Canvas: Marca

| Campo | Conteúdo |
| --- | --- |
| Propósito | Dar ao sistema a identidade visual do clube |
| Classificação | Generic |
| Papel | Configuração |
| Linguagem (termos-chave) | Marca, escudo, cores base, tema |
| Regras de negócio centrais | O sistema nasce sem marca; os temas derivam das cores base |
| Entrada | Do site: comandos de quem tem a permissão |
| Saída | Para o site e para Relatórios: a configuração vigente |
| Aggregates candidatos | Nenhum |
| Premissas | Um clube por instalação (AD-018 adiada) |
| Perguntas em aberto | Quem pode alterar a marca (pendência do M3) |

## Canvas: Relatórios

| Campo | Conteúdo |
| --- | --- |
| Propósito | Mostrar a situação do clube e exportá-la |
| Classificação | Supporting |
| Papel | Análise (só leitura) |
| Linguagem (termos-chave) | Dashboard, dashboard básico, extrato, balancete, inadimplência, realizado, previsto |
| Regras de negócio centrais | Só conta como realizado o que foi validado; cada relatório só mostra o que o usuário pode ver; este contexto não altera nada |
| Entrada | Das APIs públicas de consulta dos demais contextos |
| Saída | Para o site: dashboard e perfil. Para o usuário: PDF e CSV |
| Aggregates candidatos | Nenhum |
| Premissas | Consultas diretas, sem read models (ADR-001) |
| Perguntas em aberto | Pendências do M10; fluxo de caixa previsto e realizado (AD-016) |

## O que não é bounded context

| Conceito | Onde vive | Por quê |
| --- | --- | --- |
| Perfil do usuário | Leitura composta em Relatórios, com os dados pessoais em Identidade e Permissões | Não tem dado nem regra próprios (PRF-03); a regra de quem vê é uma permissão |
| Calendário | Consulta do contexto Eventos | É a lista dos eventos publicados |
| Anexos (comprovantes, arquivos) | Capacidade técnica compartilhada; o lugar no código é definido no rito 7 | Guardar e servir arquivo não tem linguagem de negócio; a permissão de acesso é a do item dono do anexo |
| Motivos de decisão | Cadastro dentro de Aprovações | Lista simples, usada por todos como snapshot do texto |
| Chave Pix, categorias | Cadastros dentro de Financeiro | Sem ciclo de vida próprio além de ativar e desativar |
| Agendador | Infraestrutura | Só dispara comandos dos contextos; não decide nada |
| Titular da conta, banco | Fora do sistema | A transferência acontece por fora; o sistema só registra |

## Gatilhos de revisão

- O contexto Financeiro passa a ter duas linguagens que mudam em ritmos diferentes, ou a regra de fronteira do módulo
  acumula exceções → dividir em Recebimentos e Despesas.
- Surge um terceiro usuário do motor de aprovações com necessidade que os dois primeiros não têm → rever o canvas de
  Aprovações antes de estender o motor.
- Torcedor e jogador entram (etapa futura) → rever Identidade e Permissões.
