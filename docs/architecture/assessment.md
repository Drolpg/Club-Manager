# Avaliação de arquitetura

| Campo | Valor |
| --- | --- |
| Fase | Preliminar (a partir do enunciado); a confirmação acontece ao fechar a especificação |
| Data | 2026-11-11 |
| Tipo de projeto | Sistema de domínio rico |
| Responsável | Leandro Nascimento |
| Decisão | [ADR-001](../adr/ADR-001-estilo-arquitetural.md) (Proposed) |

## Sinais

| Sinal | Nível | Evidência |
| --- | --- | --- |
| Regras e estados (invariantes, máquinas de estado, cálculos com regra) | Alto | Cobrança com 7 estados e saída com 8 (seção 7); solicitação com versões que não se sobrescrevem (APR-08); aprovação por vários setores em que uma recusa basta (APR-04); solicitante não aprova o próprio pedido (APR-02); liquidado é imutável e só se corrige por lançamento novo (APR-09, FIN-18); permissão como união de três origens (PER-03) |
| Integrações (quantas, quão instáveis, precisam de fake?) | Médio | Login com Google (ACE-01), envio de e-mail (NOT-01) e armazenamento de anexos (RNF-06). As três precisam de fake nos testes. Plataforma de pagamento é só ponto de extensão futuro (seção 3) |
| Troca de tecnologia prevista (provedor, canal, banco, LLM) | Médio | O enunciado pede ponto de extensão para trocar o provedor de e-mail e o de armazenamento (RNF-06) e prevê um canal novo de notificação, o push (NOT-02). Banco e framework não têm troca prevista |
| Equipe e trabalho em paralelo | Baixo em pessoas, alto em áreas | Uma pessoa com um agente de IA. Mas são cerca de dez áreas de negócio (seções 5 a 12), entregues em 13 marcos, e três delas (financeiro, eventos, requisições futuras) usam o mesmo motor de aprovação |
| Vida útil e evolução (POC, MVP, produto) | Alto | Produto white-label reaproveitável (seção 1), com quatro etapas futuras já previstas: app, novos tipos de usuário, gestão do time e multi-cliente (seção 14) |
| Processamento assíncrono (filas, workers, idempotência) | Médio | Tarefas agendadas para vencimentos, cobranças recorrentes, expiração de convite, fim de isenção e aviso do dia do evento (NOT-07); e-mail e relatórios pesados em segundo plano (REL-03). Gerar a mesma cobrança duas vezes seria um erro financeiro |
| Conformidade e auditoria (dinheiro, dados pessoais, regulação) | Alto | Valores financeiros, ainda que escriturais; dados pessoais sob LGPD (RNF-07); trilha de auditoria imutável para toda ação relevante (AUD-01); nada é apagado (AUD-04) |

## Fronteiras reais

| Fronteira | Por que é real | Precisa de fake nos testes? | Troca prevista? |
| --- | --- | --- | --- |
| Provedor de e-mail | Serviço externo, com falha e limite de envio | Sim | Sim (RNF-06) |
| Armazenamento de anexos | Disco local ou S3; o acesso passa por permissão (RNF-07) | Sim | Sim (RNF-06) |
| Identidade Google | Serviço externo que valida o login social | Sim | Não |
| Canais de notificação | Já nascem dois (e-mail e caixa no site) e o push está previsto | Sim | Sim (NOT-02) |
| Fila e agendador | As tarefas rodam fora da requisição e podem repetir | Não (execução síncrona nos testes) | Possível (AD-005) |
| Motor de aprovações ↔ quem o usa | O motor serve despesas, eventos e requisições futuras sem conhecê-los (APR-03) | Sim (um tipo de solicitação de teste) | Novos tipos previstos |
| Entre as áreas de negócio | Financeiro, eventos, permissões e auditoria mudam por motivos diferentes; o risco do tipo de projeto é o acoplamento entre áreas | Não | Não |
| Site e app ↔ API | Dois clientes, uma API; nenhuma regra nos clientes (RNF-01) | Contrato verificado | App futuro |

O que **não** é fronteira: o banco de dados. É um PostgreSQL só, sem troca prevista, e os testes de integração usam o
banco real.

## Recomendação

**Estilo:** monólito modular, com o estilo interno variando por módulo:

- **Módulos core** (aprovações, financeiro, eventos) → DDD tático: aggregates com invariantes e transições de estado
  testadas, e as regras de decisão em funções puras.
- **Módulos de apoio** (acesso, permissões, auditoria, notificações, feed, documentos, marca, relatórios) → camadas
  (API → serviços → modelos), com funções puras onde houver regra (por exemplo, a resolução das permissões).
- **Ports só nas fronteiras reais**, e preferindo a abstração que o framework já oferece em vez de uma paralela.

Respondendo à pergunta do enunciado: nem hexagonal completa nem Clean Architecture. O que mais se aproxima é "portas e
adaptadores" restrito às fronteiras da tabela acima, dentro de um monólito dividido por área de negócio.

