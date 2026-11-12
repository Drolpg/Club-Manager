# ADR 003: Como os contextos se integram dentro do monólito

**Status:** Accepted  
**Date:** 2026-11-11  
**Deciders:** Leandro Nascimento  
**Relacionadas:** ADR-001 (estilo), `docs/domain/context-map.md`

---

## Contexto

O context map define quem conhece quem. Falta decidir como essas relações se materializam no código. Há dois casos:

1. Um contexto precisa de outro que está acima dele no mapa (Financeiro abre uma solicitação em Aprovações).
2. Um contexto precisa provocar algo em outro que está abaixo dele (Aprovações decide uma solicitação e o Financeiro
   precisa criar a saída; Identidade conclui um cadastro e o admin precisa ser avisado). Uma chamada direta criaria
   dependência circular.

A ADR-001 já descartou mensageria, barramento de eventos e outbox. Tudo roda num processo, com um banco.

## Considered Options

### Option 1: Só chamadas diretas, aceitando ciclos

O contexto de baixo importa o de cima quando precisa. É o mais simples de escrever, mas Aprovações passaria a
conhecer Financeiro e Eventos, e deixaria de ser um motor genérico.

### Option 2: Chamada direta para cima, evento em processo para baixo ✅ SELECIONADA

- **Para cima no mapa:** chamada de função à API pública do módulo, em processo.
- **Para baixo no mapa:** o contexto publica um evento de integração num despachante em processo; quem está abaixo
  registra um tratador. O tratador roda de forma síncrona, na mesma transação.
- **Efeitos fora do banco** (enviar e-mail, gerar PDF pesado) são enfileirados depois do commit.

### Option 3: Eventos assíncronos com outbox

Desacopla também no tempo e suporta extrair módulos para serviços. Exige tabela de outbox, entrega pelo menos uma vez
e tratadores idempotentes em todos os contextos. O custo não se paga com um processo e uma pessoa.

## Decision

Adotada a **Option 2**.

| Regra | Motivo |
| --- | --- |
| Um módulo chama a API pública dos módulos acima dele no context map, e nunca importa os de baixo | Dependências acíclicas, verificadas no CI |
| O despachante de eventos é uma função de registro e uma de publicação, em processo e síncrona | Não é um barramento: não há fila, broker nem entrega posterior |
| Os tratadores rodam na mesma transação de quem publicou | Aprovação e dinheiro não podem divergir; sem outbox, não há como garantir entrega depois do commit |
| Só existem eventos de integração onde o context map mostra uma seta para baixo | Hoje: decisões de solicitação (Aprovações → Financeiro, Eventos) e cadastro concluído (Identidade → Notificações) |
| E-mail e trabalho pesado são enfileirados depois do commit | Uma falha do provedor não desfaz a operação de negócio |
| A auditoria é chamada direta, na mesma transação | Toda ação relevante tem de ficar registrada junto com o efeito |

Esta decisão detalha um item da ADR-001: "barramento de eventos" continua fora; o despachante síncrono em processo é
o mecanismo de "notificação em processo e na mesma transação" que a ADR-001 já previa para o motor de aprovações,
estendido ao caso do cadastro concluído.

## Consequências

### Positivas ✅

- Aprovações continua sem conhecer quem o usa.
- Uma operação de negócio é uma transação: ou tudo acontece, ou nada.
- Nenhuma infraestrutura nova.

### Negativas ❌

- Um tratador com erro desfaz a operação de quem publicou; os tratadores precisam ser curtos e testados.
- Uma transação pode tocar mais de um aggregate (a solicitação e a saída), contra o princípio geral.
- Extrair um módulo para outro serviço exigiria trocar o despachante por mensageria.

### Gatilhos de reavaliação

| Gatilho | Mudança esperada |
| --- | --- |
| Um módulo precisa ser extraído para outro processo | Outbox e eventos assíncronos para as relações desse módulo |
| Os eventos de integração passam de um punhado, ou surgem tratadores encadeados | Rever o context map antes de acrescentar mais eventos |

---

**Last Updated:** 2026-11-11  
**Decision Maker:** Leandro Nascimento  
**Status:** Accepted
