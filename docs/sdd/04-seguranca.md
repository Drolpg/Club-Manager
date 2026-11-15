# Segurança

Modelo de ameaças, avaliação de LGPD e o relatório de vulnerabilidades de cada marco. Toda feature registra uma
revisão de segurança, e cada marco fecha com um relatório. Reproduzir um relatório significa rodar os comandos da
seção "Como reproduzir" dele.

## 1. Modelo de ameaças

| Campo | Valor |
| --- | --- |
| Atualizado em | 2026-11-15 |
| Diagrama base | [02-plan](02-plan.md), seção Containers |
| Responsável | o dono do projeto |
| Escopo desta versão | Marcos M2 (identidade e acesso), M3 (permissões e auditoria), M4 (notificações), M5 (aprovações), M6 (financeiro: entradas e cobranças) e M7 (financeiro: saídas, prestação de contas e estornos). Cada marco seguinte acrescenta as ameaças do que entrega |

Feito uma vez neste marco, como desvio registrado em [03-tasks](03-tasks.md) (elemento do nível 3), porque o sistema passa a
guardar dados pessoais e a controlar o acesso a dados financeiros.

### Fronteiras de confiança

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

### STRIDE por elemento

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

### Ações

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

### M3: permissões e auditoria

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

### M4: notificações

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

### M5: motor de aprovações

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

### M6: financeiro — cobrança e recebimento

Elementos novos: cadastros de categorias e chaves Pix (com exceção controlada de chave tipo CPF), cobranças
avulsas e em lote com geração local de Pix copia e cola / QR Code SVG, pagamentos com upload de comprovante
ou em mão, recibo em PDF, questionamentos, isenções, recorrências e suspensões, rotina diária idempotente,
inadimplência e renegociação, entradas sem devedor, armazenamento de anexos em `STORAGES["default"]`
(`media-data`, `kernel/anexos.py`) e evento `UsuarioDesativado`.

| Elemento | Spoofing | Tampering | Repudiation | Information disclosure | Denial of service | Elevation of privilege |
| --- | --- | --- | --- | --- | --- | --- |
| Cadastros (`CategoriaFinanceira`, `ChavePix`) | — | Alterar chave Pix de cobrança emitida → snapshot imutável da chave e do BR Code gravados na criação da cobrança | Criação, edição, padrão, desativação e reativação auditados | Chave CPF → aceita apenas para chave Pix do clube, com aviso explícito de LGPD na tela; nunca há CPF no cadastro do diretor | Índice único parcial para `padrao=True`; sem rota de exclusão (`PROTECT`) | Só admin escreve nas rotas e serviços |
| Cobranças e pagamentos (`COMPROVANTE` e `EM_MAO`) | Validar em nome de outro → ator vem da sessão | Validação simultânea ou sobre pagamento já decidido → `select_for_update()` na cobrança + índice único parcial para `EM_VALIDACAO`; estado muda só pelos métodos do aggregate | Toda criação, pagamento, validação, rejeição, isenção, cancelamento e recebimento auditados na transação com motivo quando exigido | Comprovantes com dados bancários de terceiros → descarga apenas por rota autenticada (`pagamentos/{id}/comprovante/`) restrita a devedor, `pagamentos.validar` e admin, com `X-Content-Type-Options: nosniff` e `Cache-Control: private, no-store`; sem URL no detalhe para quem não pode ver e sem binário em log/auditoria/e-mail | Tamanho máximo de 5 MB, assinatura verificada por magic bytes (PDF, PNG, JPEG, WebP; HTML/SVG recusados) e chave opaca `<contexto>/<uuid7>.<ext>` | **Devedor validar ou decidir o próprio item:** `avaliar_cobranca` centraliza a regra (inclusive negando acesso total para validação pelo devedor); diretor sem cargo não enumera cobranças de terceiros (403 em qualquer ID fora das suas) |
| Questionamento e inadimplência (`perdoar`, `renegociar`, `manter-divida`) | — | Lançar parcelas negativas ou no passado → `Dinheiro > 0` e validação atômica de todas as parcelas em `transaction.atomic()` antes de marcar `RENEGOCIADA` | Decisões e justificativa da dívida auditadas com `motivo_id` e texto do motivo copiado | Lista `?inadimplentes=1` só para quem lê gestão e sem vazamento fora de diretor com cargo | Questionamento aberto trava novo questionamento e pausa contagem de inadimplência | Devedor não decide questionamento nem dívida (`DEVEDOR_NAO_DECIDE`) |
| Recorrência, suspensão e rotina diária | — | Alterar recorrência retroativamente → edição afeta só competências futuras; cobranças já geradas preservam seus snapshots | Execuções da rotina auditadas com `ator_id=None` (sistema) | Sem valores nem comprovantes em e-mails | Execução repetida no mesmo dia é idempotente por índice único `(recorrencia, devedor_id, competencia)` e datas de lembrete/atraso; diretor inativo é ignorado | Apenas `cobrancas.criar` e `cobrancas.suspender` gerenciam recorrências e suspensões |
| Entradas sem devedor e API pública | — | Rejeitar ou validar fora de `EM_VALIDACAO` → transição bloqueada na tabela e com `select_for_update()` | Registro, evidência e decisão auditados | Comprovante restrito a registrador, `entradas.validar` e admin com `nosniff` e `no-store` | Exige comprovante válido ou `evidencia_texto` | **Quem registrou validar a própria entrada:** `avaliar_entrada` exige `registrada_por_id != ator_id` (`REGISTRADOR_NAO_VALIDA`) |
| Site (Pix QR Code, formulários e ações) | — | **XSS por SVG ou textos livres:** `QrCodePix.tsx` interpreta atributos numéricos do SVG gerado sem `dangerouslySetInnerHTML`; textos livres renderizados como texto | — | Diretor sem cargo não dispara consultas administrativas nem `/permissoes/minhas/` pelo menu | Upload validado no backend em tamanho e assinatura | `acoes` é apenas conveniência visual; cada rota revalida tudo na API (teste de paridade) |

