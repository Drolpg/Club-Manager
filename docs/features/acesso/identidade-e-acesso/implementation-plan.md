# Plano de Implementação: Identidade e acesso

| Campo | Valor |
| --- | --- |
| Feature | `acesso/identidade-e-acesso` |
| Status | In Progress |
| Responsável | Leandro Nascimento |
| Atualizado em | 2026-11-12 |
| Especificação técnica | `./technical-spec.md` (aprovada em 2026-11-12) |

## Objetivo

Um diretor convidado se cadastra, comprova o e-mail e entra por senha ou pelo Google; o admin, criado por comando,
administra convites e usuários; e cada uma dessas ações fica auditada.

Cada checkpoint segue o ciclo de `sdd-method:driving-with-tests`: testes escritos e vistos falhando, código mínimo,
`uv run poe verify` verde, um commit. A evidência de cada um fica no fim deste documento.

## Checkpoint 1 — Auditoria: registro só de inserção

- O que muda: `auditoria/models.py`, `auditoria/public.py`, `auditoria/migrations/0001`, com o gatilho no banco.
- Testes: `registrar` grava ator, ação, item, justificativa e dados; alterar e apagar são recusados pelo modelo e pelo
  banco; a migração reverte.
- Evidência esperada: `uv run poe verify` verde.
- Critérios: base para CA-34.

## Checkpoint 2 — Usuário, autenticação do Django e comando `criar_admin`

- O que muda: `acesso/models.py` (`Usuario`), `acesso/domain/`, `acesso/migrations/0001`, `config/settings.py`
  (auth, sessões, cache, Argon2, validadores de senha), `management/commands/criar_admin.py`, dependência
  `argon2-cffi`.
- Testes: funções puras (normalização, nome de usuário); unicidade sem diferenciar maiúsculas; métodos de situação e
  de papel; comando com dados válidos e inválidos; auditoria do admin criado.
- Critérios: CA-01, CA-02.

## Checkpoint 3 — Sessão: entrar, consultar e sair

- O que muda: `acesso/services/sessao.py`, `acesso/http/`, `kernel/rate_limit.py`, rotas `sessao/`.
- Testes: login por nome de usuário e por e-mail; respostas iguais para conta inexistente e senha errada; conta
  aguardando verificação; conta inativa; bloqueio depois de 5 erros; sair; CSRF; rota protegida sem sessão.
- Critérios: CA-20 a CA-23, CA-36.

## Checkpoint 4 — Convites

- O que muda: `Convite` em `acesso/models.py`, `acesso/domain/convite.py`, `acesso/services/convites.py`, rotas
  `convites/`.
- Testes: situação calculada e precedência; gerar, listar, regenerar, revogar; consultar com token inválido; só
  admin; token nunca gravado em claro nem auditado.
- Critérios: CA-03 a CA-08.

## Checkpoint 5 — Cadastro com senha, verificação e e-mails

- O que muda: `acesso/services/cadastro.py`, `acesso/tasks.py`, configuração de e-mail e `SITE_URL`, agenda do
  Celery, rotas `cadastros/` e `verificacoes/`.
- Testes: cadastro válido; campos em uso e senha fraca; dois cadastros disputando o mesmo convite; verificação
  dentro e fora do prazo; reenvio; descarte de cadastros vencidos executado duas vezes; e-mail aos admins; nenhum
  token na fila.
- Critérios: CA-09 a CA-14.

## Checkpoint 6 — Recuperação de senha

- O que muda: `acesso/services/senha.py`, rotas `senhas/`.
- Testes: respostas iguais com e sem conta; link dentro e fora do prazo; uso único; sessões encerradas.
- Critérios: CA-24 a CA-26.

## Checkpoint 7 — Administração de usuários

- O que muda: `acesso/services/usuarios.py`, rotas `usuarios/`, `acesso/public.py`.
- Testes: listar; desativar encerra a sessão na hora; reativar; dar e tirar o papel de admin; proibição de alterar a
  si mesmo; só admin.
- Critérios: CA-27 a CA-32.

## Checkpoint 8 — Google: cadastro e login

- O que muda: `acesso/google.py` (port e adapter), rotas `sessao/google/`, `cadastros/google/` e `configuracao/`,
  dependência `google-auth`.
- Testes: com o verificador falso: cadastro sem link de verificação; e-mail já cadastrado; login na conta criada com
  senha e o inverso; sem conta; conta aguardando verificação passa a ativa; credencial inválida. O adapter real é
  testado contra um token forjado, sem rede.
- Critérios: CA-15 a CA-19.

## Checkpoint 9 — Documentação da API protegida

- O que muda: permissão das rotas `schema/` e `docs/`, dependência `drf-spectacular-sidecar`.
- Testes: sem sessão e como diretor, negado; como admin, permitido; a página não referencia CDN.
- Encerra a TD-001.

## Checkpoint 10 — Site

- O que muda: `frontend/src/` (roteamento, cliente da API com CSRF, telas de login, cadastro por convite,
  verificação, recuperação, página inicial do diretor, convites e usuários), dependência `react-router`.
- Testes: cada tela, com a API simulada: caminho feliz e a mensagem de cada código de erro.
- Critérios: CA-33, CA-35.

## Checkpoint 11 — Validação final

- `uv run poe verify` e `npm run verify`.
- Subir o compose e percorrer o guia de teste manual do fluxo completo.
- Revisão de segurança, documentação da lista da technical-spec, registro de requisitos, decisões e TD-001.

## Matriz critério de aceite → teste

Preenchida a cada checkpoint.

| Critério | Teste |
| --- | --- |

## Revisão de segurança

Preenchida no checkpoint 11.

| Item | Achado | Mitigação | Status |
| --- | --- | --- | --- |
| Validação de entrada e mass assignment | | | |
| Autenticação e autorização | | | |
| Exposição de dados | | | |
| Segredos e logs | | | |
| Persistência e migrations | | | |
| Respostas de erro | | | |
| Dependências novas | | | |
| Abuso do endpoint | | | |

## Definition of Done

- [ ] Checkpoints concluídos, com evidência.
- [ ] Testes relevantes criados e passando; todo CA com ao menos um teste.
- [ ] Verificação completa passando; cobertura dentro da meta.
- [ ] Fronteiras de módulo verificadas.
- [ ] Toda ação da regra 19 da funcional auditada, com teste.
- [ ] Revisão de segurança registrada, sem achado crítico ou alto aberto.
- [ ] Migrations reversíveis; nenhum seed.
- [ ] Contrato, `docs/api/` e guia de teste manual atualizados.
- [ ] Registro de requisitos, decisões e riscos atualizados.
- [ ] Critérios de aceite validados e aprovados pelo dono.

## Evidências de verificação

## Rollback ou recuperação

Não há dado de produção. As migrações revertem com `python manage.py migrate <app> zero`; a versão anterior é a tag
`v0.1.0`.
