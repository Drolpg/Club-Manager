# Especificação Funcional: Notificações, com caixa de entrada e e-mail

| Campo | Valor |
| --- | --- |
| Feature | `notificacoes/caixa-e-email` |
| Status | Approved |
| Responsável | Leandro Nascimento |
| Atualizado em | 2026-11-13 |
| Aprovado por | Leandro Nascimento |
| Aprovado em | 2026-11-13 |
| Requisitos | RF-028 a RF-032, RF-013 (passa a ser notificação), RF-119; RN-009; RNF-10 |
| Referências | Marco M4; canvas "Notificações" em `docs/domain/strategic-design.md`; ADR-003, ADR-006; AD-012; features `acesso/identidade-e-acesso` e `permissoes/catalogo-e-classificacao` |

## Problema e resultado esperado

Hoje o sistema avisa as pessoas só por e-mails soltos, sem registro: não há como provar que alguém foi avisado, e o
diretor que não abre o e-mail não fica sabendo de nada ao entrar no site.

No Club Manager, uma notificação é o **registro de que o usuário foi avisado** de algo. Depois desta feature:

- qualquer módulo pede "avise estas pessoas sobre este item", e o sistema registra, mostra na caixa do site e envia
  por e-mail;
- cada diretor tem uma caixa de entrada com indicador de não lidas;
- o diretor ajusta como quer ser alertado, sem conseguir desligar o registro;
- os marcos seguintes (aprovações, financeiro, eventos) só declaram os seus tipos de notificação e pedem o envio.

## Atores e cenários

Atores: diretor (qualquer usuário ativo); admin; o sistema, que gera as notificações.

### 1. Ser notificado

1. Algo acontece no sistema (por exemplo, um diretor conclui o cadastro).
2. O sistema registra uma notificação para cada destinatário, com o tipo, um título, um texto curto e o vínculo com
   o item.
3. A notificação aparece na caixa de cada destinatário e o indicador de não lidas aumenta.
4. O sistema envia um e-mail a cada destinatário, conforme o tipo e as preferências dele.

Falha: se o e-mail não puder ser enviado, a notificação continua registrada e na caixa; o sistema tenta o envio de
novo, e a falha definitiva fica anotada na notificação.

### 2. Ver a caixa de entrada

1. O diretor vê, em qualquer tela, um ícone com a quantidade de notificações não lidas.
2. Ao clicar, abre a caixa: as notificações dele, da mais recente para a mais antiga, com as não lidas destacadas.
3. A caixa carrega as mais antigas sob demanda.

Com o site aberto, o indicador se atualiza sozinho a cada minuto.

### 3. Ler uma notificação

1. O diretor clica numa notificação.
2. O sistema a marca como lida, guardando a data e a hora, e leva o diretor ao item relacionado.

Alternativa: o botão "marcar todas como lidas" marca de uma vez todas as não lidas dele.

### 4. Ajustar as preferências

O diretor liga ou desliga duas coisas:

- **Aviso na tela:** o aviso flutuante que aparece quando chega uma notificação com o site aberto.
- **E-mail de avisos informativos:** os e-mails das notificações que não pedem nenhuma ação dele.

As duas nascem ligadas. Nenhuma preferência desliga o registro, a caixa, o indicador nem o e-mail das notificações
que pedem uma ação.

### 5. Notificações que esta feature já entrega

| Quando | Quem é avisado | Pede ação? |
| --- | --- | --- |
| Um diretor conclui o cadastro | Todos os admins ativos | Sim: classificar |
| O admin classifica, reclassifica ou tira o cargo de um diretor | O diretor | Não |
| Um usuário ganha ou perde o papel de admin | O usuário | Não |
| Um usuário ganha ou perde uma permissão individual ou o acesso total | O usuário | Não |

A primeira substitui o e-mail simples que o M2 mandava aos admins. As notificações de aprovação, de cobrança, de
pagamento, de prestação de contas e de evento entram nos marcos que as geram.

## Regras de negócio