| Ameaça | Mitigação | Status | Registro |
| --- | --- | --- | --- |
| Vazamento de comprovante para terceiros | Rota autenticada com `autorizacao.py`, `nosniff`, `private, no-store`, URL omitida para quem não pode ver, sem binário na auditoria/e-mail | Implementada (M6) | CA-18; `test_parte2_pagamentos.py`, `test_parte6_entradas_e_public.py` |
| Upload malicioso ou SVG/HTML disfarçado | Validação em `kernel/anexos.py` até 5 MB e magic bytes (PDF, PNG, JPEG, WebP), chave `<contexto>/<uuid7>.<ext>` | Implementada (M6) | CA-20; `kernel/tests/test_anexos.py` |
| Autovalidação pelo devedor ou registrador | `avaliar_cobranca` e `avaliar_entrada`, inclusive com acesso total, cobertos por paridade `acoes` ↔ rotas | Implementada (M6) | CA-15, CA-41, CA-43; `test_parte6_entradas_e_public.py` |
| Enumeração de IDs por diretor sem cargo | 403 imediato ao consultar recurso de outro devedor ou rotas de gestão | Implementada (M6) | CA-45; `test_parte1_cobrancas.py` |
| Concorrência em validação dupla ou duplicata recorrente | `select_for_update()`, índices únicos parciais (`EM_VALIDACAO`, competência) e unicidade atômica | Implementada (M6) | CA-22; `test_parte2_pagamentos.py`, `test_parte3_recorrencias.py` |
| XSS via SVG do QR Code ou textos | Renderização declarativa em `<QrCodePix />` sem `dangerouslySetInnerHTML` | Implementada (M6) | `frontend/src/financeiro.test.tsx` |
| BR Code recusado por algum banco real | Payload EMV + CRC16 conferido nos testes e nos contêineres; resta teste manual com bancos reais | Pendente do dono (risco 3) | [02-plan](02-plan.md) § 6 |

### M7: financeiro — gastos, saídas, prestação de contas e estornos

Elementos novos: upload e download de cotações (`Cotacao`), solicitações estruturadas de gasto e complemento
(`financeiro.gasto` no motor `aprovacoes`), aggregate `Saida` (`Envio`, `PrestacaoDeContas`, `Complemento`),
devolução de sobra ligada a `Entrada` (`saida`), rotina diária de lembretes (5 e 7 dias), visão do caixa
(`total_entradas_validadas`, `total_saidas_liquidadas`, `total_comprometido`) e aggregate imutável `Estorno`
(`ADR-013`).

| Elemento | Spoofing | Tampering | Repudiation | Information disclosure | Denial of service | Elevation of privilege |
| --- | --- | --- | --- | --- | --- | --- |
| Solicitação de gasto e cancelamento pré-envio | — | Cancelar ou editar gasto após o dinheiro sair → primeiro `Envio` transiciona a solicitação para `EM_EXECUCAO` (`select_for_update()`), travando edição e cancelamento no motor | Abertura, reaprovação e cancelamento automático gravados na auditoria (`SAIDA_ABERTA`, `SAIDA_CANCELADA`) com IDs e versões | Visão do caixa e lista de solicitações de gasto restritas a quem lê gestão (`403` para diretor sem cargo) | Limite de itens > 0, soma positiva em `Decimal` e payload validado pelo tipo | Solicitante não aprova o próprio gasto sem permissão específica (`INV-SOL-02`) |
| `Cotacao`, `Envio` e `PrestacaoDeContas` (anexos) | — | SVG/HTML disfarçado de comprovante → `kernel/anexos.py` valida magic bytes (PDF, PNG, JPEG, WebP) e tamanho <= 5 MB, gravando em chave opaca `<contexto>/<uuid7>.<ext>` | Metadados (`chave`, `nome`, `tamanho`) gravados na entidade e na auditoria; nunca o binário nem caminho em disco | Download apenas via rotas autenticadas `LeGestao` (`cotacoes/{id}/`, `saidas/{id}/envios/{eid}/comprovante/`, `prestacoes/{pid}/comprovante/`) com `X-Content-Type-Options: nosniff` e `Cache-Control: private, no-store`; omitido fora de gestão | Sem endereço direto para `MEDIA_ROOT`; `Envio` sem comprovante é recusado | Diretor sem cargo recebe `403` sem confirmar se o ID existe; envio exige `saidas.enviar`; prestação exige ser o solicitante (`SO_O_SOLICITANTE`) |
| Devolução de sobra e liquidação (`INV-ENT-04`, `INV-SAI-05`) | — | Liquidar saída antes da validação da devolução ou com envio/complemento concorrente → `select_for_update()` na saída + `DEVOLUCAO_PENDENTE` (`422`); excesso sem reembolso exige justificativa | `PRESTACAO_REGISTRADA`, `PRESTACAO_DEVOLVIDA` (com `motivo_id` e snapshot), `COMPLEMENTO_*` e `SAIDA_LIQUIDADA` auditados na mesma transação | **Vazamento de comprovante bancário na devolução:** `devolucoes` usa sigilo de `Entrada` — quem tem `saidas.liquidar` sem `entradas.validar` recebe `403` ao baixar comprovante de devolução (`INV-ENT-04`) e `comprovante_disponivel=false` no JSON | Limite de devolução `<= total_enviado`; no máximo um `Complemento` em andamento por índice único parcial e uma `PrestacaoDeContas` vigente | Quem pediu o gasto não liquida (`SOLICITANTE_NAO_LIQUIDA`), não devolve prestação e não valida devolução (`REGISTRADOR_NAO_VALIDA`), inclusive com `acesso.total` |
| Estorno (`ADR-013`) | — | Alterar registro liquidado/pago/validado ou estornar duas vezes → `OneToOneField(PROTECT)` + `CheckConstraint` de exclusividade por `alvo_tipo` + recusa de `UPDATE`/`DELETE` em `Estorno` + tabela de transições proíbe saída de `ESTORNADA`; devolução de saída `LIQUIDADA` é bloqueada (`NAO_PODE_ESTORNAR`) | Dupla trilha na mesma transação (`SAIDA_ESTORNADA` / `ENTRADA_ESTORNADA` / `COBRANCA_ESTORNADA` e `ESTORNO_REGISTRADO`) com `motivo_id`, snapshot e justificativa obrigatória | Recibo PDF de cobrança estornada retorna `422 NAO_ESTA_PAGA` | Consulta paginada por cursor com limite <= 50 | Permissão `financeiro.estornar` nasce restrita ao admin (sem atribuição automática a setores, `P7`) |
| Visão do caixa, rotina diária e site | — | XSS em textos livres de gastos, prestações ou estornos → React renderiza campos como texto (`DetalhesConteudoGasto`, `BlocoEstorno`, `DetalheDaSaida`) | Execuções de lembretes 5d/7d notificam por chave idempotente sem duplicar alerta | Devoluções ligadas (`saida__isnull=False`) ficam fora de `total_entradas_validadas` (zero dupla contagem); diretor sem cargo é redirecionado fora de `/saidas` e `/gastos/novo` | Lembretes idempotentes por `lembrete_5_dias_em` e `aviso_7_dias_em` sob `select_for_update()` | Botões no site apenas refletem `acoes` calculadas no backend; rotas e serviços revalidam tudo (teste de paridade) |

