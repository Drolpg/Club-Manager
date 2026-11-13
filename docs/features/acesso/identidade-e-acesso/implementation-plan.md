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
| CA-01 | `acesso/tests/test_criar_admin.py::test_ca01_comando_cria_um_admin_ativo_com_email_verificado` |
| CA-02 | `acesso/tests/test_criar_admin.py::test_ca02_senha_fraca_nao_cria_usuario_e_mostra_o_motivo`, `::test_ca02_nome_de_usuario_ja_usado_nao_cria_outro` |
| CA-03 | `acesso/tests/test_convites.py::test_ca03_admin_gera_um_convite_e_recebe_o_link` |
| CA-04 | `acesso/tests/test_convites.py::test_ca04_quem_nao_e_admin_nao_mexe_em_convites` |
| CA-05 | `acesso/tests/test_convites.py::test_ca05_convite_com_mais_de_24_horas_e_invalido`; `acesso/tests/test_convite_domain.py` |
| CA-06 | `acesso/tests/test_convites.py::test_ca06_convite_revogado_usado_ou_inexistente_tem_a_mesma_resposta` |
| CA-07 | `acesso/tests/test_convites.py::test_ca07_regenerar_invalida_o_link_antigo_e_cria_um_novo_de_24_horas`, `::test_ca07_convite_expirado_pode_ser_regenerado` |
| CA-08 | `acesso/tests/test_convites.py::test_ca08_lista_mostra_situacao_quem_gerou_e_quando` |
| CA-09 | `acesso/tests/test_cadastro.py::test_ca09_cadastro_valido_fica_aguardando_usa_o_convite_e_envia_o_link` |
| CA-10 (login) | `acesso/tests/test_sessao.py::test_ca10_conta_aguardando_verificacao_e_recusada_com_aviso_proprio` |
| CA-11 | `acesso/tests/test_cadastro.py::test_ca11_verificar_ativa_a_conta_sem_cargo_e_avisa_os_admins` |
| CA-12 | `acesso/tests/test_cadastro.py::test_ca12_cadastro_nao_verificado_em_24_horas_nao_verifica_e_e_descartado`, `::test_cadastro_vencido_ainda_nao_descartado_nao_prende_o_nome_de_usuario` |
| CA-13 | `acesso/tests/test_cadastro.py::test_ca13_dado_invalido_ou_em_uso_nao_cria_conta_e_nao_gasta_o_convite`, `::test_ca13_senha_fraca_aponta_o_campo` |
| CA-14 (API) | `acesso/tests/test_cadastro.py::test_ca14_o_cadastro_nao_aceita_nem_guarda_cpf`; o aviso de privacidade é do site (checkpoint 10) |
| CA-14 (site) | `frontend/src/App.test.tsx` › "CA-14: o formulário mostra o aviso de privacidade e não pede CPF" |
| CA-15 | `acesso/tests/test_google.py::test_ca15_cadastro_pelo_google_ativa_a_conta_sem_link_de_verificacao` |
| CA-16 | `acesso/tests/test_google.py::test_ca16_email_do_google_que_ja_tem_conta_nao_cria_outra_e_nao_gasta_o_convite` |
| CA-17 | `acesso/tests/test_google.py::test_ca17_conta_criada_com_senha_entra_pelo_google_com_o_mesmo_email` |
| CA-18 | `acesso/tests/test_google.py::test_ca18_conta_criada_pelo_google_entra_com_usuario_e_senha` |
| CA-19 | `acesso/tests/test_google.py::test_ca19_quem_nao_tem_conta_nao_entra_pelo_google` |
| CA-20 | `acesso/tests/test_sessao.py::test_ca20_entra_por_nome_de_usuario_ou_email_em_qualquer_caixa` |
| CA-21 | `acesso/tests/test_sessao.py::test_ca21_conta_inexistente_e_senha_errada_tem_a_mesma_resposta` |
| CA-22 | `acesso/tests/test_sessao.py::test_ca22_sexta_tentativa_e_recusada_mesmo_com_a_senha_certa` |
| CA-23 | `acesso/tests/test_sessao.py::test_ca23_sair_encerra_a_sessao` |
| CA-24 | `acesso/tests/test_senha.py::test_ca24_resposta_e_igual_com_e_sem_conta_e_so_a_conta_ativa_recebe_email` |
| CA-25 | `acesso/tests/test_senha.py::test_ca25_link_dentro_do_prazo_troca_a_senha_e_encerra_as_sessoes`, `::test_ca25_o_mesmo_link_nao_funciona_de_novo` |
| CA-26 | `acesso/tests/test_senha.py::test_ca26_link_com_mais_de_uma_hora_e_recusado` |
| CA-27 | `acesso/tests/test_usuarios_admin.py::test_ca27_lista_mostra_situacao_papel_e_cargo` |
| CA-28 (senha) | `acesso/tests/test_usuarios_admin.py::test_ca28_desativar_encerra_a_sessao_na_hora_e_barra_o_login`; o login pelo Google entra no checkpoint 8 |
| CA-28 (Google) | `acesso/tests/test_google.py::test_ca28_usuario_desativado_nao_entra_pelo_google` |
| CA-29 | `acesso/tests/test_usuarios_admin.py::test_ca29_reativar_devolve_o_acesso_com_o_mesmo_historico` |
| CA-30 | `acesso/tests/test_usuarios_admin.py::test_ca30_ninguem_desativa_a_si_mesmo_nem_tira_o_proprio_papel` |
| CA-31 | `acesso/tests/test_usuarios_admin.py::test_ca31_diretor_tornado_admin_passa_a_gerar_convites` |
| CA-32 | `acesso/tests/test_usuarios_admin.py::test_ca32_quem_nao_e_admin_nao_administra_usuarios`, `::test_ca32_quem_nao_e_admin_nao_lista_usuarios` |
| CA-33 | `frontend/src/App.test.tsx` › "CA-33: o diretor sem cargo vê que aguarda a classificação e nenhum atalho de gestão" |
| CA-34 | Testes de auditoria em `acesso/tests/`: `test_criar_admin.py`, `test_convites.py`, `test_cadastro.py`, `test_senha.py`, `test_usuarios_admin.py`, `test_google.py` |
| CA-35 | Todos os testes de `backend/acesso/tests/` exercitam os fluxos só pela API; o site não tem regra (`frontend/src/App.test.tsx` simula a API) |
| CA-36 | `acesso/tests/test_sessao.py::test_ca36_rota_protegida_sem_sessao_e_negada`; `tests/test_errors.py::test_rota_sem_permissao_explicita_e_negada_por_padrao` |

