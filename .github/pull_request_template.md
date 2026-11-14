## Resumo

<!-- Uma ou duas frases: o que muda e por quê. Marco, tarefa e requisitos: M2-T3 · RF-NN, RN-NN -->

## Tipo de mudança

- [ ] Funcionalidade nova (`feat`)
- [ ] Correção (`fix`)
- [ ] Refatoração, desempenho ou estilo (`refactor`, `perf`, `style`)
- [ ] Testes (`test`)
- [ ] Documentação (`docs`)
- [ ] Infraestrutura, CI ou dependências (`build`, `ci`, `chore`)

## Validação

- [ ] Testes escritos antes do código e passando
- [ ] `uv run poe verify` (backend) e `npm run verify` (site) verdes
- [ ] Teste de fronteira de módulos verde
- [ ] Sistema subido e fluxo percorrido, quando a mudança afeta o que roda nos contêineres

<!-- Comandos executados e resultado, ou o que não foi validado. -->

## Contratos e dados

- [ ] Contrato da API inalterado, ou atualizado em `docs/sdd/01-spec.md`
- [ ] Migrações reversíveis e `poe migrations-check` verde, se houve mudança de schema
- [ ] Spec, matriz requisito → teste e status em `docs/sdd/03-tasks.md` atualizados
- [ ] README e diagramas atualizados, se a arquitetura ou o uso mudaram

## Segurança e qualidade

- [ ] Li o diff inteiro como se fosse de outra pessoa; ele faz só o que a tarefa pede
- [ ] Nenhum elemento estrutural fora do estilo decidido (ports, camadas, abstrações novas)
- [ ] Sem segredos, dados pessoais ou logs sensíveis
- [ ] Toda rota de escrita declara quem pode, e a ação relevante gera auditoria
- [ ] Revisão de segurança registrada em `docs/sdd/04-seguranca.md`, se este merge fecha um marco
