# Teste manual: identidade, acesso, permissões e notificações

Guia para percorrer o fluxo do M2 pelo site, com o sistema no ar (`docs/setup/local.md`). Executado pela API em
2026-11-12, com todos os passos passando; pelo navegador, ainda não foi conferido por uma pessoa.

## Preparação

Na raiz do repositório:

```text
docker compose up -d --build
docker compose exec api python manage.py criar_admin
```

O comando pede nome, nome de usuário, e-mail, telefone e a senha (duas vezes). Resultado esperado:
`Admin <nome de usuário> criado.`

Os e-mails não saem para a internet em desenvolvimento: chegam ao Mailpit, em <http://localhost:8025>, com o link
inteiro e clicável. (Sem o Mailpit, por exemplo com `docker compose -f compose.yaml up`, eles saem no log do
`worker`, codificados: junte as linhas tirando o `=` do fim de cada uma.)

## Roteiro

| # | Passo | Resultado esperado |
| --- | --- | --- |
| 1 | Abrir <http://localhost:8080> | Tela "Entrar" |
| 2 | Entrar com o e-mail do admin (em maiúsculas) e a senha | Página inicial com os atalhos "Convites" e "Usuários" |
| 3 | Convites → "Gerar convite" | Aparece o link, com o aviso de que só aparece agora; a lista mostra um convite "Ativo" |
| 4 | Abrir o link numa janela anônima | Formulário de cadastro, com o aviso de privacidade e sem campo de CPF |
| 5 | Cadastrar com uma senha curta (`12345678`) | O campo "Senha" mostra o motivo; o formulário continua preenchido |
| 6 | Cadastrar com dados válidos | Tela "Verifique seu e-mail" |
| 7 | Abrir de novo o mesmo link de convite | "Convite inválido ou expirado." |
| 8 | Na janela anônima, tentar entrar com o novo usuário | "Falta verificar o seu e-mail para entrar." e o botão de reenvio |
| 9 | Pegar o link `/verificar/…` no e-mail do Mailpit e abri-lo | "E-mail verificado." O admin recebe a notificação "Novo diretor para classificar" (veja o roteiro N) |
| 10 | Entrar com o novo usuário | "…aguarda a classificação…", sem atalhos de administração |
| 11 | Como admin: Usuários | O novo diretor aparece "Ativo", "Diretor", "Sem cargo"; a linha do próprio admin não tem botões |
| 12 | Como admin: "Desativar" o novo diretor | A situação vira "Inativo" |
| 13 | Na janela do diretor, recarregar a página | Volta para "Entrar"; a senha dele não entra mais |
| 14 | Como admin: "Reativar" | O diretor volta a entrar |
| 15 | "Esqueci a senha" com o e-mail do diretor | Mensagem "Se houver uma conta…"; no Mailpit, o e-mail com o link `/redefinir-senha/…` |
| 16 | Abrir o link e trocar a senha | "Senha trocada."; a senha antiga não entra, a nova entra |
| 17 | Abrir o mesmo link de novo | "Este link é inválido ou venceu." |
| 18 | Errar a senha 5 vezes e tentar com a certa | "Muitas tentativas…" |
| 19 | Como admin: Convites → gerar e "Revogar" | O convite vira "Revogado" e o link não abre o formulário |
| 20 | "Sair" | Tela "Entrar"; abrir `/admin/usuarios` leva de volta a ela |

## Login com o Google

Só depois de criar o ID de cliente ([setup/google.md](../setup/google.md)) e definir `GOOGLE_CLIENT_ID` no `.env`.

| # | Passo | Resultado esperado |
| --- | --- | --- |
| G1 | Abrir "Entrar" | Aparece o botão do Google |
| G2 | Entrar com uma conta Google cujo e-mail não tem conta no sistema | "O acesso é só por convite." |
| G3 | Abrir um convite novo, escolher o Google e completar nome de usuário, telefone e senha | Entra direto, sem link de verificação |
| G4 | Sair e entrar com nome de usuário e senha | Entra na mesma conta |

Sem `GOOGLE_CLIENT_ID`, o botão não aparece e o resto do roteiro funciona igual.

## Classificação e permissões (M3)

