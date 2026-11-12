# Club Manager — Enunciado do Projeto (reescrita do zero)

Nov 11, 2026 · @Leandro Nascimento

## 1. Contexto e objetivo

O Club Manager é um sistema de gestão de um time de futebol, cujo núcleo na etapa 1 é a governança financeira e institucional usada pelos diretores. Este enunciado é o plano completo para construir o sistema do zero, em um único prompt inicial.

- **Por que reescrever:** já existe um protótipo em `C:\projects_dro\Club-Manager`. A nova versão parte de uma arquitetura proposta com SDD, e o protótipo serve só para conferir funcionalidades esquecidas (seção 16).
- **Problema que resolve:** controle de entradas e saídas, aprovação formal de gastos e eventos, e rastreabilidade de quem fez o quê e quando.
- **Produto agnóstico (white-label):** o primeiro cliente é o time do dono do projeto, mas o sistema deve poder ser reaproveitado por outros clientes, com escudo e cores próprios.
- **Sem integração bancária:** os valores são escriturais. A aprovação reflete nos registros, e a transferência real de dinheiro acontece fora do sistema.
- **Escala pequena:** poucos usuários (os diretores de um clube), com infraestrutura de custo mínimo.

## 2. Como trabalhar: SDD com o plugin claude-sdd-method

O projeto segue Spec-Driven Development com o plugin autoral **`claude-sdd-method`**, que já está instalado. O agente executor deve usar o fluxo e os comandos do plugin, e não inventar um processo próprio.

1. **Primeiro passo:** confirmar que o plugin está disponível e ler o seu fluxo antes de qualquer código.
2. **Arquitetura do zero:** o plugin avalia este enunciado e **propõe a arquitetura, a stack e a estrutura do repositório**, registrando cada decisão (o que foi escolhido e o que foi descartado). A arquitetura do protótipo não é ponto de partida.
3. **Marco a marco:** para cada marco da seção 14, especificar, planejar, quebrar em tarefas, implementar e validar com critérios de aceite, nessa ordem.
4. **Plano vivo:** o plano deste enunciado está completo, mas pode mudar. Qualquer alteração do plano é feita na especificação e registrada, e não só no código.
5. **Pendências:** os itens da seção 15 são decididos no refinamento do marco correspondente, perguntando ao dono do projeto quando não houver hipótese razoável.

## 3. Escopo

A etapa 1 entrega o sistema completo **para os diretores**, no **site**. O aplicativo e os outros tipos de usuário vêm depois.

**Dentro da etapa 1**

- Financeiro (o núcleo): entradas, saídas, cobranças recorrentes, validação, prestação de contas.
- Eventos com aprovação e calendário.
- Notificações (e-mail e caixa de entrada no site).
- Feed de comunicados, documentos e perfil do usuário.
- Dashboard e relatórios em PDF e CSV.
- Autenticação, convites, permissões em catálogo e motor de aprovações.
- Personalização por time (escudo e cores) e auditoria transversal.

**Fora da etapa 1 (etapas futuras, só documentadas)**

- **Aplicativo mobile**, feito depois que o site estiver funcionando por completo. Inclui o push no celular.
- **Outros tipos de usuário:** torcedor e jogador, com funcionalidades, visão e permissionamento próprios, e cadastro aberto.
- **Gestão do time como um todo** (além da governança financeira e institucional).
- Recebimento automático por plataforma de pagamento, com ponto de extensão previsto, sem implementar.

A arquitetura não deve implementar os itens futuros, mas também não pode impedi-los: tipos de usuário e permissões precisam ser extensíveis, e a API deve servir site e app.

## 4. Atores, cargos, setores e glossário

Na etapa 1 existe **um único tipo de usuário: o diretor**. O que o diferencia é o cargo, os setores e as permissões que o admin atribui.

| Papel | Quem é | O que tem por padrão |
| --- | --- | --- |
| Admin | Gestor do sistema | Todas as permissões. Aprova e recusa qualquer coisa. Único que gerencia usuários, cargos, setores, categorias e permissões. |
| Presidente | Cargo como os outros | Sem acesso total por padrão. O admin pode conceder acesso total ou aprovação. Não gerencia usuários. |
| Diretor com cargo | Diretor classificado pelo admin | Leitura completa de gestão. Escrita só no que o cargo, o setor ou concessão individual permitirem. |
| Diretor sem cargo | Diretor recém-cadastrado | Apenas o dashboard básico, sem muitos detalhes, até o admin classificá-lo. |
| Responsável de setor | Ex.: responsável pelo Financeiro | Aprova o que se relaciona ao seu setor, conforme as regras. |
| Torcedor e jogador | Usuários comuns | Etapas futuras. Não implementar agora. |

