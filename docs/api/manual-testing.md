# Teste manual: identidade e acesso

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

Os e-mails não são enviados em desenvolvimento: saem no log do `worker`. Para ver o último:

```text
docker compose logs worker --since 5m
```

No log, o e-mail aparece codificado: linhas longas são quebradas e terminam com `=`. Para usar um link, junte as
linhas tirando o `=` do fim de cada uma.

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
| 9 | Pegar o link `/verificar/…` no log do `worker` e abri-lo | "E-mail verificado." No log do `worker`, um e-mail aos admins sobre o diretor a classificar |
| 10 | Entrar com o novo usuário | "…aguarda a classificação…", sem atalhos de administração |
| 11 | Como admin: Usuários | O novo diretor aparece "Ativo", "Diretor", "Sem cargo"; a linha do próprio admin não tem botões |
| 12 | Como admin: "Desativar" o novo diretor | A situação vira "Inativo" |
| 13 | Na janela do diretor, recarregar a página | Volta para "Entrar"; a senha dele não entra mais |
| 14 | Como admin: "Reativar" | O diretor volta a entrar |
| 15 | "Esqueci a senha" com o e-mail do diretor | Mensagem "Se houver uma conta…"; no log do `worker`, o link `/redefinir-senha/…` |
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
