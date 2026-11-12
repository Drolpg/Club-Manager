# Hotspots

Todo hotspot termina com um destino. Hotspot sem destino bloqueia o gate da descoberta (rito 3).

## Abertos ou encaminhados

| ID | Hotspot | Etapa | Tipo | Destino | Dono | Status |
| --- | --- | --- | --- | --- | --- | --- |
| H11 | Limite de tempo de inadimplência, convocação, perdão, renegociação em parcelas e suspensão não estão no enunciado | Storytelling, história 4 | Risco (escopo) | Registro de requisitos (rito 6), como mudança do plano | Leandro | Resolvido (RF-048, RF-064, RF-066 a RF-070) |
| H23 | "Cada solicitação tem um só validador; evento com custo gera duas solicitações" contradiz APR-03, APR-04 e EVT-02 do enunciado (uma solicitação aprovada por vários setores) | Storytelling, história 8 | Conflito | Registro de requisitos (rito 6), como mudança do plano; AD-008 | Leandro | Resolvido (RN-010, RN-020, CB-03) |
| H25 | Notificar todos os diretores quando um evento é aprovado e quando é cancelado não está em NOT-06 | Storytelling, história 9 | Risco (escopo) | Registro de requisitos (rito 6), como requisito novo | Leandro | Resolvido (RF-087, RF-093) |
| H26 | O aprovador que decidiria o próprio pedido pode indicar qualquer diretor para aprová-lo (H19). Risco de governança: a indicação pode ser usada para escolher um aprovador conveniente. O enunciado já pede que a aprovação própria apareça de forma explícita no histórico (APR-02) | Linha do tempo | Risco | Caso de borda no rito 6: propor ao dono que a indicação fique explícita no histórico e gere aviso ao admin | Leandro | Resolvido (RF-035, CB-02) |
| H27 | Evento sem custo precisa sempre da aprovação do responsável de eventos? (pendência do M8 no enunciado) | Linha do tempo | Dúvida | Refinamento do M8 | Leandro | Encaminhado |
| H28 | Orçamento negado em definitivo deixa o evento parado, fora do calendário. Quem o cancela, e há prazo? | Linha do tempo | Dúvida | Refinamento do M8 | Leandro | Encaminhado |
| H29 | As demais pendências e hipóteses da seção 15 do enunciado que as histórias não tocaram (lembrete antes do vencimento, cobranças de diretor desativado, prazo da prestação de contas, quem valida entradas sem usuário) | — | Dúvida | Refinamento do marco correspondente (M2 a M10) | Leandro | Encaminhado |
| H30 | Itens do protótipo ainda sem resposta: cobranças em lote, fluxo de caixa previsto e realizado, atas de reunião, postagem fixada | — | Dúvida | AD-016, perguntar no rito 6 | Leandro | Resolvido (CB-01) |

## Resolvidos

| ID | Resolução | Onde ficou registrada | Data |
| --- | --- | --- | --- |
| — | Pix copia e cola e QR Code na cobrança entram na etapa 1 (item da AD-016 confirmado) | `domain-storytelling.md`, história 1 | 2026-11-11 |
| H01 | O admin cadastra várias chaves Pix; cada cobrança ou categoria aponta para uma delas, e o QR Code leva o valor | Resposta do dono | 2026-11-11 |
| H02 | O diretor registra o pagamento, anexa o comprovante e sinaliza o envio; o pagamento fica em processamento até o responsável aprovar | História 2 | 2026-11-11 |
| H03 | O sistema emite recibo em PDF ao pagador, a partir da cobrança paga (item da AD-016 confirmado) | Resposta do dono | 2026-11-11 |
| H04 | Os motivos de decisão são uma lista cadastrada pelo admin; quem decide escolhe um e pode acrescentar texto livre | Resposta do dono | 2026-11-11 |
| H05 | No dinheiro em mão, quem recebeu tem de ser um usuário do sistema, escolhido pelo pagador; o aprovador o consulta por fora | Resposta do dono | 2026-11-11 |
| H06 | Pagamento reprovado com justificativa: fica registrado e o devedor é notificado para refazer. Atraso: ao fim do limite de inadimplência, o devedor é convocado e os responsáveis decidem | Histórias 3 e 4 | 2026-11-11 |
| H07 | A lista de motivos vale para toda decisão do sistema, por tipo de decisão, e não só para a aprovação de pagamento. Altera APR-05 (que previa só texto) | Resposta do dono | 2026-11-11 |
| H08 | Perdão é um terceiro desfecho da cobrança, com estado próprio, separado de isenta e de cancelada | Resposta do dono | 2026-11-11 |
| H09 | Na renegociação, a cobrança original é encerrada e nascem parcelas, cada uma com seu vencimento, ligadas à original | Resposta do dono | 2026-11-11 |
| H10 | A convocação acontece dentro do sistema: o devedor escreve a justificativa na cobrança e os responsáveis registram a decisão (perdão, renegociação ou manter a dívida) | Resposta do dono | 2026-11-11 |
| H12 | Contestar devolve a solicitação ao solicitante para ajustes; ele recebe notificação e e-mail com texto padrão e a mensagem do responsável, corrige e reenvia | História 6 | 2026-11-11 |
| H13 | Gasto maior que o aprovado precisa de nova aprovação. Gasto menor: o solicitante devolve por fora e registra a devolução, que vira uma entrada ligada à saída e é confirmada pelo financeiro como qualquer entrada | História 6 e resposta do dono | 2026-11-11 |
| H14 | Os itens da solicitação de gasto são uma lista estruturada, cada um com descrição e valor; o sistema soma o total | Resposta do dono | 2026-11-11 |
| H15 | A saída só é liquidada depois que o financeiro confere a prestação de contas e a encerra | Resposta do dono | 2026-11-11 |
| H16 | Cada solicitação tem um só validador. Evento com custo gera duas solicitações distintas, a do evento e a orçamentária | História 8 | 2026-11-11 |
| H17 | Isenção vale para uma cobrança já gerada. Suspensão impede que as próximas cobranças recorrentes daquele diretor sejam geradas | Resposta do dono | 2026-11-11 |
| H18 | A contestação de uma cobrança é decidida por um usuário com a permissão para isso (em regra o responsável financeiro, ou o admin), com justificativa. Não há votação | Resposta do dono | 2026-11-11 |
| H19 | Quando o solicitante é quem aprovaria o pedido, ele indica qualquer diretor, que ganha o direito de decidir só aquele pedido (ver o risco em H26) | Resposta do dono | 2026-11-11 |
| H20 | O evento com custo só entra no calendário com as duas solicitações aprovadas | Resposta do dono | 2026-11-11 |
| H21 | Sugerir teto de gasto é contestar a solicitação informando também um valor máximo sugerido; vale para qualquer solicitação com custo | Resposta do dono | 2026-11-11 |
| H22 | O proponente, o responsável por eventos ou o admin podem confirmar que o evento aconteceu; o primeiro que fizer encerra | Resposta do dono | 2026-11-11 |
| H24 | Mudar a data de um evento aprovado é editá-lo: ele sai do calendário, volta a pendente e só reaparece depois de aprovado de novo (confirma EVT-05) | Resposta do dono | 2026-11-11 |