| Ameaça | Mitigação | Status | Registro |
| --- | --- | --- | --- |
| Sigilo da devolução quebrado por quem liquida | `pode_ver_comprovante_entrada` aplicado também em `devolucoes` do detalhe e na rota de download (`403`) | Implementada (M7) | `INV-ENT-04`; `test_parte10_saidas_http.py` e E2E |
| Cancelamento ou alteração após transferência financeira | Transição atômica `Solicitacao -> EM_EXECUCAO` no primeiro `Envio` (`INV-SAI-08`, `INV-SOL-09`) | Implementada (M7) | `CA-10`; `test_parte8_saidas_servicos.py` |
| Autoliquidação ou ação fora do solicitante | `avaliar_saida` centraliza segregação (`SO_O_SOLICITANTE`, `SOLICITANTE_NAO_LIQUIDA`), inclusive com `acesso.total`, com teste de paridade | Implementada (M7) | `CA-12`, `CA-25`; `test_parte10_saidas_http.py` |
| Estorno duplo, retroativo inconsistente ou alteração de saldo final | Modelo imutável `Estorno` (`OneToOneField` + `CheckConstraint`), bloqueio de devolução de saída liquidada e remoção de recibo estornado | Implementada (M7) | `ADR-013`, `INV-SAI-09`; `test_parte9_estornos_e_caixa.py` |
| Acesso a anexos de gasto por diretor sem cargo | `LeGestao` nas rotas de cotação, envio e prestação + `nosniff` e `private, no-store` | Implementada (M7) | `P6`; `test_parte10_saidas_http.py` e E2E |
| Notificações repetidas de atraso em reexecução | `lembrete_5_dias_em` / `aviso_7_dias_em` gravados sob `select_for_update()` + chave idempotente | Implementada (M7) | `RF-126`, `CA-14`; `test_parte9_estornos_e_caixa.py` |

## 2. Avaliação de LGPD

| Campo | Valor |
| --- | --- |
| Atualizado em | 2026-11-14 |
| Decisão | AD-015 |
| Escopo | Etapa 1: diretores de um clube |

> Isto é uma avaliação técnica, não um parecer jurídico. Antes de o sistema ir para
> produção com dados reais, vale o dono conferir os pontos marcados como "a confirmar" com alguém que entenda de
> proteção de dados.

### Quem é quem

| Papel na LGPD | Quem |
| --- | --- |
| Controlador | O clube que usa o sistema (hoje, o time do dono) |
| Titulares | Os diretores cadastrados |
| Operador | Quem hospeda e mantém o sistema para o clube (hoje, o próprio dono) |

### Dados pessoais tratados

| Dado | Para quê | Marco |
| --- | --- | --- |
| Nome, nome de usuário | Identificar o diretor nas decisões e nos registros | M2 |
| E-mail | Login, verificação, recuperação de senha, notificações | M2 |
| Telefone | Contato entre diretores | M2 |
| Hash da senha, identificador do Google | Autenticação | M2 |
| Registros de auditoria (quem fez o quê) | Rastreabilidade das decisões do clube | M2 em diante |
| Cobranças, pagamentos e comprovantes do diretor | Controle financeiro do clube (download restrito e sigilo contra terceiros) | M6, M7 |

O sistema não trata dado sensível (saúde, biometria, religião) e não coleta CPF cadastral de usuários
(RN-003); a única exceção é a chave Pix do clube tipo CPF cadastrada pelo admin, com aviso específico na tela.

