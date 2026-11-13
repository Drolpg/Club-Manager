# Especificação Funcional: Catálogo de permissões, classificação e histórico

| Campo | Valor |
| --- | --- |
| Feature | `permissoes/catalogo-e-classificacao` |
| Status | Draft |
| Responsável | Leandro Nascimento |
| Atualizado em | 2026-11-13 |
| Aprovado por | — |
| Aprovado em | — |
| Requisitos | RF-015 a RF-027, RF-118; RN-005 a RN-008, RN-014; RF-001 e RF-002 (permissão de convidar) |
| Referências | Marco M3; canvas "Identidade e Permissões" e "Auditoria" em `docs/domain/strategic-design.md`; AD-007, AD-014; feature `acesso/identidade-e-acesso` |

## Problema e resultado esperado

Depois do M2, um diretor consegue entrar, mas fica parado em "aguardando classificação": o sistema ainda não sabe o
cargo dele, a que setores pertence, nem o que ele pode fazer. E o admin não tem como delegar nada: só ele age.

Depois desta feature:

- o admin mantém os cargos e os setores do clube e classifica cada diretor;
- o admin concede permissões a um cargo, a um setor ou a uma pessoa, e vê o que cada um tem e de onde vem;
- o sistema responde, para qualquer módulo, "este usuário pode fazer isto?" e "quem pode fazer isto?";
- quem pode ver um item consulta o histórico dele.

Os marcos seguintes só precisam declarar as suas permissões no catálogo e perguntar.

## Atores e cenários

Atores: admin; diretor sem cargo; diretor com cargo.

### 1. Manter cargos e setores

1. O admin abre a lista de cargos (ou de setores).
2. O admin cria um cargo, informando o nome.
3. O admin renomeia ou desativa um cargo.

O sistema nasce com os setores Financeiro, Futebol, Eventos e Operacional, e com os cargos Presidente,
Vice-presidente, Tesoureiro, Secretário e Diretor. Nenhum deles vem com permissão.

Falhas:

- **Nome repetido** (sem diferenciar maiúsculas): o sistema recusa.
- **Desativar um cargo ou setor que algum usuário ativo tem:** o sistema recusa e diz quantos usuários o têm. O
  admin reclassifica essas pessoas antes.
- Um cargo ou setor desativado some das opções de classificação e deixa de conceder permissões; pode ser reativado.

### 2. Classificar um diretor

1. O admin abre um diretor ativo na lista de usuários.
2. O admin escolhe um cargo e zero ou mais setores.
3. O sistema grava a classificação. O diretor deixa de ser "sem cargo" e passa a ler os dados de gestão.

Alternativas:

- **Reclassificar:** o admin troca o cargo ou os setores; vale na requisição seguinte do diretor.
- **Tirar o cargo:** o admin deixa o diretor sem cargo; ele volta a ver só o dashboard básico, e os setores são
  retirados junto.

Falha: classificar um usuário inativo, ou que aguarda verificação, é recusado.

### 3. Conceder e revogar permissões

1. O admin abre o catálogo, que lista as permissões que o sistema conhece, cada uma com uma descrição.
2. O admin concede uma permissão a um cargo, a um setor ou a um usuário.
3. Todos os usuários ativos daquele cargo ou setor passam a ter a permissão; a concessão individual vale só para a
   pessoa, mesmo que ela não pertença ao setor de onde a permissão costuma vir.
4. O admin revoga uma concessão; quem só a tinha por ali deixa de poder.

Falha: conceder duas vezes a mesma permissão ao mesmo alvo não cria duplicata; o sistema avisa que já existe.

### 4. Acesso total

O admin concede "acesso total" a um usuário. Ele passa a ter todas as permissões do catálogo, as de hoje e as que
vierem, menos duas coisas: a auto-aprovação, que é uma permissão à parte, e a administração de usuários, cargos,
setores e concessões, que é só do admin.

### 5. Ver o que cada um pode

- **Painel do admin:** para um usuário, o sistema mostra cada permissão que ele tem e todas as origens dela (por
  exemplo: "pelo cargo Tesoureiro" e "pelo setor Financeiro").