## Revisão de segurança

Preenchida no checkpoint 11.

| Item | Achado | Mitigação | Status |
| --- | --- | --- | --- |
| Validação de entrada e mass assignment | Serializers declaram campo a campo, com tamanho máximo; campo extra (por exemplo, `cpf` ou `email` no cadastro com Google) é ignorado; `admin` e `situacao` nunca vêm do cliente | Testes `test_ca14…`, `test_o_email_da_conta_e_sempre_o_do_google…` | OK |
| Autenticação e autorização | Negado por padrão; rotas abertas declaram `AllowAny`; rotas de admin exigem `EhAdmin` na view e `exigir_admin` no serviço; sessão conferida a cada requisição | `test_ca04…`, `test_ca32…`, `test_servico_recusa…`, `test_usuario_desativado_perde_a_sessao…` | OK |
| Exposição de dados | Respostas sem hash de senha; listas só para admin; login, recuperação, reenvio e convite inválido não revelam existência. O cadastro revela nome de usuário ou e-mail em uso a quem tem convite válido | Aceito no modelo de ameaças, com limite por IP | Mitigado |
| Segredos e logs | Token de convite só como hash; tokens de verificação e de recuperação assinados, nunca guardados nem na fila; auditoria e logs sem senha, token ou e-mail; `.env` fora do git | `test_token_do_convite_nao_e_guardado…`, `test_o_token_nunca_passa_pela_fila` | OK |
| Persistência e migrations | Quatro migrações novas, reversíveis; auditoria com gatilho que recusa alterar e apagar; nenhum seed | `test_migracao_reverte_e_reaplica`, `test_banco_recusa_…` | OK |
| Respostas de erro | Envelope com código estável em todos os casos, inclusive falha de CSRF (achado na validação final e corrigido) | `test_falha_de_csrf_responde_no_envelope_de_erro` | OK |
| Dependências novas | `argon2-cffi`, `google-auth` (com `requests`), `drf-spectacular-sidecar`, `packaging`, `react-router`; todas com versão no lockfile | `pip-audit` e `npm audit` sem achados em 2026-11-12 | OK |
| Abuso do endpoint | 5 erros de login em 15 minutos por conta; 20 requisições por minuto por IP nas rotas abertas de escrita; 3 reenvios e 3 pedidos de recuperação por hora | `test_ca22…`, `test_consulta_de_convite_e_limitada_por_ip`, `test_reenvio_e_limitado…`, `test_pedido_de_recuperacao_e_limitado…` | OK |
| Integrações externas | Token do Google validado por assinatura, público-alvo, validade e e-mail verificado; conta já vinculada não é tomada por outra conta Google com o mesmo e-mail | `test_adapter_real_…`, `test_outra_conta_google…` | OK |
| Cookies | `HttpOnly`, `SameSite=Lax` e `Secure` fora de depuração; CSRF em toda escrita, inclusive no login | `test_cookie_de_sessao…`, `test_login_sem_token_csrf_e_recusado` | OK |

