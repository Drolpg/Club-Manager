# Enunciado — Fase 1

| Campo | Valor |
| --- | --- |
| Recebido em | 2026-11-11 |
| Fonte | Documento "Club Manager — Enunciado do Projeto (reescrita do zero)", colado na sessão por Leandro Nascimento |
| Prazo de entrega | Sem prazo fixo (Leandro Nascimento, 2026-11-11) |

## Texto literal

O texto literal, sem edição, está em [phase-1-enunciado.md](phase-1-enunciado.md). Ele fica em arquivo próprio porque
tem títulos e numeração de seções próprios, citados pelos IDs abaixo. Interpretações vão para o charter ou a
constituição e para a especificação.

## Entregáveis rastreáveis

Os entregáveis são os marcos da seção 14 do enunciado; a evidência esperada é o critério de aceite de cada marco.

| ID | Entregável (como está no enunciado) | Artefato ou evidência esperada | Responsável | Status |
| --- | --- | --- | --- | --- |
| E1 | M0 Arquitetura: avaliação do enunciado e proposta de arquitetura, stack, estrutura e repositório, com decisões registradas | Decisões aprovadas pelo dono e especificações dos marcos seguintes geradas | Leandro Nascimento | Pronto (evidência: `docs/method.md`, ritos 0 a 6 aprovados em 2026-11-11) |
| E2 | M1 Fundação: projeto, Docker, banco, CI no GitHub Actions, configuração por ambiente, esqueleto da API e do site | Subir tudo com um comando local e pipeline verde | Leandro Nascimento | Pronto (evidência: `docs/setup/local.md`; CI verde em 2026-11-12; tag `v0.1.0`) |
| E3 | M2 Identidade e acesso: login Google e usuário/senha, verificação de e-mail, convite de 24 horas, cadastro, desativação | Diretor convidado se cadastra, valida o e-mail e entra pelos dois modos | Leandro Nascimento | Pronto (evidência: `docs/features/acesso/identidade-e-acesso/implementation-plan.md`; PR #1; tag `v0.2.0`) |
| E4 | M3 Permissões e auditoria: catálogo, três origens, cargos, setores, categorias, painel do admin, trilha de auditoria | Admin atribui permissões por cargo, setor e individual, e cada concessão fica auditada | Leandro Nascimento | Pendente |
| E5 | M4 Notificações: tarefas agendadas, e-mail, caixa de notificações no site, preferências de alerta | Evento de teste gera registro, e-mail e item na caixa; usuário não desliga o registro | Leandro Nascimento | Pendente |
| E6 | M5 Motor de aprovações: solicitação genérica com versões, regras por setor, justificativas, reabertura, cancelamento e liquidação | Fluxos de aprovar, recusar, reabrir e editar aprovada passam nos testes, com solicitante nunca aprovando o próprio pedido sem permissão | Leandro Nascimento | Pendente |
| E7 | M6 Financeiro, entradas: categorias, cobranças únicas e recorrentes, mensalidade por diretor, validação, questionamento, isenção, atraso | Cobrança recorrente é gerada sozinha, notificada, paga, validada e liquidada | Leandro Nascimento | Pendente |
| E8 | M7 Financeiro, saídas: solicitação de recurso, envio com comprovante, prestação de contas, estorno e cancelamento | Ciclo completo de uma saída, da solicitação à liquidação, com histórico | Leandro Nascimento | Pendente |
| E9 | M8 Eventos: proposta, regras por tipo, calendário, histórico, encerramento e cancelamento | Evento com custo exige o Financeiro, só aprovado aparece no calendário, editar o tira de lá | Leandro Nascimento | Pendente |
| E10 | M9 Feed, documentos e perfil: comunicados, aba de documentos, perfil privado | Perfil só visível ao dono e ao admin; documentos acessíveis pelo feed | Leandro Nascimento | Pendente |
| E11 | M10 Dashboard e relatórios: dashboard completo e básico, listas e detalhes, relatórios em PDF e CSV | Números batem com os lançamentos validados e relatórios respeitam permissões | Leandro Nascimento | Pendente |
| E12 | M11 Personalização: cadastro de escudo e cores, temas derivados, ícones customizáveis | Sistema nasce em branco e assume a identidade configurada em todas as telas e no PDF | Leandro Nascimento | Pendente |
| E13 | M12 Produção: deploy na AWS, backups, rollback, segurança, testes ponta a ponta, documentação, limpeza do protótipo antigo | Sistema no ar na instância única, backup e rollback testados, resquícios do protótipo removidos | Leandro Nascimento | Pendente |
| E14 | Etapas futuras "só documentadas" (mobile, torcedor e jogador, gestão do time, multi-cliente) | Seção de etapas futuras na documentação, sem implementação | Leandro Nascimento | Pendente |

Status: `Pendente`, `Em andamento`, `Pronto (evidência: <link>)`, `Não se aplica (<motivo>)`.

## Requisitos extraídos

O enunciado traz IDs próprios, listados abaixo. O registro de requisitos (rito 6) renumera para `RF-NN`, `RNF-NN` e
`RN-NN` e mantém, em cada requisito, o ID de origem do enunciado.

| Trecho do enunciado | Requisito na spec ou no registro (rito 6) |
| --- | --- |
| Seção 5 — Acesso, cadastro e usuários | ACE-01 a ACE-13 |
| Seção 6 — Permissões | PER-01 a PER-06 |
| Seção 6 — Aprovação | APR-01 a APR-11 |
| Seção 7 — Financeiro | FIN-01 a FIN-18 |
| Seção 8 — Eventos | EVT-01 a EVT-10 |
| Seção 9 — Notificações | NOT-01 a NOT-07 |
| Seção 10 — Feed, documentos e perfil | COM-01 a COM-03, DOC-01 e DOC-02, PRF-01 a PRF-03 |
| Seção 11 — Dashboard, telas e relatórios | DSH-01 a DSH-08, REL-01 a REL-04 |
| Seção 12 — Personalização e auditoria | BRD-01 a BRD-05, AUD-01 a AUD-04 |
| Seção 13 — Requisitos não funcionais | RNF-01 a RNF-08 |
| Seção 15 — Hipóteses assumidas | Confirmar ou corrigir na especificação de cada marco |
| Seção 15 — Pendências por marco | Decidir no refinamento do marco correspondente |
| Seção 16 — Itens do protótipo não cobertos (Pix e QR Code, recibo, cobranças em lote, fluxo de caixa previsto e realizado, atas, postagem fixada) | Confirmar ou descartar com o dono no M0 (AD-016) |

## Restrições extraídas

Restrições e preferências do enunciado são itens a decidir, não decisões. Cada uma aponta para a entrada
correspondente em `docs/decision-register.md`.

| Restrição | Entrada no registro de decisões |
| --- | --- |
| Backend em Python; framework entre Django (preferência) e FastAPI; Flask fora | AD-003 |
| PostgreSQL, Celery com Redis, Docker e AWS como stack preferida | AD-003, AD-005, AD-013 |
| Frontend web livre, com React como direção provável | AD-004 |
| Mobile (etapa futura): comparar Kotlin, React Native e outras | AD-017 (Deferred) |
| Arquitetura proposta pelo plugin (hexagonal, Clean simplificada ou portas e adaptadores); a do protótipo não é ponto de partida | AD-001 |
| API única, versionada e documentada, servindo site e depois app (RNF-01) | AD-001, AD-006 |
| Uma única instância AWS, free tier pelo maior tempo possível, sem impedir separar banco ou workers (RNF-02) | AD-013 |
| Tudo dockerizado, mesmas imagens em desenvolvimento e produção (RNF-03) | AD-013 |
| CI/CD no GitHub Actions dentro do plano gratuito (RNF-04) | AD-013 |
| Só ambientes local e produção; migrações reversíveis, imagens versionadas e backup antes de mudanças com dados (RNF-05) | AD-013 |
| Armazenamento de anexos e e-mail de custo mínimo, com ponto de extensão para trocar de provedor (RNF-06) | AD-011, AD-012 |
| Dados pessoais e financeiros, sem CPF; avaliar o que a LGPD exige (RNF-07) | AD-015 |
| Estratégia de autenticação: Google, usuário/senha e tokens para site e app | AD-006 |
| Modelagem de permissões, motor de aprovações, versões de solicitação, auditoria, estornos e cancelamentos | AD-007, AD-008, AD-009, AD-010 |
| Não implementar etapas futuras, mas não impedi-las (tipos de usuário e permissões extensíveis; nem deploy por cliente nem SaaS fechados) | AD-001, AD-018 (Deferred) |
| Repositório novo ou reaproveitamento do atual; resquícios do protótipo removidos até o M12 | AD-002 |
| O que o painel do admin cria sozinho e o que exige programação (PER-05) | AD-014 |
| Novo sistema começa vazio, sem migração de dados; primeiro admin criado de forma segura, sem senha padrão | AD-019 |

## Delta em relação à fase anterior

Não se aplica: primeira fase.
