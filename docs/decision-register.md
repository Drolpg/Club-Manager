# Registro de decisões

## Propósito

Separa decisões de arquitetura e de processo de trabalho apenas não feito. Cada entrada é uma escolha real, com dono,
escopo e o que ela bloqueia. Decisão tomada vira ADR em `docs/adr/`.

## Fontes e autoridade

| Fonte | Autoridade sobre |
| --- | --- |
| Enunciado (`docs/challenge/`) | Resultados obrigatórios e preferências do dono; não define o desenho interno |
| Board (Miro, quando houver) | Intenção de domínio, até que um artefato aceito mais novo a substitua |
| Repositório (`docs/`) | Decisões, requisitos e specs vigentes |
| Código | Apenas o que está implementado agora |
| Protótipo (`_prototipo/`, fora do git) | Nenhuma: só consulta, para conferir funcionalidades esquecidas |

## Status

| Status | Significado |
| --- | --- |
| **Pending** | Há uma escolha real e o dono indicado pode fazê-la. |
| **Not Blocking** | A pergunta é válida, mas nenhuma implementação atual depende da resposta. |
| **Deferred** | Adiada de propósito para outra fase ou até um gatilho. |
| **Resolved** | Há evidência de que foi decidida explicitamente e adotada. |
| **Superseded** | Substituída por uma decisão mais nova. |

Status descreve a decisão, não a implementação. O projeto é solo: toda decisão é do dono, Leandro Nascimento, e o
agente só recomenda.

## Conflitos entre fontes

| Diferença | Classificação | Por que importa |
| --- | --- | --- |
| O enunciado chama o plugin de `claude-sdd-method`; o plugin instalado é `sdd-method` (0.2.1) | Diferença inofensiva | Nenhum impacto; é o mesmo plugin |
| O enunciado diz que o plugin "propõe a arquitetura, a stack e a estrutura" no M0; no método, estilo é o rito 2 e stack e estrutura são o rito 7 | Diferença inofensiva | O M0 cobre os ritos 0 a 6 e a decisão de stack é antecipada como proposta na avaliação; a estrutura é criada no M1 (rito 7) |

## Resumo

| ID | Título | Status | Escopo | Dono | Bloqueia |
| --- | --- | --- | --- | --- | --- |
| AD-001 | Estilo de arquitetura e trilha de domínio | Resolved | Arquitetura compartilhada | Leandro | Ritos 3 a 7 |
| AD-002 | Repositório novo ou reaproveitado, e destino do protótipo | Resolved | Arquitetura compartilhada | Leandro | Rito 7 (M1) |
| AD-003 | Framework do backend: Django ou FastAPI | Resolved | Arquitetura compartilhada | Leandro | Rito 7 (M1) |
| AD-004 | Frontend web | Resolved | Arquitetura compartilhada | Leandro | Rito 7 (M1) |
| AD-005 | Filas e tarefas agendadas | Resolved | Arquitetura compartilhada | Leandro | M4 |
| AD-006 | Estratégia de autenticação e tokens para site e app | Resolved | Arquitetura compartilhada | Leandro | M2 |
| AD-007 | Modelagem das permissões (ação, recurso e escopo) | Resolved | Arquitetura compartilhada | Leandro | M3 |
| AD-008 | Modelagem do motor de aprovações e das versões de solicitação | Pending | Arquitetura compartilhada | Leandro | M5 |
| AD-009 | Modelagem da trilha de auditoria | Resolved | Arquitetura compartilhada | Leandro | M3 |
| AD-010 | Estornos e cancelamentos como lançamentos ligados ao original | Pending | Arquitetura compartilhada | Leandro | M7 |
| AD-011 | Armazenamento de anexos | Pending | Arquitetura compartilhada | Leandro | M6 (primeiro comprovante) |
| AD-012 | Provedor de e-mail | Not Blocking | Arquitetura compartilhada | Leandro | M12 (produção) |
| AD-013 | CI/CD, deploy e dimensionamento da instância única | Pending | Arquitetura compartilhada | Leandro | M1 (CI) e M12 (deploy) |
| AD-014 | O que o painel do admin cria sozinho e o que exige programação | Resolved | Dono do marco M3 | Leandro | M3 |
| AD-015 | Adequação à LGPD | Pending | Arquitetura compartilhada | Leandro | M2 |
| AD-016 | Itens do protótipo que o enunciado não cobre | Resolved | Escopo de entrega | Leandro | Rito 6 |
| AD-017 | Tecnologia do aplicativo mobile | Deferred | Arquitetura compartilhada | Leandro | Nada na etapa 1 |
| AD-018 | Multi-cliente: deploy por cliente ou SaaS com contas | Deferred | Arquitetura compartilhada | Leandro | Nada na etapa 1 |
| AD-019 | Criação segura do primeiro admin | Resolved | Dono do marco M2 | Leandro | M2 |