Pontos em aberto, sem achado crítico ou alto: sem HTTPS (M12); o `TRUNCATE` da tabela de auditoria não é barrado pelo
gatilho de linha (exige ser dono da tabela; avaliar no M12 com o usuário de banco da aplicação); sem verificação em
duas etapas (backlog).

## Definition of Done

- [x] Checkpoints concluídos, com evidência.
- [x] Testes relevantes criados e passando; todo CA com ao menos um teste (matriz acima).
- [x] Verificação completa passando; cobertura dentro da meta (backend 96%, site 86%).
- [x] Fronteiras de módulo verificadas.
- [x] Toda ação da regra 19 da funcional auditada, com teste.
- [x] Revisão de segurança registrada, sem achado crítico ou alto aberto.
- [x] Migrations reversíveis; nenhum seed.
- [x] Contrato, `docs/api/` e guia de teste manual atualizados.
- [x] Registro de requisitos, decisões e riscos atualizados.
- [ ] Critérios de aceite validados e aprovados pelo dono.
- [ ] CI verde no GitHub (roda ao integrar na `dev`).

## Evidências de verificação

### Checkpoint 1 — Auditoria (2026-11-12)

```text
uv run poe verify
27 passed; cobertura 95,20%; import-linter: 1 contrato mantido; nenhuma migração pendente
```

Testes novos: `backend/auditoria/tests/test_registro.py` (8).

### Checkpoint 2 — Usuário e comando `criar_admin` (2026-11-12)

```text
uv run poe verify
71 passed; cobertura 93,32%; import-linter: 1 contrato mantido; nenhuma migração pendente
```

Testes novos: `backend/acesso/tests/test_identificacao.py`, `test_usuario.py`, `test_criar_admin.py`.

### Checkpoints 3 e 4 — Sessão e convites (2026-11-12)

```text
uv run poe verify
127 passed; cobertura 95,44%; import-linter: 1 contrato mantido; nenhuma migração pendente
```

Os dois checkpoints passaram por uma única verificação completa e foram para um commit só, porque as rotas dos dois
ficam nos mesmos arquivos e a máquina estava com a CPU tomada por um contêiner de outro projeto. Os testes do
checkpoint 3 tinham sido vistos falhando e depois passando antes de o checkpoint 4 começar.

Testes novos: `backend/tests/test_rate_limit.py`, `backend/acesso/tests/test_sessao.py`,
`test_convite_domain.py`, `test_convites.py`.

### Checkpoint 5 — Cadastro com senha, verificação e e-mails (2026-11-12)

```text
uv run poe verify
154 passed; cobertura 95,48%; import-linter: 1 contrato mantido; nenhuma migração pendente
```

Testes novos: `backend/acesso/tests/test_cadastro.py` (27). Ajustes fora do previsto: a migração
`0003_convite_usado_por_opcional` (o convite continua usado quando o cadastro que o usou é descartado), e um Argon2
de custo mínimo só nos testes (`backend/tests/hashers.py`).

### Checkpoints 6 e 7 — Recuperação de senha e administração de usuários (2026-11-12)

```text
uv run poe verify
190 passed; cobertura 96,18%; import-linter: 1 contrato mantido; nenhuma migração pendente
```

