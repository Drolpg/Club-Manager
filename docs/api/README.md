# API

Referência de uso. O contrato completo, rota a rota, é o gerado pela aplicação: com o sistema no ar e um admin
logado, abra `/api/v1/docs/` (navegável) ou `/api/v1/schema/` (OpenAPI).

Todas as rotas ficam sob `/api/v1/`, falam JSON e usam nomes de recursos e campos em português.

## Autenticação

Sessão no servidor, em cookie (ADR-008). Não há token no corpo das respostas.

1. `GET /api/v1/acesso/sessao/` devolve quem está logado (`{"usuario": null}` se ninguém) e entrega o cookie
   `csrftoken`.
2. `POST /api/v1/acesso/sessao/` com `identificador` (nome de usuário ou e-mail) e `senha` abre a sessão: a resposta
   traz o cookie `sessionid`, que é `HttpOnly`.
3. Toda escrita (`POST`, `DELETE`) precisa do cabeçalho `X-CSRFToken` com o valor do cookie `csrftoken`. Sem ele, a
   resposta é 403 `CSRF_FAILED`.
4. `DELETE /api/v1/acesso/sessao/` encerra a sessão.

A sessão acaba depois de 7 dias sem uso. Desativar o usuário ou trocar a senha encerra as sessões na requisição
seguinte.

Os cookies são marcados como `Secure` quando `DJANGO_DEBUG=0`. Navegadores aceitam isso em `http://localhost`;
ferramentas como o `curl` também. Bibliotecas que não enviam cookie `Secure` por HTTP precisam ser configuradas.

O login com o Google usa `POST /api/v1/acesso/sessao/google/` com a `credencial` devolvida pelo botão do Google.

## Erros

Toda resposta de erro tem o mesmo envelope, com um código estável:

```json
{"error": {"code": "CREDENCIAIS_INVALIDAS", "message": "Usuário ou senha inválidos.", "details": null}}
```

Em `VALIDATION_ERROR`, `details` traz os motivos por campo.

| Código | HTTP | Quando |
| --- | --- | --- |
| `NOT_AUTHENTICATED` | 401 | Rota protegida sem sessão |
| `PERMISSION_DENIED` | 403 | Logado, sem permissão (por exemplo, sem ser admin) |
| `CSRF_FAILED` | 403 | Escrita sem o token CSRF válido |
| `VALIDATION_ERROR` | 400 | Campo ausente, mal formatado ou senha fora da política |
| `NOT_FOUND` | 404 | Recurso ou rota inexistente |
| `MUITAS_TENTATIVAS` | 429 | Limite de tentativas de login ou de requisições por IP |
| `CREDENCIAIS_INVALIDAS` | 401 | Identificador ou senha errados, conta inexistente ou inativa |
| `EMAIL_NAO_VERIFICADO` | 403 | Senha certa numa conta que aguarda verificação |
| `CONVITE_INVALIDO` | 404 | Convite usado, expirado, revogado ou inexistente |
| `NOME_DE_USUARIO_EM_USO`, `EMAIL_EM_USO` | 409 | Cadastro com dado já usado |
| `LINK_INVALIDO` | 400 | Link de verificação ou de recuperação inválido ou vencido |
| `GOOGLE_INVALIDO` | 401 | Credencial do Google recusada, ou login com Google não configurado |
| `ACESSO_SO_POR_CONVITE` | 403 | Login com Google de quem não tem conta |
| `CONTA_JA_EXISTE` | 409 | Cadastro com Google de um e-mail que já tem conta |
| `NAO_PODE_ALTERAR_A_SI_MESMO` | 422 | Desativar a si mesmo ou tirar o próprio papel de admin |
| `CONVITE_NAO_ESTA_ATIVO`, `CONVITE_NAO_PODE_SER_REGENERADO` | 422 | Ação fora da situação do convite |
| `USUARIO_NAO_ESTA_ATIVO`, `USUARIO_NAO_ESTA_INATIVO`, `USUARIO_JA_E_ADMIN`, `USUARIO_NAO_E_ADMIN` | 422 | Ação fora da situação do usuário |
| `INTERNAL_ERROR` | 500 | Erro inesperado; o detalhe fica só no log, com o `X-Request-ID` da resposta |

Login, recuperação de senha, reenvio de verificação e convite inválido respondem do mesmo jeito exista a conta (ou o
convite) ou não.

## Recursos

| Recurso | Rotas | Quem |
| --- | --- | --- |
| Saúde | `GET health/` | Aberta |
| Sessão | `GET`, `POST`, `DELETE acesso/sessao/`; `POST acesso/sessao/google/` | Aberta (sair exige sessão) |
| Configuração pública | `GET acesso/configuracao/` | Aberta |
| Convites | `GET`, `POST acesso/convites/`; `POST acesso/convites/{id}/regenerar/`, `…/revogar/` | Admin |
| Consulta de convite | `POST acesso/convites/consultar/` | Aberta |
| Cadastro | `POST acesso/cadastros/`, `POST acesso/cadastros/google/` | Aberta, com convite |
| Verificação de e-mail | `POST acesso/verificacoes/`, `POST acesso/verificacoes/reenviar/` | Aberta |
| Senha | `POST acesso/senhas/recuperar/`, `POST acesso/senhas/redefinir/` | Aberta |
| Usuários | `GET acesso/usuarios/`; `POST acesso/usuarios/{id}/desativar/`, `…/reativar/`, `…/tornar-admin/`, `…/remover-admin/` | Admin |
| Contrato | `GET schema/`, `GET docs/` | Admin |

O token de convite, de verificação e de recuperação vai sempre no corpo, nunca na URL da API.

Teste manual do fluxo completo: [manual-testing.md](manual-testing.md).
