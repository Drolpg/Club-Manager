# ADR 008: Sessão no servidor para o site, token de identidade para o Google

**Status:** Proposed  
**Date:** 2026-11-12  
**Deciders:** Leandro Nascimento  
**Resolve:** AD-006

---

## Contexto

A mesma API serve o site e, depois, o aplicativo (RNF-01). O login é por senha ou pelo Google (RF-006, RF-007).
Desativar um usuário precisa tirar o acesso dele na hora (RF-012), e trocar a senha precisa encerrar as sessões
abertas (RF-010). O protótipo usava JWT.

## Considered Options

### Option 1: Sessão guardada no servidor, em cookie ✅ RECOMENDADA

O Django guarda a sessão no banco e o navegador só leva um identificador num cookie `HttpOnly`. A sessão é conferida
a cada requisição.

### Option 2: JWT de acesso com token de renovação

Não consulta o banco a cada requisição e serve bem a aplicativos. Em troca, um token emitido vale até vencer: tirar
o acesso na hora exige uma lista de revogação, que traz de volta a consulta ao servidor. No navegador, o token fica
ao alcance de script, ou vai para um cookie e passa a precisar de CSRF do mesmo jeito.

### Option 3: Biblioteca completa de autenticação social (fluxo de redirecionamento)

Resolve vários provedores e a troca de código no servidor. É muito mais do que um provedor só exige, e traz telas e
modelos próprios.

## Decision

Recomenda-se a **Option 1**, com o Google pelo token de identidade.

| Decisão | Motivo |
| --- | --- |
| Sessão do Django no banco, cookie `HttpOnly`, `Secure`, `SameSite=Lax`, com CSRF | Encerrar o acesso na hora é requisito; com poucos usuários, a consulta por requisição não pesa |
| Site e API na mesma origem, pelo proxy | Dispensa CORS e deixa o cookie restrito ao próprio site |
| 7 dias sem uso, renovados a cada requisição | Funcional, P6 |
| Google pelo botão do Google Identity Services; a API valida o token de identidade com `google-auth` | Um provedor só; sem redirecionamento, sem segredo de cliente no servidor |
| O Google só identifica: a conta, a situação e as permissões são sempre as do sistema | O acesso é só por convite (RN-001) |
| Aplicativo futuro: token opaco no cabeçalho `Authorization`, guardado no servidor | Mesma propriedade de encerramento na hora; construído só na fase do aplicativo |

## Consequências

### Positivas ✅

- Desativar um usuário ou trocar a senha encerra o acesso na requisição seguinte, sem código extra.
- Nenhum token de acesso fica ao alcance de script no navegador.
- Usa só o que o Django já traz e testa.

### Negativas ❌

- Uma consulta ao banco por requisição autenticada.
- O aplicativo vai precisar de um segundo mecanismo (token opaco); não reaproveita o cookie.
- Toda escrita do site precisa enviar o token CSRF.

### Gatilhos de reavaliação

| Gatilho | Mudança esperada |
| --- | --- |
| Início da fase do aplicativo | Especificar o token opaco e a sua revogação |
| Um segundo provedor de login | Avaliar uma biblioteca de autenticação social |
| Site e API em origens diferentes | Rever cookie, CSRF e CORS |

---

**Last Updated:** 2026-11-12  
**Decision Maker:** Leandro Nascimento (pendente)  
**Status:** Proposed