| # | Regra | Requisito |
| --- | --- | --- |
| 1 | Toda notificação é registrada; nenhum usuário desliga o registro | RN-009 |
| 2 | Cada usuário vê, lê e marca só as próprias notificações; nem o admin vê as dos outros | RN-009 |
| 3 | Uma notificação nunca é alterada nem apagada; só ganha a data de leitura e o resultado do envio | RN-014 |
| 4 | Cada tipo de notificação é declarado no código pelo módulo que o gera, e diz se pede ação ou é informativo | Decisão 1 |
| 5 | A notificação que pede ação sempre vai por e-mail | Decisão 1 |
| 6 | A notificação informativa vai por e-mail, a menos que o destinatário tenha desligado os e-mails informativos | Decisão 1 |
| 7 | Só usuário ativo recebe notificação nova. As antigas de um usuário desativado continuam guardadas | RN-004 |
| 8 | A notificação é registrada na mesma transação do fato que a gerou; o e-mail sai depois, pela fila | ADR-003 |
| 9 | A notificação fica lida quando o destinatário a abre, ou usa "marcar todas como lidas"; a data e a hora ficam registradas e não mudam mais | RF-031; decisão 4 |
| 10 | A notificação guarda o vínculo com o item; se o destinatário perdeu o acesso ao item, o sistema mostra a notificação, mas nega o item | RF-028 |
| 11 | O mesmo fato não gera duas notificações iguais para a mesma pessoa, mesmo que a tarefa que o gera rode duas vezes | RNF-10 |
| 12 | O texto da notificação e do e-mail não traz dado sensível além do necessário para entender o aviso; valores e detalhes ficam no item | RNF-07 |
| 13 | O e-mail traz um link para o item no site; não traz link que entre sem login | RNF-07 |

## Fora de escopo

| Item | Onde está |
| --- | --- |
| Notificações de aprovação, financeiro, eventos e comunicados | M5 a M9; cada marco declara os seus tipos |
| Push no celular e aba de notificações do aplicativo | Etapa futura (NOT-02); o desenho já prevê um terceiro canal |
| Tempo real (sem a espera de até um minuto) | Backlog; decisão 2 |
| Preferência por tipo de notificação | Backlog; decisão 3 |
| Resumo diário por e-mail | Não pedido; backlog |
| Reenvio quando ninguém confirma um evento depois da data | M8 |
| Apagar ou arquivar notificações | Não previsto: a notificação é um registro |

## Critérios de aceite

Registro e entrega:

- [ ] CA-01 Dado um fato que gera notificação para dois usuários ativos, então existem duas notificações, uma para
      cada um, com tipo, título, texto, item relacionado e data de criação.
- [ ] CA-02 Dado um destinatário inativo, então nenhuma notificação nova é criada para ele.
- [ ] CA-03 Dada uma notificação que pede ação, então o e-mail é enviado mesmo que o destinatário tenha desligado
      os e-mails informativos.
- [ ] CA-04 Dada uma notificação informativa, quando o destinatário desligou os e-mails informativos, então nenhum
      e-mail é enviado, e a notificação existe na caixa dele.
- [ ] CA-05 Dada uma notificação criada, então o e-mail só é enfileirado depois de a transação ser confirmada; se a
      transação for desfeita, não há notificação nem e-mail.
- [ ] CA-06 Dado um e-mail que falha ao ser enviado, então a notificação continua na caixa, o envio é tentado de
      novo, e a falha definitiva fica registrada na notificação.
- [ ] CA-07 Dado o mesmo fato processado duas vezes, então cada destinatário tem uma notificação só.
- [ ] CA-08 Dado um e-mail de notificação, então ele traz o título, o texto e um link para o item no site, e não
      traz link que dispense o login.

Caixa de entrada:

- [ ] CA-09 Dado um usuário com notificações, quando ele abre a caixa, então vê só as dele, da mais recente para a
      mais antiga, cada uma marcada como lida ou não lida.
- [ ] CA-10 Dado um usuário, quando ele consulta o indicador, então recebe a quantidade de não lidas dele.
- [ ] CA-11 Dado um usuário, quando ele abre uma notificação, então ela fica lida, com data e hora, e a quantidade
      de não lidas diminui.