### Base legal (a confirmar)

| Tratamento | Base provável |
| --- | --- |
| Cadastro, login e contato | Execução do vínculo do diretor com o clube, ou legítimo interesse do clube |
| Registros financeiros e auditoria | Legítimo interesse do clube na prestação de contas; obrigação estatutária, se o clube tiver estatuto |
| Notificações por e-mail | As mesmas: fazem parte da função de diretor, e não de publicidade |

O sistema não pede consentimento porque nenhuma dessas bases depende dele. Se o clube passar a usar os dados para
outro fim (divulgação, por exemplo), isso muda.

### O que o sistema faz

| Princípio ou direito | Como é atendido | Marco |
| --- | --- | --- |
| Necessidade | Só os dados da tabela acima; sem CPF, endereço ou data de nascimento | M2 |
| Transparência | Aviso de privacidade no cadastro (texto abaixo) | M2 |
| Segurança | Senha em Argon2, sessão protegida, acesso negado por padrão, auditoria, logs sem dado pessoal | M2 |
| Acesso aos próprios dados | Perfil do usuário | M9 |
| Correção | Edição dos próprios dados (pendência do enunciado) ou pedido ao admin | M9 |
| Eliminação | Ver a tensão abaixo | M12 |
| Portabilidade | Exportação dos próprios dados em CSV, pelos relatórios | M10 |
| Resposta a incidente | Procedimento de comunicação | M12 |

### Tensão: "nada é apagado" e o direito de eliminação

O enunciado manda nunca apagar (AUD-04, RN-004, RN-014), para preservar o histórico financeiro. A LGPD permite
manter dados quando há base para isso, e a prestação de contas do clube é uma. Mas o nome e o contato de quem saiu
não precisam ficar visíveis para sempre.

Proposta, a decidir no M12 (fica registrada na AD-015): quando um diretor desativado pedir, o admin **anonimiza** o
cadastro. Nome, nome de usuário, e-mail e telefone são trocados por um marcador ("Diretor removido 0193"), e os
registros financeiros e de auditoria continuam íntegros, ligados ao mesmo ID. Nada é apagado, e o titular deixa de
ser identificável.

### Texto do aviso de privacidade (cadastro)

> **Seus dados no Club Manager**
>
> Para você participar da gestão do clube, guardamos seu nome, nome de usuário, e-mail e telefone. Eles são usados
> para identificar você nas decisões e nos registros financeiros, para o login e para avisos do sistema.
>
> Os outros diretores veem seu nome nas decisões e nos registros. Seu perfil completo só é visto por você e pelo
> administrador.
>
> As ações feitas no sistema ficam registradas, porque a rastreabilidade é o propósito dele. Se você deixar a
> diretoria, sua conta é desativada e o histórico é mantido.
>
> Para ver, corrigir ou pedir a anonimização dos seus dados, fale com o administrador do clube.

O texto é fixo na etapa 1. O nome e o contato do administrador do clube passam a aparecer quando a marca for
configurável (M11).

### Pendências

| Pendência | Quando |
| --- | --- |
| Confirmar a base legal com alguém qualificado | Antes da produção (M12) |
| Decidir a anonimização a pedido | M12 |
| Procedimento de incidente e contato do encarregado, se o clube precisar de um | M12 |
| Comprovantes (dados bancários de terceiros) | Tratada no M6 (ADR-014; acesso restrito a devedor/registrador, validador e admin; `nosniff`, `no-store`; sem e-mail nem binário em auditoria) |

## 3. Relatório de vulnerabilidades — M1

| Campo | Valor |
| --- | --- |
| Projeto | Club Manager |
| Escopo | Projeto inteiro: esqueleto do backend, do site, imagens, compose e CI |
| Data da execução | 2026-11-12 |
| Responsável | o dono do projeto |
| Ferramentas | SCA: pip-audit 2.10 e `npm audit` (npm 10). SAST: regras `S` do Ruff 0.17. DAST: não executado (ver lacunas). Revisão manual da configuração e dos contêineres em execução |
| Especificação | Rito 7 do método; ADR-004 a ADR-007 |
| Achados aceitos sem correção | TD-001 |

### 1. Contexto e escopo

O sistema ainda não tem função de negócio. A superfície é uma rota aberta de saúde (`/api/v1/health/`), o contrato
da API e a página do site. Não há autenticação, usuário, upload nem dado pessoal: isso entra no M2, junto com o
threat model (STRIDE) previsto em [03-tasks](03-tasks.md).

Foram analisados: dependências do backend e do site, o código do esqueleto, a configuração do Django, as imagens e o
compose em execução. Ficou de fora o DAST, pelo motivo da seção 7.

### 2. Frentes

| Frente | Ferramenta | O que cobre | Mapeamento OWASP |
| --- | --- | --- | --- |
| SCA | pip-audit; `npm audit --audit-level=high` | Vulnerabilidades conhecidas em dependências diretas e transitivas | A06 — Vulnerable and Outdated Components |
| SAST | Regras `S` (Bandit) do Ruff | Padrões inseguros no código Python | A02, A03, A05 |
| Configuração | Revisão manual e inspeção dos contêineres | Segredos, permissões padrão, cabeçalhos, usuário dos processos, portas | A05 — Security Misconfiguration |
| DAST | Não executado | — | — |

### 3. Como reproduzir

```text
# SCA e SAST do backend (em backend/)
uv run pip-audit
uv run ruff check --select S .

# SCA do site (em frontend/)
npm audit --audit-level=high

# Configuração, com o sistema no ar (na raiz)
docker compose up -d --build
docker compose exec -T api id
docker compose exec -T web id
docker compose port db 5432
curl -s -i http://localhost:8080/api/v1/health/
```