**Setores** são entidades configuráveis. Iniciais: Financeiro, Futebol, Eventos e Operacional (herdados do protótipo; o dono confirma ou renomeia). Um usuário pode pertencer a **vários setores**.

**Glossário**

- **Solicitação:** pedido que passa por aprovação (despesa, evento ou outro tipo). Tem versões, histórico e decisões por setor.
- **Cobrança:** valor esperado de um diretor (mensalidade, cota, patrocínio etc.), única ou recorrente.
- **Entrada e saída:** lançamentos de dinheiro que entra e que sai, sempre escriturais.
- **Validação:** confirmação do responsável de que o valor realmente entrou na conta.
- **Liquidado (encerrado):** estado final em que o registro não pode mais ser editado, só retornado ou cancelado por nova ação.
- **Isenção:** dispensa de uma cobrança específica de um diretor, com justificativa e período.
- **Prestação de contas:** comprovação de um gasto, com comprovante ou justificativa em texto.
- **Permissão (regra):** combinação de ação, tipo de recurso e escopo, atribuível por cargo, por setor ou individualmente.

## 5. Acesso, cadastro e usuários (ACE)

O acesso na etapa 1 é **só por convite**: o diretor entra por um link gerado pelo admin, e depois o admin o classifica.

- **ACE-01 Login com Google:** login social. Quem tem o Gmail logado na máquina entra sem digitar senha.
- **ACE-02 Login com usuário e senha:** nome de usuário (único) e senha. Os dois modos convivem na mesma conta, e o mesmo e-mail nunca duplica o usuário.
- **ACE-03 Primeiro acesso pelo Google:** o usuário completa o cadastro com nome de usuário e senha. O e-mail do Google já vem verificado.
- **ACE-04 E-mail válido e verificado:** obrigatório no cadastro manual, com **link de verificação**. O e-mail é o do convite, o da validação, o de login e o das notificações.
- **ACE-05 Convite de diretor:** o admin (ou usuário com a permissão de convidar) gera o link. O link **não carrega cargo nem setor**, é de uso único e **expira em 24 horas**. Pode ser **regenerado ou revogado** por quem tem a permissão.
- **ACE-06 Cadastro pelo convite:** o diretor informa nome, nome de usuário, telefone, e-mail válido e senha, e valida o e-mail para ter acesso.
- **ACE-07 Aviso ao admin:** quando um diretor conclui o cadastro, o admin recebe um aviso para classificá-lo (cargo e setores).
- **ACE-08 Diretor sem cargo:** enquanto não classificado, vê apenas o dashboard básico, sem detalhes.
- **ACE-09 Campos do usuário:** nome, nome de usuário, telefone, e-mail, senha e flag **ativo/inativo**. **Não coletar CPF.**
- **ACE-10 Desativação:** o usuário pode ser desativado (bloqueia o acesso) e nunca apagado, para preservar o histórico. Só o admin ativa e desativa.
- **ACE-11 Recuperação de senha** pelo e-mail verificado (hipótese, ver seção 15).
- **ACE-12 Quem não foi convidado** e tenta entrar pelo Google não acessa o sistema na etapa 1 (hipótese, ver seção 15).
- **ACE-13 Mesmo fluxo no site e no app**, pois ambos usam a mesma API.

## 6. Permissões e fluxo de aprovação (PER, APR)

O acesso é controlado por um **catálogo de permissões** flexível. A aprovação é um motor genérico, usado por despesas, eventos e qualquer requisição futura.

**Permissões**

- **PER-01 Leitura:** todo diretor com cargo lê os dados de gestão (financeiro, eventos, feed, documentos). Escrita depende de permissão. O perfil de cada usuário é exceção: só o próprio usuário e o admin o veem.
- **PER-02 Catálogo:** uma permissão combina **ação** (ver, criar, editar, aprovar, cancelar, reabrir, isentar, convidar, auto-aprovar, acesso total etc.), **tipo de recurso** (despesa, evento, entrada, convite etc.) e, se preciso, **setor**.
- **PER-03 Três origens que se somam:** por **cargo**, por **setor** (cada setor traz um pacote de regras) e **individual**. O usuário fica com a união de tudo. O admin pode dar uma regra de um setor a quem não pertence a ele (exemplo: um usuário de Futebol aprovar um evento).
- **PER-04 Admin:** tem todas as permissões. Só ele gerencia usuários, cargos, setores, categorias (entrada, saída e evento) e concessões. Presidente não gerencia usuários.
- **PER-05 Painel do admin:** monta e atribui combinações a partir de ações e recursos conhecidos, e mostra o que cada usuário tem e de onde vem. Comportamento totalmente novo é criado por programação, não pelo painel (o plugin pode propor outra abordagem).
- **PER-06 Acesso total e auto-aprovação:** o admin pode conceder acesso total a um usuário. Auto-aprovação é uma permissão à parte, que acesso total não dá por si.

