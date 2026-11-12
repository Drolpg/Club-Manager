# TD 001: Contrato e documentação da API abertos e dependentes de CDN

**Status:** Accepted  
**Date:** 2026-11-12  
**Reported by:** Revisão de segurança do M1  
**Affected areas:** `backend/config` (rotas `/api/v1/schema/` e `/api/v1/docs/`)  
**Related decisions:** ADR-004; AD-013

---

## Contexto

O esqueleto serve o contrato OpenAPI e a página do Swagger sem autenticação, porque ainda não existe autenticação
(M2). A página do Swagger, na configuração padrão do drf-spectacular, carrega os arquivos dela de uma CDN pública.

## A dívida

- Qualquer pessoa que alcance a API lê o contrato completo.
- A página de documentação depende de um terceiro para carregar e executa script vindo dele.

## Evidência

- `backend/config/settings.py`: `SERVE_PERMISSIONS` com `AllowAny`.
- `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/v1/schema/` devolve 200 sem credencial.

## Impacto se não for pago

Com as rotas de negócio no ar, o contrato aberto facilita o mapeamento do sistema por quem não deveria. A CDN impede
uma política de conteúdo (CSP) estrita no domínio da API.

## Opções de encaminhamento

### Opção A: Exigir login para o contrato e a documentação

Troca a permissão das duas rotas quando a autenticação existir. Esforço pequeno. O contrato deixa de servir a quem
ainda não tem conta, o que não é um caso de uso aqui.

### Opção B: Servir a documentação só em desenvolvimento

Desliga as duas rotas quando `DJANGO_DEBUG=0`. Esforço pequeno. Perde a consulta ao contrato em produção.

### Opção C: Empacotar os arquivos do Swagger na imagem

Biblioteca auxiliar do drf-spectacular que serve os arquivos localmente. Resolve só a dependência da CDN; combina com
A ou B.

## Recomendação

Opção A com a C, na especificação do M2, quando a autenticação for definida (AD-006).

## Custo de não decidir agora

Nenhum enquanto o sistema não estiver publicado e só existir a rota de saúde. Não fazer deploy de produção com esta
dívida aberta.

---

**Last Updated:** 2026-11-12  
**Status:** Accepted
