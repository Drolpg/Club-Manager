# ADR 004: Backend em Django com DRF e PostgreSQL

**Status:** Accepted  
**Date:** 2026-11-11  
**Deciders:** Leandro Nascimento  
**Resolve:** AD-003

---

## Contexto

O enunciado pede backend em Python, com Django (preferência, por familiaridade) ou FastAPI, e PostgreSQL. A ADR-001
supõe um framework com ORM, migrações e abstrações prontas de e-mail e de armazenamento, que servem de ports.

## Considered Options

### Option 1: Django com Django Ninja

Camada de API tipada com Pydantic e contrato gerado sem biblioteca extra. Era a recomendação do agente: a camada de API
fica fina por natureza. Ecossistema menor e desconhecido do dono.

### Option 2: Django com Django REST Framework ✅ SELECIONADA

É o que o dono conhece e o que o protótipo usava. É o mais maduro, com mais material e mais bibliotecas. O contrato
OpenAPI vem do drf-spectacular.

### Option 3: FastAPI

Tipado e leve, mas ORM, migrações, autenticação, e-mail e armazenamento seriam montados à mão, e a ADR-001 teria de
ser revista.

## Decision

Django 6.1 com Django REST Framework 3.18, PostgreSQL 18 e Python 3.14. Contrato da API gerado pelo drf-spectacular.

| Escolha | Motivo |
| --- | --- |
| Django | ORM com migrações reversíveis, hash de senha, e as abstrações de e-mail e de arquivos que servem de ports |
| DRF | Familiaridade do dono, que vai manter o sistema com apoio de IA |
| PostgreSQL | Preferência do enunciado; um banco só, usado também nos testes |
| Python 3.14 | Versão instalada e suportada por todas as dependências em 2026-11 |

Para o DRF não puxar regra para a camada de API, valem estas restrições, que entram no `AGENTS.md`:

- Views e serializers só validam a entrada, chamam um serviço e formatam a saída.
- Não usar `ModelViewSet` nem `ModelSerializer` que gravem direto no modelo: toda escrita passa por um serviço.
- Um serializer de saída nunca é o modelo exposto como está; os campos são declarados.

## Consequências

### Positivas ✅

- O dono lê e mantém o código sem aprender um framework novo.
- Bibliotecas maduras para autenticação, filtros e documentação.

### Negativas ❌

- O DRF facilita atalhos (viewsets sobre o modelo) que violam a regra de serviços; a disciplina depende das
  restrições acima e da revisão.
- Tipagem mais fraca que a do Pydantic na borda; compensada com mypy, django-stubs e djangorestframework-stubs.

### Gatilhos de reavaliação

| Gatilho | Mudança esperada |
| --- | --- |
| Regras de negócio aparecem repetidamente em serializers ou views nas revisões | Acrescentar uma verificação automática, ou rever a camada de API |

---

**Last Updated:** 2026-11-11  
**Decision Maker:** Leandro Nascimento  
**Status:** Accepted