**Aprovação**

- **APR-01 Quem aprova:** quem tem a permissão de aprovar aquele tipo de pedido. O admin aprova ou reprova tudo. O responsável do Financeiro aprova o que é financeiro, e assim por diante.
- **APR-02 Solicitante não aprova o próprio pedido,** salvo o admin ou quem tem a permissão de auto-aprovação. Se o setor tem um único aprovador e ele mesmo pede, outro aprovador decide (admin ou quem receber essa permissão, como o presidente). Aprovação própria aparece de forma explícita no histórico.
- **APR-03 Regras por tipo:** o admin define quais setores precisam aprovar cada tipo de requisição (exemplo: evento X exige setores X e Y; evento Y exige só o setor X). Vale para eventos, despesas e requisições futuras. Evento ou despesa com custo exige sempre o setor Financeiro.
- **APR-04 Vários setores:** **todos** precisam aprovar, e **uma recusa basta** para recusar a requisição inteira. Mudar uma regra não afeta pedidos em andamento (hipótese).
- **APR-05 Justificativa obrigatória** em toda decisão, aprovar ou recusar, podendo ser só texto. O registro traz decisor, setor, data e hora e motivo.
- **APR-06 Reabertura:** uma requisição recusada pode ser reaberta, com **justificativa** da reabertura e edição do corpo. Sem limite de reaberturas. Quem reabre: o solicitante, o admin e quem tiver a permissão de reabrir. Sempre volta para nova aprovação.
- **APR-07 Edição de requisição aprovada:** permitida, mas ela volta a **pendente** e exige nova aprovação com os novos termos. As aprovações antigas não valem para a nova versão.
- **APR-08 Versões e histórico:** cada edição ou reabertura cria uma **nova versão** da mesma solicitação, sem sobrescrever a anterior. O detalhe mostra todas as versões, decisões e justificativas.
- **APR-09 Liquidação:** depois de **liquidada**, a requisição não pode ser editada. Pode ser **retornada (estornada) ou cancelada**, sempre como nova ação justificada e ligada ao original. Para corrigir um item efetuado, estornado ou cancelado, é preciso uma **solicitação nova**.
- **APR-10 Cancelamento** exige motivo e uma permissão específica. Por padrão, o solicitante e o admin podem cancelar.
- **APR-11 Fila de pendências** por aprovador, integrada às notificações.

## 7. Financeiro (FIN)

O financeiro é o núcleo da etapa 1. Os valores são **escriturais**: não há integração bancária, e a transferência real acontece fora do sistema.

**Categorias e recorrência**

- **FIN-01 Categorias** de entrada e de saída, geridas só pelo admin. Entradas iniciais: patrocínio, mensalidade, ajuda, rifa e diversos. Excluir uma categoria já usada deve desativá-la, sem apagar o histórico (hipótese).
- **FIN-02 Recorrência:** toda entrada ou saída pode ser **única ou periódica** (mensal, semanal etc.), escolhida no registro. Cobranças periódicas são geradas automaticamente por tarefas agendadas.
- **FIN-03 Mensalidade por diretor:** cada diretor tem a sua cobrança e o seu valor de mensalidade.

**Entradas e cobranças**

- **FIN-04 Geração e aviso:** toda cobrança nova gera notificação ao devedor. No **dia do vencimento**, o sistema notifica os devedores de mensalidades e cobranças recorrentes.
- **FIN-05 Pagamento e validação:** o diretor paga por fora e registra o pagamento. A cobrança fica **pendente de validação**, e o responsável financeiro é notificado. Ele confere na conta, verifica o comprovante e, ao confirmar, a cobrança passa a **paga**.
- **FIN-06 Evidência:** **toda entrada precisa de validação**. O comprovante é anexado quando existe; quando não existe, basta uma evidência em texto.
- **FIN-07 Entradas sem usuário** (patrocínio, rifa, ajuda): o financeiro registra, confere o recebimento e valida (hipótese: quem valida é definido na seção 15).
- **FIN-08 Recusa de comprovante:** o responsável recusa com justificativa e o devedor é notificado (hipótese: a cobrança volta a pendente para novo envio).
- **FIN-09 Cobrança em atraso:** vencida e não paga fica em atraso, e alimenta os relatórios de inadimplência.
- **FIN-10 Questionamento:** cada cobrança tem um campo para o devedor **questionar**, com texto. O responsável avalia e decide entre **isentar**, **cancelar** ou **manter pendente**, com justificativa. Enquanto questionada, a cobrança não dispara novos avisos de atraso (hipótese).
- **FIN-11 Isenção:** vale **por cobrança**, e não por diretor. Exemplo: o diretor X é isento da mensalidade porque ajuda de outra forma, e continua devendo as outras cobranças. Exige justificativa, tem período (início e fim) e é uma permissão do catálogo. Cobrança isenta não notifica nem conta como inadimplente.
- **FIN-12 Usuário desativado:** não gera cobrança nova. As cobranças pendentes e recorrentes dele são tratadas por regra definida no refinamento.

