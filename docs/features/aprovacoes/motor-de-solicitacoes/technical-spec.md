# Especificação Técnica: Motor de solicitações e aprovações

| Campo | Valor |
| --- | --- |
| Feature | `aprovacoes/motor-de-solicitacoes` |
| Status | Approved |
| Responsável | Leandro Nascimento |
| Atualizado em | 2026-11-13 |
| Aprovado por | Leandro Nascimento |
| Aprovado em | 2026-11-13 |
| Especificação funcional | `./functional-spec.md` (aprovada em 2026-11-13) |
| Decisões aplicadas | ADR-001 (DDD tático neste módulo), ADR-003, ADR-004; AD-008 |
| Pré-requisito | Features `permissoes/catalogo-e-classificacao` (M3) e `notificacoes/caixa-e-email` (M4) implementadas |

## Contexto e desenho

| Módulo | O que ganha |
| --- | --- |
| `kernel` | `dinheiro.py`: o value object `Dinheiro`, usado por `aprovacoes`, `financeiro` e `eventos` |
| `aprovacoes` | O aggregate `Solicitacao` (com `Versao` e `Decisao`), `MotivoDeDecisao`, o registro de tipos, serviços, rotas, a tarefa de lembretes e a API pública para os módulos donos |
| `frontend` | Fila de pendências, lista, detalhe com versões e decisões, ações e a tela de motivos |

### O motor não conhece quem o usa

Um módulo de cima registra um **tipo de solicitação** ao iniciar, com `aprovacoes.public.registrar_tipo(...)`:

| Campo do tipo | Para quê |
| --- | --- |
| `codigo`, `nome` | Identificação estável (`<modulo>.<tipo>`, por exemplo `financeiro.gasto`) e nome para as telas |
| `permissao_de_aprovar` | Código da permissão, no catálogo, de quem decide esse tipo |
| `permissao_de_enviar` | Opcional; sem ela, qualquer diretor com cargo envia |
| `tem_valor` | Se as versões têm valor (habilita o teto sugerido) |
| `preparar(conteudo, solicitante_id)` | Valida o conteúdo recebido e devolve o conteúdo normalizado, o valor e um resumo de uma linha. Recusa com `VALIDATION_ERROR` |
| `ao_mudar(mudanca)` | Chamado pelo motor, na mesma transação, a cada mudança de situação |

`ao_mudar` recebe um `MudancaDeSolicitacao` (congelado): `solicitacao_id`, `tipo`, `acontecimento` (`APROVADA`,
`CONTESTADA`, `RECUSADA`, `EDITADA`, `REABERTA`, `RETIRADA`, `CANCELADA`), `versao`, `valor`, `ator_id` e
`teto_sugerido`. Como cada tipo tem o próprio `ao_mudar`, um módulo só recebe os avisos do tipo dele. É a forma
concreta do "evento em processo para baixo" da ADR-003 neste módulo; não usa o despachante geral, porque o
destinatário é sempre um só e conhecido pelo registro.

Só o módulo dono chama `aprovacoes.public.iniciar_execucao(solicitacao_id)` e `encerrar(solicitacao_id)`; não há
rota para isso.

### Estrutura

```text
aprovacoes/
├── public.py        registrar_tipo, MudancaDeSolicitacao, iniciar_execucao, encerrar, situacao_de, motivo_aplicado
├── tipos.py         registro dos tipos de solicitação e dos tipos de decisão
├── models.py        Solicitacao (aggregate), Versao, Decisao, MotivoDeDecisao
├── domain/          transicoes.py (tabela de transições), decisores.py (quem pode decidir)
├── services/        solicitacoes, decisoes, execucao, motivos, consulta, lembretes
├── http/            serializers, views, urls
├── tasks.py         lembrar_solicitacoes_paradas
├── migrations/
└── tests/
```

## Modelo de domínio

Módulo core: o aggregate é o modelo persistido, e o estado só muda pelos métodos dele (ADR-001).

