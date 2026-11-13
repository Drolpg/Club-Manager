# Backlog

Ideias e evoluções deixadas fora do escopo atual. Não é dívida técnica (desvio que já existe no código) nem decisão
em aberto (escolha que bloqueia trabalho).

## Etapas futuras do enunciado

| Item | Origem | Por que ficou fora | Gatilho para retomar | Registrado em |
| --- | --- | --- | --- | --- |
| Aplicativo mobile, com push e caixa de entrada | Seção 3, NOT-02 | Só depois de o site estar completo | M12 concluído; novo enunciado de fase; comparar tecnologias (AD-017) | 2026-11-11 |
| Torcedor e jogador, com cadastro aberto e permissões próprias | Seção 3 | Etapa 1 é só para diretores | Novo enunciado de fase | 2026-11-11 |
| Gestão do time como um todo | Seção 3 | Além da governança financeira e institucional | Novo enunciado de fase | 2026-11-11 |
| Multi-cliente: deploy por cliente ou SaaS com contas | BRD-05 | Só se decide quando for hora de escalar | Segundo cliente real (AD-018) | 2026-11-11 |
| Recebimento automático por plataforma de pagamento | Seção 3 | Só o ponto de extensão é previsto; os valores são escriturais | Decisão do dono de integrar | 2026-11-11 |
| Importação de CSV | REL-01 | Não prevista | Pedido do dono | 2026-11-11 |

## Ideias surgidas na descoberta

| Item | Origem | Por que ficou fora | Gatilho para retomar | Registrado em |
| --- | --- | --- | --- | --- |
| Aprovação de uma mesma solicitação por dois ou mais setores | APR-03, APR-04; H16 | O dono preferiu um aprovador por solicitação; casos com duas decisões são duas solicitações ligadas | Primeiro caso real que não caiba em solicitações ligadas | 2026-11-11 |
| Votação de diretores para decidir questionamentos ou dívidas | H18 | Decide quem tem a permissão | Pedido do dono | 2026-11-11 |
| Confirmação, no sistema, de quem recebeu dinheiro em mão | H05 | O validador consulta por fora | Disputa sobre um recebimento em mão | 2026-11-11 |
| Confirmação do admin antes de uma indicação de aprovador valer | H26 | Basta histórico e aviso ao admin | Abuso da indicação | 2026-11-11 |
| Pagamento parcial de uma cobrança | Canvas Cobrança | Não foi pedido; a renegociação em parcelas cobre o caso | Pedido do dono no refinamento do M6 | 2026-11-11 |
| Envio do recurso em mais de uma transferência | Canvas Saída | Não foi pedido | Pedido do dono no refinamento do M7 | 2026-11-11 |
| Comentários e reações no feed | Seção 10 | "A definir" no enunciado; decidir no refinamento do M9 | Refinamento do M9 | 2026-11-11 |
| Pastas, categorias e acesso restrito por cargo nos documentos | Seção 10 | "A definir" no enunciado; decidir no refinamento do M9 | Refinamento do M9 | 2026-11-11 |
| Registro de participação em eventos | Seção 10, pendência do M8 | "A definir" no enunciado | Refinamento do M8 | 2026-11-11 |
| Notificações em tempo real; preferência por tipo de notificação; resumo diário por e-mail | Spec `notificacoes/caixa-e-email` | O dono escolheu a consulta a cada minuto e uma chave só | Pedido do dono | 2026-11-13 |
| Prazos de lembrete de solicitação configuráveis; trocar o aprovador indicado depois do envio | Spec `aprovacoes/motor-de-solicitacoes` | Prazos fixos e admin como saída bastam para começar | Pedido do dono | 2026-11-13 |
| Juros e multa em cobrança atrasada | Spec `financeiro/cobrancas-e-recebimentos` | Não pedido | Pedido do dono | 2026-11-13 |
| Bloquear novos pedidos de quem tem prestação de contas atrasada; reembolso de gasto sem pedido prévio | Spec `financeiro/gastos-e-prestacao-de-contas` | Não pedido | Pedido do dono | 2026-11-13 |
| Evento recorrente; lista de presença marcada pelo organizador; lembrete a quem confirmou presença; aprovação diferente por categoria de evento | Spec `eventos/eventos-e-calendario` | Fora do mínimo escolhido pelo dono | Pedido do dono | 2026-11-13 |
