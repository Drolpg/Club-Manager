# Especificação Técnica: Notificações, com caixa de entrada e e-mail

| Campo | Valor |
| --- | --- |
| Feature | `notificacoes/caixa-e-email` |
| Status | Draft |
| Responsável | Leandro Nascimento |
| Atualizado em | 2026-11-13 |
| Aprovado por | — |
| Aprovado em | — |
| Especificação funcional | `./functional-spec.md` (aprovada em 2026-11-13) |
| Decisões aplicadas | ADR-001, ADR-003 (com o adendo 1), ADR-006, ADR-008; AD-012 |
| Pré-requisito | Feature `permissoes/catalogo-e-classificacao` implementada (o M3 inteiro) |

## Contexto e desenho

| Módulo | O que ganha |
| --- | --- |
| `kernel` | `events.py`: o despachante de eventos em processo previsto na ADR-003 |
| `acesso` | Publica `CadastroConcluido` e `PapelDeAdminAlterado`; deixa de enviar o e-mail simples aos admins |
| `permissoes` | Publica `ClassificacaoAlterada` e `ConcessaoIndividualAlterada` |
| `notificacoes` | Modelos `Notificacao` e `PreferenciaDeAlerta`; a API pública `notificar`; a tarefa de e-mail; os tratadores dos quatro eventos; as rotas da caixa e das preferências |
| `frontend` | Moldura comum das telas logadas, com o sino; a caixa; o aviso flutuante; a tela de preferências |

### Dois caminhos para gerar uma notificação

`notificacoes` fica acima de `acesso` e de `permissoes`, e abaixo dos módulos de negócio.

| Quem gera | Como | Por quê |
| --- | --- | --- |
| Módulo acima (`aprovacoes`, `financeiro`, `eventos`, `comunicacao`) | Chama `notificacoes.public.notificar(...)` | Dependência normal, para baixo |
| Módulo abaixo (`acesso`, `permissoes`) | Publica um evento; `notificacoes` trata e chama `notificar` | Quem está abaixo não conhece `notificacoes` (ADR-003) |

### Despachante de eventos (`kernel/events.py`)

Duas funções: `subscribe(tipo_do_evento, tratador)` e `publish(evento)`. Um evento é um `@dataclass(frozen=True)`
definido na API pública do módulo que o publica. `publish` chama os tratadores na hora, na mesma transação; uma
exceção num tratador desfaz a operação de quem publicou. Os tratadores são registrados no `ready` da aplicação.

| Evento | Publicado por | Campos |
| --- | --- | --- |
| `CadastroConcluido` | `acesso`, ao ativar a conta (verificação por link ou Google) | `usuario_id` |
| `PapelDeAdminAlterado` | `acesso`, em `tornar_admin` e `remover_admin` | `usuario_id`, `admin` |
| `ClassificacaoAlterada` | `permissoes`, em `classificar` | `usuario_id` |
| `ConcessaoIndividualAlterada` | `permissoes`, ao conceder ou revogar para um usuário | `usuario_id`, `permissao`, `concedida` |

### Tipos de notificação

Cada tipo tem um código estável (`<modulo>.<fato>`), a marca "pede ação" e uma descrição. Os módulos de cima
declaram os seus com `notificacoes.public.registrar_tipo(...)`, ao iniciar. Os quatro tipos desta feature são
declarados pelo próprio `notificacoes`, porque `acesso` e `permissoes` não podem importá-lo.

| Código | Pede ação | Destinatários | Caminho no site |
| --- | --- | --- | --- |
| `acesso.cadastro_concluido` | Sim | `acesso.public.admins_ativos()` | `/admin/usuarios/<id>` |
| `permissoes.classificacao_alterada` | Não | O usuário | `/` |
| `acesso.papel_de_admin_alterado` | Não | O usuário | `/` |
| `permissoes.concessao_individual_alterada` | Não | O usuário | `/` |

## Modelo de domínio

Módulo genérico, em camadas, sem aggregate formal.

`Notificacao`:

| Campo | Observação |
| --- | --- |
| `id` | UUID 7 |
| `destinatario_id` | UUID, sem chave estrangeira |
| `tipo`, `pede_acao` | Código do tipo e a marca, copiada no momento da criação |
| `titulo` (até 120), `texto` (até 500) | Texto puro, montado pelo código que notifica |
| `item_tipo`, `item_id`, `caminho` | O item relacionado e o caminho dele no site |
| `chave` | Identifica o fato; única por destinatário. É o que impede a duplicata |
| `criada_em`, `lida_em` | `lida_em` só é preenchida uma vez |
| `email_situacao` | `PENDENTE`, `ENVIADO`, `DISPENSADO` (preferência do usuário) ou `FALHOU` |
| `email_enviado_em`, `email_tentativas` | |

`PreferenciaDeAlerta`: `usuario_id` (chave), `aviso_na_tela` e `email_informativos`, os dois verdadeiros por padrão.
A linha é criada quando o usuário altera algo; sem linha, valem os padrões.

| ID | Regra | Onde |
| --- | --- | --- |
| NOT-R01 | Só usuário ativo recebe notificação | `notificar`, com `acesso.public.ids_ativos` |
| NOT-R02 | Uma notificação por destinatário e chave | Índice único e `get_or_create` |
| NOT-R03 | O e-mail é enviado se o tipo pede ação, ou se o destinatário não desligou os informativos | Função pura `deve_enviar_email(pede_acao, email_informativos)` |
| NOT-R04 | `lida_em` nunca muda depois de preenchida | Método `marcar_lida` |
| NOT-R05 | Título, texto, tipo, item e destinatário nunca mudam; nenhuma notificação é apagada | O modelo recusa; não há rota |
| NOT-R06 | A consulta de uma notificação sempre filtra pelo destinatário | Serviços de consulta |
| NOT-R07 | O e-mail só é enfileirado depois do commit | `transaction.on_commit` |

## Interfaces e fluxo de dados

### API pública (em processo)

```text
notificar(*, tipo, destinatarios, titulo, texto, item_tipo, item_id, caminho, chave) -> int
registrar_tipo(codigo, *, pede_acao, descricao) -> None
```

`notificar` devolve quantas notificações criou. Deve ser chamada dentro da transação do caso de uso. A `chave` é
montada por quem chama e identifica o fato (por exemplo, `cadastro-concluido:<usuario_id>`).

### Rotas, sob `/api/v1/notificacoes/`

| Método e caminho | Quem | Saída |
| --- | --- | --- |
| `GET ` (raiz), com `?antes=<id>&limite=20` | Logado | `itens` (as do usuário, da mais recente para a mais antiga) e `tem_mais` |
| `GET resumo/` | Logado | `nao_lidas` e `mais_recente_id` |
| `POST {id}/ler/` | Logado | A notificação, com `lida_em` |
| `POST ler-todas/` | Logado | `marcadas` |
| `GET preferencias/`, `PUT preferencias/` | Logado | `aviso_na_tela`, `email_informativos` |

Formato de um item: `id`, `tipo`, `pede_acao`, `titulo`, `texto`, `caminho`, `criada_em`, `lida_em`.

| Situação | Código HTTP | Código de erro |
| --- | --- | --- |
| Notificação inexistente ou de outro usuário | 404 | `NOT_FOUND` |
| `limite` fora de 1 a 50, `antes` inválido, preferência que não é booleana | 400 | `VALIDATION_ERROR` |
| Sem sessão | 401 | `NOT_AUTHENTICATED` |

### E-mail

A tarefa `notificacoes.enviar_email(notificacao_id)` é enfileirada depois do commit, só para as notificações que
devem ir por e-mail (as demais nascem `DISPENSADO`). Ela é idempotente: se a situação já é `ENVIADO`, não faz nada.
Em falha do servidor de e-mail, tenta de novo com espera crescente, até 5 vezes; esgotadas, grava `FALHOU`.

O e-mail é texto puro: o título no assunto, o texto no corpo e o link `SITE_URL` + `caminho`. O link exige login.

### Site