| Elemento | Tipo | Campos e observações |
| --- | --- | --- |
| `Solicitacao` | Aggregate root | `id`, `tipo`, `solicitante_id`, `aprovador_indicado_id`, `situacao`, `numero_da_versao_atual`, `criada_em`, `atualizada_em` |
| `Versao` | Entity | `numero`, `conteudo` (JSON), `valor`, `resumo`, `autor_id`, `justificativa`, `criada_em`, `lembrete_em`, `aviso_ao_admin_em`. Única por solicitação e número. Imutável, exceto as duas datas de lembrete |
| `Decisao` | Entity | Uma por versão (relação um para um): `tipo` (`APROVAR`, `CONTESTAR`, `RECUSAR`), `aprovador_id`, `motivo`, `motivo_texto` (cópia), `texto`, `mensagem`, `teto_sugerido`, `aprovacao_propria`, `criada_em`. Imutável |
| `MotivoDeDecisao` | Cadastro | `tipo_de_decisao` (código), `texto`, `ativo`. Único por tipo e texto, sem diferenciar maiúsculas |
| `Dinheiro` | Value object (`kernel`) | `Decimal` com duas casas, não negativo; recusa `float`. No banco, `DecimalField(max_digits=12, decimal_places=2)`; na API, texto |

### Funções puras

| Função | Regra |
| --- | --- |
| `transicao_permitida(situacao, comando)` | A tabela do diagrama da funcional, num lugar só. Todo método do aggregate a consulta antes de mudar o estado |
| `pode_decidir(fatos)` | Recebe: quem pergunta; o solicitante; o aprovador indicado; se quem pergunta tem a permissão de aprovar o tipo; se tem auto-aprovação. Devolve se pode decidir e se seria aprovação própria |
| `precisa_indicar_aprovador(tem_permissao_de_aprovar, tem_auto_aprovacao)` | INV-SOL-10 |

### Invariantes

As do canvas (INV-SOL-01 a INV-SOL-11) valem como estão. Esta spec acrescenta, por adendo ao canvas:

| ID | Regra | Como é garantida |
| --- | --- | --- |
| INV-SOL-12 | Só o solicitante retira, e só em análise; a retirada não cria versão | Método `retirar` |
| INV-SOL-13 | Só se reenvia uma solicitação `CONTESTADA` ou `RETIRADA`; o reenvio cria a versão seguinte | Método `reenviar` |
| INV-SOL-14 | Uma versão tem no máximo uma decisão | Relação um para um no banco, além da conferência no método |
| INV-SOL-15 | O aprovador indicado é um diretor ativo com cargo e não é o solicitante | Serviço de envio, com `permissoes.public.le_gestao` |

Toda mudança bloqueia a linha da solicitação (`select_for_update`). Duas decisões simultâneas: a segunda encontra a
solicitação fora de análise e é recusada (INV-SOL-01); o índice único da decisão é a segunda barreira.

### Tipos de decisão e motivos

Os tipos de decisão são declarados no código (`registrar_tipo_de_decisao(codigo, nome)`). Esta feature declara
`solicitacao.aprovar`, `solicitacao.contestar` e `solicitacao.recusar`; o M6 acrescentará os de pagamento. Os motivos
ficam no banco, por tipo de decisão. `aprovacoes.public.motivo_aplicado(motivo_id, tipo_de_decisao)` devolve o
texto a copiar, ou recusa (motivo inexistente, inativo ou de outro tipo): é o que os outros módulos usarão.

## Interfaces e fluxo de dados

### Rotas, sob `/api/v1/aprovacoes/`

| Método e caminho | Quem | Entrada | Observação |
| --- | --- | --- | --- |
| `GET tipos/` | Quem lê gestão | — | Tipos registrados: `codigo`, `nome`, `tem_valor` |
| `GET solicitacoes/` | Quem lê gestão | `?tipo=`, `?situacao=`, `?minhas=1`, `?antes=`, `?limite=` | Lista paginada, com o resumo e o valor da versão atual |
| `POST solicitacoes/` | Quem pode enviar o tipo | `tipo`, `conteudo`, `aprovador_indicado_id` | Cria em análise |
| `GET solicitacoes/{id}/` | Quem lê gestão | — | Detalhe: versões, decisões, indicação, e `acoes` (o que quem pergunta pode fazer agora) |
| `GET solicitacoes/{id}/historico/` | Quem lê gestão | — | Histórico de auditoria |
| `POST solicitacoes/{id}/retirar/` | Solicitante | — | |
| `POST solicitacoes/{id}/reenviar/` | Solicitante | `conteudo` | |
| `POST solicitacoes/{id}/reabrir/` | Solicitante, admin ou permissão | `justificativa`, `conteudo` (opcional) | |
| `POST solicitacoes/{id}/editar/` | Solicitante | `conteudo`, `justificativa` (opcional) | |
| `POST solicitacoes/{id}/cancelar/` | Solicitante, admin ou permissão | `motivo` (texto) | |
| `POST solicitacoes/{id}/aprovar/` | Quem pode decidir | `motivo_id`, `texto` | |
| `POST solicitacoes/{id}/contestar/` | Quem pode decidir | `motivo_id`, `mensagem`, `texto`, `teto_sugerido` | |
| `POST solicitacoes/{id}/recusar/` | Quem pode decidir | `motivo_id`, `texto` | |
| `GET fila/` | Logado | — | Em análise que quem pergunta pode decidir, da mais antiga para a mais nova |
| `GET motivos/` | Quem lê gestão | `?tipo_de_decisao=` | Os ativos; o admin vê também os inativos com `?todos=1` |
| `POST motivos/`, `POST motivos/{id}/editar/`, `…/desativar/`, `…/reativar/` | Admin | `tipo_de_decisao`, `texto` | |