### 4. Resultado: inicial → correções → final

| Frente | Severidade | Inicial | Final | Variação |
| --- | --- | --- | --- | --- |
| SCA backend | Crítica, alta, média | 0 | 0 | — |
| SCA site | Crítica, alta, média | 0 | 0 | — |
| SAST | Qualquer | 0 | 0 | — |
| Configuração | Média | 1 | 0 | −1 |
| Configuração | Baixa | 2 | 1 (aceita, TD-001) | −1 |

Regra adotada: críticas e altas são corrigidas obrigatoriamente; médias e baixas são avaliadas e registradas.

### 5. Achados corrigidos

#### CFG-01 — Banco, Redis e API de desenvolvimento expostos para a rede

| Campo | Valor |
| --- | --- |
| Ferramenta | Inspeção (`docker compose port`) |
| Componente afetado | `compose.override.yaml` |
| Severidade | Média |
| Impacto e risco | As portas 5433, 6380 e 8000 escutavam em `0.0.0.0`. Numa rede compartilhada, outra máquina alcançaria o Redis, que não tem senha, e o banco |
| Ação realizada | As três portas passaram a escutar só em `127.0.0.1`. O `compose.yaml` de produção nunca as publicou |
| Regressão | `uv run poe verify`: 19 testes passando, com o banco em `127.0.0.1:5433` |
| Evidência | `docker compose port db 5432` → `127.0.0.1:5433`; `docker compose port redis 6379` → `127.0.0.1:6380` |

#### CFG-02 — Contêiner do site rodando como root

| Campo | Valor |
| --- | --- |
| Ferramenta | Inspeção (`docker compose exec web id`) |
| Componente afetado | `frontend/Dockerfile`, `frontend/Caddyfile` |
| Severidade | Baixa |
| Impacto e risco | Uma falha no proxy daria root dentro do contêiner |
| Ação realizada | Usuário próprio (`web`, uid 10001) e porta alta (8080) dentro do contêiner |
| Regressão | Site e `/api/v1/health/` respondem pelo proxy depois da mudança |
| Evidência | `docker compose exec -T web id` → `uid=10001(web)`; a API e o worker já rodavam como `uid=10001(app)` |

### 6. Achados não corrigidos

#### CFG-03 — Contrato e documentação da API abertos, com a página carregando arquivos de uma CDN

| Campo | Valor |
| --- | --- |
| Motivo | Risco aceito por ora: não há rota de negócio nem ambiente de produção |
| Mitigação em vigor | A documentação só lista a rota de saúde; o sistema não está publicado |
| Registro | TD-001 |
| Gatilho de reavaliação | Antes do deploy de produção (M12), ou quando a primeira rota de negócio entrar (M2), o que vier primeiro |

### 7. Lacunas conhecidas

| Lacuna | Por quê | Onde está rastreado |
| --- | --- | --- |
| DAST não executado | A única rota é de leitura, sem entrada e sem autenticação; um scan agora não mediria nada útil | Perfil de stack ("DAST: a definir"); M12 |
| Sem HTTPS nem HSTS | Não há ambiente de produção | AD-013; M12 |
| Sem limite de requisições | Não há rota que aceite entrada; entra com o login | Especificação do M2 |
| O CI não sobe o compose | Um erro que só aparece na imagem (como a dependência `packaging` que faltava) não é pego pelo CI | ADR-007; M12 |
| O cabeçalho `Server: gunicorn` identifica o servidor | Informativo | M12, com a configuração do proxy de produção |
| Threat model | Previsto para o M2, quando entram dados pessoais e autenticação | [03-tasks](03-tasks.md), desvios do método |

### 8. Evidências

| Evidência | Onde |
| --- | --- |
| CI do backend verde (inclui pip-audit e as regras `S`) | Execução 43185410165 do workflow `backend`, branch `dev` |
| CI do site verde (inclui `npm audit`) | Execução 43185308390 do workflow `frontend`, branch `dev` |
| Negação por padrão | `backend/tests/test_errors.py::test_rota_sem_permissao_explicita_e_negada_por_padrao` |
| Erro sem detalhe interno | `backend/tests/test_errors.py::test_erro_inesperado_nao_expoe_mensagem_interna`, `backend/tests/test_health.py::test_health_responde_503_sem_expor_o_erro_quando_o_banco_cai` |
| ID de correlação recebido é validado | `backend/tests/test_request_id.py::test_request_id_recebido_malformado_e_substituido` |
| Sem segredo no repositório | `.env` ignorado pelo git; `.env.example` só com placeholders; a aplicação não inicia sem `DJANGO_SECRET_KEY` |

## 4. Relatório de vulnerabilidades — M2

| Campo | Valor |
| --- | --- |
| Projeto | Club Manager |
| Escopo | Feature `acesso/identidade-e-acesso`: módulos `acesso` e `auditoria`, base técnica, site |
| Data da execução | 2026-11-12 |
| Responsável | o dono do projeto |
| Ferramentas | SCA: pip-audit 2.10 e `npm audit` (npm 10). SAST: regras `S` do Ruff 0.17. DAST: não executado (ver lacunas). Revisão manual guiada pelo modelo de ameaças |
| Especificação | a feature do marco |
| Achados aceitos sem correção | Nenhum novo; os riscos aceitos estão em a seção 1 deste documento |

### 1. Contexto e escopo

O marco introduz autenticação, sessão, convites, dados pessoais e a trilha de auditoria. O modelo de ameaças
(`threat-model.md`) foi escrito antes da implementação e listou as mitigações planejadas; este relatório confere se
elas existem e têm teste.

