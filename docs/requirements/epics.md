# Épicos

| Campo | Valor |
| --- | --- |
| Status | Approved |
| Atualizado em | 2026-11-11 |
| Aprovado por / em | Leandro Nascimento / 2026-11-11 |

Os épicos são os marcos da seção 14 do enunciado. O projeto é solo, então todos têm o mesmo dono e são feitos um por
vez, na ordem de dependência. Cada épico é quebrado em features pequenas na hora de especificar
(`docs/features/<contexto>/<slug>/`).

## Épicos

| Épico | Objetivo | RFs | Contextos / aggregates | Dono |
| --- | --- | --- | --- | --- |
| M1 — Fundação | Projeto, contêineres, banco, CI, esqueleto da API e do site | RNF-01 a RNF-05, RNF-08, RNF-09 | Todos os módulos, vazios | Leandro |
| M2 — Identidade e acesso | Convite, cadastro, login, verificação, desativação | RF-001 a RF-014 | Identidade e Permissões (`acesso`) | Leandro |
| M3 — Permissões e auditoria | Cargos, setores, concessões, painel do admin, trilha de auditoria | RF-015 a RF-027 | Identidade e Permissões (`permissoes`), Auditoria | Leandro |
| M4 — Notificações | Registro, e-mail, caixa de entrada, preferências, agendador | RF-028 a RF-032, RNF-10 | Notificações | Leandro |
| M5 — Motor de aprovações | Solicitação com versões, decisões, motivos, fila | RF-033 a RF-045 | Aprovações: Solicitação | Leandro |
| M6 — Financeiro: cobrança e recebimento | Cobranças, recorrência, Pix, validação, inadimplência, entradas | RF-046 a RF-072 | Financeiro: Cobrança, Recorrência, Suspensão, Renegociação, Entrada | Leandro |
| M7 — Financeiro: gasto e prestação de contas | Solicitação de gasto, envio, prestação, devolução, liquidação, estorno | RF-073 a RF-083 | Financeiro: Saída, Entrada (devolução) | Leandro |
| M8 — Eventos | Proposta, orçamento, calendário, realização, cancelamento | RF-084 a RF-093 | Eventos: Evento | Leandro |
| M9 — Comunicação e perfil | Feed, documentos, atas, perfil | RF-094 a RF-101 | Comunicação; Relatórios (perfil) | Leandro |
| M10 — Dashboard e relatórios | Dashboards, lista de transações, relatórios em PDF e CSV | RF-102 a RF-111 | Relatórios | Leandro |
| M11 — Personalização | Escudo, cores, temas, ícones | RF-112 a RF-115 | Marca | Leandro |
| M12 — Produção | Deploy, backup, rollback, segurança, testes de ponta a ponta, limpeza do protótipo | RNF-02, RNF-05, RNF-07, RNF-14 | Infraestrutura | Leandro |

O M0 (arquitetura) corresponde aos ritos 0 a 6 do método e termina com a aprovação deste registro.

### M5 — Motor de aprovações

É o épico que mais mudou em relação ao enunciado. Não há aprovação por vários setores: cada solicitação tem um
aprovador por versão, e o que exige duas decisões são duas solicitações ligadas. Em troca entraram a contestação com
teto sugerido, a lista de motivos de decisão e a indicação de aprovador com aviso ao admin.

As regras mais críticas são as invariantes INV-SOL-01 a INV-SOL-11, em especial a de que ninguém decide o próprio
pedido. O épico entrega o motor com um tipo de solicitação de teste; os tipos reais (gasto, orçamento, evento) entram
no M7 e no M8.

### M6 — Financeiro: cobrança e recebimento

É o maior épico: 27 requisitos. Cresceu com o limite de inadimplência, a convocação, o perdão, a renegociação em
parcelas, a suspensão, as chaves Pix e o recibo. Para caber em entregas pequenas, a especificação o divide em
features, nesta ordem sugerida:

1. Categorias, chaves Pix e cobrança avulsa, com Pix copia e cola e QR Code (RF-046 a RF-049, RF-052, RF-053, RF-065).
2. Pagamento, validação, rejeição e recibo (RF-054 a RF-059).
3. Recorrência, geração automática e suspensão (RF-050, RF-051, RF-064).
4. Atraso, questionamento e isenção (RF-060 a RF-063).
5. Inadimplência: convocação, perdão, renegociação (RF-066 a RF-070).
6. Entradas sem devedor (RF-071, RF-072).

O critério de aceite do enunciado (cobrança recorrente gerada sozinha, notificada, paga, validada e encerrada) é
atendido ao fim da feature 3.

### M7 — Financeiro: gasto e prestação de contas

Registra a solicitação de gasto como tipo no motor do M5 e implementa a saída. A regra mais delicada é a liquidação
(INV-SAI-05): só com a diferença acertada, por devolução validada ou complemento aprovado. O estorno (RF-083) depende
da decisão AD-010.

### M8 — Eventos

Registra a solicitação de evento como tipo no motor e liga o evento à solicitação orçamentária do M7. O estado do
evento é derivado das duas solicitações por uma função só (`situacao_do_evento`).

## Mapa de dependências

| Épico dependente | Depende de | Natureza | Como destravar sem esperar |
| --- | --- | --- | --- |
| M2 | M1 | Projeto, banco e CI | Não se aplica: sequência |
| M3 | M2 | Usuários para receber cargos, setores e concessões | Não se aplica: sequência |
| M4 | M2, M3 | Destinatários e a consulta "quem pode fazer?" | Não se aplica: sequência |
| M5 | M3, M4 | Permissão de aprovar; notificação de decisão; auditoria | Não se aplica: sequência |
| M6 | M3, M4, M5 (só os motivos de decisão) | Validação de pagamento usa motivos de decisão e permissões | A feature 1 do M6 não depende do M5 |
| M7 | M5, M6 | Solicitação de gasto é um tipo do motor; a devolução é uma entrada | Não se aplica: sequência |
| M8 | M5, M7 | Solicitação do evento e solicitação orçamentária | Evento sem custo só depende do M5 |
| M9 | M3, M4 | Permissão de publicar; notificação de comunicado | Pode ser feito logo depois do M4, se convier |
| M10 | M6, M7, M8, M9 | Lê os dados dos outros contextos | O dashboard básico só depende do M3 |
| M11 | M3 | Permissão de alterar a marca | Pode ser feito logo depois do M3; o PDF com marca depende do M10 |
| M12 | Todos | Sistema completo | A infraestrutura de deploy pode ser ensaiada a partir do M1 |

A ordem do enunciado (M0 a M12) respeita todas as dependências. As colunas "como destravar" só registram onde há
liberdade para reordenar, caso o dono queira ver algo antes.

## Contratos a combinar primeiro

O projeto é solo, então não há trabalho em paralelo a coordenar. Os contratos abaixo são os que mais de um épico
consome; cada um é fixado na technical-spec do épico que o cria e não muda sem decisão registrada.

| Contrato | Dono | Consumidores | Combinado em |
| --- | --- | --- | --- |
| API pública de permissões: "pode fazer?", "quem pode fazer?" | M3 | M4 a M11 | Technical-spec do M3 |
| API pública de auditoria: registrar ação, consultar histórico | M3 | Todos | Technical-spec do M3 |
| API pública de notificações: notificar usuários sobre um item | M4 | M5 a M9 | Technical-spec do M4 |
| Registro de tipo de solicitação e eventos de decisão (`SolicitacaoAprovada` etc.) | M5 | M7, M8 | Technical-spec do M5 (AD-008) |
| Catálogo de motivos de decisão | M5 | M6, M7, M8 | Technical-spec do M5 |
| Abertura de solicitação orçamentária para um evento | M7 | M8 | Technical-spec do M7 |
| Consultas públicas de cada contexto | M6 a M9 | M10 | Technical-spec de cada épico |
| Configuração de marca | M11 | M10 (PDF), site | Technical-spec do M11 |