O campo `acoes` do detalhe é calculado pela API com as mesmas funções puras; o site só mostra os botões que vierem
nele, sem repetir a regra.

| Situação | Código HTTP | Código de erro |
| --- | --- | --- |
| Tipo de solicitação desconhecido | 400 | `VALIDATION_ERROR` |
| Conteúdo recusado pelo módulo dono | 400 | `VALIDATION_ERROR` (com os campos em `details`) |
| Comando fora da situação certa | 422 | `NAO_ESTA_EM_ANALISE`, `NAO_ESTA_CONTESTADA_NEM_RETIRADA`, `NAO_ESTA_RECUSADA`, `NAO_PODE_EDITAR`, `NAO_PODE_CANCELAR` |
| Solicitante tentando decidir o próprio pedido sem auto-aprovação | 403 | `SOLICITANTE_NAO_DECIDE` |
| Quem não pode decidir esse tipo | 403 | `PERMISSION_DENIED` |
| Só o solicitante pode | 403 | `SO_O_SOLICITANTE` |
| Envio sem aprovador indicado quando é exigido | 422 | `APROVADOR_NAO_INDICADO` |
| Aprovador indicado inválido | 422 | `APROVADOR_INVALIDO` |
| Motivo ausente, inativo ou de outro tipo de decisão | 400 | `VALIDATION_ERROR` (`motivo_id`) |
| Contestar sem mensagem; reabrir sem justificativa; cancelar sem motivo | 400 | `VALIDATION_ERROR` |
| Teto numa solicitação sem valor | 422 | `TETO_SEM_VALOR` |
| Motivo repetido no mesmo tipo de decisão | 409 | `MOTIVO_JA_EXISTE` |
| Solicitação ou motivo inexistente | 404 | `NOT_FOUND` |

### Permissões declaradas

`solicitacoes.auto_aprovar` (fora do acesso total), `solicitacoes.reabrir` e `solicitacoes.cancelar`.

### Notificações

Tipos declarados em `notificacoes`: `aprovacoes.para_decidir` (ação), `aprovacoes.decidida` (informativa),
`aprovacoes.contestada` (ação), `aprovacoes.aprovador_indicado` (ação, ao indicado), `aprovacoes.indicacao_feita`
(informativa, ao admin), `aprovacoes.aprovacao_propria` (informativa, ao admin), `aprovacoes.lembrete` (ação),
`aprovacoes.parada` (informativa, ao admin) e `aprovacoes.saiu_da_fila` (informativa). A chave de cada notificação
inclui a solicitação e o número da versão, o que impede a duplicata. Os destinatários de "quem pode decidir" vêm de
`permissoes.public.quem_pode`, mais o aprovador indicado, menos o solicitante sem auto-aprovação.

### Lembretes

A tarefa `aprovacoes.lembrar_solicitacoes_paradas` roda uma vez por dia. Para cada solicitação em análise cuja
versão atual tem 3 dias ou mais e `lembrete_em` vazio, notifica quem pode decidir e preenche a data; aos 7 dias, o
mesmo com `aviso_ao_admin_em` e os admins. Rodar de novo não repete.

### Auditoria

`SOLICITACAO_ENVIADA`, `_RETIRADA`, `_REENVIADA`, `_REABERTA`, `_EDITADA`, `_CANCELADA`, `_APROVADA`, `_CONTESTADA`,
`_RECUSADA`, `_EM_EXECUCAO`, `_ENCERRADA`, `APROVADOR_INDICADO`; `MOTIVO_CRIADO`, `_EDITADO`, `_DESATIVADO`,
`_REATIVADO`. A justificativa de reabrir e o motivo de cancelar vão no campo `justificativa` do registro.

## Persistência e dados