### 2. Frentes

| Frente | Ferramenta | O que cobre | Mapeamento OWASP |
| --- | --- | --- | --- |
| SCA | pip-audit; `npm audit --audit-level=high` | Dependências diretas e transitivas | A06 |
| SAST | Regras `S` do Ruff | Padrões inseguros no código Python | A02, A03, A05 |
| Revisão por ameaça | Testes automatizados e inspeção do sistema no ar | Autenticação, sessão, autorização, enumeração, abuso | A01, A04, A05, A07 |
| DAST | Não executado | — | — |

### 3. Como reproduzir

```text
# em backend/
uv run pip-audit
uv run ruff check --select S .
uv run pytest acesso auditoria

# em frontend/
npm audit --audit-level=high

# com o sistema no ar
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/v1/schema/     # 401
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/v1/acesso/usuarios/   # 401
```

### 4. Resultado: inicial → correções → final

| Frente | Severidade | Inicial | Final | Variação |
| --- | --- | --- | --- | --- |
| SCA backend e site | Crítica, alta, média | 0 | 0 | — |
| SAST | Qualquer | 0 | 0 | — |
| Revisão por ameaça | Baixa | 1 | 0 | −1 |
| Dívida anterior (TD-001) | Baixa | 1 aberta | 0 | −1 |

### 5. Achados corrigidos

#### ACE-01 — Falha de CSRF respondia fora do envelope de erro

| Campo | Valor |
| --- | --- |
| Ferramenta | Validação final contra o sistema no ar |
| Componente afetado | Configuração do Django (`CSRF_FAILURE_VIEW`) |
| Severidade | Baixa |
| Impacto e risco | A resposta era a página HTML padrão do Django, que identifica o framework e quebrava o cliente da API. Não havia vazamento de dado |
| Ação realizada | `kernel.errors.csrf_failure` devolve o envelope, com o código `CSRF_FAILED` |
| Regressão | `acesso/tests/test_sessao.py::test_falha_de_csrf_responde_no_envelope_de_erro`; suíte com 217 testes |

#### TD-001 — Contrato e documentação da API abertos e dependentes de CDN

Encerrada no checkpoint 9: as rotas exigem admin logado e os arquivos vêm da própria imagem. Evidência: 401 sem
sessão em `/api/v1/schema/` e `/api/v1/docs/`; `acesso/tests/test_documentacao.py`.

### 6. Mitigações do modelo de ameaças: situação

| Ameaça | Mitigação | Evidência |
| --- | --- | --- |
| Adivinhação de senha | 5 erros em 15 minutos por conta; limite por IP; política de senha | `test_ca22…`, `test_dados_invalidos_sao_recusados…` |
| Enumeração de contas | Respostas iguais; hash calculado mesmo sem conta | `test_ca21…`, `test_ca24…`, `test_reenvio_responde_igual…` |
| Convite vazado ou reusado | Uso único com bloqueio da linha, 24 horas, revogação, só o hash guardado | `test_ca05…` a `test_ca07…`, `test_token_do_convite_nao_e_guardado…` |
| CSRF e roubo de cookie | `HttpOnly`, `SameSite=Lax`, `Secure` fora de depuração; CSRF em toda escrita | `test_login_sem_token_csrf_e_recusado`, `test_cookie_de_sessao…` |
| Fixação de sessão | Chave nova no login | `test_login_troca_a_chave_da_sessao` |
| Acesso de usuário desativado | Sessão conferida a cada requisição | `test_ca28…`, `test_usuario_desativado_perde_a_sessao…` |
| Elevação de privilégio | Admin exigido na rota e no serviço; ninguém altera a si mesmo | `test_ca32…`, `test_servico_recusa…`, `test_ca30…` |
| Alteração da auditoria | Modelo e gatilho no banco recusam alterar e apagar | `auditoria/tests/test_registro.py` |
| Token do Google forjado | Assinatura, público-alvo, validade e e-mail verificado | `test_adapter_real_…` |
| Token em fila ou log | Tarefas recebem só IDs | `test_o_token_nunca_passa_pela_fila` |

### 7. Lacunas conhecidas

| Lacuna | Por quê | Onde está rastreado |
| --- | --- | --- |
| DAST não executado | Decidido avaliar no M12, com o sistema completo e autenticado | Perfil de stack; M12 |
| Sem HTTPS, HSTS, SPF e DKIM | Não há ambiente de produção | AD-012, AD-013; M12 |
| `TRUNCATE` na tabela de auditoria não é barrado pelo gatilho | Exige ser dono da tabela; depende do usuário de banco de produção | M12 |
| Dados pessoais em claro no banco | Cifragem de disco e de backup é decisão de infraestrutura | Modelo de ameaças; M12 |
| Login com Google não exercitado com uma conta real | Depende do ID de cliente do dono | guia de configuração do Google |
| Roteiro não percorrido pelo navegador | Validação feita pela API | roteiro de teste manual |

### 8. Evidências

| Evidência | Onde |
| --- | --- |
| CI verde no pull request | PR #1, workflows `backend` e `frontend`, em 2026-11-13 |
| Verificação completa | `implementation-plan.md`, checkpoint 11 |
| Revisão de segurança por item | `implementation-plan.md`, seção "Revisão de segurança" |

## 5. Relatório de vulnerabilidades — M6