As entradas abaixo trazem o problema e as opções que o enunciado já cita. Vantagens, desvantagens e a recomendação
entram no rito indicado, quando a avaliação for feita.

---

### AD-001 — Qual estilo de arquitetura e qual trilha de domínio o sistema adota?

**Status:** Resolved

**Decision:** monólito modular, com DDD tático em aprovações, financeiro e eventos e camadas nos demais módulos;
trilha de domínio DDD completo restrita ao core, com o rito 3 simplificado.

**Resolved on:** 2026-11-11, por Leandro Nascimento (estilo aceito; a ADR-001 passa a Accepted no gate do rito 7)

**Scope:** Arquitetura compartilhada

**Blocking:** ritos 3 a 5 (se o estilo pedir), rito 6 (forma da especificação) e rito 7.

**Problem:** o enunciado delega a escolha ao plugin e cita hexagonal completa, Clean Architecture simplificada ou
portas e adaptadores, "conforme o que melhor couber ao tamanho real do projeto". A arquitetura do protótipo (portas e
adaptadores) não é ponto de partida.

**Options:** as do catálogo de `sdd-method:choosing-architecture`, incluindo as três citadas no enunciado e o
monólito modular (com ou sem DDD), que é o estilo de partida do tipo "sistema de domínio rico".

**Follow-up:** ADR-001 (Accepted em 2026-11-12, no gate da arquitetura base); avaliação em `docs/architecture/assessment.md`.

---

### AD-002 — Repositório novo ou reaproveitar o atual? O que acontece com o protótipo?

**Status:** Resolved

**Decision:** Option A. O protótipo foi movido para `_prototipo/`, ignorada pelo git, e é apagado no M12.

**Resolved on:** 2026-11-11, por Leandro Nascimento

**Scope:** Arquitetura compartilhada

**Blocking:** rito 7 (onde a estrutura nova é criada).

**Problem:** o repositório `Drolpg/Club-Manager` tem só o commit inicial. O protótipo (`backend/`, `frontend/`,
`docs/football_club_manager_spec.md`, `images/`, `docker-compose.yml`) está na pasta de trabalho, sem commit. O dono
confirmou em 2026-11-11 que ele pode ser reescrito ou excluído. O enunciado pede a opção mais barata e a remoção de
todos os resquícios até o M12.

**Options:**

Option A — Reaproveitar este repositório, movendo ou removendo o protótipo.

Option B — Criar um repositório novo e manter este só como consulta.

**Follow-up:** ADR-002.

---

### AD-003 — Django ou FastAPI no backend?

**Status:** Resolved

**Decision:** Django com DRF, PostgreSQL 18 e Python 3.14.

**Resolved on:** 2026-11-11, por Leandro Nascimento

**Scope:** Arquitetura compartilhada

**Blocking:** rito 7.

**Problem:** backend em Python e PostgreSQL são preferências do dono. O framework fica entre Django (preferência, por
familiaridade) e FastAPI (se couber melhor). Flask está fora.

