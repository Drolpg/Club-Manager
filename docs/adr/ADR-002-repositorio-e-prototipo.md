# ADR 002: Reaproveitar o repositório e isolar o protótipo

**Status:** Accepted  
**Date:** 2026-11-11  
**Deciders:** Leandro Nascimento  
**Resolve:** AD-002

---

## Contexto

O enunciado (seção 16) pede que o M0 decida entre criar um repositório novo ou reaproveitar o atual, o que for mais
barato, e que todos os resquícios do protótipo sejam removidos até o M12. O repositório `Drolpg/Club-Manager` tinha
só o commit inicial; o protótipo estava na pasta de trabalho, sem nunca ter sido commitado. O protótipo ainda serve
para conferir funcionalidades esquecidas.

## Considered Options

### Option 1: Repositório novo

Histórico limpo por definição. Custa criar o repositório, refazer remoto e autenticação, e manter duas pastas.

### Option 2: Reaproveitar este repositório, com o protótipo numa pasta ignorada ✅ SELECIONADA

O histórico já é limpo (um commit, sem código do protótipo) e o remoto já existe. O protótipo continua disponível
para consulta sem nunca entrar no histórico.

### Option 3: Reaproveitar e apagar o protótipo agora

O mais simples, mas perde a consulta que o enunciado permite até o M12.

## Decision

O projeto novo é construído neste repositório. O protótipo foi movido para `_prototipo/`, que está no `.gitignore`:
`backend/`, `frontend/`, `images/`, `docker-compose.yml` e os dois documentos antigos de `docs/`.

## Consequências

### Positivas ✅

- Nenhum custo de migração; o remoto e o tracker continuam os mesmos.
- O protótipo não contamina o histórico nem a estrutura nova.

### Negativas ❌

- `_prototipo/` existe só na máquina do dono, sem backup pelo git.
- `venv/` e `notas-internas/` (já ignorados antes) continuam na raiz e não foram tocados.

### Pendências

- No M12: apagar `_prototipo/` e conferir `venv/` e `notas-internas/` (critério de aceite do E13).

---

**Last Updated:** 2026-11-11  
**Decision Maker:** Leandro Nascimento  
**Status:** Accepted