**Saídas e solicitações de recurso**

- **FIN-13 Solicitação de saída:** o solicitante informa descrição, categoria, valor, setor e, se houver, cotação ou orçamento anexo. Passa pelo fluxo de aprovação (seção 6).
- **FIN-14 Aprovado:** o valor é debitado dos registros do sistema.
- **FIN-15 Envio do recurso:** depois de aprovar, o financeiro pede o dinheiro ao titular da conta, **por fora**, envia ao responsável pelo gasto e **anexa o comprovante do envio**.
- **FIN-16 Prestação de contas:** o sistema pede ao solicitante o **comprovante do gasto** ou uma **justificativa em texto** (alguns gastos não geram comprovante). Há controle de prestações pendentes.
- **FIN-17 Liquidação da saída:** quando o responsável confirma que foi pago, o registro fica liquidado e imutável (APR-09).
- **FIN-18 Estorno e cancelamento:** de lançamentos liquidados, geram um **novo lançamento ligado ao original**, com justificativa e permissão.

**Estados (hipótese para o plugin validar)**

- Cobrança: gerada, questionada, pendente de validação, paga (liquidada), em atraso, isenta, cancelada.
- Saída: pendente de aprovação, recusada, aprovada, recurso enviado, prestação de contas pendente, liquidada, estornada ou cancelada.

## 8. Eventos (EVT)

Eventos usam o mesmo motor de aprovação das despesas (seção 6). O calendário mostra só o que foi aprovado, e o histórico mostra tudo.

- **EVT-01 Proposta:** um diretor com permissão propõe um evento com título, descrição, data, categoria de evento e a flag **"envolve custo"**. Com custo, informa o valor.
- **EVT-02 Aprovação por regra:** evento com custo exige sempre o setor **Financeiro**, além dos setores que as regras do tipo de evento definirem. Evento sem custo segue só as regras do tipo (que podem não exigir aprovação).
- **EVT-03 Custo e despesa:** o custo do evento se liga à solicitação de despesa e ao ciclo financeiro (envio do recurso e prestação de contas), sem cadastrar a mesma coisa duas vezes.
- **EVT-04 Calendário:** mostra **só eventos aprovados**. Cada evento é um **card** que abre o detalhe ao clicar.
- **EVT-05 Edição:** editar um evento aprovado o **tira do calendário** até uma nova aprovação. Só volta quando for aprovado de novo.
- **EVT-06 Histórico para todos:** inclui eventos aprovados, recusados e cancelados, com todos os dados do evento, quem propôs, quem aprovou ou recusou (por setor), data e hora, e as justificativas.
- **EVT-07 Encerramento:** na data do evento, o sistema notifica o responsável (o solicitante) ou o admin. Ele pode **confirmar que aconteceu** (evento liquidado), **cancelar** com motivo, ou, se aconteceu antes da data, usar o botão **"aconteceu"** para atualizar a data e informar o motivo. A mudança de data fica registrada e não reabre a aprovação (hipótese).
- **EVT-08 Cancelar evento aprovado:** permitido com motivo, pelo solicitante, pelo admin ou por quem tem a permissão. Sai do calendário e continua no histórico.
- **EVT-09 Evento liquidado** não pode ser editado (APR-09).
- **EVT-10 Categorias de evento:** geridas só pelo admin, e são a base das regras de aprovação por tipo.

## 9. Notificações (NOT)

Cada notificação é um **registro de que o usuário foi avisado** daquele recurso, evento ou responsabilidade. Por isso ela é sempre gerada e guardada, e o usuário não pode desligar a notificação em si.

