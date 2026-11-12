# ADR 001: Estilo arquitetural e nível de investimento

**Status:** Accepted  
**Date:** 2026-11-11  
**Deciders:** Leandro Nascimento  
**Avaliação:** [docs/architecture/assessment.md](../architecture/assessment.md)  
**Resolve:** AD-001

---

## Contexto

Tipo de projeto: sistema de domínio rico. Sinais determinantes (detalhes na avaliação):

- **Regras e estados, alto:** cobrança com 7 estados, saída com 8, solicitação versionada, aprovação por vários
  setores, registros liquidados imutáveis.
- **Conformidade, alto:** dinheiro, dados pessoais sob LGPD, auditoria imutável de toda ação relevante.
- **Vida útil, alto:** produto white-label com quatro etapas futuras previstas.
- **Áreas de negócio, alto:** cerca de dez, com um motor de aprovação compartilhado por três delas.
- **Integrações e troca de tecnologia, médio:** e-mail, armazenamento e login Google; troca prevista só de provedor.
- **Equipe, baixo:** uma pessoa com um agente de IA.

Fronteiras reais: provedor de e-mail, armazenamento de anexos, identidade Google, canais de notificação, fila e
agendador, o motor de aprovações em relação a quem o usa, as áreas de negócio entre si, e os clientes (site e app) em
relação à API. O banco de dados não é fronteira.

## Considered Options

### Option 1: Camadas + ports nas fronteiras, sem DDD

É a arquitetura do protótipo. Resolve as integrações com pouco código. Faltaria o principal: nada organiza dez áreas
de negócio nem protege estados e invariantes, que acabariam espalhados por serviços.

### Option 2: Monólito modular, com DDD tático no core e camadas no resto ✅ RECOMENDADA

Um módulo por área de negócio, com fronteira verificada no CI. Aggregates só onde há regra e estado (aprovações,
financeiro, eventos); camadas simples nos módulos de apoio; ports só nas fronteiras reais. Paga a estrutura onde o
problema está e em nenhum outro lugar.

### Option 3: Hexagonal completa ou Clean Architecture

Acrescentaria um núcleo sem ORM, com ports e mappers para o banco, e (na Clean) boundaries e presenters por caso de
uso. O custo não se paga: o banco e o framework não vão ser trocados, e não há time que já pratique o estilo.

## Decision

Será adotado **monólito modular**, com o estilo interno por módulo:

- `aprovacoes`, `financeiro`, `eventos` → DDD tático;
- demais módulos → camadas (API → serviços → modelos).

Elementos estruturais e o sinal que justifica cada um:

| Elemento | Justificativa |
| --- | --- |
| Módulo de topo por área de negócio, com API pública e dependências acíclicas | Número de áreas alto; risco de acoplamento |
| Teste de fronteira de módulos no CI | Projeto solo, sem revisor para segurar a fronteira |
| Aggregates com invariantes no core | Regras e estados altos; dinheiro |
| Funções puras de decisão, sem import de framework | Regras testáveis sem infraestrutura; sem ambiente de homologação |
| Registro de tipos de solicitação no motor de aprovações | Motor genérico para despesas, eventos e requisições futuras |
| Auditoria só de inserção, na mesma transação do caso de uso | Conformidade alta |
| Abstração de canal de notificação | Dois canais hoje, push previsto |
| Ports de e-mail e de armazenamento | Troca de provedor prevista; fake nos testes |
| Tarefas agendadas idempotentes | Cobrança duplicada é erro financeiro |
| Contrato da API gerado e versionado | Dois clientes, uma API |

Regras de dependência:

- Um módulo só importa a API pública de outro, nunca os modelos ou os serviços internos.
- As dependências entre módulos são acíclicas; `aprovacoes` não conhece `financeiro` nem `eventos`.
- Dentro de um módulo: a camada de API não tem regra de negócio; os serviços abrem a transação, checam a permissão e
  registram a auditoria; as funções de decisão não importam o framework.
- O aggregate é o modelo persistido; o estado só muda pelos métodos dele.

Trilha de domínio: **DDD completo restrito ao core, com a descoberta (rito 3) simplificada** para uma entrevista guiada
sobre os fluxos do core e os hotspots da seção 15 do enunciado. O rito 4 cobre o sistema inteiro; o rito 5, só
aprovações, financeiro e eventos.

## O que não será adotado

| Elemento | Motivo |
| --- | --- |
| Port ou repository para o banco; núcleo sem ORM | Um banco só, sem troca prevista |
| Entidade de domínio separada do modelo de persistência, com mapper | Duplicaria cada modelo sem fronteira que justifique |
| Interactors, presenters e DTOs de boundary (Clean Architecture) | Cerimônia sem ganho para uma pessoa |
| Ports para o que não é fronteira (relógio, banco, framework) | Uma implementação só e nenhum fake que as justifique |
| Container de injeção de dependência | Poucas fronteiras; configuração por ambiente basta |
| Aggregates, value objects e eventos de domínio nos módulos de apoio | CRUD com pouca regra |
| Mensageria entre módulos, barramento de eventos, outbox | Um processo e uma transação |
| Event sourcing | Auditoria e versões já dão o histórico pedido |
| CQRS com read models | Poucos usuários; consultas diretas bastam |
| Microsserviços | Uma instância e uma pessoa |
| Multi-tenancy | Fora de escopo (BRD-05) |
| Port de pagamento | Só ponto de extensão previsto |

Estas regras entram no `AGENTS.md` (seção "Regras de arquitetura"). Adotar qualquer um deles exige nova decisão.

## Gatilhos de reavaliação

| Gatilho | Mudança esperada |
| --- | --- |
| Segundo cliente real | Resolver a AD-018 antes de mexer no modelo |
| Plataforma de pagamento entra no escopo | Criar a port de pagamento no financeiro |
| App mobile e push | Terceiro canal de notificação; revisar tokens |
| Invariantes do core lentas ou difíceis de testar por causa do banco | Separar domínio e persistência no aggregate afetado |
| Módulo de apoio ganha estados e invariantes | DDD tático nesse módulo |
| Dashboard ou relatório lento | Read model só para a consulta afetada |
| A instância única não comporta o conjunto | Separar banco ou workers |
| Aggregate sem invariante testada, ou interface com uma implementação e sem fake | Remover a estrutura |

## Consequências

### Positivas ✅

- A estrutura pesada fica só em três módulos; o resto é código direto.
- Regras críticas testáveis sem banco, o que compensa a falta de homologação.
- Fronteiras verificadas por ferramenta, e não por disciplina.
- Extrair banco, workers ou um módulo continua possível.

### Negativas ❌

- Dentro do core, as invariantes dependem do ORM: parte dos testes precisa do banco.
- Virar SaaS multi-cliente exigirá migração em todas as tabelas.
- Três ritos de domínio antes de especificar, mesmo simplificados.
- Esta decisão supõe um framework com ORM e abstrações de e-mail e armazenamento (inclinação por Django, AD-003). Se
  a AD-003 for por FastAPI, as ports de e-mail e armazenamento passam a ser código próprio e esta ADR é revista.

### Mitigação de riscos

- Gatilhos revisados na auditoria de coerência ao fim de cada marco.
- Avaliação confirmada ao fechar a especificação (rito 6), antes da arquitetura base.

---

**Last Updated:** 2026-11-12  
**Decision Maker:** Leandro Nascimento (estilo, exclusões e gatilhos aceitos em 2026-11-11)  
**Status:** Accepted (gate da arquitetura base, 2026-11-12)