| Migração | Conteúdo |
| --- | --- |
| `aprovacoes/0001_solicitacao_versao_decisao_motivo` | As quatro tabelas e os índices |
| `aprovacoes/0002_motivos_iniciais` | A lista sugerida de motivos |

Classificação dos dados: os motivos iniciais são **referência obrigatória**; a reversão remove os que nenhuma
decisão usa.

| Tipo de decisão | Motivos iniciais |
| --- | --- |
| Aprovar | "Dentro do orçamento"; "Necessário para a atividade do clube"; "Conforme combinado em reunião" |
| Contestar | "Valor acima do necessário"; "Faltam detalhes dos itens"; "Falta justificativa"; "Data ou prazo a rever" |
| Recusar | "Sem caixa disponível"; "Fora das prioridades do clube"; "Pedido duplicado" |

`conteudo` é JSON validado pelo módulo dono; o motor nunca o consulta por dentro. `resumo` e `valor` ficam em
colunas próprias, para a lista e a fila não dependerem do formato de cada tipo.

## Segurança e operação

| Tema | Decisão |
| --- | --- |
| Autorização | Cada comando confere o ator no serviço, com as funções puras; a rota não decide nada. `acoes` no detalhe é só conveniência do site |
| Separação de funções | INV-SOL-02 é testada por todos os caminhos: sem permissão, com permissão, com indicação, com acesso total e com auto-aprovação |
| Elevação pela indicação | O indicado ganha o direito de decidir só aquela solicitação; a indicação é auditada e o admin é notificado |
| Conteúdo | JSON limitado a 64 KB; validado pelo módulo dono; o site o mostra como texto |
| Imutabilidade | Versões e decisões recusam alteração no modelo; não há rota de edição nem de exclusão |
| Concorrência | Bloqueio da linha em todo comando; teste com duas decisões concorrentes |
| Tratador do módulo dono | Roda na transação: um erro nele desfaz a decisão, e o aprovador vê o erro |
| Modelo de ameaças | `docs/security/threat-model.md` ganha a seção deste marco: decidir o próprio pedido por atalho, decisão sobre versão antiga, indicação abusiva, conteúdo malicioso |

Sem dependência nova e sem configuração nova. A agenda do Celery ganha a tarefa diária de lembretes.

## Estratégia de testes

| Camada | O que cobre | Tipo de teste |
| --- | --- | --- |
| Domínio puro | `Dinheiro`; a tabela de transições inteira (cada par situação e comando); `pode_decidir` e `precisa_indicar_aprovador` em todas as combinações | Unitário, sem banco |
| Aggregate | INV-SOL-01 a INV-SOL-15, uma a uma; imutabilidade de versão e decisão | Integração com PostgreSQL |
| Serviços | Cada cenário da funcional, com um tipo de teste registrado; avisos ao módulo dono; auditoria; notificações e destinatários | Integração |
| Concorrência | Duas decisões na mesma versão, em transações separadas | Integração, com `transaction=True` |
| Contrato | Cada rota: sucesso, cada erro da tabela, e os níveis de acesso | Integração HTTP |
| Isolamento entre tipos | Dois tipos de teste: cada `ao_mudar` recebe só o seu (CA-34) | Integração |
| Lembretes | 3 e 7 dias; rodar duas vezes; nova versão zera a contagem | Integração, com o relógio fixado |
| Fronteiras | `aprovacoes` não importa `financeiro` nem `eventos`; `aprovacoes/domain` sem framework | Teste de arquitetura existente |
| Site | Fila, lista, detalhe com versões, cada ação com o seletor de motivo, e a tela de motivos | Vitest e Testing Library |

O tipo de teste (`teste.pedido`, com a permissão `teste.aprovar`) é registrado numa fixture e removido ao fim. Cada
critério de aceite CA-01 a CA-34 tem ao menos um teste; a matriz fica no plano.

## Documentação a atualizar

- [ ] Contrato gerado; `docs/api/README.md`; `docs/api/manual-testing.md`
- [ ] `docs/domain/aggregates/solicitacao.md`: adendo com `RETIRADA` e INV-SOL-12 a INV-SOL-15
- [ ] `docs/domain/domain-events.md` e `domain-model.md`: `MudancaDeSolicitacao` e a situação nova
- [ ] `docs/domain/ubiquitous-language.md`: "retirar" e "retirada"
- [ ] `docs/architecture/project-structure.md`: como um módulo registra um tipo de solicitação
- [ ] `docs/security/threat-model.md`: seção do M5
- [ ] Registro de requisitos e de decisões (AD-008)

## Adendos