- **NOT-01 Canais da etapa 1:** **e-mail** no endereço cadastrado e **caixa de notificações no site**. Na caixa, um ícone com indicador de novas abre um modal, como uma caixa de entrada, com as notificações do usuário.
- **NOT-02 App mobile (etapa futura):** push no celular e uma aba com a caixa de entrada, com as notificações pendentes.
- **NOT-03 Registro:** toda notificação fica guardada com data e hora de envio e de leitura (hipótese), estado lida ou não lida, e vínculo com o item relacionado.
- **NOT-04 Preferências:** o usuário personaliza **como é alertado** (o pop-up e o push), mas a notificação continua sendo registrada. Se o e-mail também pode ser desligado fica para o refinamento.
- **NOT-05 Privacidade:** cada usuário vê apenas as suas notificações.
- **NOT-06 Eventos que geram notificação:**
  - pedido aguardando aprovação (ao aprovador) e decisão sobre o pedido, com o motivo (ao solicitante);
  - cobrança nova, vencimento, atraso e decisão sobre questionamento (ao devedor);
  - pagamento aguardando validação (ao responsável) e resultado da validação (ao devedor);
  - recurso enviado e prestação de contas pendente;
  - evento na data para confirmar, cancelar ou marcar como realizado;
  - cadastro de diretor concluído (ao admin) e convite;
  - setor sem aprovador alternativo para um pedido pendente (ao admin, hipótese).
- **NOT-07 Tarefas agendadas:** vencimentos, cobranças recorrentes, expiração de convite (24 horas), fim de isenção e aviso do dia do evento rodam como tarefas agendadas em segundo plano.

## 10. Feed, documentos e perfil (COM, DOC, PRF)

O feed e os documentos são de uso dos diretores na etapa 1. O desenho é mínimo, e os detalhes ficam para o refinamento do marco (seção 15).

**Feed de comunicados**

- **COM-01** Tela própria onde usuários com permissão **postam comunicados e pautas**. Todos os diretores leem.
- **COM-02** Uma postagem pode **indexar documentos** da aba de documentos.
- **COM-03** A cada comunicado, a quem for definido, o sistema pode gerar notificação (hipótese).
- A definir: comentários, reações e fixar uma postagem no topo (o protótipo tinha a opção de fixar).

**Documentos**

- **DOC-01** Aba própria de documentos, com envio e consulta de arquivos.
- **DOC-02** Os documentos do feed e os da aba usam o mesmo repositório e a mesma regra de permissão.
- A definir: pastas ou categorias, acesso restrito por cargo, e atas de reunião (o protótipo tinha atas; o dono confirma se entram).

**Perfil do usuário**

- **PRF-01** Cada usuário tem uma área de perfil com seus dados, o **histórico de pagamentos** e os eventos relacionados a ele, e as suas notificações e preferências.
- **PRF-02** **Só o próprio usuário e o admin** vêem o perfil. Mesmo diretores com leitura total não veem o perfil dos outros.
- **PRF-03** O histórico do perfil consome os dados do financeiro e dos eventos, sem duplicar a informação.
- A definir: o que mais entra no perfil, como se registra a **participação em eventos** (presença confirmada, lista do organizador ou só eventos propostos) e se o usuário edita os próprios dados.

## 11. Dashboard, telas e relatórios (DSH, REL)

**Dashboard**

- **DSH-01** A tela principal é um **dashboard financeiro bonito e moderno**, com **números absolutos** de entradas e saídas. Concentra a maioria das informações, e as abas trazem o detalhe.
- **DSH-02** Conteúdo provavél (a refinar): totais do mês, saldo, pendências de aprovação e de validação, inadimplência, próximos eventos e últimos comunicados. Só conta como realizado o que foi validado.
- **DSH-03** O diretor sem cargo vê uma versão **básica**, sem muitos detalhes (o que entra nela fica para o refinamento).
- **DSH-04** O visual do protótipo (`frontend/`) é apenas ponto de partida de layout e estilo. O refinamento visual vem depois da base funcional.

**Telas da etapa 1**

- **DSH-05** Dashboard, Financeiro, Eventos (calendário e histórico), Feed, Documentos, Perfil, Notificações e Administração (usuários, convites, cargos, setores, categorias, permissões, regras de aprovação).
- **DSH-06** **Financeiro:** lista todas as transações, e cada uma abre o detalhe (descrição, comprovante, histórico de ações, prestação de contas). Hipótese: filtros por período, categoria, tipo e status.
- **DSH-07** **Eventos:** calendário com cards clicáveis para o detalhe, e feed de comunicados em tela própria.
- **DSH-08** Todos os diretores **veem** essas telas. As ações (adicionar, editar, cancelar, aprovar) dependem de permissão.