**Options:** Option A — Django. Option B — FastAPI.

**Follow-up:** ADR-004.

---

### AD-004 — Qual frontend web?

**Status:** Resolved

**Decision:** React com Vite e TypeScript, como SPA servida por Caddy.

**Resolved on:** 2026-11-11, por Leandro Nascimento

**Scope:** Arquitetura compartilhada

**Blocking:** rito 7.

**Problem:** o enunciado deixa livre, com React como direção provável. Pesa o reaproveitamento com o app mobile
futuro (AD-017) e o white-label com temas derivados (BRD-02).

**Options:** a levantar na avaliação; React é a opção de referência.

**Follow-up:** ADR-005.

---

### AD-005 — Celery com Redis, ou algo mais leve, para filas e tarefas agendadas?

**Status:** Resolved

**Decision:** Celery com Redis, um worker com o agendador embutido.

**Resolved on:** 2026-11-11, por Leandro Nascimento

**Scope:** Arquitetura compartilhada

**Blocking:** M4.

**Problem:** Celery com Redis é a preferência do enunciado, mas ele também pede verificar se API, PostgreSQL, Redis e
workers cabem numa única instância do free tier (RNF-02).

**Options:** Option A — Celery com Redis. Option B — alternativa mais leve, a levantar na avaliação.

**Follow-up:** ADR-006.

---

### AD-006 — Como autenticar com Google e com usuário e senha, e que tokens servem site e app?

**Status:** Resolved

**Decision:** sessão no servidor em cookie para o site; Google por token de identidade; token opaco para o
aplicativo futuro.

**Resolved on:** 2026-11-12, por Leandro Nascimento

**Scope:** Arquitetura compartilhada

**Blocking:** M2.

**Problem:** os dois modos de login convivem na mesma conta (ACE-02), e a mesma API serve o site e depois o app
(ACE-13, RNF-01).

**Options:** a levantar na especificação do M2 (sessão por cookie, JWT, tokens opacos).

**Nota (2026-11-12):** decidida na ADR-008 (Accepted): sessão no servidor em cookie para o site, token de identidade
para o Google, token opaco para o aplicativo futuro.

**Follow-up:** ADR-008.

---

### AD-007 — Como modelar as permissões?

**Status:** Resolved

**Decision:** catálogo de permissões em código (`<recurso>.<acao>`); concessões a cargo, setor ou usuário, revogadas e nunca
apagadas; união por função pura; sem escopo por setor do item.

**Resolved on:** 2026-11-13, por Leandro Nascimento

**Scope:** Arquitetura compartilhada

**Blocking:** M3.

**Problem:** uma permissão combina ação, tipo de recurso e, se preciso, setor (PER-02), vem de três origens que se
somam (PER-03) e precisa ser extensível para tipos de usuário futuros.

**Nota (2026-11-13):** proposta na technical-spec `permissoes/catalogo-e-classificacao`: permissão como código
`<recurso>.<acao>` num catálogo em código; concessões a cargo, setor ou usuário, revogadas e nunca apagadas; união
calculada por função pura; sem escopo por setor do item (decisão do dono).

**Follow-up:** technical-spec `permissoes/catalogo-e-classificacao`.

---

### AD-008 — Como modelar o motor de aprovações e as versões de solicitação?

**Status:** Pending

**Scope:** Arquitetura compartilhada

**Blocking:** M5, e por consequência M7 e M8.

**Problem:** o motor é genérico (despesas, eventos e requisições futuras), com regras por tipo e por setor, versões
que não se sobrescrevem e liquidação imutável (APR-01 a APR-11).

**Nota (2026-11-11):** a descoberta do domínio mudou as premissas: um só validador por solicitação, contestar como
terceira decisão, e evento com custo como duas solicitações ligadas (`docs/domain/discovery/event-storming.md`).

**Follow-up:** ADR na especificação do M5.

---

### AD-009 — Como modelar a trilha de auditoria?

**Status:** Resolved

