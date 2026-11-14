# Tarefas e marcos

Único lugar do repositório com os marcos, o andamento e as pendências. Os marcos vêm do enunciado da etapa 1 e
seguem a ordem de dependência; um por vez. Cada marco passa por spec, plano, implementação com evidência, revisão
de segurança e auditoria de coerência (ver a Definition of Done na [constituição](00-constitution.md)).

Legenda do status: `Concluído`, `Em andamento`, `Spec aprovada`, `Pendente`. A coluna "Cartão" recebe o ID do cartão
do board quando ele existir; até lá fica `—`.

## Resumo

| Marco | Entregável | Requisitos | Status | Concluído em | Cartão |
| --- | --- | --- | --- | --- | --- |
| M0 Arquitetura | Avaliação, stack, estrutura, decisões e requisitos | — | Concluído | 2026-11-11 | — |
| M1 Fundação | Projeto, contêineres, banco, CI, esqueleto da API e do site | RNF-01 a RNF-05, RNF-08, RNF-09 | Concluído (`v0.1.0`) | 2026-11-12 | — |
| M2 Identidade e acesso | Convite, cadastro, login, verificação, desativação | RF-001 a RF-014, RF-116, RF-117 | Concluído (`v0.2.0`) | 2026-11-13 | — |
| M3 Permissões e auditoria | Cargos, setores, concessões, painel do admin, trilha | RF-015 a RF-027, RF-118 | Concluído (na `dev`) | 2026-11-13 | — |
| M4 Notificações | Registro, e-mail, caixa de entrada, preferências, agendador | RF-028 a RF-032, RF-119, RNF-10 | Concluído (na `dev`) | 2026-11-13 | — |
| M5 Motor de aprovações | Solicitação com versões, decisões, motivos, fila | RF-033 a RF-045, RF-120 a RF-122 | Concluído (na `dev`) | 2026-11-14 | — |
| M6 Financeiro: entradas | Cobranças, recorrência, Pix, validação, inadimplência, entradas | RF-046 a RF-072, RF-123 a RF-125 | Spec funcional aprovada | | — |
| M7 Financeiro: saídas | Solicitação de gasto, envio, prestação, liquidação, estorno | RF-073 a RF-083, RF-126 a RF-128 | Spec funcional aprovada | | — |
| M8 Eventos | Proposta, orçamento, calendário, realização, cancelamento | RF-084 a RF-093, RF-129 a RF-131 | Spec funcional aprovada | | — |
| M9 Feed, documentos e perfil | Comunicados, documentos, atas, perfil | RF-094 a RF-101 | Pendente | | — |
| M10 Dashboard e relatórios | Dashboards, lista de transações, relatórios em PDF e CSV | RF-102 a RF-111 | Pendente | | — |
| M11 Personalização | Escudo, cores, temas, ícones | RF-112 a RF-115 | Pendente | | — |
| M12 Produção | Deploy, backup, rollback, segurança, ponta a ponta, limpeza do legado | RNF-02, RNF-05, RNF-07, RNF-14 | Pendente | | — |

Marcos concluídos foram aprovados pelo dono do projeto na data indicada. O próximo é o M6.

## Dependências

| Marco | Depende de | Observação |
| --- | --- | --- |
| M2 | M1 | Sequência |
| M3 | M2 | Usuários para receber cargos, setores e concessões |
| M4 | M2, M3 | Destinatários e a consulta "quem pode fazer?" |
| M5 | M3, M4 | Permissão de aprovar, notificação de decisão e auditoria |
| M6 | M3, M4, M5 (só os motivos de decisão) | A feature 1 do M6 não depende do M5 |
| M7 | M5, M6 | A solicitação de gasto é um tipo do motor; a devolução é uma entrada |
| M8 | M5, M7 | Evento sem custo só depende do M5 |
| M9 | M3, M4 | Pode vir logo depois do M4, se convier |
| M10 | M6, M7, M8, M9 | O dashboard básico só depende do M3 |
| M11 | M3 | O PDF com marca depende do M10 |
| M12 | Todos | A infraestrutura de deploy pode ser ensaiada a partir do M1 |