### Adendo 1 — Ajustes da conferência do plano contra o código

| Campo | Valor |
| --- | --- |
| Status | Draft |
| Motivo | Esta spec foi escrita antes de o M3 e o M4 serem implementados; a conferência do plano contra o código, antes da implementação, pediu os ajustes abaixo. Acompanha o adendo 1 da funcional |
| Aprovado por | — |
| Aprovado em | — |

**API pública (`aprovacoes/public.py`).** Além do que a seção "Estrutura" lista:

| Função | Por quê |
| --- | --- |
| `enviar(...)`, que devolve o ID da solicitação | O mapa de contextos já prometia "abrir solicitação de um tipo registrado"; o complemento (M7) e o orçamento de evento (M8) são abertos pelo módulo dono, e não pela rota genérica |
| `registrar_tipo_de_decisao(codigo, nome)` | O Financeiro (M6) declara os próprios tipos de decisão (RN-011) |

`iniciar_execucao` e `encerrar` ganham `ator_id` opcional (nulo quando é o sistema). `registrar_tipo` falha ao
iniciar se a permissão informada não está no catálogo. `preparar` roda dentro da transação do serviço.

**Autorização num lugar só.** Uma função pura `avaliar(comando, fatos)` em `aprovacoes/domain/` devolve se o ator
pode, o código de erro e se é aprovação própria; `pode_decidir` e `precisa_indicar_aprovador` são usadas por ela. Os
serviços levantam o erro que ela devolve e o campo `acoes` do detalhe é calculado com ela. Os serviços mantêm a
autorização separada da mudança de estado, para que um caminho "o módulo dono já autorizou" possa ser acrescentado
depois sem reescrevê-los.

**Ordem das conferências:** entrada (400) → leitura de gestão (403) → existência (404) → quem pode (403) →
situação (422). A leitura vem antes da existência para que quem não lê os dados não descubra quais IDs existem.

**Códigos de erro de situação.** Vale a tabela desta spec; o canvas do aggregate é alinhado a ela. Para o que a
tabela não trazia: `iniciar_execucao` → `NAO_ESTA_APROVADA`; `encerrar` → `NAO_PODE_ENCERRAR`; indicação por quem
não precisa indicar → `APROVADOR_INVALIDO`.

**Rota nova:** `GET tipos-de-decisao/`, só leitura, para o admin: a tela de motivos precisa da lista.

**Imutabilidade também no banco** (decisão do dono, 2026-11-13; substitui a linha "Imutabilidade" da tabela de
segurança). Além de `save` e `delete` recusarem no modelo, um gatilho no banco, no padrão do de `auditoria`:
`Decisao` recusa alteração e exclusão; `Versao` recusa exclusão e só aceita alterar `lembrete_em` e
`aviso_ao_admin_em`. O gatilho entra numa migração própria, reversível, com teste por SQL direto.

**Tipo de demonstração** (decisão do dono, 2026-11-13; substitui "sem configuração nova"). A variável
`APROVACOES_TIPO_DE_DEMONSTRACAO` liga, no `ready`, o tipo `demonstracao.pedido` (com valor) e a permissão
`demonstracao.aprovar`. Só vale com `DEBUG` ligado: com `DEBUG` desligado ela é ignorada, mesmo definida, e isso
tem teste. Fica desligada por padrão, entra no `.env.example` e em `docs/setup/configuration.md`, e não aparece no
compose de produção. É o que permite percorrer o ciclo no navegador antes do M7.

**Limites de texto:** mensagem, justificativa e complemento do motivo até 1000 caracteres; resumo da versão até
200. O texto da notificação é cortado para caber nos limites de `notificacoes` (título 120, texto 500).

**Dependências do módulo.** `aprovacoes` importa `acesso.public` (dados básicos do usuário, admins ativos e
histórico com nomes), além de `permissoes.public`, `notificacoes.public` e `auditoria.public`. As classes de
permissão das rotas e a conferência de admin são do próprio módulo, escritas sobre essas APIs públicas.

**Fora deste adendo, para o refinamento do M7 e do M8.** A conferência mostrou que a API pública ainda não basta
para: avisar o Eventos quando muda um orçamento, que é um tipo do Financeiro (hoje só o dono do tipo é avisado);
cancelar ou editar uma solicitação por decisão do módulo dono, quando quem age não é o solicitante; e avisar o
dono do tipo no envio e no reenvio. São acréscimos à API, sem mudança no que este marco entrega, e cada um entra
por adendo na especificação técnica do marco que precisar dele.