| Campo | Valor |
| --- | --- |
| Projeto | Club Manager |
| Escopo | Feature `financeiro/cobrancas-e-recebimentos`: `kernel/anexos.py`, `acesso.UsuarioDesativado`, módulo `financeiro`, site |
| Data da execução | 2026-11-14 |
| Responsável | o dono do projeto |
| Ferramentas | SCA: pip-audit e `npm audit --audit-level=high`. SAST: regras `S` do Ruff. DAST: não executado (M12). Revisão por ameaça e inspeção nos contêineres Docker Compose |
| Especificação | RNF-07; [01-spec](01-spec.md) § 1 (M6); modelo de ameaças § 1 (M6) |
| Achados aceitos sem correção | Risco 3 pendente de teste manual do dono em dois aplicativos bancários reais |

### 1. Contexto e escopo

O M6 introduz o fluxo financeiro de entradas e cobranças: cadastros de categorias e chaves Pix (incluindo
chave CPF do clube com aviso LGPD), geração local de BR Code EMV e QR Code SVG, upload e armazenamento de
comprovantes em `STORAGES["default"]` (`media-data`, ADR-014), validação/rejeição segregada, emissão de
recibos PDF 1.4 determinísticos, recorrências, suspensões, inadimplência/renegociação e entradas sem devedor.

### 2. Frentes

| Frente | Ferramenta | O que cobre | Mapeamento OWASP |
| --- | --- | --- | --- |
| SCA | `pip-audit`; `npm audit --audit-level=high` | Dependências Python e Node | A06 |
| SAST | `ruff check --select S .` | Padrões inseguros em Python | A02, A03, A05 |
| Revisão por ameaça e contêineres | 1181 testes backend (94,32%), 173 testes site, fluxo ponta a ponta no Compose | Controle de acesso a anexos, segregação de funções, upload, enumeração, XSS, UIDs e cabeçalhos | A01, A03, A04, A05 |
| DAST | Não executado | — | — |

### 3. Como reproduzir

```text
# em backend/
uv run pip-audit
uv run ruff check --select S .
uv run poe verify

# em frontend/
npm audit --audit-level=high
npm run verify

# com o sistema no ar (na raiz)
docker compose up -d --build
docker compose exec -T api id
docker compose exec -T web id
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/v1/health/     # 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/v1/schema/     # 401
```

### 4. Resultado: inicial → correções → final

| Frente | Severidade | Inicial | Final | Variação |
| --- | --- | --- | --- | --- |
| SCA backend (`pip-audit`) | Qualquer | 0 | 0 | — |
| SCA site (`npm audit --audit-level=high`) | Crítica, alta | 0 | 0 | — |
| SAST (`ruff --select S`) | Qualquer | 0 | 0 | — |
| Revisão por ameaça | Média, baixa | 0 novos abertos | 0 | — |

### 5. Controles verificados e lacunas

| Controle ou lacuna | Resultado / Situação | Evidência |
| --- | --- | --- |
| Acesso a comprovantes (RNF-07, CA-18) | Download com `X-Content-Type-Options: nosniff` e `Cache-Control: private, no-store` para autorizado; `403` para outro diretor sem cargo | Teste nos contêineres + `test_parte2_pagamentos.py`, `test_parte6_entradas_e_public.py` |
| Validação de uploads (CA-20) | Limite de 5 MB e magic bytes (PDF, PNG, JPEG, WebP); chave opaca `<contexto>/<uuid7>.<ext>` | `kernel/tests/test_anexos.py` |
| Segregação de funções (RN-012) | Devedor/registrador impedido de validar/decidir (inclusive acesso total); paridade `acoes` ↔ rotas verde | `test_parte6_entradas_e_public.py` |
| Contêineres e isolamento de dados | `api`/`worker` em `uid=10001(app)`, `web` em `uid=10001(web)`, portas `db`/`redis` em `127.0.0.1`, volume `media-data` em `/app/media` | Execução direta no Compose rebuildado |
| DAST e HTTPS/HSTS | Avaliar e configurar no M12 | `02-plan.md` (D-03, M12) |
| BR Code em aplicativos bancários reais (Risco 3) | Payload EMV + CRC16 conferido nos testes; validação em apps reais pendente do dono | `02-plan.md` § 6, `03-tasks.md` |

### 6. Evidências

| Evidência | Onde |
| --- | --- |
| Verificação do backend (`1181` testes, cobertura `94.32%`) | `uv run poe verify`, `uv run ruff check --select S .`, `uv run pip-audit` |
| Verificação do site (`173` testes, cobertura global `88.38%` Stmts / `90.37%` Lines) | `npm run verify`, `npm audit --audit-level=high` |
| Exercício nos contêineres e Mailpit | `docker compose up -d --build` (saúde, Pix, recorrência idempotente, e-mail, comprovante e recibo `%PDF-1.4`) |

## 6. Relatório de vulnerabilidades — M7

| Campo | Valor |
| --- | --- |
| Projeto | Club Manager |
| Escopo | Feature `financeiro/gastos-e-prestacao-de-contas`: `permissoes.public`, `aprovacoes.public`, domínio/serviços/rotas M7 de `financeiro`, rotina diária e telas React de gastos/saídas/estorno |
| Data da execução | 2026-11-15 |
| Responsável | o dono do projeto |
| Ferramentas | SCA: `pip-audit` e `npm audit --audit-level=high`. SAST: `ruff check --select S .`, `mypy .`, `oxlint --deny-warnings`, `tsc -b`, `lint-imports`. DAST: não executado (M12). Revisão por ameaça e fluxo ponta a ponta HTTP nos contêineres Docker Compose |
| Especificação | RNF-07; [01-spec](01-spec.md) § 1 (M7); `ADR-013`; modelo de ameaças § 1 (M7) |
| Achados aceitos sem correção | Nenhum achado novo em aberto no M7 (mantidos apenas DAST, HTTPS/HSTS, SPF/DKIM e cifragem em disco previstos no M12, além do risco 3 do M6) |