**Decision:** tabela só de inserção (`RegistroDeAuditoria`), com IDs e códigos, sem dado pessoal; o modelo recusa
alterar e apagar, e um gatilho no banco recusa o mesmo por qualquer caminho. Escrita por `auditoria.public.registrar`,
na transação do caso de uso.

**Resolved on:** 2026-11-12, por Leandro Nascimento, na aprovação da technical-spec `acesso/identidade-e-acesso`

**Scope:** Arquitetura compartilhada

**Blocking:** M3.

**Problem:** toda ação relevante gera registro imutável (AUD-01), consultável no detalhe de cada item (AUD-03).

**Nota (2026-11-12):** modelagem proposta na technical-spec `acesso/identidade-e-acesso`: tabela só de inserção, com
gatilho no banco que recusa alterar e apagar. A gravação entra no M2; a consulta, no M3.

**Follow-up:** implementada no M2; a consulta nas telas (RF-027) entra no M3.

---

### AD-010 — Como modelar estornos e cancelamentos?

**Status:** Pending

**Scope:** Arquitetura compartilhada

**Blocking:** M7.

**Problem:** estorno e cancelamento de lançamentos liquidados geram um novo lançamento ligado ao original, com
justificativa e permissão (APR-09, FIN-18).

**Follow-up:** ADR na especificação do M7.

---

### AD-011 — Onde ficam os anexos?

**Status:** Pending

**Scope:** Arquitetura compartilhada

**Blocking:** M6.

**Problem:** comprovantes e documentos precisam caber no custo mínimo, com acesso controlado por permissão e ponto de
extensão para trocar de provedor (RNF-06, RNF-07).

**Options:** Option A — armazenamento local na instância. Option B — S3 no free tier. (Hipóteses do enunciado.)

**Follow-up:** ADR no rito 7 ou antes do M6.

---

### AD-012 — Qual provedor de e-mail?

**Status:** Pending

**Scope:** Arquitetura compartilhada

**Blocking:** M2 (verificação de e-mail) e M4.

**Problem:** o envio precisa caber no custo mínimo, com ponto de extensão para trocar de provedor (RNF-06).

**Nota (2026-11-12):** o sistema usa SMTP genérico pela abstração do Django, configurado por variável de ambiente. A
escolha do provedor deixa de bloquear o M2 e fica para o M12.

**Follow-up:** ADR antes do M2.

---

### AD-013 — Como ficam o CI/CD, o deploy e o dimensionamento da instância única?

**Status:** Pending

**Scope:** Arquitetura compartilhada

**Blocking:** M1 (CI) e M12 (deploy).

**Problem:** GitHub Actions dentro do plano gratuito (RNF-04), tudo numa instância AWS do free tier (RNF-02), mesmas
imagens em desenvolvimento e produção (RNF-03), imagens versionadas para rollback e backup do banco (RNF-05). O
enunciado pede verificar se o conjunto cabe na máquina.

**Nota (2026-11-11):** CI, estrutura do repositório e imagens estão na ADR-007 (Accepted em 2026-11-12). Memória medida com o
esqueleto no ar: cerca de 330 MB em repouso. Continuam em aberto: registro de imagens, deploy na instância, HTTPS,
backup, rollback e as regras do free tier para a conta do dono.

**Follow-up:** ADR-007 agora; ADR de deploy no M12.

---

### AD-014 — O que o painel do admin cria sozinho e o que exige programação?

**Status:** Resolved

**Decision:** o painel concede e revoga permissões do catálogo; criar uma permissão nova é programação.

**Resolved on:** 2026-11-13, por Leandro Nascimento

**Scope:** Dono do marco M3

**Blocking:** M3.

**Problem:** o painel monta combinações a partir de ações e recursos conhecidos; comportamento totalmente novo é
criado por programação (PER-05). O enunciado permite propor outra abordagem.