**Relatórios**

- **REL-01** O sistema **gera** relatórios em **PDF e CSV** (importação de CSV não está prevista).
- **REL-02** Conjunto inicial: extrato do mês e por período, balancete, inadimplência, eventos e prestação de contas. Novos relatórios podem ser pedidos depois, e a estrutura deve facilitar acrescentá-los.
- **REL-03** Cada relatório respeita as permissões: só exporta o que o usuário pode ver. Relatórios pesados rodam em segundo plano.
- **REL-04** O PDF leva o escudo e as cores do time (hipótese).

## 12. Personalização por time e auditoria (BRD, AUD)

**Personalização (white-label)**

Na etapa 1, white-label significa **só personalização visual**. O sistema nasce em branco e o cliente configura a identidade dele.

- **BRD-01** O sistema inicia **sem marca**. O cliente (no caso, o time do dono) **cadastra o escudo e as cores**.
- **BRD-02** O sistema aplica isso em toda a interface e oferece **algumas opções de tema** geradas a partir das cores base do cliente.
- **BRD-03** Os **ícones e símbolos** podem ser fixos, mas devem ser **customizáveis**, pois no futuro cada time pode ter a sua identidade e a sua base de dados.
- **BRD-04** A configuração de marca vem da API e vale para o site e, depois, para o app. Quem altera a marca é uma permissão do catálogo (hipótese: só o admin).
- **BRD-05** **Fora de escopo agora:** decidir se cada cliente terá um deploy próprio ou se será um SaaS com contas por cliente. Isso só se avalia quando for hora de escalar. O único cliente hoje é o time do dono. A arquitetura não deve fechar nenhuma das duas portas.

**Auditoria e rastreabilidade (transversal)**

- **AUD-01** **Toda ação relevante gera registro** imutável: quem, o quê, quando, sobre qual item e, quando houver, a justificativa.
- **AUD-02** Entram na auditoria: criação, edição, versão, aprovação, recusa, reabertura, cancelamento, estorno, liquidação, validação de pagamento, isenção, questionamento, convite, classificação de usuário, ativação e desativação, concessão e revogação de permissões, mudança de regras de aprovação, mudança de marca e exportação de relatórios (hipótese).
- **AUD-03** O histórico de cada item é consultável no próprio detalhe, por quem pode ver o item.
- **AUD-04** Nada é apagado: o que é desativado, cancelado ou estornado continua no histórico.

## 13. Requisitos não funcionais, stack e infraestrutura (RNF)

A premissa é **gastar o mínimo possível**. O volume de usuários é muito pequeno, então vale simplicidade e baixo consumo, e não escala.

**Stack preferida (familiar ao dono; o plugin confirma ou propõe)**

- **Backend:** Python. Framework entre **Django** (preferência, por familiaridade) e **FastAPI** (se couber melhor). Flask está fora.
- **Banco:** PostgreSQL. **Filas e tarefas agendadas:** Celery com Redis. **Contêineres:** Docker. **Nuvem:** AWS.
- **Frontend web:** livre para propor, com React como direção provável.
- **Mobile (etapa futura):** livre para propor. Comparar Kotlin, React Native e outras, com prós e contras. O dono tem pouco domínio de mobile e a construção será guiada por IA, então pesam produtividade, ecossistema e reaproveitamento com o web.
- **Arquitetura:** o plugin propõe. Pode ser hexagonal completa, Clean Architecture simplificada ou portas e adaptadores, conforme o que melhor couber ao tamanho real do projeto.

**Entrega e operação**

- **RNF-01 API única:** o núcleo é uma API que serve o site e, depois, o app. Regras de negócio, permissões e auditoria ficam nela, nunca nos clientes. API versionada e documentada.
- **RNF-02 Infra de custo mínimo:** tudo em **uma única instância AWS**, usando o **free tier pelo maior tempo possível**. Escalar fica para depois, e a arquitetura não deve impedir separar banco ou workers no futuro. O plugin verifica se o conjunto (API, PostgreSQL, Redis e workers) cabe na máquina, com configuração enxuta.
- **RNF-03 Docker:** tudo dockerizado, na medida do possível, com as mesmas imagens em desenvolvimento e produção.
- **RNF-04 CI/CD:** GitHub Actions, **desde que caiba no plano gratuito** (cache de dependências e imagens, jobs só quando necessário).
- **RNF-05 Ambientes:** apenas **local e produção**, sem homologação. Em troca, exigem-se testes automatizados sólidos nos fluxos críticos (aprovação, validação, permissões, recorrência), migrações reversíveis, imagens versionadas para rollback rápido e backup do banco antes de mudanças com dados. A premissa de rollback barato deve ser reavaliada se houver outros clientes ou dados de terceiros.
- **RNF-06 Armazenamento e e-mail baratos:** anexos (comprovantes, documentos) e envio de e-mails precisam caber no custo mínimo, com ponto de extensão para trocar de provedor (hipótese: armazenamento local ou S3 no free tier).
- **RNF-07 Segurança e dados pessoais:** os dados são financeiros e pessoais (nome, telefone, e-mail). Senhas com hash forte, tokens seguros, acesso a anexos controlado por permissão, e sem coletar CPF. O plugin avalia o que a LGPD exige para o caso.
- **RNF-08 Qualidade:** código testado, tipado quando a linguagem permitir, análise estática no CI, e decisões de arquitetura registradas.

