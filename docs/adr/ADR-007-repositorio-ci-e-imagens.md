# ADR 007: Um repositório, CI por pasta e as mesmas imagens em todo lugar

**Status:** Accepted  
**Date:** 2026-11-11  
**Deciders:** Leandro Nascimento  
**Resolve em parte:** AD-013 (CI e imagens; o deploy na AWS fica para o M12)

---

## Contexto

O enunciado pede tudo em contêineres, com as mesmas imagens em desenvolvimento e produção (RNF-03), CI no GitHub
Actions dentro do plano gratuito (RNF-04), só os ambientes local e produção (RNF-05), e tudo numa instância (RNF-02).

## Considered Options

### Option 1: Um repositório, com `backend/` e `frontend/`, e um workflow por pasta ✅ SELECIONADA

Um lugar só para specs, código e decisões. Cada workflow roda só quando a sua pasta muda.

### Option 2: Dois repositórios

Separa os ciclos, mas duplica convenções e specs, e uma feature passa a exigir dois PRs. Sem ganho para uma pessoa.

### Option 3: Um workflow único que roda tudo sempre

Mais simples de ler, mas gasta minutos do plano gratuito rodando o backend quando só o site mudou.

## Decision

Adotada a **Option 1**.

| Decisão | Detalhe |
| --- | --- |
| Estrutura | `backend/` (API e worker), `frontend/` (site), `docs/`, `compose.yaml` na raiz |
| Imagens | Duas: `club-manager-api` (API e worker, com comandos diferentes) e `club-manager-web` (site compilado mais proxy). As mesmas em desenvolvimento e em produção |
| Subir localmente | `docker compose up --build`; o `compose.override.yaml` só expõe portas para o desenvolvimento |
| CI | Um workflow por pasta, com filtro de caminho, cache de dependências e cancelamento da execução anterior no mesmo ramo |
| O que o CI verifica | Backend: formato, lint, tipos, fronteiras de módulo, migrações pendentes, testes com PostgreSQL real, cobertura e vulnerabilidades. Site: lint, tipos, testes com cobertura, build e vulnerabilidades |
| Configuração | Só por variável de ambiente; `.env` fora do git, `.env.example` versionado; sem chave nem senha padrão |
| Verificação completa | `uv run poe verify` no backend e `npm run verify` no site: os mesmos comandos na máquina e no CI |

Ficam para o M12, com o restante da AD-013: publicação das imagens num registro, deploy na instância, HTTPS, backup e
rollback.

## Consequências

### Positivas ✅

- Memória medida em repouso, com tudo no ar (2026-11-11): API 117 MB, worker 144 MB, banco 46 MB, Redis 12 MB, site
  12 MB; total perto de 330 MB. Cabe numa instância de 1 GB, com folga para crescer.
- O que passa na máquina passa no CI, porque o comando é o mesmo.

### Negativas ❌

- A medição é do esqueleto vazio; o consumo sobe com as features e precisa ser medido de novo no M12.
- Não há teste automático do `compose` no CI; um erro de imagem (como dependência faltando só em produção) só aparece
  ao subir localmente. Entra no M12, com os testes de ponta a ponta.

---

**Last Updated:** 2026-11-12  
**Decision Maker:** Leandro Nascimento  
**Status:** Accepted