| Elemento estrutural | Sinal que justifica | Custo |
| --- | --- | --- |
| Um módulo de topo por área de negócio, com API pública e dependências acíclicas | Número de áreas alto; risco de acoplamento entre áreas | Disciplina de import; uma regra por módulo na ferramenta de fronteira |
| Teste de fronteira de módulos no CI | Sem ele, a fronteira some na primeira pressa; não há segunda pessoa para revisar | Configuração única e um job curto |
| Aggregates com invariantes nos módulos core (candidatos: Solicitação, Cobrança, Saída, Evento) | Regras e estados altos; dinheiro; liquidado imutável | Ritos 4 e 5; mais testes de invariantes |
| Funções puras de decisão (transições permitidas, resultado da aprovação, quem pode decidir, resolução de permissões, datas de recorrência) | Regras que precisam ser testadas sem infraestrutura; fluxos críticos sem homologação (RNF-05) | Um pacote sem import de framework por módulo que tiver regra |
| Registro de tipos de solicitação no motor de aprovações, com notificação em processo e na mesma transação para quem usa o motor | Motor genérico para despesas, eventos e requisições futuras | Uma interface pequena e um registro; nada de mensageria |
| Serviço de auditoria só de inserção, chamado pelos serviços na mesma transação | Conformidade alta (AUD-01 a AUD-04) | Um módulo e uma chamada por caso de uso |
| Abstração de canal de notificação | Dois canais hoje, um terceiro previsto | Uma interface e duas implementações |
| Port de e-mail e port de armazenamento | Troca de provedor prevista; fake nos testes | Zero código próprio se o framework já tiver a abstração (ver "Indicações para a stack") |
| Tarefas agendadas idempotentes | Assíncrono médio; cobrança duplicada é erro financeiro | Restrição de unicidade por recorrência e competência; teste de reexecução |
| Contrato da API gerado pela aplicação e versionado | Dois clientes, uma API (RNF-01) | Geração automática e um teste de contrato |

### Módulos candidatos

A lista definitiva sai do desenho estratégico (rito 4). Ponto de partida:

| Módulo | Papel | Depende de |
| --- | --- | --- |
| `acesso` | Usuários, convites, login, verificação de e-mail | auditoria, notificações |
| `permissoes` | Catálogo, cargos, setores, concessões | acesso, auditoria |
| `auditoria` | Trilha imutável | — |
| `notificacoes` | Registro, caixa de entrada, e-mail, preferências | acesso |
| `aprovacoes` (core) | Solicitação genérica, versões, regras por setor, decisões | permissoes, auditoria, notificacoes |
| `financeiro` (core) | Categorias, cobranças, entradas, saídas, isenção, estorno | aprovacoes, permissoes, auditoria, notificacoes |
| `eventos` (core) | Proposta, calendário, encerramento | aprovacoes, financeiro, permissoes, auditoria, notificacoes |
| `comunicacao` | Feed de comunicados e documentos | permissoes, auditoria, notificacoes |
| `marca` | Escudo, cores, temas | permissoes, auditoria |
| `relatorios` | Dashboard, perfil (leitura composta), PDF e CSV | lê as APIs públicas dos demais |

## O que não adotar

| Elemento | Por quê | Regra no AGENTS.md |
| --- | --- | --- |
| Hexagonal completa (ports para o banco, núcleo sem ORM) | Um banco só, sem troca prevista; duplicaria cada modelo | "Não criar port nem repository para o banco" |
| Entidades de domínio separadas dos modelos de persistência, com mappers | Mesmo motivo; as invariantes ficam no próprio modelo e as decisões em funções puras | "O aggregate é o modelo persistido; não criar entidade paralela nem mapper" |
| Clean Architecture (boundaries de entrada e saída, presenters) | Cerimônia sem ganho para uma pessoa; os serviços de cada módulo já são os casos de uso | "Não criar interactors, presenters nem DTOs de boundary" |
| Ports para o que não é fronteira (relógio, banco, o próprio framework) | Uma implementação só, sem fake que justifique; tempo se congela nos testes | "Port só para as fronteiras listadas na ADR-001" |
| Container de injeção de dependência | Poucas fronteiras; configuração por ambiente basta | "Não adicionar container de DI" |
| Aggregates, value objects e eventos de domínio nos módulos de apoio | CRUD com pouca regra | "DDD tático só em aprovacoes, financeiro e eventos" |
| Mensageria entre módulos, barramento de eventos, outbox | Um processo, uma transação; a fila serve só para tarefas agendadas e envio | "Módulos se chamam por API pública em processo" |
| Event sourcing | A trilha de auditoria e as versões da solicitação já dão o histórico pedido | "Não adotar event sourcing" |
| CQRS com read models | Poucos usuários; o dashboard lê direto com consultas | "Não criar read models; consultas diretas" |
| Microsserviços ou serviços separados | Uma instância, uma pessoa (RNF-02) | "Um único deployável de backend" |
| Multi-tenancy (coluna de cliente, schema por cliente) | Fora de escopo (BRD-05); o único cliente é o time do dono | "Não adicionar tenant; ver gatilhos" |
| Gateway de pagamento | Só ponto de extensão previsto (seção 3) | "Não criar port de pagamento antes do gatilho" |