## 14. Marcos do projeto

A etapa 1 tem 13 marcos (M0 a M12), na ordem de dependência. Cada marco passa pelo ciclo do SDD (especificar, planejar, tarefas, implementar, validar) e só termina com os critérios de aceite atendidos. O plano pode ser ajustado, desde que a mudança seja registrada.

| Marco | Entrega | Requisitos | Critério de aceite |
| --- | --- | --- | --- |
| M0 Arquitetura | O plugin avalia este enunciado e propõe arquitetura, stack, estrutura e repositório (novo ou reaproveitado), com decisões registradas | Seções 2, 13 e 15 | Decisões aprovadas pelo dono e especificações dos marcos seguintes geradas |
| M1 Fundação | Projeto, Docker, banco, CI no GitHub Actions, configuração por ambiente, esqueleto da API e do site | RNF-01 a 05, 08 | Subir tudo com um comando local e pipeline verde |
| M2 Identidade e acesso | Login Google e usuário/senha, verificação de e-mail, convite de 24 horas, cadastro, desativação | ACE-01 a 13 | Diretor convidado se cadastra, valida o e-mail e entra pelos dois modos |
| M3 Permissões e auditoria | Catálogo, três origens, cargos, setores, categorias, painel do admin, trilha de auditoria | PER-01 a 06, AUD-01 a 04 | Admin atribui permissões por cargo, setor e individual, e cada concessão fica auditada |
| M4 Notificações | Tarefas agendadas (Celery e Redis), e-mail, caixa de notificações no site, preferências de alerta | NOT-01 a 07 | Evento de teste gera registro, e-mail e item na caixa; usuário não desliga o registro |
| M5 Motor de aprovações | Solicitação genérica com versões, regras por setor, justificativas, reabertura, cancelamento e liquidação | APR-01 a 11 | Fluxos de aprovar, recusar, reabrir e editar aprovada passam nos testes, com solicitante nunca aprovando o próprio pedido sem permissão |
| M6 Financeiro: entradas | Categorias, cobranças únicas e recorrentes, mensalidade por diretor, validação, questionamento, isenção, atraso | FIN-01 a 12 | Cobrança recorrente é gerada sozinha, notificada, paga, validada e liquidada |
| M7 Financeiro: saídas | Solicitação de recurso, envio com comprovante, prestação de contas, estorno e cancelamento | FIN-13 a 18 | Ciclo completo de uma saída, da solicitação à liquidação, com histórico |
| M8 Eventos | Proposta, regras por tipo, calendário, histórico, encerramento e cancelamento | EVT-01 a 10 | Evento com custo exige o Financeiro, só aprovado aparece no calendário, editar o tira de lá |
| M9 Feed, documentos e perfil | Comunicados, aba de documentos, perfil privado | COM, DOC, PRF | Perfil só visível ao dono e ao admin; documentos acessíveis pelo feed |
| M10 Dashboard e relatórios | Dashboard completo e básico, listas e detalhes, relatórios em PDF e CSV | DSH-01 a 08, REL-01 a 04 | Números batem com os lançamentos validados e relatórios respeitam permissões |
| M11 Personalização | Cadastro de escudo e cores, temas derivados, ícones customizáveis | BRD-01 a 05 | Sistema nasce em branco e assume a identidade configurada em todas as telas e no PDF |
| M12 Produção | Deploy na AWS, backups, rollback, segurança, testes ponta a ponta, documentação, limpeza do protótipo antigo | RNF-02, 05, 07 | Sistema no ar na instância única, backup e rollback testados, resquícios do protótipo removidos |

**Etapas futuras (só documentadas, fora de M0 a M12)**