Com o sistema no ar e o admin do roteiro anterior, mais um diretor ativo (um que já passou pelo roteiro acima).
Os passos P1 a P9 e P11 foram executados pela API, atrás do proxy do compose, em 2026-11-13, todos passando; o P10
(acesso total) só está coberto pelos testes automáticos, e nenhum passo foi conferido pelo navegador por uma pessoa.

| # | Passo | Resultado esperado |
| --- | --- | --- |
| P1 | Como admin: Cargos → criar "Tesoureiro de teste" | O cargo aparece "Ativo" |
| P2 | Usuários → abrir o diretor → cargo "Tesoureiro de teste" e setor "Financeiro" → "Salvar classificação" | Em Usuários, o diretor passa a "Com cargo"; no histórico, "Classificado" com o nome do admin |
| P3 | Como diretor: abrir a página inicial | Cargo, setores e "Nenhuma permissão concedida ainda." |
| P4 | Como diretor: tentar gerar um convite (pela API: `POST acesso/convites/`) | 403 `PERMISSION_DENIED` |
| P5 | Como admin: Permissões → conceder "Gerenciar convites" ao setor Financeiro | A concessão aparece na lista; repetir mostra "Esta concessão já existia." |
| P6 | Como diretor: gerar, listar e revogar um convite (pela API) | 201, 200 e 200; a lista de usuários continua negada (403) |
| P7 | Como admin: Permissões → "Revogar" a concessão | A concessão sai da lista |
| P8 | Como diretor: gerar convite de novo | 403 |
| P9 | Como admin: abrir o diretor | Histórico com a classificação, e o do setor com a concessão e a revogação, sempre com o nome de quem agiu |
| P10 | Como admin: "Conceder acesso total" ao diretor e abrir "Permissões" do usuário | "Gerenciar convites — pelo acesso total"; o diretor continua sem acesso às telas de admin |
| P11 | Como admin: "Revogar acesso total"; tirar o cargo do diretor; desativar o cargo de teste | Cada passo funciona; o cargo só desativa depois de ninguém o ter |

## Notificações (M4)

Com o sistema no ar (`docker compose up -d --build`), a caixa do Mailpit aberta em <http://localhost:8025>, um admin e
um diretor recém-cadastrado que ainda não foi classificado. Em 2026-11-13, os passos N1 a N5 e N10 foram executados
pela API, atrás do proxy do compose, com os e-mails lidos pela API do Mailpit; os passos N6 a N8 foram executados no
Chrome, com o diretor logado e o admin agindo pela API durante o N6. O N9 não foi executado (só se abriu a tela de
preferências). Nenhum passo foi conferido por outra pessoa.

| # | Passo | Resultado esperado |
| --- | --- | --- |
| N1 | Como admin: Convites → "Gerar convite"; cadastrar o diretor; abrir o link `/verificar/…` do e-mail no Mailpit | "E-mail verificado." O e-mail de verificação mostra o link inteiro |
| N2 | Como admin: olhar o sino | O sino mostra 1; a caixa tem "Novo diretor para classificar", com o nome do diretor |
| N3 | No Mailpit: e-mails ao admin | Um e-mail "Novo diretor para classificar", com o texto e o link `…/admin/usuarios/<id>`, sem token. Nenhum "Novo diretor aguardando classificação" (o do M2 não existe mais) |
| N4 | Como admin: classificar o diretor (cargo e setor) | A classificação é salva |
| N5 | Como diretor: entrar | O sino mostra 1; a caixa tem "Sua classificação mudou", com o cargo e os setores; o Mailpit tem o e-mail "Sua classificação mudou" |
| N6 | Com o diretor logado e a tela aberta, o admin reclassifica o diretor | Em até um minuto, sem recarregar, o sino do diretor sobe de 1 para 2 |
| N7 | Como diretor: clicar no sino | A caixa abre, com as duas notificações destacadas ("Nova") |
| N8 | Clicar na mais recente | Ela fica lida, o sino cai para 1, a caixa fecha e a tela vai para o item (aqui, a página inicial) |
| N9 | Preferências → desligar "E-mail dos avisos informativos" e "Salvar" | "Preferências salvas." A próxima notificação informativa fica na caixa e não gera e-mail; o que pede ação continua indo por e-mail |
| N10 | Como admin: tentar abrir a notificação do diretor (`POST notificacoes/{id}/ler/` com o ID dela) | 404 `NOT_FOUND`, igual a uma notificação que não existe |

