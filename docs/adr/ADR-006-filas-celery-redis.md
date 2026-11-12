# ADR 006: Celery com Redis para filas e tarefas agendadas

**Status:** Accepted  
**Date:** 2026-11-11  
**Deciders:** Leandro Nascimento  
**Resolve:** AD-005

---

## Contexto

O sistema precisa de tarefas agendadas (cobranças recorrentes, atrasos, convocações, expiração de convites, aviso do
dia do evento) e de trabalho em segundo plano (e-mail, relatórios pesados). O enunciado prefere Celery com Redis e
pede para verificar se o conjunto cabe na instância única.

## Considered Options

### Option 1: Celery com Redis, um worker com o agendador embutido ✅ SELECIONADA

A preferência do enunciado. Maduro e conhecido. O agendador roda dentro do worker (`-B`), o que poupa um processo.

### Option 2: Fila no próprio PostgreSQL

Um serviço a menos. Bibliotecas menos maduras e fora da preferência do dono; a economia de memória do Redis é pequena
(cerca de 12 MB medidos).

## Decision

Celery 5.7 com Redis 8 como broker. Um único worker, com concorrência 1 e o agendador embutido. Sem backend de
resultados: as tarefas gravam o que fazem no banco.

| Regra | Motivo |
| --- | --- |
| Toda tarefa agendada é idempotente | O agendador pode disparar duas vezes (RNF-10) |
| Uma tarefa só chama um serviço do módulo dono; não contém regra | Mesma disciplina da camada de API |
| E-mail e trabalho pesado são enfileirados depois do commit | ADR-003 |
| Nos testes, as tarefas rodam na hora, sem worker | Testes determinísticos |
| Redis sem persistência em disco e com limite de memória | Ele é só fila; perder a fila num reinício é aceitável, porque as tarefas agendadas são refeitas no ciclo seguinte |

## Consequências

### Positivas ✅

- Memória medida em repouso (2026-11-11): worker com agendador 144 MB, Redis 12 MB.
- Separar o worker ou o Redis para outra máquina depois é trocar uma variável de ambiente.

### Negativas ❌

- O agendador embutido não permite mais de um worker; escalar exige separar o agendador.
- Uma tarefa enfileirada e ainda não executada se perde se o Redis reiniciar. Por isso nenhuma regra pode depender só
  de uma tarefa avulsa: o que importa fica registrado no banco e é reprocessado pela tarefa agendada.

### Gatilhos de reavaliação

| Gatilho | Mudança esperada |
| --- | --- |
| Precisa de mais de um worker | Agendador em processo próprio |
| A instância não comporta o conjunto | Reavaliar a fila no PostgreSQL, ou separar o worker |

---

**Last Updated:** 2026-11-11  
**Decision Maker:** Leandro Nascimento  
**Status:** Accepted