- **O próprio diretor:** na página inicial, vê o seu cargo, os seus setores e as suas permissões.

### 6. Convidar sem ser admin

A permissão "gerenciar convites" entra no catálogo. Quem a tem gera, lista, regenera e revoga convites, como o admin
fazia sozinho no M2.

### 7. Consultar o histórico de um item

1. Quem pode ver um item abre o detalhe dele.
2. O sistema mostra o histórico: quem fez o quê, quando e com que justificativa, do mais recente para o mais antigo.

Nesta feature, os itens com histórico são usuário, convite, cargo e setor, e quem pode vê-los é o admin (e, para
convites, quem tem a permissão de gerenciá-los). Os marcos seguintes acrescentam os seus itens.

### 8. Diretor sem cargo e diretor com cargo

- **Sem cargo:** continua vendo só a página "aguardando classificação".
- **Com cargo:** vê a página inicial com o cargo, os setores e as permissões. Os dados de gestão em si (financeiro,
  eventos, feed) chegam nos marcos seguintes; o que esta feature entrega é a regra de leitura que eles vão usar.

## Regras de negócio

| # | Regra | Requisito |
| --- | --- | --- |
| 1 | Só o admin cria, renomeia e desativa cargos e setores, classifica diretores e concede ou revoga permissões | RN-005, RF-015 a RF-020 |
| 2 | Um diretor tem no máximo um cargo e pode ter vários setores | RF-017 |
| 3 | Só se classifica usuário ativo; só se atribui cargo e setor ativos | RF-017 |
| 4 | Diretor sem cargo não tem setores e não lê dados de gestão | RF-024 |
| 5 | Diretor ativo com cargo lê os dados de gestão; escrever depende de permissão | RF-025 |
| 6 | Uma permissão é a combinação de uma ação e de um tipo de recurso. Não há escopo por setor | RF-021; decisão 3 |
| 7 | O catálogo é definido no código: o painel concede e revoga permissões conhecidas, mas não cria permissões novas | AD-014 |
| 8 | As permissões de um usuário são a união das concedidas ao cargo dele, aos setores dele e a ele mesmo | RF-021 |
| 9 | Cargo e setor desativados não concedem permissões | RF-015, RF-016 |
| 10 | Só usuário ativo tem permissões; desativar um usuário não apaga as concessões dele, que voltam a valer se ele for reativado | RN-004 |
| 11 | O admin tem todas as permissões, inclusive a de auto-aprovação | RN-005 |
| 12 | Acesso total dá todas as permissões do catálogo, menos a auto-aprovação; e nunca dá o que é só do admin (regra 1) | RF-023, RN-007 |
| 13 | Presidente é um cargo como os outros: sem concessão, não tem permissão nenhuma | RN-006 |
| 14 | Nomes de cargo e de setor são únicos, sem diferenciar maiúsculas | RF-015, RF-016 |
| 15 | Cargo ou setor que algum usuário ativo tem não pode ser desativado | Proposta P1 |
| 16 | Cargo, setor e concessão nunca são apagados: são desativados ou revogados, e o histórico fica | RN-014 |
| 17 | Criar, renomear, desativar e reativar cargo ou setor; classificar; conceder e revogar permissão; e conceder e revogar acesso total geram registro de auditoria | RF-026 |
| 18 | O histórico de um item é visível a quem pode ver o item | RF-027 |
| 19 | Mudança de classificação ou de concessão vale na requisição seguinte de quem foi afetado | RF-021 |

Catálogo desta feature:

| Permissão | O que permite | Concedida de início a |
| --- | --- | --- |
| Gerenciar convites | Gerar, listar, regenerar e revogar convites | Ninguém (o admin já pode) |
| Acesso total | Ver a regra 12 | Ninguém |

As permissões de auto-aprovação, financeiras e de eventos entram no catálogo nos marcos que as usam (M5 a M8), cada
uma já sugerida ao setor natural.

## Fora de escopo