Testes novos: `backend/acesso/tests/test_senha.py` (14) e `test_usuarios_admin.py` (22). Desvio do ciclo: nestes dois
checkpoints os testes foram escritos antes do código, mas não foram executados antes dele (a máquina estava lenta);
passaram na primeira execução depois do código. Um commit para os dois, pelo mesmo motivo dos checkpoints 3 e 4.

### Checkpoint 8 — Google: cadastro e login (2026-11-12)

```text
uv run poe verify
210 passed; cobertura 96,41%; import-linter: 1 contrato mantido; nenhuma migração pendente
```

Testes novos: `backend/acesso/tests/test_google.py` (20), com o verificador falso em `acesso/tests/fakes.py`. O
adapter real é testado sem rede. O login com uma conta Google de verdade só pode ser conferido quando o dono criar o
ID de cliente.

### Checkpoint 9 — Documentação da API protegida (2026-11-12)

```text
uv run poe verify
216 passed; cobertura 96,41%; import-linter: 1 contrato mantido; nenhuma migração pendente
```

Registro honesto: o commit `b056db3` deste checkpoint saiu com o lint falhando (uma linha com 112 colunas num
comentário de teste), porque o comando de commit não conferiu o código de saída da verificação. O commit seguinte
corrige a linha, e o resultado acima é o da verificação refeita, com saída 0.

Testes novos: `backend/acesso/tests/test_documentacao.py` (6). O teste antigo que esperava o contrato aberto a
qualquer pessoa (`tests/test_contract.py`) foi substituído, porque a technical-spec aprovada mudou esse
comportamento. Encerra a TD-001.

### Checkpoint 10 — Site (2026-11-12)

```text
npm run verify
30 passed; cobertura 86,39% (linhas 89,57%); lint, tipos e build sem erro; saída 0
```

Testes: `frontend/src/App.test.tsx` (26) e `frontend/src/api/client.test.ts` (4). Os cinco testes da página
provisória do M1 ("API no ar") foram substituídos, porque a página deu lugar às telas desta feature. Dois testes
novos tinham suposições de tempo erradas (ordem das chamadas e espera pela lista) e foram corrigidos antes do
commit, sem mudar o que conferem.

### Checkpoint 11 — Validação final (2026-11-12)

```text
uv run poe verify        → saída 0; 217 passed; cobertura 96,42%; import-linter: 1 contrato mantido
npm run verify           → saída 0; 30 passed; cobertura 86,39%
uv run pip-audit         → No known vulnerabilities found
npm audit --audit-level=high → found 0 vulnerabilities
docker compose up -d --build → api, worker, web, db e redis no ar
```

Fluxo completo percorrido pela API contra o sistema no ar, pelo proxy (`http://localhost:8080`), em 17 passos, todos
com o resultado esperado: admin criado pelo comando; login pelo e-mail; convite gerado; cadastro; convite gasto; login
recusado antes da verificação; e-mail de verificação no log do `worker`; verificação; login do diretor sem cargo;
diretor impedido de gerar convite; listagem; desativação; sessão do desativado encerrada na hora; saída; rota de admin
negada sem sessão.

O que essa validação achou, e que os testes automatizados não pegavam:

- a falha de CSRF respondia com a página HTML padrão do Django, fora do envelope de erro. Corrigido
  (`CSRF_FAILED`), com teste;
- no log, os links dos e-mails aparecem quebrados com `=`. É a codificação do e-mail, não um defeito do sistema;
  ficou documentado em `docs/setup/local.md` e `docs/api/manual-testing.md`.

Um teste do site falhou uma vez nesta etapa, e só quando a suíte do backend rodava ao mesmo tempo: o prazo padrão de
1 segundo para a tela reagir estourou. O prazo dos testes passou a 5 segundos (`frontend/src/test/setup.ts`); em três
execuções seguidas isoladas, os 30 testes passaram. O commit `4890554` saiu antes dessa correção.

Não validado: o roteiro pelo navegador, por uma pessoa, e o login com uma conta Google real (depende de o dono criar
o ID de cliente). O CI no GitHub só roda quando a branch for integrada à `dev` ou num pull request.

Memória em repouso com o M2 no ar: `api` 167 MB, `worker` 168 MB, `db` 46 MB, `redis` 14 MB, `web` 16 MB; cerca de
410 MB (eram 330 MB no M1).

## Rollback ou recuperação

Não há dado de produção. As migrações revertem com `python manage.py migrate <app> zero`; a versão anterior é a tag
`v0.1.0`.