**Nota (2026-11-13):** o dono aprovou, na spec funcional, que o catálogo fica no código e o painel só concede e
revoga o que existe nele. Passa a Resolved com a aprovação da technical-spec.

**Follow-up:** technical-spec `permissoes/catalogo-e-classificacao`.

---

### AD-015 — O que a LGPD exige para este caso?

**Status:** Pending

**Scope:** Arquitetura compartilhada

**Blocking:** M2.

**Problem:** o sistema guarda nome, telefone, e-mail e dados financeiros de diretores, sem CPF (RNF-07). Nada é
apagado (AUD-04), o que precisa ser conciliado com os direitos do titular.

**Nota (2026-11-12):** avaliação em `docs/security/lgpd.md` e modelo de ameaças em `docs/security/threat-model.md`.
Ficam para o M12: confirmar a base legal, decidir a anonimização a pedido e o procedimento de incidente.

**Follow-up:** avaliação junto com o threat model do M2 (`sdd-method:reviewing-security`).

---

### AD-016 — Quais itens do protótipo, não cobertos pelo enunciado, entram na etapa 1?

**Status:** Resolved

**Decision:** todos os itens entram na etapa 1: chave Pix, Pix copia e cola e QR Code, recibo, cobranças em lote,
fluxo de caixa previsto e realizado, atas de reunião e postagem fixada.

**Resolved on:** 2026-11-11, por Leandro Nascimento

**Scope:** Escopo de entrega

**Blocking:** rito 6 (registro de requisitos).

**Problem:** a seção 16 do enunciado lista itens que o dono deve confirmar ou descartar no M0:

- chave Pix e QR Code na cobrança, e recibo ao pagador depois de pago;
- criação de cobranças em lote;
- fluxo de caixa com total previsto, realizado e inadimplência;
- atas de reunião e postagem fixada no feed.

**Nota (2026-11-11):** na descoberta do domínio, o dono confirmou a chave Pix (várias chaves, cadastradas pelo
admin), o Pix copia e cola e o QR Code com valor, e o recibo em PDF ao pagador. Continuam sem resposta: cobranças em
lote, fluxo de caixa previsto e realizado, atas de reunião e postagem fixada.

**Follow-up:** RF-047, RF-049, RF-052, RF-059, RF-096, RF-099 e RF-110 em `docs/requirements/requirements.md`
(CB-01).

---

### AD-017 — Qual tecnologia para o aplicativo mobile?

**Status:** Deferred

**Scope:** Arquitetura compartilhada

**Blocking:** nada na etapa 1.

**Problem:** o enunciado pede comparar Kotlin, React Native e outras, pesando produtividade, ecossistema e
reaproveitamento com o web. É etapa futura, só documentada.

**Follow-up:** comparação documentada como parte do E14; decisão no enunciado da fase do app. Gatilho: site completo.

---

### AD-018 — Multi-cliente: um deploy por cliente ou SaaS com contas?

**Status:** Deferred

**Scope:** Arquitetura compartilhada

**Blocking:** nada na etapa 1.

**Problem:** o enunciado tira essa decisão do escopo (BRD-05), mas exige que a arquitetura não feche nenhuma das duas
portas.

**Follow-up:** a avaliação do rito 2 registra o que manter aberto. Gatilho: segundo cliente.

---

### AD-019 — Como criar o primeiro admin de forma segura?

**Status:** Resolved

**Decision:** comando no servidor (`criar_admin`), que pede os dados na hora; pode haver vários admins.

**Resolved on:** 2026-11-12, por Leandro Nascimento, na aprovação da spec funcional `acesso/identidade-e-acesso`

**Scope:** Dono do marco M2

**Blocking:** M2.

**Problem:** o novo sistema começa vazio e o acesso é só por convite gerado pelo admin, então o primeiro admin
precisa de outro caminho, sem senha padrão (seção 16 do enunciado).

**Nota (2026-11-12):** o dono escolheu um comando no servidor, que pede os dados na hora; pode haver vários admins.

**Follow-up:** especificação do M2.