| Item | Onde está |
| --- | --- |
| Permissões e pacotes financeiros, de aprovação e de eventos | M5 a M8; cada marco declara as suas |
| Auto-aprovação | M5, com o motor de aprovações |
| Permissão por setor do item (escopo) | Backlog; decisão 3 |
| Criar permissões novas pelo painel | Não previsto (AD-014): comportamento novo é programação |
| Categorias de entrada, de saída e de evento | M6 e M8 (RF-046, RF-084) |
| Dashboard básico e dados de gestão | M10 e marcos de cada área |
| Histórico dos próprios dados no perfil do diretor | M9 |
| Notificar o diretor de que foi classificado | M4 |
| Quem pode alterar a marca | M11 |

## Critérios de aceite

Cargos e setores:

- [ ] CA-01 Dado um sistema recém-instalado, então existem os quatro setores e os cinco cargos iniciais, todos
      ativos e sem nenhuma permissão concedida.
- [ ] CA-02 Dado um admin, quando ele cria um cargo (ou setor) com nome novo, então ele aparece na lista, ativo.
- [ ] CA-03 Dado um cargo (ou setor) existente, quando o admin cria ou renomeia outro com o mesmo nome em qualquer
      combinação de maiúsculas, então o sistema recusa.
- [ ] CA-04 Dado um cargo que nenhum usuário ativo tem, quando o admin o desativa, então ele some das opções de
      classificação e pode ser reativado.
- [ ] CA-05 Dado um cargo (ou setor) que um usuário ativo tem, quando o admin tenta desativá-lo, então o sistema
      recusa e informa quantos usuários o têm.
- [ ] CA-06 Dado um usuário que não é admin, quando ele tenta criar, renomear, desativar ou reativar cargo ou setor,
      então o sistema nega; listar cargos e setores é permitido a todo diretor com cargo.

Classificação:

- [ ] CA-07 Dado um diretor ativo sem cargo, quando o admin lhe atribui um cargo e dois setores, então ele passa a
      constar com cargo e com esses setores, e a lista de usuários mostra "com cargo".
- [ ] CA-08 Dado um diretor classificado, quando o admin troca o cargo ou os setores, então a mudança vale na
      requisição seguinte dele.
- [ ] CA-09 Dado um diretor classificado, quando o admin tira o cargo, então ele fica sem cargo e sem setores.
- [ ] CA-10 Dado um usuário inativo ou aguardando verificação, quando o admin tenta classificá-lo, então o sistema
      recusa.
- [ ] CA-11 Dado um cargo ou setor desativado, quando o admin tenta atribuí-lo, então o sistema recusa.
- [ ] CA-12 Dado um usuário que não é admin, quando ele tenta classificar alguém, então o sistema nega.

Permissões:

- [ ] CA-13 Dado um admin, quando ele abre o catálogo, então vê cada permissão com nome e descrição.
- [ ] CA-14 Dada uma permissão concedida a um cargo, então todo usuário ativo com esse cargo a tem, e quem não tem
      o cargo não a tem.
- [ ] CA-15 Dada uma permissão concedida a um setor, então todo usuário ativo desse setor a tem.
- [ ] CA-16 Dada uma permissão concedida a um usuário que não é do setor de onde ela costuma vir, então ele a tem.
- [ ] CA-17 Dado um usuário que tem a mesma permissão pelo cargo e por um setor, quando uma das duas concessões é
      revogada, então ele continua com a permissão; quando a outra é revogada, deixa de ter.
- [ ] CA-18 Dada uma permissão concedida a um cargo ou setor que depois é desativado, então quem a tinha só por ali
      deixa de ter.
- [ ] CA-19 Dado um usuário desativado com concessão individual, então ele não tem permissão nenhuma; reativado,
      volta a ter.
- [ ] CA-20 Dado um admin, então ele tem todas as permissões do catálogo sem nenhuma concessão.
- [ ] CA-21 Dado um usuário com acesso total, então ele tem todas as permissões do catálogo que não são a
      auto-aprovação, e continua sem poder administrar usuários, cargos, setores e concessões.
