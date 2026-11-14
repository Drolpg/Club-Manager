# Modelo de ameaças

| Campo | Valor |
| --- | --- |
| Atualizado em | 2026-11-13 |
| Diagrama base | `docs/architecture/overview.md` § Containers |
| Responsável | Leandro Nascimento |
| Escopo desta versão | Marcos M2 (identidade e acesso), M3 (permissões e auditoria) e M4 (notificações). Cada marco seguinte acrescenta as ameaças do que entrega |

Feito uma vez neste marco, como desvio registrado em `docs/method.md` (elemento do nível 3), porque o sistema passa a
guardar dados pessoais e a controlar o acesso a dados financeiros.

## Fronteiras de confiança

| Fronteira | Entre | Dados que atravessam |
| --- | --- | --- |
| Internet → `web` | Navegador de qualquer pessoa e o proxy | Senha, cookie de sessão, token de convite, credencial do Google, dados pessoais do cadastro |
| `web` → `api` | Proxy e API, na rede interna do compose | Os mesmos, mais o IP do cliente no cabeçalho do proxy |
| `api` → Google | API e os servidores do Google | Token de identidade a validar; chaves públicas do Google |
| `api` e `worker` → e-mail | Sistema e o servidor SMTP | Endereço de e-mail, links de verificação e de recuperação |
| `api` e `worker` → `db` | Aplicação e banco | Todos os dados |
| `api` → `redis` → `worker` | Fila | IDs de usuário e tipo de e-mail; contadores de tentativas |
| Operador → servidor | Quem tem acesso ao servidor e o comando `criar_admin` | Senha do admin, digitada |
| Admin → convidado | Link de convite, enviado por fora (WhatsApp, e-mail pessoal) | Token de convite |

## STRIDE por elemento

| Elemento | Spoofing | Tampering | Repudiation | Information disclosure | Denial of service | Elevation of privilege |
| --- | --- | --- | --- | --- | --- | --- |
| Login com senha | Adivinhar senha → limite de 5 tentativas em 15 minutos por conta e limite por IP; política de senha | — | Login sem registro → fora da auditoria por volume; fica só no log (aceito) | Descobrir se uma conta existe → respostas e tempos iguais | Bloquear a conta de outro errando a senha de propósito → o bloqueio é temporário e a recuperação de senha continua disponível (aceito) | — |
| Login com Google | Token forjado ou de outro aplicativo → validar assinatura, público-alvo, validade e `email_verified` | — | — | — | Google fora do ar → o login por senha continua | Conta Google de quem não foi convidado → só entra e-mail que já tem conta |
| Convite | Link vazado é usado por outra pessoa → uso único, 24 horas, revogável; o admin confere quem entrou antes de classificar | Reusar o link → marcado como usado ao enviar o cadastro, com a linha bloqueada | Quem gerou → auditoria | Token em log ou no banco → só o hash é guardado; token no corpo da requisição | — | Convidado indevido vira diretor → nasce sem cargo e sem acesso a dados de gestão |
| Cadastro | Usar o e-mail de outra pessoa → só ativa com o link enviado àquele e-mail | — | — | Descobrir e-mails cadastrados pelo erro "em uso" → só com convite válido, e com limite por IP (aceito) | Encher o banco de cadastros pendentes → cada um exige um convite | — |
| Recuperação de senha | Tomar a conta pelo link → link de 1 hora e uso único, enviado só ao e-mail da conta | — | Redefinição → auditoria | Descobrir se o e-mail existe → resposta igual | Disparar e-mails em massa para alguém → 3 por hora por e-mail | — |
| Sessão | Roubar o cookie → `HttpOnly`, `Secure`, `SameSite=Lax`; nova chave no login | Forjar requisição em nome do usuário (CSRF) → token CSRF em toda escrita | — | — | — | Sessão de usuário desativado → conferida no banco a cada requisição |
| Administração de usuários | — | Alterar outro usuário sem ser admin → permissão na view e no serviço | Quem desativou ou deu o papel → auditoria | Listar usuários sem ser admin → negado | Trancar todos para fora → ninguém desativa a si mesmo nem tira o próprio papel; o comando do servidor recupera | Diretor se tornar admin → só um admin dá o papel |
| Auditoria | — | Alterar ou apagar registro → gatilho no banco recusa `UPDATE` e `DELETE`; o modelo não oferece esses caminhos | É a própria mitigação de repúdio | Dado pessoal no registro → só IDs e códigos | — | — |
| Banco, Redis | Acesso direto pela rede → em produção nenhuma porta é publicada; em desenvolvimento, só em `127.0.0.1` | Idem | — | Vazamento do banco → senhas em Argon2, convites em hash; os demais dados pessoais ficam em claro (ver ações) | — | — |
| E-mail | Falsificar o remetente para enganar diretores → SPF e DKIM do domínio (M12) | — | — | Link interceptado no caminho → validade curta; TLS com o servidor SMTP | — | — |
| Comando `criar_admin` | — | — | Admin criado fora do sistema → auditoria, com ator "sistema" | Senha no histórico do terminal → o comando lê sem ecoar e não aceita senha por argumento | — | Quem tem o servidor cria um admin → é o controle esperado: o acesso ao servidor é a raiz de confiança |

