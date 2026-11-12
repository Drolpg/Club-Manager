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
| Visão geral da arquitetura, `architecture/overview.md` (rito 7) | Como o sistema é dividido e onde ele roda |
| Domínio, `domain/` (ritos 3 a 5, se o estilo pedir) | Contextos, context map e linguagem ubíqua |
| Requisitos, `requirements/requirements.md` (rito 6) | O que o sistema faz, com IDs rastreáveis |
| [Decisões arquiteturais](adr/) | Por que cada escolha estrutural foi feita |
| Segurança, `security/` (M2 em diante) | Threat model, achados de segurança e o tratamento de cada um |

## Para rodar o sistema

| Documento | Tipo | Responde |
| --- | --- | --- |
| `setup/local.md` (M1) | Tutorial | Como subir o sistema localmente |
| `setup/configuration.md` (M1) | Referência | Que variáveis existem e de onde vem cada valor |
| `operations/` (M12) | Guia | Deploy, backup e rollback na instância única |

## Para consumir a API

| Documento | Responde |
| --- | --- |
| `api/README.md` (M2) | Autenticação e recursos disponíveis |

## Para contribuir

| Documento | Responde |
| --- | --- |
| [AGENTS.md](../AGENTS.md) | Regras do projeto: arquitetura, SDD, testes, segurança, Git |
| [Método](method.md) | Nível, estado dos ritos e dos marcos, mapa de artefatos |
| Features, `features/` (rito 6 em diante) | O fluxo SDD e as specs de cada marco |
| [Registro de decisões](decision-register.md) | Decisões em aberto e resolvidas (AD-NNN) |
| [RFCs](rfc/) | Propostas discutidas antes da implementação |
| [Dívida técnica](tech-debt/) | Desvios conhecidos, com motivo e encaminhamento |
| Backlog, `requirements/backlog.md` (rito 6) | Ideias deixadas fora do escopo atual, incluindo as etapas futuras |

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