### 1. Contexto e escopo

O M7 entrega o fluxo completo de saídas financeiras e desfazimento controlado: upload de cotações (`Cotacao`),
abertura estruturada de gastos (`financeiro.gasto` no motor `aprovacoes`), visão consolidada do caixa durante a
análise e no painel de saídas, criação única de `Saida` na aprovação, envio de recurso com comprovante e trava
pós-envio (`EM_EXECUCAO`), prestação de contas, devolução de prestação com motivo, devolução de sobra ligada
a `Entrada` (mantendo `INV-ENT-04`), pedido e envio de complemento, liquidação com encerramento no motor,
lembretes idempotentes de 5 e 7 dias e estorno imutável (`Estorno`, `ADR-013`) de saída liquidada, entrada
validada ou cobrança paga.

### 2. Frentes

| Frente | Ferramenta | O que cobre | Mapeamento OWASP |
| --- | --- | --- | --- |
| SCA | `pip-audit`; `npm audit --audit-level=high` | Dependências Python e Node | A06 |
| SAST e arquitetura | `ruff check --select S .`, `mypy .`, `lint-imports`, `oxlint --deny-warnings`, `tsc -b` | Padrões inseguros em Python/TS, tipagem estrita e fronteiras entre contextos | A01, A02, A03, A05 |
| Revisão por ameaça e contêineres | `1202` testes backend (`93,02%`), `186` testes site (`89,51%` Stmts / `83,44%` Branch), fluxo HTTP ponta a ponta sobre Caddy + Gunicorn + PostgreSQL + Redis + Celery Worker | Segregação de funções, sigilo de anexos (`INV-ENT-04`, `P6`), trava pós-envio, unicidade de estorno, cabeçalhos, esquema OpenAPI autenticado (`401`) e UIDs sem privilégio (`10001`) | A01, A03, A04, A05 |
| DAST | Não executado | — | — |

### 3. Como reproduzir

```text
# em backend/
uv run poe audit
uv run ruff check --select S .
uv run poe verify

# em frontend/
npm audit --audit-level=high
npm run verify

# com o sistema no ar (na raiz)
docker compose up -d --build --wait
docker compose exec -T api id
docker compose exec -T web id
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/v1/health/     # 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/v1/schema/     # 401
```

### 4. Resultado: inicial → correções → final

| Frente | Severidade | Inicial | Final | Variação |
| --- | --- | --- | --- | --- |
| SCA backend (`pip-audit`) | Qualquer | 0 | 0 | — |
| SCA site (`npm audit --audit-level=high`) | Crítica, alta | 0 | 0 | — |
| SAST (`ruff --select S`, `mypy`, `oxlint`) | Qualquer | 0 | 0 | — |
| Revisão por ameaça e fluxo E2E | Média, baixa | 0 novos abertos | 0 | — |

### 5. Controles verificados e lacunas

| Controle ou lacuna | Resultado / Situação | Evidência |
| --- | --- | --- |
| Anexos de gasto (`P6`) e sigilo de devolução (`INV-ENT-04`) | Cotação e comprovante de envio com `nosniff` e `private, no-store`; `403` para diretor sem cargo e `403` para titular com `saidas.liquidar` sem `entradas.validar` no comprovante da devolução | E2E nos contêineres + `test_parte10_saidas_http.py` |
| Segregação e paridade `acoes` ↔ rotas (`RN-012`) | `SO_O_SOLICITANTE`, `SOLICITANTE_NAO_LIQUIDA`, `REGISTRADOR_NAO_VALIDA` e restrição inicial de `financeiro.estornar` conferidas no domínio, serviço e rota (inclusive com `acesso.total`) | `test_parte7_saidas_dominio.py`, `test_parte8_saidas_servicos.py`, `test_parte10_saidas_http.py` |
| Imutabilidade pós-liquidação e estorno (`ADR-013`) | `Estorno` com `OneToOneField(PROTECT)`, `CheckConstraint`, bloqueio de alteração/exclusão em modelo e impossibilidade de estornar devolução de saída liquidada | `test_parte9_estornos_e_caixa.py`, `test_migracoes.py` e E2E |
| Contêineres, migração e worker assíncrono | `api` e `worker` em `uid=10001(app)`, `web` em `uid=10001(web)`, migração `0003` aplicada no boot, `/api/v1/schema/` retornando `401` sem sessão e tarefas de e-mail executadas pelo Celery via Mailpit | `docker compose up -d --build --wait`, logs `api`/`worker` |
| DAST, HTTPS/HSTS, SPF/DKIM e cifragem de disco | Previsto para o M12 com ambiente de produção | [02-plan](02-plan.md) § 6 (D-03, M12) |

### 6. Evidências

| Evidência | Onde |
| --- | --- |
| Verificação do backend (`1202` testes, cobertura `93,02%`, `lint-imports` `1 kept / 0 broken`) | `uv run poe verify`, `uv run ruff check --select S .`, `uv run poe audit` |
| Verificação do site (`186` testes, cobertura global `89,51%` Stmts / `83,44%` Branch / `91,46%` Lines) | `npm run verify`, `npm audit --audit-level=high` |
| Fluxo ponta a ponta real no Compose | `docker compose up -d --build --wait` (web `200`, health `200`, schema `401`, cotação → gasto → aprovação → caixa comprometido → envio → prestação → devolução `INV-ENT-04` `403`/`200` → validação → liquidação → estorno → caixa zerado → worker e-mails `succeeded`) |