Não conferido: o N9; o aviso flutuante no navegador (os testes automáticos o cobrem com o relógio simulado); as
telas do admin (N2) e o sino do diretor logo após entrar (N5), vistos só pela API; e a falha real de SMTP.

## Aprovações (M5)

Com o sistema no ar em desenvolvimento e o tipo de demonstração ligado (`DJANGO_DEBUG=1
APROVACOES_TIPO_DE_DEMONSTRACAO=1 docker compose up -d --build`), a caixa do Mailpit em <http://localhost:8025> e
quatro usuários: um admin; Bia, diretora com cargo; Dora e Caio, diretores com cargo e a permissão
`demonstracao.aprovar`. Em 2026-11-14, os passos A1, A6, A7, A8 e A10 foram executados pela API, atrás do proxy do
compose; A2 a A5 e A9 no Chrome; os e-mails, lidos pela API do Mailpit. Nenhum passo foi conferido por outra pessoa.

| # | Passo | Resultado esperado |
| --- | --- | --- |
| A1 | Como Bia: `POST aprovacoes/solicitacoes/` com `tipo` `demonstracao.pedido` e `conteudo` `{"descricao": "Coletes de treino", "valor": "320.00"}` | 201, em análise, versão 1 |
| A2 | Como Dora: abrir "Fila de pendências" e o sino | A fila mostra o pedido, com tipo, solicitante, R$ 320,00 e "Aguardando desde"; o sino tem "Solicitação para decidir"; abrir a notificação leva ao detalhe |
| A3 | No detalhe, "Contestar": motivo "Valor acima do necessário", mensagem e teto R$ 250,00 | Situação "Contestada"; a versão 1 mostra a decisão com motivo, mensagem e teto; o histórico ganha "Contestada"; a Dora fica sem ações |
| A4 | Como Bia: abrir o sino e a notificação "Solicitação contestada"; "Reenviar" com o conteúdo editado (`"valor": "240.00"`) | O aviso traz o texto padrão, o motivo, o teto e a mensagem; as ações eram só "Reenviar" e "Cancelar"; nasce a versão 2, em análise, e a versão 1 continua com a contestação |
| A5 | Como Dora: "Aprovar" com motivo "Dentro do orçamento" e um texto | Situação "Aprovada"; a versão 2 mostra a aprovação; o histórico tem as quatro ações |
| A6 | Como Caio: enviar sem indicar aprovador | 422 `APROVADOR_NAO_INDICADO` |
| A7 | Como Caio: enviar indicando a Dora, e tentar aprovar o próprio pedido | 201; depois 403 `SOLICITANTE_NAO_DECIDE`; o `acoes` do Caio é só `retirar` e `cancelar` |
| A8 | No contêiner do `worker`: `lembretes.lembrar_paradas` com o relógio 3 dias à frente, duas vezes; depois 7 dias à frente | 1, 0 e 1 avisos: o lembrete não se repete |
| A9 | Como Dora: abrir o sino | "Solicitação esperando decisão" para o pedido do Caio; pela indicação, só o aviso de indicação, sem o "para decidir" daquele pedido (A6 do adendo) |
| A10 | No Mailpit | E-mails de cada aviso, ao destinatário certo: "Solicitação contestada" e "aprovada" à Bia; nenhum ao Caio sobre o próprio pedido; "Aprovador indicado", "Solicitação esperando decisão" e "Solicitação parada há 7 dias" ao admin. O corpo traz o texto e o link `…/solicitacoes/<id>`, sem token |
| A11 | No contêiner da `api`, com `DJANGO_DEBUG=0` e a variável ligada | O tipo e a permissão de demonstração não existem |

Não conferido: a recusa, a retirada, a reabertura, a edição e o cancelamento no navegador (cobertos pelos testes
automáticos do site e da API); a tela de motivos no navegador; o aviso de "saiu da fila"; e a tarefa agendada
disparada pelo próprio agendador às 8h (a validação chamou o serviço com o relógio adiantado).