- [ ] CA-22 Dado um diretor com o cargo Presidente e nenhuma concessão, então ele não tem permissão nenhuma.
- [ ] CA-23 Dada a mesma permissão concedida duas vezes ao mesmo alvo, então existe uma concessão só.
- [ ] CA-24 Dado um usuário que não é admin, quando ele tenta conceder ou revogar permissão ou acesso total, então
      o sistema nega.
- [ ] CA-25 Dado um admin, quando ele consulta um usuário no painel, então vê cada permissão dele com todas as
      origens (cargo, cada setor, individual, acesso total).
- [ ] CA-26 Dado um diretor, quando ele abre a página inicial, então vê o próprio cargo, setores e permissões, e
      não vê os de outra pessoa.

Uso das permissões:

- [ ] CA-27 Dado um diretor com a permissão de gerenciar convites, então ele gera, lista, regenera e revoga
      convites; sem a permissão, o sistema nega.
- [ ] CA-28 Dado um diretor ativo sem cargo, quando o sistema pergunta se ele lê os dados de gestão, então a
      resposta é não; com cargo, é sim; inativo, é não.

Histórico e auditoria:

- [ ] CA-29 Dada cada ação da regra 17, quando ela acontece, então existe um registro de auditoria com quem, o quê,
      quando e sobre qual item.
- [ ] CA-30 Dado um admin, quando ele abre o detalhe de um usuário, convite, cargo ou setor, então vê o histórico do
      item, do mais recente para o mais antigo, com o nome de quem fez cada ação.
- [ ] CA-31 Dado um usuário que não pode ver um item, quando ele pede o histórico desse item, então o sistema nega.
- [ ] CA-32 Dado qualquer cargo, setor ou concessão, então não existe caminho para apagá-lo: só desativar ou revogar.

## Decisões registradas nesta spec

| # | Decisão | Quem decidiu | Data |
| --- | --- | --- | --- |
| 1 | O sistema nasce com os setores Financeiro, Futebol, Eventos e Operacional | Leandro Nascimento | 2026-11-13 |
| 2 | O sistema nasce com os cargos Presidente, Vice-presidente, Tesoureiro, Secretário e Diretor | Leandro Nascimento | 2026-11-13 |
| 3 | Permissão é ação mais recurso, sem escopo por setor do item | Leandro Nascimento | 2026-11-13 |
| 4 | Cada marco acrescenta as suas permissões ao catálogo e já as sugere ao setor natural | Leandro Nascimento | 2026-11-13 |

Propostas do agente, que passam a valer com a aprovação desta spec:

| # | Proposta | Motivo |
| --- | --- | --- |
| P1 | Cargo ou setor em uso por usuário ativo não pode ser desativado (regra 15) | Evita diretores "com cargo" que na prática não têm cargo válido; o admin reclassifica primeiro |
| P2 | Tirar o cargo de um diretor também tira os setores dele (regra 4) | Sem cargo ele não lê nada; manter setores só confundiria o painel |
| P3 | Acesso total é uma concessão individual especial, e não torna a pessoa admin (regra 12) | É o que o enunciado descreve (PER-06) e mantém a regra de que só o admin gerencia usuários e concessões |
| P4 | O catálogo fica no código; o painel só concede e revoga (regra 7) | Resolve a AD-014: uma permissão sem código que a confira não faz nada |
| P5 | O diretor vê as próprias permissões na página inicial (cenário 5, RF-118) | Ele precisa saber o que pode fazer sem perguntar ao admin |
| P6 | Todo diretor com cargo pode listar cargos e setores; só o admin os altera | São dados de gestão, sem nada sensível |
| P7 | Nenhuma permissão é concedida de início nesta feature | A única do catálogo agora é a de convites, que o enunciado deixa com o admin por padrão |
| P8 | O histórico dos itens desta feature é visível só ao admin (e os convites, a quem os gerencia) | São itens de administração; o histórico dos itens de negócio segue a regra de cada marco |

## Adendos

Nenhum.