Contratos que mais de um marco consome, fixados na spec técnica do marco que os cria: API pública de permissões
(M3), de auditoria (M3) e de notificações (M4); registro de tipo de solicitação e eventos de decisão (M5); catálogo
de motivos de decisão (M5); abertura de solicitação orçamentária para um evento (M7); consultas públicas de cada
contexto (M6 a M9, consumidas no M10); configuração de marca (M11).

## Marcos

### M0 — Arquitetura

- [x] Enunciado lido e rastreado em entregáveis
- [x] Descoberta do domínio: histórias, eventos e pontos em aberto
- [x] Desenho estratégico: contextos, mapa de contextos e linguagem ubíqua
- [x] Desenho tático dos três módulos core
- [x] Avaliação de arquitetura e decisão de estilo (ADR-001)
- [x] Requisitos numerados e Definition of Ready e Done ([spec](01-spec.md))

### M1 — Fundação

- [x] Estrutura de pastas, um módulo por contexto, com `public.py`
- [x] Contêineres: um comando sobe API, worker, banco, fila e site
- [x] CI por pasta, com a verificação completa e as fronteiras de módulo
- [x] Configuração só por variável de ambiente; `.env.example` versionado
- [x] Revisão de segurança do marco ([04-seguranca](04-seguranca.md), seção 3)
- [x] Auditoria de coerência e tag `v0.1.0`

### M2 — Identidade e acesso

- [x] Auditoria: registro só de inserção
- [x] Usuário, autenticação e comando `criar_admin`
- [x] Sessão: entrar, consultar e sair
- [x] Convites
- [x] Cadastro com senha, verificação e e-mails
- [x] Recuperação de senha
- [x] Administração de usuários
- [x] Google: cadastro e login
- [x] Documentação da API protegida (D-01)
- [x] Site
- [x] Validação final, revisão de segurança (seção 4 de [04-seguranca](04-seguranca.md)) e tag `v0.2.0`

### M3 — Permissões e auditoria

- [x] Catálogo e resolução de permissões
- [x] Cargos e setores
- [x] Classificação, concessões e API pública
- [x] Portas em `acesso` e histórico
- [x] Site
- [x] Validação final e auditoria de coerência

### M4 — Notificações

- [x] Despachante de eventos e eventos publicados
- [x] Registro, `notificar` e preferências
- [x] Tarefa de e-mail
- [x] Tratadores dos quatro eventos
- [x] Rotas da caixa e das preferências
- [x] Site
- [x] Mailpit e validação final

### M5 — Motor de aprovações

- [x] Domínio puro
- [x] Modelos e motivos de decisão
- [x] Tipos de solicitação e ciclo do solicitante
- [x] Decisões
- [x] Execução, encerramento e isolamento entre tipos
- [x] Notificações e lembretes
- [x] Consultas
- [x] Site
- [x] Tipo de demonstração e validação final

### M6 — Financeiro: entradas

Maior marco, dividido em seis features, nesta ordem. O critério de aceite (cobrança recorrente gerada sozinha,
notificada, paga, validada e encerrada) é atendido ao fim da terceira.

- [ ] Categorias, chaves Pix e cobrança avulsa, com Pix copia e cola e QR Code (RF-046 a RF-049, RF-052, RF-053, RF-065)
- [ ] Pagamento, validação, rejeição e recibo (RF-054 a RF-059)
- [ ] Recorrência, geração automática e suspensão (RF-050, RF-051, RF-064)
- [ ] Atraso, questionamento e isenção (RF-060 a RF-063)
- [ ] Inadimplência: convocação, perdão e renegociação (RF-066 a RF-070)
- [ ] Entradas sem devedor (RF-071, RF-072)
- [ ] Decidir o armazenamento de anexos (ADR-014) antes do primeiro comprovante
- [ ] Reavaliar a LGPD com os comprovantes, que podem conter dados bancários de terceiros
- [ ] Testar o Pix copia e cola em aplicativos de banco reais (risco 3)
- [ ] Revisão de segurança e auditoria de coerência do marco

