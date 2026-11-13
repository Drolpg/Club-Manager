# Modelo de ameaças

| Campo | Valor |
| --- | --- |
| Atualizado em | 2026-11-12 |
| Diagrama base | `docs/architecture/overview.md` § Containers |
| Responsável | Leandro Nascimento |
| Escopo desta versão | Marco M2: identidade e acesso. Cada marco seguinte acrescenta as ameaças do que entrega |

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
