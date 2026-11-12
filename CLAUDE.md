@AGENTS.md

# Contexto operacional compartilhado

Complementa o `AGENTS.md` sem repeti-lo. Vale para o projeto inteiro, não para uma tarefa ou uma pessoa.

## Método

Este projeto usa o plugin `sdd-method`. No início de cada sessão, leia `docs/method.md` (tipo de projeto, nível,
estilo de arquitetura, estado dos ritos e dos marcos). Para saber o próximo passo, use a skill
`sdd-method:guiding-projects`.

## Idioma

Responda e documente em pt-BR. Nomes técnicos e de código conforme o `AGENTS.md`.

## Git

Siga o `CONTRIBUTING.md`. Commits sem trailer de autoria de IA (nem `Co-Authored-By` de assistente): decisão do dono
em 2026-11-11. Se a ferramenta adicionar por padrão, remova antes de commitar.

## Numeração

ADR, RFC, TD, AD e requisitos (`RF-NN` funcional, `RNF-NN` não funcional, `RN-NN` regra de negócio): o próximo número
é o maior existente + 1. Cada requisito cita o ID de origem do enunciado (ex.: FIN-05). Nenhum documento registra
"próximo número livre".

## O que não vai para o git

Histórico bruto de decisões, depuração e evidências com dados de ambiente ficam em `docs/_local/`. O que virar
conhecimento permanente é promovido para a spec, o plano ou o README.

## Board e tracker

URLs e índice de frames estão em `docs/method.md`. Se a integração estiver indisponível ou sem cota, não invente
conteúdo: diga isso e peça o trecho ou um print.
