# ADR 005: Site em React com Vite e TypeScript, como aplicação de página única

**Status:** Accepted  
**Date:** 2026-11-11  
**Deciders:** Leandro Nascimento  
**Resolve:** AD-004

---

## Contexto

O enunciado deixa o frontend livre, com React como direção provável. O site fica todo atrás de login, o que dispensa
indexação por buscadores. A instância única tem pouca memória (RNF-02), e um app mobile virá depois (AD-017).

## Considered Options

### Option 1: React com Vite e TypeScript, SPA ✅ SELECIONADA

O site é compilado para arquivos estáticos, servidos pelo mesmo proxy que repassa as chamadas à API. Não há processo
Node em produção.

### Option 2: Next.js

Renderização no servidor e rotas prontas. Exige um processo Node rodando na instância, e o ganho principal (SEO e
primeira carga pública) não se aplica a um sistema fechado.

## Decision

React 19 com Vite 8 e TypeScript 7, como SPA. Em produção, um contêiner com Caddy serve os arquivos e repassa `/api`
para a API. Testes com Vitest e Testing Library; lint com oxlint, que é o padrão do gerador do Vite.

O site não contém regra de negócio (RNF-01): chama a API e mostra o resultado. Biblioteca de componentes, roteamento
e estratégia de temas são decididos na primeira feature que precisar deles (M2 e M11).

## Consequências

### Positivas ✅

- O site custa cerca de 12 MB de memória em produção (medido em 2026-11-11).
- O conhecimento de React e TypeScript é reaproveitado se o app for em React Native.

### Negativas ❌

- Sem renderização no servidor; a primeira carga depende do JavaScript.
- Roteamento e estado ficam por conta de bibliotecas a escolher.

---

**Last Updated:** 2026-11-11  
**Decision Maker:** Leandro Nascimento  
**Status:** Accepted
