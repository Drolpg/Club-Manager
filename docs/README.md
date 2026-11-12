# Documentação

Índice de toda a documentação, organizado por quem está lendo. Cada documento responde a uma pergunta; se duas páginas
parecerem dizer a mesma coisa, a mais específica é a fonte da verdade e a outra só aponta para ela.

Documentos marcados com "(rito N)" ou "(Mn)" ainda não existem: são criados no rito ou no marco indicado.

## Para avaliar o projeto

| Documento | Responde |
| --- | --- |
| [Enunciado da fase 1](challenge/phase-1.md) | O que foi pedido, com entregáveis e restrições rastreáveis |
| [Charter](project-charter.md) | Que problema o projeto resolve e como saberemos que deu certo |
| [Avaliação de arquitetura](architecture/assessment.md) | Que estilo o problema pede, o que fica de fora e quando rever |
| [Visão geral da arquitetura](architecture/overview.md) | Como o sistema é dividido e onde ele roda |
| [Estrutura do projeto](architecture/project-structure.md) | Onde fica cada coisa e quem pode importar quem |
| [Perfil de stack](architecture/stack-profile.md) | Que ferramenta cuida de cada preocupação, com versão e comando |
| [Domínio](domain/) | Descoberta, contextos, context map, glossário, aggregates e modelo |
| [Requisitos](requirements/requirements.md) | O que o sistema faz, com IDs rastreáveis |
| [Épicos](requirements/epics.md) | Como os requisitos se agrupam em marcos e do que cada um depende |
| [Decisões arquiteturais](adr/) | Por que cada escolha estrutural foi feita |
| [Segurança](security/) | Relatório de cada marco, [modelo de ameaças](security/threat-model.md) e [avaliação de LGPD](security/lgpd.md) |

## Para rodar o sistema

| Documento | Tipo | Responde |
| --- | --- | --- |
| [setup/local.md](setup/local.md) | Tutorial | Como subir o sistema localmente e rodar os testes |
| [setup/configuration.md](setup/configuration.md) | Referência | Que variáveis existem e de onde vem cada valor |
| `operations/` (M12) | Guia | Deploy, backup e rollback na instância única |

## Para consumir a API

| Documento | Responde |
| --- | --- |
| `/api/v1/docs/` no sistema em execução | O contrato gerado pela aplicação, navegável |
| `api/README.md` (M2) | Autenticação e recursos disponíveis |

## Para contribuir

| Documento | Responde |
| --- | --- |
| [AGENTS.md](../AGENTS.md) | Regras do projeto: arquitetura, SDD, testes, segurança, Git |
| [Método](method.md) | Nível, estado dos ritos e dos marcos, mapa de artefatos |
| [Features](features/README.md) | O fluxo SDD e as specs de cada marco |
| [Registro de decisões](decision-register.md) | Decisões em aberto e resolvidas (AD-NNN) |
| [RFCs](rfc/) | Propostas discutidas antes da implementação |
| [Auditorias](audits/) | Onde documentos e código divergiam ao fim de cada marco, e o que foi feito |
| [Dívida técnica](tech-debt/) | Desvios conhecidos, com motivo e encaminhamento |
| [Definition of Ready e Done](requirements/definition-of-ready-done.md) | Quando uma feature pode começar e quando termina |
| [Backlog](requirements/backlog.md) | Ideias deixadas fora do escopo atual, incluindo as etapas futuras |

## Fora deste índice

O protótipo antigo, com os documentos dele, está em `_prototipo/`, fora do git (ADR-002). Serve só de consulta e é
apagado no M12.

## Como manter esta documentação

- **Um documento, uma pergunta.** Conteúdo novo entra no documento cuja pergunta ele responde; se nenhum servir, crie
  um arquivo novo e adicione uma linha aqui.
- **Apontar em vez de copiar.** O contrato da API é o gerado pela aplicação; variáveis vivem no documento de
  configuração; decisões vivem nas ADRs.
- **Comandos testados.** Todo comando de um guia foi executado; registre a saída esperada e como verificar.
- **Idioma:** texto em pt-BR; nomes de código, arquivos, endpoints e status na forma original.