## Trilha de domínio

**DDD completo, restrito ao core e com a descoberta simplificada** — as regras e os estados são altos, mas o enunciado
já traz glossário, estados e fluxos, e o projeto é solo.

| Rito | Como roda |
| --- | --- |
| 3 Descoberta | Simplificado: entrevista guiada só sobre os fluxos do core (cobrança, saída, solicitação, evento) e os hotspots, que são as pendências e hipóteses da seção 15. Sem Event Storming completo |
| 4 Estratégico | Completo, mas curto: contextos, context map e glossário para o sistema inteiro |
| 5 Tático | Só para aprovações, financeiro e eventos |

## Gatilhos para subir de nível

- Segundo cliente real → resolver a AD-018 (deploy por cliente ou SaaS) antes de qualquer mudança de modelo.
- Integração com plataforma de pagamento entra no escopo → criar a port de pagamento no financeiro.
- App mobile começa e o push entra → terceira implementação do canal de notificação; revisar a estratégia de tokens.
- Invariantes do core ficam lentas ou difíceis de testar por causa do banco → separar entidade de domínio e
  persistência só no aggregate afetado.
- Um módulo de apoio ganha estados e invariantes (por exemplo, permissões com vigência e aprovação) → DDD tático nele.
- O dashboard ou os relatórios ficam lentos com consultas diretas → read model só para a consulta afetada.
- A instância única não comporta API, banco e workers → separar banco ou workers (o enunciado já exige que isso seja
  possível).

## Sinais de excesso (para descer de nível)

- Um aggregate sem nenhuma invariante testada → volta a ser modelo simples com serviço.
- Uma interface com uma implementação só, sem fake nos testes e sem troca prevista → remover.
- Um módulo que só repassa chamadas para outro → fundir os dois.
- A regra de fronteira de um módulo acumula exceções → a divisão está errada; rever no context map.

## Alternativas consideradas

| Estilo | Por que não |
| --- | --- |
| Camadas simples, sem módulos | Dez áreas num pacote só; estados e invariantes espalhados por serviços (o erro "camadas anêmicas num domínio com muitas regras") |
| Camadas + ports nas fronteiras, sem DDD (a arquitetura do protótipo) | Resolve as integrações, mas não o problema central, que são regras e estados; não organiza as áreas |
| Hexagonal completa | Paga por trocar tecnologia que o projeto não vai trocar (banco, framework); as fronteiras reais são poucas |
| Clean Architecture simplificada | Mesma regra de dependência da hexagonal, com mais cerimônia; não há time que já a pratique |
| Fatias verticais | As features compartilham muita regra (motor de aprovações, permissões, auditoria) |
| Monólito modular com DDD completo em todos os módulos | Aggregates em feed, documentos e marca seriam excesso |

## Indicações para a stack (não são decisão)

A stack se decide em ADRs próprias, antes da arquitetura base (rito 7). O que esta avaliação adianta, porque o
enunciado pede a proposta já no M0 e porque o estilo depende em parte dela:

| Decisão | Inclinação | Motivo | A verificar |
| --- | --- | --- | --- |
| AD-003 Framework | Django | ORM com migrações reversíveis, autenticação e hash de senha prontos, e as abstrações de e-mail e de armazenamento já são as duas ports de que o projeto precisa, com fakes inclusos. É a opção familiar ao dono. FastAPI exigiria montar tudo isso à mão | Biblioteca da camada de API e geração do contrato |
| AD-004 Frontend | React com TypeScript | Direção do enunciado; reaproveita conhecimento para um app em React Native (AD-017) | Biblioteca de componentes e estratégia de temas (BRD-02) |
| AD-005 Filas | Celery com Redis, com o agendador embutido no worker | É a preferência do enunciado; o agendador embutido poupa um processo na instância única | Memória real medida no M1 |
| AD-013 Instância | Cabe, mas apertado | Estimativa grosseira para 1 GB de RAM: API, PostgreSQL, Redis, um worker, proxy e sistema somam perto de 800 MB; exige configuração enxuta e swap | Medição no M1. As regras do free tier da AWS mudaram para contas novas (créditos por tempo limitado, em vez de 12 meses de instância); confirmar o que vale para a conta do dono |
| AD-002 Repositório | Reaproveitar este | Só tem o commit inicial e o remoto já existe; o protótipo nunca entrou no histórico. Sugestão: mover o protótipo para uma pasta ignorada pelo git (`_prototipo/`), para consulta, e apagá-la no M12 | Decisão do dono |

## Quality gates do tipo de projeto

- Invariantes dos aggregates testadas.
- Teste de fronteira de módulos no CI.
- Contrato da API gerado e verificado.
- Idempotência das tarefas agendadas testada.
- Auditoria de coerência ao fim de cada marco.

Diagramas esperados no README: C4 (contexto e containers), context map, estados (cobrança, saída, solicitação,
evento) e modelo de domínio.
