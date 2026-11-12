# Definition of Ready e Definition of Done

Aprovado por Leandro Nascimento em 2026-11-11.

Adaptadas ao projeto solo: onde o método pede revisão por outra pessoa, vale a auto-revisão com a checklist do
`CONTRIBUTING.md` e a aprovação explícita do dono.

## Definition of Ready

Uma feature só começa quando:

- [ ] A regra de negócio está mapeada no domínio: nos contextos core, aggregate, invariantes e eventos identificados;
      nos de apoio, as regras (RN) identificadas.
- [ ] Os RFs estão no registro de requisitos, com status `Aprovado`.
- [ ] Os critérios de aceite estão escritos e são verificáveis.
- [ ] As dependências com outros marcos foram identificadas, e os contratos consumidos já existem (ver `epics.md`).
- [ ] As pendências do marco na seção 15 do enunciado, e as perguntas em aberto dos canvases que tocam a feature,
      foram decididas pelo dono ou postas explicitamente fora do escopo.
- [ ] O contrato de entrada e saída está definido, ao menos no nível conceitual.
- [ ] Não há decisão em aberto no registro que bloqueie este trabalho.
- [ ] A functional-spec e a technical-spec foram aprovadas pelo dono.

## Definition of Done

Uma feature só termina quando:

- [ ] A regra de negócio está no aggregate, nas funções de decisão ou no serviço; não vazou para a camada de API nem
      para o site.
- [ ] Toda invariante tocada tem teste; o fluxo do caso de uso tem teste de integração com o banco real.
- [ ] Toda ação relevante da feature gera registro de auditoria, e isso está testado.
- [ ] O comando de verificação completa passa e a cobertura de 80% foi respeitada.
- [ ] O teste de fronteira de módulos continua verde.
- [ ] A revisão de segurança foi registrada, sem achado crítico ou alto em aberto.
- [ ] O contrato da API e a documentação foram atualizados, se o contrato mudou.
- [ ] Os eventos de integração previstos são publicados e tratados corretamente.
- [ ] A checklist de auto-revisão foi conferida antes do merge.
- [ ] Os critérios de aceite foram validados, por teste automatizado ou manualmente com evidência, e o dono aprovou.
- [ ] Registro de requisitos (status e feature), riscos, decisões e a matriz requisito → teste refletem o que foi
      feito.

## Fim de marco

Além do Done de cada feature, um marco só termina quando:

- [ ] O critério de aceite do marco no enunciado (`docs/challenge/phase-1.md`) foi demonstrado.
- [ ] O relatório de segurança do marco foi escrito.
- [ ] A auditoria de coerência foi feita e as divergências foram resolvidas ou registradas.
- [ ] O dono aprovou o marco, com nome e data em `docs/method.md`.
- [ ] A `dev` foi integrada à `main` com autorização do dono, e a versão foi marcada com tag.