1. **Aplicativo mobile**, depois que o site estiver completo, com push e caixa de entrada.
2. **Torcedor e jogador:** novos tipos de usuário com cadastro aberto, visão e permissões próprias.
3. **Gestão do time** como um todo.
4. **Multi-cliente:** decidir entre um deploy por cliente ou SaaS com contas, quando for hora de escalar.

## 15. Decisões delegadas, hipóteses e pendências

**Decisões delegadas ao plugin (M0)**

- Arquitetura (hexagonal, Clean simplificada ou portas e adaptadores), estrutura de pastas e módulos.
- Framework final (Django ou FastAPI), frontend web e estratégia de autenticação com Google, usuário/senha e tokens para site e app.
- Modelagem das permissões (ação, recurso e escopo), do motor de aprovações, das versões de solicitação e da trilha de auditoria.
- Modelo de estornos e cancelamentos como lançamentos ligados ao original.
- Armazenamento de anexos, provedor de e-mail, desenho do pipeline de CI/CD e do deploy numa única instância.
- Repositório novo ou reaproveitamento do atual.
- O que o painel do admin cria sozinho e o que exige programação.
- Adequação à LGPD.

**Hipóteses assumidas (o dono corrige se estiverem erradas)**

- O admin é um perfil de gestão, e a conta de presidente é um cargo sem poderes especiais.
- Quem não foi convidado e entra pelo Google não acessa o sistema na etapa 1.
- O Google dispensa o link de verificação de e-mail.
- Regras de aprovação alteradas valem só para pedidos novos.
- Um evento com data corrigida na liquidação antecipada não reabre a aprovação.
- Categorias usadas são desativadas, e não apagadas.
- A cobrança questionada não conta como inadimplente até a decisão.
- O novo sistema começa vazio, sem migração de dados do protótipo.

**Pendências para o refinamento do marco correspondente**

- **M2:** login por nome de usuário ou por e-mail com a mesma senha; recuperação de senha; o diretor convidado pode aceitar o convite com outro e-mail do Google.
- **M3:** nomes e pacotes de permissões de cada cargo e setor; setores iniciais (Financeiro, Futebol, Eventos, Operacional) a confirmar; quem pode alterar a marca.
- **M4:** se o e-mail também pode ser desligado; reenvio de notificação quando ninguém confirma um evento após a data.
- **M5:** como tratar a diferença de valor quando uma solicitação é editada depois do recurso enviado ou da despesa paga.
- **M6:** quem valida entradas sem usuário (patrocínio, rifa); lembrete antes do vencimento; o que acontece com cobranças de um diretor desativado; recusa de comprovante volta a cobrança para pendente.
- **M7:** prazo da prestação de contas e cobrança automática; gasto real diferente do orçado.
- **M8:** evento sem custo precisa de aprovação por padrão; liquidação do evento depende da despesa ligada; participação em eventos.
- **M9:** comentários e fixar no feed; pastas e acesso nos documentos; atas de reunião; o que mais entra no perfil e se o usuário edita os próprios dados.
- **M10:** o que entra no dashboard básico; período exibido e saldo acumulado.
- **Transversal:** ordem de prioridade entre funcionalidades, se for preciso encurtar o escopo.

## 16. Referência: o repositório antigo

O repositório atual (`C:\projects_dro\Club-Manager`) pode ser **totalmente reescrito e até apagado**. O plugin decide, no M0, entre criar um repositório novo ou reaproveitar o mesmo, o que for mais barato. Em qualquer caso o protótipo é só base e consulta, e **todos os resquícios dele são removidos** até o M12.

**Uso permitido:** conferir se alguma funcionalidade foi esquecida neste enunciado. Nada de lá é requisito por si só.

**O que o protótipo tinha** (Django, DRF, PostgreSQL em Docker, login por e-mail e senha com JWT, backend em portas e adaptadores, frontend React com Vite):

- Setores (Financeiro, Futebol, Eventos, Operacional), receitas e despesas com categorias, comprovantes, aprovação de despesas, propostas de evento ligadas a despesa, atas de reunião e feed de notícias, e um PDF simples de fluxo de caixa.
- Telas: login, dashboard, financeiro, eventos e usuários.

**Itens do protótipo que este enunciado não cobre e o dono deve confirmar ou descartar no M0**

- Chave Pix e QR Code na cobrança, e recibo ao pagador depois de pago.
- Criação de cobranças em lote e status de cobrança cancelada (este enunciado já cobre o cancelamento).
- Fluxo de caixa com total previsto, realizado e inadimplência.
- Atas de reunião e postagem fixada no feed.
- Dados de seed: setores padrão e usuário admin inicial (o novo sistema deve ter um jeito seguro de criar o primeiro admin, sem senha padrão).
