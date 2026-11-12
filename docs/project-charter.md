# Charter do projeto: Club Manager

| Campo | Valor |
| --- | --- |
| Status | Approved |
| Responsável | Leandro Nascimento |
| Atualizado em | 2026-11-11 |
| Aprovado por | Leandro Nascimento |
| Aprovado em | 2026-11-11 |
| Enunciado | `docs/challenge/phase-1.md` |

## Problema

Os diretores de um time de futebol administram o dinheiro e as decisões do clube sem um registro formal. Não há
controle confiável do que entrou e do que saiu, os gastos e os eventos não passam por aprovação registrada, e não dá
para saber depois quem fez o quê e quando. O dinheiro circula por fora (conta de um titular), então o que falta não é
um banco, e sim a escrituração e a governança em volta dele.

## Proposta de valor

O diferencial não é lançar receitas e despesas, e sim dar aos diretores aprovação formal e rastreabilidade completa de
cada valor e de cada decisão: quem pediu, quem aprovou, por quê, e o que aconteceu depois.

## Critérios de sucesso

- [ ] Os 13 marcos da etapa 1 (E1 a E13) concluídos, cada um com o critério de aceite do enunciado atendido e
      aprovado pelo dono.
- [ ] Uma cobrança recorrente é gerada sozinha, notificada, paga, validada e liquidada (E7).
- [ ] Uma saída percorre o ciclo completo, da solicitação à liquidação, com histórico (E8).
- [ ] O solicitante nunca aprova o próprio pedido sem a permissão específica (E6).
- [ ] Os números do dashboard batem com os lançamentos validados, e os relatórios respeitam as permissões (E11).
- [ ] O sistema roda em produção numa única instância AWS, com backup e rollback testados (E13).
- [ ] Nenhum resquício do protótipo permanece no repositório (E13).
- [ ] As etapas futuras estão documentadas, e nada na arquitetura as impede (E14).

## Escopo

Etapa 1: o sistema completo para os diretores, no site.

- Financeiro: entradas, saídas, cobranças recorrentes, validação e prestação de contas.
- Eventos com aprovação e calendário.
- Notificações por e-mail e caixa de entrada no site.
- Feed de comunicados, documentos e perfil do usuário.
- Dashboard e relatórios em PDF e CSV.
- Autenticação, convites, catálogo de permissões e motor de aprovações.
- Personalização visual por time (escudo e cores) e auditoria transversal.

## Fora de escopo

| Item | Por quê |
| --- | --- |
| Aplicativo mobile e push | Vem depois que o site estiver completo; a API já deve servi-lo |
| Torcedor e jogador, com cadastro aberto | Tipos de usuário de etapas futuras; o modelo de usuários e permissões deve ser extensível |
| Gestão do time como um todo | Além da governança financeira e institucional |
| Recebimento automático por plataforma de pagamento | Só o ponto de extensão é previsto |
| Integração bancária | Os valores são escriturais; a transferência real acontece fora do sistema |
| Multi-cliente (deploy por cliente ou SaaS) | Só se decide quando for hora de escalar (AD-018) |
| Importação de CSV | Não prevista (REL-01) |
| Migração de dados do protótipo | O novo sistema começa vazio |

## Restrições

| Restrição | Origem | Vira decisão? |
| --- | --- | --- |
| Custo mínimo: uma única instância AWS, free tier pelo maior tempo possível | Enunciado, RNF-02 | AD-013 |
| Só dois ambientes, local e produção | Enunciado, RNF-05 | AD-013 |
| Backend em Python, Django ou FastAPI; Flask fora | Enunciado, seção 13 | AD-003 |
| PostgreSQL, Docker e AWS | Enunciado, seção 13 | AD-003, AD-013 |
| Celery com Redis para filas e tarefas agendadas | Enunciado, seção 13 | AD-005 |
| API única, versionada e documentada; regras nunca nos clientes | Enunciado, RNF-01 | AD-001 |
| CI/CD no GitHub Actions dentro do plano gratuito | Enunciado, RNF-04 | AD-013 |
| Sem CPF; dados pessoais e financeiros sob LGPD | Enunciado, RNF-07 | AD-015 |
| Nada é apagado; registros liquidados são imutáveis | Enunciado, AUD-04 e APR-09 | AD-008, AD-009, AD-010 |
| Projeto solo, construído com agente de IA | Equipe | — |
| Sem prazo fixo | Dono, 2026-11-11 | — |

## Stakeholders e atores

| Quem | Interesse | Participa de |
| --- | --- | --- |
| Leandro Nascimento (dono) | Ter o sistema em produção para o próprio time e poder reaproveitá-lo em outros clubes | Todas as decisões e aprovações |
| Admin do sistema | Gerenciar usuários, cargos, setores, categorias, permissões e regras de aprovação | Uso; validação dos marcos M2, M3 e M5 |
| Diretores (com e sem cargo) | Consultar a gestão, pedir recursos, propor eventos, pagar e questionar cobranças | Uso |
| Responsáveis de setor | Aprovar pedidos do setor e validar pagamentos | Uso |
| Torcedores e jogadores | Usuários de etapas futuras | Nenhuma na etapa 1 |

## Riscos e premissas

| Risco ou premissa | Probabilidade | Impacto | Mitigação |
| --- | --- | --- | --- |
| API, PostgreSQL, Redis e workers não cabem com folga na instância do free tier | Média | Alto | Verificar no rito 7, com configuração enxuta e medição de memória; o enunciado pede essa checagem (RNF-02) |
| O free tier da AWS expira e o custo passa a existir | Alta | Médio | Registrar o custo esperado depois do free tier na decisão de infraestrutura (AD-013) |
| Sem homologação, um erro vai direto para produção | Média | Alto | Testes sólidos nos fluxos críticos, migrações reversíveis, imagens versionadas e backup antes de mudanças com dados (RNF-05) |
| Escopo grande (13 marcos) para um projeto solo sem prazo | Média | Médio | Um marco por vez, com gate; ordem de prioridade para encurtar o escopo é pergunta em aberto |
| Motor de aprovações genérico demais ou de menos para despesas, eventos e requisições futuras | Média | Alto | Especificar o M5 antes do M6 ao M8 e validar com os dois primeiros usos reais |
| Vazamento de dados pessoais ou financeiros | Baixa | Alto | Threat model no M2, revisão de segurança por marco, acesso a anexos por permissão |
| O protótipo existe só na pasta local (`_prototipo/`), sem commit | Baixa | Baixo | É só consulta e é apagado no M12 (ADR-002) |
| Premissa: o primeiro e único cliente é o time do dono | — | — | Reavaliar rollback e isolamento se surgirem outros clientes (RNF-05, BRD-05) |

## Perguntas em aberto

- Hipóteses da seção 15 do enunciado: confirmar ou corrigir na especificação de cada marco — dono: Leandro Nascimento.
- Pendências por marco da seção 15 (M2 a M10): decidir no refinamento do marco — dono: Leandro Nascimento.
- Itens do protótipo que o enunciado não cobre (Pix e QR Code, recibo, cobranças em lote, fluxo de caixa previsto e
  realizado, atas, postagem fixada): confirmar ou descartar no M0 (AD-016) — dono: Leandro Nascimento.
- Ordem de prioridade entre funcionalidades, se for preciso encurtar o escopo — dono: Leandro Nascimento.