- **Moldura:** as telas logadas passam a ter um cabeçalho comum, com o nome do usuário, o menu, o sino e "Sair".
- **Sino:** consulta `resumo/` ao carregar e a cada 60 segundos, só com a aba visível.
- **Aviso flutuante:** aparece quando `mais_recente_id` muda entre duas consultas e `aviso_na_tela` está ligado.
- **Caixa:** abre sobre a tela; carrega mais ao chegar ao fim; clicar num item chama `ler/` e navega para `caminho`.
- **Preferências:** tela `/preferencias`, com as duas chaves.

## Persistência e dados

| Migração | Conteúdo |
| --- | --- |
| `notificacoes/0001_notificacao_e_preferencia` | As duas tabelas; índice único (`destinatario_id`, `chave`); índice (`destinatario_id`, `criada_em`); índice parcial das não lidas |

Classificação dos dados: **nenhum seed**.

## Segurança e operação

| Tema | Decisão |
| --- | --- |
| Isolamento | Toda consulta filtra por `destinatario_id` igual ao usuário logado; a notificação de outro responde 404, inclusive para o admin |
| Conteúdo | Título e texto são montados pelo código, com nomes de pessoas e de itens, sem valores nem dados de contato; o site os mostra como texto, nunca como HTML |
| E-mail | Só texto; link para o site, que exige login; nada de token |
| Usuário inativo | Não recebe notificação nem e-mail |
| Abuso | A consulta a cada minuto é leve (duas agregações indexadas); `limite` máximo de 50 |
| Falha de tratador | Um erro ao notificar desfaz a operação que gerou o fato; por isso os tratadores só montam texto e chamam `notificar` |
| Modelo de ameaças | `docs/security/threat-model.md` ganha a seção deste marco: leitura da caixa alheia, vazamento por e-mail, notificação forjada |

### Servidor de e-mail de desenvolvimento

Hoje os e-mails de desenvolvimento saem no log, codificados, e os links precisam ser remontados à mão (risco 10 do
registro de requisitos). Proposta: acrescentar o **Mailpit** ao `compose.override.yaml`, só em desenvolvimento. Ele
recebe os e-mails por SMTP e os mostra numa página (`http://localhost:8025`). Custa cerca de 15 MB e não vai para a
produção. Para isso, `EMAIL_URL` passa a aceitar `smtp://…?tls=0` (sem criptografia, só para o Mailpit).

Sem dependência nova de Python nem de JavaScript; a única novidade é a imagem do Mailpit em desenvolvimento.

## Estratégia de testes

| Camada | O que cobre | Tipo de teste |
| --- | --- | --- |
| Função pura | NOT-R03 | Unitário |
| Despachante | Entrega a todos os tratadores do tipo; erro num tratador propaga; tipos diferentes não se misturam | Unitário |
| Serviços | `notificar`: NOT-R01, NOT-R02, NOT-R07; leitura e preferências: NOT-R04 a NOT-R06 | Integração com PostgreSQL |
| Tarefa de e-mail | Envio; dispensado por preferência; nova tentativa em falha; `FALHOU` ao esgotar; idempotência | Integração, com o servidor de e-mail em memória e um que falha |
| Tratadores | Cada um dos quatro eventos gera a notificação certa, para as pessoas certas; `acesso` e `permissoes` publicam os eventos | Integração |
| Contrato | Cada rota: sucesso, erros e isolamento entre usuários | Integração HTTP |
| Fronteiras | `acesso` e `permissoes` não importam `notificacoes`; `kernel` não importa nenhum módulo | Teste de arquitetura existente |
| Site | Sino, caixa, aviso flutuante (com e sem a preferência), preferências, com relógio simulado para os 60 segundos | Vitest e Testing Library |

Cada critério de aceite CA-01 a CA-24 tem ao menos um teste; a matriz fica no plano.

## Documentação a atualizar

- [ ] Contrato gerado; `docs/api/README.md`; `docs/api/manual-testing.md`
- [ ] `docs/setup/local.md` e `configuration.md`: Mailpit e `?tls=0`
- [ ] `docs/architecture/project-structure.md` e `stack-profile.md`: o despachante e como um módulo notifica
- [ ] `docs/domain/domain-events.md`: os quatro eventos novos
- [ ] `docs/security/threat-model.md`: seção do M4
- [ ] Registro de requisitos e risco 10

## Adendos

Nenhum.