### M7 — Financeiro: saídas

- [ ] Solicitação de gasto como tipo do motor (RF-073, RF-074)
- [ ] Envio do recurso e prestação de contas (RF-075 a RF-077, RF-080)
- [ ] Devolução da diferença e complemento (RF-078, RF-079, RF-128)
- [ ] Liquidação (RF-081), cancelamento (RF-082) e estorno (RF-083, ADR-013)
- [ ] Lembretes e visão de comprometido (RF-126, RF-127)
- [ ] Revisão de segurança e auditoria de coerência do marco

### M8 — Eventos

- [ ] Categorias e proposta de evento (RF-084, RF-085)
- [ ] Solicitação orçamentária ligada ao evento (RF-086)
- [ ] Publicação, calendário e histórico (RF-087, RF-088, RF-090)
- [ ] Edição, realização e cancelamento (RF-089, RF-091 a RF-093, RF-130, RF-131)
- [ ] Confirmação de presença (RF-129)
- [ ] Revisão de segurança e auditoria de coerência do marco

### M9 — Feed, documentos e perfil

- [ ] Refinar a spec: comentários, pastas e acesso por cargo (D-16)
- [ ] Feed, comunicados e fixação (RF-094 a RF-097)
- [ ] Documentos e atas (RF-095, RF-098, RF-099)
- [ ] Perfil próprio e do admin (RF-100, RF-101)
- [ ] Revisão de segurança e auditoria de coerência do marco

### M10 — Dashboard e relatórios

- [ ] Dashboard financeiro e básico (RF-102, RF-103)
- [ ] Lista de transações com filtros (RF-104)
- [ ] Relatórios em PDF e CSV (RF-105 a RF-110)
- [ ] Geração em segundo plano (RF-111); escolher a biblioteca de PDF (risco 6)
- [ ] Revisão de segurança e auditoria de coerência do marco

### M11 — Personalização

- [ ] Escudo e cores base (RF-112)
- [ ] Aplicação da marca e temas derivados (RF-113)
- [ ] Ícones e símbolos (RF-114)
- [ ] Configuração entregue ao site e aos PDFs (RF-115)
- [ ] Revisão de segurança e auditoria de coerência do marco

### M12 — Produção

- [ ] Deploy na instância única, HTTPS e publicação das imagens (ADR-016)
- [ ] Backup e rollback ensaiados (RNF-05)
- [ ] Medir a memória na instância (risco 1) e conferir o free tier (risco 2)
- [ ] Escolher o provedor de e-mail e configurar SPF e DKIM (ADR-015)
- [ ] Testes de ponta a ponta dos fluxos críticos (RNF-14)
- [ ] Avaliar DAST (D-03) e configurar o login do Google em produção (D-02)
- [ ] LGPD: confirmar a base legal, decidir a anonimização a pedido e o procedimento de incidente
- [ ] Remover os resquícios do legado
- [ ] Revisão de segurança final e auditoria de coerência
- [ ] Merge da `dev` na `main`, com autorização do dono, e tag `v1.0.0`

## Pendências

| Pendência | Quando | Dono |
| --- | --- | --- |
| IDs dos cartões do board para cada marco | Antes de abrir o M6 | Dono do projeto |
| Armazenamento de anexos (ADR-014) | Spec técnica do M6 | Dono do projeto |
| Estornos e cancelamentos como lançamentos ligados (ADR-013) | Spec técnica do M7 | Dono do projeto |
| Provedor de e-mail (ADR-015) | M12 | Dono do projeto |
| CI/CD, deploy e dimensionamento da instância (ADR-016) | M12 | Dono do projeto |
| Base legal da LGPD confirmada por alguém qualificado | Antes da produção | Dono do projeto |
| Decisões do enunciado ainda abertas para os marcos M6 a M11 | Refinamento de cada marco | Dono do projeto |
