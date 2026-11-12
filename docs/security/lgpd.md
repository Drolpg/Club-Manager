# Avaliação de LGPD

| Campo | Valor |
| --- | --- |
| Atualizado em | 2026-11-12 |
| Decisão | AD-015 |
| Escopo | Etapa 1: diretores de um clube |

> Isto é uma avaliação técnica feita por um agente de IA, não um parecer jurídico. Antes de o sistema ir para
> produção com dados reais, vale o dono conferir os pontos marcados como "a confirmar" com alguém que entenda de
> proteção de dados.

## Quem é quem

| Papel na LGPD | Quem |
| --- | --- |
| Controlador | O clube que usa o sistema (hoje, o time do dono) |
| Titulares | Os diretores cadastrados |
| Operador | Quem hospeda e mantém o sistema para o clube (hoje, o próprio dono) |

## Dados pessoais tratados

| Dado | Para quê | Marco |
| --- | --- | --- |
| Nome, nome de usuário | Identificar o diretor nas decisões e nos registros | M2 |
| E-mail | Login, verificação, recuperação de senha, notificações | M2 |
| Telefone | Contato entre diretores | M2 |
| Hash da senha, identificador do Google | Autenticação | M2 |
| Registros de auditoria (quem fez o quê) | Rastreabilidade das decisões do clube | M2 em diante |
| Cobranças, pagamentos e comprovantes do diretor | Controle financeiro do clube | M6, M7 |

O sistema não trata dado sensível (saúde, biometria, religião) e não coleta CPF (RN-003).

## Base legal (a confirmar)

| Tratamento | Base provável |
| --- | --- |
| Cadastro, login e contato | Execução do vínculo do diretor com o clube, ou legítimo interesse do clube |
| Registros financeiros e auditoria | Legítimo interesse do clube na prestação de contas; obrigação estatutária, se o clube tiver estatuto |
| Notificações por e-mail | As mesmas: fazem parte da função de diretor, e não de publicidade |

O sistema não pede consentimento porque nenhuma dessas bases depende dele. Se o clube passar a usar os dados para
outro fim (divulgação, por exemplo), isso muda.

## O que o sistema faz

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

## Tensão: "nada é apagado" e o direito de eliminação

O enunciado manda nunca apagar (AUD-04, RN-004, RN-014), para preservar o histórico financeiro. A LGPD permite
manter dados quando há base para isso, e a prestação de contas do clube é uma. Mas o nome e o contato de quem saiu
não precisam ficar visíveis para sempre.

Proposta, a decidir no M12 (fica registrada na AD-015): quando um diretor desativado pedir, o admin **anonimiza** o
cadastro. Nome, nome de usuário, e-mail e telefone são trocados por um marcador ("Diretor removido 0193"), e os
registros financeiros e de auditoria continuam íntegros, ligados ao mesmo ID. Nada é apagado, e o titular deixa de
ser identificável.

## Texto do aviso de privacidade (cadastro)

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

## Pendências

| Pendência | Quando |
| --- | --- |
| Confirmar a base legal com alguém qualificado | Antes da produção (M12) |
| Decidir a anonimização a pedido | M12 |
| Procedimento de incidente e contato do encarregado, se o clube precisar de um | M12 |
| Reavaliar quando entrarem comprovantes (M6), que podem conter dados bancários de terceiros | Especificação do M6 |