## Ações

| Ameaça | Mitigação | Status | Registro |
| --- | --- | --- | --- |
| Adivinhação de senha | Limite por conta e por IP; política de senha | Planejada (M2) | CA-22; technical-spec |
| Enumeração de contas | Respostas e tempos iguais | Planejada (M2) | RN-025; CA-21, CA-24 |
| Convite vazado | Uso único, 24 horas, revogação, hash | Planejada (M2) | CA-05 a CA-07 |
| CSRF e roubo de cookie | Atributos do cookie; CSRF | Planejada (M2) | ADR-008 |
| Acesso de usuário desativado | Sessão conferida a cada requisição | Planejada (M2) | CA-28 |
| Alteração da auditoria | Gatilho no banco | Planejada (M2) | Technical-spec |
| Sem HTTPS | Certificado e HSTS no proxy de produção | Planejada (M12) | AD-013 |
| E-mail falsificado | SPF, DKIM e DMARC no domínio | Planejada (M12) | AD-012 |
| Dados pessoais em claro no banco | Backup cifrado e disco cifrado na instância | Planejada (M12) | AD-013 |
| Login sem trilha de auditoria | Só log | Aceita | Rever se houver incidente |
| Bloqueio de conta por terceiro | Bloqueio temporário | Aceita | — |
| Enumeração de e-mail no cadastro, por quem tem convite | Limite por IP | Aceita | Technical-spec |
| Sem verificação em duas etapas | — | Aceita | Backlog |

## M3: permissões e auditoria

Elementos novos: catálogo de permissões, concessões (a cargo, setor ou usuário), classificação, portas de `acesso`
preenchidas por `permissoes`, rotas de histórico.

| Elemento | Spoofing | Tampering | Repudiation | Information disclosure | Denial of service | Elevation of privilege |
| --- | --- | --- | --- | --- | --- | --- |
| Concessões e classificação | — | Alterar quem pode o quê sem ser admin → `EhAdmin` na rota e `exigir_admin` no serviço; `acesso.total` nunca passa em `EhAdmin` | Quem concedeu, revogou ou classificou → auditoria na mesma transação, com ator e alvo | Ver permissões de outro usuário → o detalhe é só do admin; `minhas/` devolve só as de quem pergunta | Conceder em massa → só o admin, e a concessão repetida não cria duplicata | Diretor dar permissão a si mesmo → só o admin concede. Acesso total virar admin → o acesso total só amplia o catálogo e nunca dá administração |
| Catálogo | — | Criar permissão pelo painel → o catálogo vive no código; código fora dele é recusado | — | — | — | **Permissão órfã:** concessão de um código que saiu do catálogo → ignorada na resolução (PER-R05) |
| Portas de `acesso` | — | — | — | — | — | **Porta sem implementação:** sem `permissoes` registrado, `acesso` usa o padrão seguro (convites só do admin; ninguém com cargo). Porta que responde "sim" demais → a sessão ainda tem de estar ativa, e o serviço confere de novo |
| Histórico | — | Alterar o histórico → a auditoria é imutável (gatilho do banco) | — | Ver o histórico sem direito → segue a regra do item (admin; convites, também quem os gerencia); só o nome do ator sai, nunca `dados` | — | — |
| Cargo, setor | — | Apagar para sumir com o rastro → não existe rota de apagar; só desativar | Renomear para confundir → auditoria de cada renomeação | — | — | — |