- [ ] CA-12 Dada uma notificação já lida, quando ela é aberta de novo, então a data da primeira leitura não muda.
- [ ] CA-13 Dado um usuário com várias não lidas, quando ele usa "marcar todas como lidas", então todas as dele
      ficam lidas, e as de outros usuários não mudam.
- [ ] CA-14 Dado um usuário, quando ele tenta ver, abrir ou marcar a notificação de outro, então o sistema responde
      que ela não existe; isso vale também para o admin.
- [ ] CA-15 Dada uma caixa com mais notificações do que cabem numa página, então o usuário consegue carregar as
      seguintes.

Preferências:

- [ ] CA-16 Dado um usuário novo, então o aviso na tela e os e-mails informativos estão ligados.
- [ ] CA-17 Dado um usuário, quando ele altera as preferências, então só as dele mudam, e a mudança vale para as
      próximas notificações.
- [ ] CA-18 Dado um usuário com o aviso na tela desligado, então o site não mostra o aviso flutuante, e o indicador
      de não lidas continua aparecendo.
- [ ] CA-19 Dado qualquer usuário, então não existe preferência, rota ou ação que impeça uma notificação de ser
      registrada.

Notificações desta feature:

- [ ] CA-20 Dado um diretor que conclui o cadastro (por senha ou pelo Google), então todo admin ativo recebe uma
      notificação que pede ação, com vínculo para o usuário, e o e-mail simples do M2 deixa de existir.
- [ ] CA-21 Dado um diretor classificado, reclassificado ou que perdeu o cargo, então ele recebe uma notificação
      informativa dizendo o cargo e os setores atuais.
- [ ] CA-22 Dado um usuário que ganha ou perde o papel de admin, uma permissão individual ou o acesso total, então
      ele recebe uma notificação informativa.

Site:

- [ ] CA-23 Dado um usuário logado, então toda tela mostra o ícone com a quantidade de não lidas, que se atualiza
      sozinha em até um minuto.
- [ ] CA-24 Dada a chegada de uma notificação com o site aberto e o aviso na tela ligado, então o aviso flutuante
      aparece.

## Decisões registradas nesta spec

| # | Decisão | Quem decidiu | Data |
| --- | --- | --- | --- |
| 1 | O usuário pode desligar só o e-mail das notificações informativas; as que pedem ação sempre vão por e-mail | Leandro Nascimento | 2026-11-13 |
| 2 | O site consulta as notificações a cada minuto; sem tempo real | Leandro Nascimento | 2026-11-13 |
| 3 | O aviso na tela tem uma chave só, liga ou desliga | Leandro Nascimento | 2026-11-13 |
| 4 | A notificação fica lida ao ser aberta; há o botão "marcar todas como lidas" | Leandro Nascimento | 2026-11-13 |

Propostas do agente, aprovadas pelo dono junto com esta spec, em 2026-11-13:

| # | Proposta | Motivo |
| --- | --- | --- |
| P1 | Nem o admin vê as notificações de outro usuário (regra 2) | É o que o enunciado pede (NOT-05); o admin audita pelos históricos dos itens |
| P2 | Usuário inativo não recebe notificação nova (regra 7) | Ele não entra no sistema; e-mail para quem saiu do clube seria um vazamento |
| P3 | O e-mail leva ao item, mas exige login (regra 13) | Um link que entra sozinho viraria uma chave de acesso circulando por e-mail |
| P4 | Além do cadastro concluído, esta feature já notifica classificação, papel de admin e permissões individuais (cenário 5) | São os fatos que já existem e interessam a quem é afetado; servem de prova real do mecanismo |
| P5 | O texto da notificação é curto e sem valores (regra 12) | E-mail não é canal seguro; o detalhe fica no sistema, atrás do login |
| P6 | Falha de e-mail não desfaz nada: a notificação vale pela caixa (cenário 1) | O registro é a notificação; o e-mail é um canal |

## Adendos

Nenhum.