| Ameaça | Mitigação | Status | Registro |
| --- | --- | --- | --- |
| Elevação por concessão | Só admin concede; acesso total não administra | Implementada (M3) | CA-21, CA-24 |
| Porta sem implementação | Padrão seguro, testado com a porta restaurada | Implementada (M3) | `acesso/tests/test_portas.py` |
| Permissão órfã | Ignorada na resolução | Implementada (M3) | PER-R05; `test_permissao_fora_do_catalogo_e_ignorada` |
| Alteração de permissão sem rastro | Auditoria na transação | Implementada (M3) | CA-29 |
| Escrita autenticada sem token CSRF respondia `PERMISSION_DENIED` e não `CSRF_FAILED` | `kernel.http.SessionAuthentication.enforce_csrf` converte a falha em `CSRF_FAILED`, no mesmo texto de `csrf_failure` | Corrigida (revisão do PR #2) | `backend/tests/test_csrf.py` |

## M4: notificações

Elementos novos: o registro e a caixa de notificações, o e-mail das notificações (fila), o despachante de eventos
em processo, as preferências de alerta, o sino e o aviso flutuante no site, e o Mailpit (só em desenvolvimento).

| Elemento | Spoofing | Tampering | Repudiation | Information disclosure | Denial of service | Elevation of privilege |
| --- | --- | --- | --- | --- | --- | --- |
| Caixa e resumo (rotas) | Ler a caixa de outro com a sessão dele → só a sessão do dono; nada novo | Alterar o conteúdo de uma notificação → o modelo recusa e não há rota que grave conteúdo; `ler` só preenche `lida_em` na primeira vez | Dizer que não foi avisado → o registro guarda criação, leitura e resultado do e-mail, e não pode ser apagado | **Ler a caixa alheia:** toda consulta filtra pelo usuário logado; a de outro responde 404, igual à que não existe, inclusive para o admin; um cursor `antes` de outra pessoa responde 400. IDs são UUID 7, mas o filtro, e não o segredo do ID, é a defesa | Consulta a cada minuto por todos os diretores → duas contagens indexadas; `limite` de no máximo 50 | Admin ler a caixa dos outros → não existe rota nem permissão para isso (o admin audita pelos históricos dos itens) |
| Criação de notificação | **Notificação forjada:** só código do sistema cria (`notificar`, `registrar_tipo`); não há rota de criação, e o tipo desconhecido é erro de programação | Duplicar para encher a caixa → `chave` única por destinatário | — | Texto com dado sensível → o texto é curto e montado pelo código, sem valores nem dados de contato; o site o mostra como texto, nunca como HTML | Fato repetido gera aviso em dobro → idempotente pela chave | — |
| E-mail da notificação | Remetente falso → SPF, DKIM e DMARC (M12), como já planejado | — | Falha de envio sem registro → `email_situacao`, tentativas e `FALHOU` ficam na notificação | **Vazamento por e-mail:** só texto puro, com título, texto e o link do site; nenhum token, senha ou dado de contato; o link exige login; só vai ao endereço do usuário ativo. Nada de dado pessoal nos logs (só o ID e o tipo do erro) | Servidor SMTP fora do ar → 5 tentativas com espera crescente e então `FALHOU`; a notificação segue na caixa e a operação de negócio não depende do e-mail | — |
| Despachante de eventos | — | Um tratador malicioso ou com erro → só `notificacoes` registra tratadores, no `ready`; o erro de um tratador desfaz a operação de quem publicou (risco 4), por isso ele só monta o texto e chama `notificar` | — | — | Tratador lento → roda na transação; por isso é curto | — |
| Preferências | — | Desligar o registro por uma chave → nenhuma chave faz isso; o `PUT` ignora campos desconhecidos e só aceita `true` ou `false` | — | Ver ou mudar a preferência de outro → só a do usuário logado | — | — |
| Sino e aviso flutuante (site) | — | **`caminho` vindo da API:** só se navega para caminho do próprio site (`/…`, nunca `//`, `\` nem `https://…`) | — | Texto da notificação interpretado como HTML (XSS) → React o renderiza como texto, com teste | A consulta a cada 60 s só com a aba visível, e a falha não vira laço | — |
| Mailpit (desenvolvimento) | — | — | — | E-mails de desenvolvimento visíveis a quem acessa a máquina → a página só atende em `127.0.0.1:8025`, o SMTP (1025) só na rede interna do compose, e o `compose.yaml` de produção não o contém | — | `EMAIL_URL` com `?tls=0` em produção por engano → só `?tls=0`, só em `smtp://`, e qualquer outra opção é recusada; o `.env.example` e a configuração dizem que é só para o Mailpit |

| Ameaça | Mitigação | Status | Registro |
| --- | --- | --- | --- |
| Leitura da caixa de outro usuário | Filtro por destinatário em toda consulta; 404 igual ao inexistente; sem rota de admin | Implementada (M4) | CA-14; `notificacoes/tests/test_rotas.py` |
| Notificação forjada ou alterada | Sem rota de criação; modelo recusa alterar e apagar | Implementada (M4) | NOT-R05; `notificacoes/tests/test_modelos.py` |
| Vazamento por e-mail | Texto puro, sem token nem dado de contato; link que exige login | Implementada (M4) | CA-08; `notificacoes/tests/test_email.py` |
| Notificação duplicada | Chave única por destinatário | Implementada (M4) | CA-07; NOT-R02 |
| Falha do servidor de e-mail | Nova tentativa, `FALHOU`, a caixa continua | Implementada (M4) | CA-06 |
| XSS e redirecionamento por `caminho` ou texto | Texto como texto; só caminhos do site | Implementada (M4) | `frontend/src/notificacoes.test.tsx` |
| Servidor sem criptografia por engano | `?tls=0` só em `smtp://` e só ele | Implementada (M4) | `backend/tests/test_email_url.py` |
| Tratador com erro desfaz a operação | Tratadores curtos e testados | Mitigada (risco 4) | ADR-003 |
| Intervalo real entre as tentativas de e-mail não testado | Configuração conferida no teste; o modo imediato dos testes o ignora | Aceita | Rever ao ver um e-mail atrasar em produção |
| Aviso flutuante e preferência não conferidos por outra pessoa no navegador | Testes automáticos com relógio simulado; conferência manual parcial | Aceita | Conferir na validação do dono |

## M5: motor de aprovações

Elementos novos: o motor de solicitações (rotas de envio, comandos, decisões e consultas), o registro de tipos em
processo, os motivos de decisão, a tarefa diária de lembretes e o tipo de demonstração (só em desenvolvimento).

| Elemento | Spoofing | Tampering | Repudiation | Information disclosure | Denial of service | Elevation of privilege |
| --- | --- | --- | --- | --- | --- | --- |
| Decisões (`aprovar`, `contestar`, `recusar`) | Decidir em nome de outro → a decisão grava o ator da sessão; não há campo de aprovador na entrada | **Decisão sobre versão antiga:** a decisão vale só para a versão vigente e só em análise; a linha fica bloqueada, e o índice único por versão é a segunda barreira | Negar uma decisão → a decisão é imutável no modelo e no banco, com aprovador, motivo e momento, e a auditoria registra o mesmo na transação | — | Duas decisões ao mesmo tempo → a segunda espera o bloqueio e recebe `NAO_ESTA_EM_ANALISE` | **Decidir o próprio pedido por atalho:** uma função pura só (`avaliar`) responde em todos os caminhos; o solicitante só decide com a auto-aprovação, que fica fora do acesso total; acesso total, admin, indicado e quem não tem cargo testados um a um |
| Indicação de aprovador | — | Trocar o indicado depois → não há rota para isso | A indicação fica no histórico e o admin é avisado | — | — | **Indicação abusiva:** só indica quem aprovaria o próprio pedido; o indicado precisa ser outro diretor ativo com cargo; decide só aquela solicitação, sem ganhar permissão; quem não precisa indicar é recusado (A1) |
| Envio e conteúdo | — | **Conteúdo malicioso:** objeto JSON de até 64 KB, validado pelo módulo dono; o site o mostra como texto, nunca como HTML (com teste) | — | — | Conteúdo enorme → limite de 64 KB; textos livres até 1000 caracteres | Enviar tipo de quem não pode → leitura de gestão e, se o tipo pede, a permissão de enviar |
| Consultas (lista, fila, detalhe, histórico) | — | — | — | **Enumeração de IDs:** a leitura de gestão vem antes da existência; quem não lê recebe 403 sem saber se o ID existe. Diretor sem cargo não lê nada | Lista e caixa paginadas (até 50) | `acoes` é só conveniência do site: cada rota confere de novo, e um teste de paridade compara as duas por papel e situação |
| Versões e motivos | — | **Alterar versão, decisão ou motivo usado:** gatilho no banco recusa alterar decisão e versão (só as datas de lembrete mudam) e apagar as duas; motivos e solicitações nunca são apagados; a decisão guarda o texto do motivo | Motivos editados → auditados; a decisão antiga mantém o texto | — | — | Manter motivos sem ser admin → rotas e serviço exigem admin |
| Registro de tipos e execução | Módulo que se passa por dono de outro tipo → o registro é código do sistema, no `ready`; um código registrado com outra definição falha ao iniciar | — | Execução e encerramento auditados, com o ator do módulo dono ou nulo (sistema) | — | — | Usuário pôr em execução ou encerrar → não existe rota (teste) |
| Tarefa de lembretes | — | — | — | Texto do lembrete com dado sensível → resumo e tipo, sem valores de contato | Tarefa repetida → idempotente pela data na versão e pela chave da notificação | — |
| Tipo de demonstração | — | — | — | — | — | **Tipo e permissão de demonstração em produção:** só existem com `DJANGO_DEBUG=1` e a variável ligada; com `DEBUG` desligado a variável é ignorada (teste); o `compose.yaml` de produção não a repassa |

| Ameaça | Mitigação | Status | Registro |
| --- | --- | --- | --- |
| Decidir o próprio pedido por atalho | `avaliar` em todos os caminhos; auto-aprovação fora do acesso total | Implementada (M5) | INV-SOL-02; CA-19, CA-22 a CA-25 |
| Decisão sobre versão antiga, ou duas decisões | Só em análise, versão vigente, bloqueio da linha, índice único | Implementada (M5) | INV-SOL-01, INV-SOL-14; CA-06 |
| Indicação abusiva | Só quem precisa; indicado ativo com cargo; vale só para aquela solicitação | Implementada (M5) | INV-SOL-10, 11, 15; A1 |
| Conteúdo malicioso | 64 KB, validado pelo dono, mostrado como texto | Implementada (M5) | `frontend/src/aprovacoes.test.tsx` |
| Enumeração de IDs | Leitura antes da existência | Implementada (M5) | `aprovacoes/tests/test_consultas.py` |
| Versão ou decisão alterada por fora do modelo | Gatilho no banco | Implementada (M5) | `aprovacoes/tests/test_modelos.py` |
| Tipo de demonstração em produção | Só com `DEBUG` ligado | Implementada (M5) | `aprovacoes/tests/test_demonstracao.py` |
| `acoes` e as rotas divergirem | A mesma função pura; teste de paridade | Implementada (M5) | `test_acoes_do_detalhe_coincidem_com_o_que_as_rotas_aceitam` |
| Aprovador indicado desativado deixa o pedido parado | O aviso de 7 dias ao admin; os demais aprovadores e o admin continuam decidindo | Aceita | Backlog (aviso ao admin na desativação) |
| O módulo dono não é avisado do envio e do reenvio | Fora do M5, por decisão do adendo 1 | Aceita | M7 e M8, por adendo |
