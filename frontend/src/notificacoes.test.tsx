import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { ADMIN, DIRETOR, SEM_GOOGLE, erro, simularApi, type Chamada } from './test/api'

function abrir(caminho: string) {
  return render(
    <MemoryRouter initialEntries={[caminho]}>
      <App />
    </MemoryRouter>,
  )
}

const COMO_ADMIN = { 'GET /acesso/sessao/': { usuario: ADMIN }, ...SEM_GOOGLE }
const COMO_DIRETOR = { 'GET /acesso/sessao/': { usuario: DIRETOR }, ...SEM_GOOGLE }
const SEM_SESSAO = { 'GET /acesso/sessao/': { usuario: null }, ...SEM_GOOGLE }

const LIGADAS = { aviso_na_tela: true, email_informativos: true }
const SEM_AVISO = { aviso_na_tela: false, email_informativos: true }

function notificacao(n: number, extra: Record<string, unknown> = {}) {
  return {
    id: `n-${n}`,
    tipo: 'teste.fato',
    pede_acao: false,
    titulo: `Título ${n}`,
    texto: `Texto ${n}`,
    caminho: '/preferencias',
    criada_em: '2026-11-13T10:00:00-03:00',
    lida_em: null,
    ...extra,
  }
}

function resumo(naoLidas: number, maisRecenteId: string | null) {
  return { nao_lidas: naoLidas, mais_recente_id: maisRecenteId }
}

/** Devolve uma resposta diferente a cada consulta; a última se repete. */
function sequencia<T>(...respostas: T[]) {
  let vez = 0
  return () => respostas[Math.min(vez++, respostas.length - 1)]
}

function consultas(chamadas: Chamada[], caminho: string) {
  return chamadas.filter((c) => c.metodo === 'GET' && c.caminho === caminho).length
}

async function passar(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

/** Deixa as respostas simuladas chegarem, com o relógio simulado. */
async function esperarRespostas() {
  await passar(0)
  await passar(0)
}

function usarRelogioSimulado() {
  vi.useFakeTimers()
  return userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) })
}

function definirVisibilidade(estado: 'visible' | 'hidden') {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => estado })
}

function sinoComNaoLidas(quantidade: number) {
  return screen.getByRole('button', {
    name: quantidade ? `Notificações, ${quantidade} não lidas` : 'Notificações',
  })
}

afterEach(() => {
  vi.clearAllTimers()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  Reflect.deleteProperty(document, 'visibilityState')
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
})

describe('moldura das telas logadas', () => {
  it('mostra o nome, o menu do admin, o sino, as preferências e Sair em qualquer tela', async () => {
    simularApi({ ...COMO_ADMIN, 'GET /notificacoes/resumo/': resumo(0, null), 'GET /permissoes/cargos/': [] })

    abrir('/admin/cargos')

    expect(await screen.findByText('Olá, Ana Admin')).toBeInTheDocument()
    const menu = screen.getByRole('navigation', { name: 'Administração' })
    expect(within(menu).getAllByRole('link').map((l) => l.textContent)).toEqual([
      'Convites',
      'Usuários',
      'Cargos',
      'Setores',
      'Permissões',
    ])
    expect(screen.getByRole('link', { name: 'Preferências' })).toHaveAttribute('href', '/preferencias')
    expect(screen.getByRole('button', { name: 'Notificações' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sair' })).toBeInTheDocument()
  })

  it('o diretor com a permissão de convites vê o atalho Convites em qualquer tela', async () => {
    simularApi({
      'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
      ...SEM_GOOGLE,
      'GET /permissoes/minhas/': {
        cargo: { id: 'ca-1', nome: 'Tesoureiro', ativo: true },
        setores: [],
        permissoes: [{ codigo: 'convites.gerenciar', nome: 'Gerenciar convites', origens: [] }],
      },
      'GET /notificacoes/resumo/': resumo(0, null),
      'GET /notificacoes/preferencias/': LIGADAS,
    })

    abrir('/preferencias')

    const menu = await screen.findByRole('navigation', { name: 'Convites' })
    expect(within(menu).getByRole('link', { name: 'Convites' })).toHaveAttribute('href', '/admin/convites')
    expect(screen.queryByRole('navigation', { name: 'Administração' })).not.toBeInTheDocument()
  })

  it('o diretor sem a permissão de convites não vê o atalho', async () => {
    simularApi({
      'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
      ...SEM_GOOGLE,
      'GET /permissoes/minhas/': { cargo: { id: 'ca-1', nome: 'Tesoureiro', ativo: true }, setores: [], permissoes: [] },
      'GET /notificacoes/resumo/': resumo(0, null),
    })

    abrir('/')

    expect(await screen.findByText('Nenhuma permissão concedida ainda.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Convites' })).not.toBeInTheDocument()
  })

  it('o diretor sem cargo não consulta as permissões só para montar o menu', async () => {
    const chamadas = simularApi({ ...COMO_DIRETOR, 'GET /notificacoes/resumo/': resumo(0, null) })

    abrir('/')

    expect(await screen.findByText('Olá, Bia Diretora')).toBeInTheDocument()
    expect(consultas(chamadas, '/permissoes/minhas/')).toBe(0)
  })

  it('o diretor com cargo consulta as permissões uma vez só, para a moldura e para a página inicial', async () => {
    const chamadas = simularApi({
      'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
      ...SEM_GOOGLE,
      'GET /permissoes/minhas/': { cargo: { id: 'ca-1', nome: 'Tesoureiro', ativo: true }, setores: [], permissoes: [] },
      'GET /notificacoes/resumo/': resumo(0, null),
    })

    abrir('/')

    expect(await screen.findByText('Cargo: Tesoureiro')).toBeInTheDocument()
    expect(consultas(chamadas, '/permissoes/minhas/')).toBe(1)
  })

  it('não há moldura nem sino sem sessão', async () => {
    const chamadas = simularApi(SEM_SESSAO)

    abrir('/entrar')

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Notificações/ })).not.toBeInTheDocument()
    expect(consultas(chamadas, '/notificacoes/resumo/')).toBe(0)
  })

  it('Sair, na moldura, encerra a sessão', async () => {
    simularApi({ ...COMO_DIRETOR, 'GET /notificacoes/resumo/': resumo(0, null), 'POST /acesso/sessao/sair/': [204, null] })
    abrir('/')

    await userEvent.click(await screen.findByRole('button', { name: 'Sair' }))

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument()
  })
})

describe('sino (CA-23)', () => {
  it('CA-23: mostra a quantidade de não lidas ao carregar', async () => {
    const chamadas = simularApi({ ...COMO_DIRETOR, 'GET /notificacoes/resumo/': resumo(3, 'n-3') })

    abrir('/')

    expect(await screen.findByRole('button', { name: 'Notificações, 3 não lidas' })).toHaveTextContent('3')
    expect(consultas(chamadas, '/notificacoes/resumo/')).toBe(1)
  })

  it('sem não lidas mostra o sino sem número', async () => {
    simularApi({ ...COMO_DIRETOR, 'GET /notificacoes/resumo/': resumo(0, 'n-1') })

    abrir('/')

    expect(await screen.findByRole('button', { name: 'Notificações' })).not.toHaveTextContent(/\d/)
  })

  it('acima de 99 mostra 99+', async () => {
    simularApi({ ...COMO_DIRETOR, 'GET /notificacoes/resumo/': resumo(250, 'n-250') })

    abrir('/')

    expect(await screen.findByRole('button', { name: 'Notificações, 250 não lidas' })).toHaveTextContent('99+')
  })

  it('CA-23: a quantidade se atualiza sozinha a cada 60 segundos', async () => {
    usarRelogioSimulado()
    const chamadas = simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': sequencia(resumo(1, 'n-1'), resumo(2, 'n-2'), resumo(5, 'n-5')),
      'GET /notificacoes/preferencias/': SEM_AVISO,
    })
    abrir('/')
    await esperarRespostas()
    expect(sinoComNaoLidas(1)).toBeInTheDocument()

    await passar(59_999)
    expect(consultas(chamadas, '/notificacoes/resumo/')).toBe(1)
    await passar(1)
    expect(sinoComNaoLidas(2)).toBeInTheDocument()
    await passar(60_000)
    expect(sinoComNaoLidas(5)).toBeInTheDocument()
    expect(consultas(chamadas, '/notificacoes/resumo/')).toBe(3)
  })

  it('com a aba escondida não consulta, e ao voltar a ficar visível consulta na hora', async () => {
    usarRelogioSimulado()
    definirVisibilidade('hidden')
    const chamadas = simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': sequencia(resumo(1, 'n-1'), resumo(4, 'n-4')),
      'GET /notificacoes/preferencias/': SEM_AVISO,
    })
    abrir('/')
    await esperarRespostas()
    const antes = consultas(chamadas, '/notificacoes/resumo/')

    await passar(180_000)
    expect(consultas(chamadas, '/notificacoes/resumo/')).toBe(antes)

    definirVisibilidade('visible')
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'))
    })
    await esperarRespostas()
    expect(consultas(chamadas, '/notificacoes/resumo/')).toBe(antes + 1)
    expect(sinoComNaoLidas(4)).toBeInTheDocument()
  })

  it('a falha ao consultar não mostra alerta nem derruba a tela, e a próxima consulta recupera', async () => {
    usarRelogioSimulado()
    simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': sequencia<unknown>(erro(500, 'INTERNAL_ERROR', 'falhou'), resumo(2, 'n-2')),
      'GET /notificacoes/preferencias/': SEM_AVISO,
    })
    abrir('/')
    await esperarRespostas()

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Notificações' })).toBeInTheDocument()
    await passar(60_000)
    expect(sinoComNaoLidas(2)).toBeInTheDocument()
  })

  it('ao sair da tela o sino para de consultar e limpa o temporizador', async () => {
    usarRelogioSimulado()
    const chamadas = simularApi({ ...COMO_DIRETOR, 'GET /notificacoes/resumo/': resumo(1, 'n-1') })
    const { unmount } = abrir('/')
    await esperarRespostas()
    expect(vi.getTimerCount()).toBeGreaterThan(0)

    unmount()
    await passar(300_000)

    expect(consultas(chamadas, '/notificacoes/resumo/')).toBe(1)
    expect(vi.getTimerCount()).toBe(0)
  })
})

describe('aviso flutuante (CA-24, CA-18)', () => {
  // Uma função, e não um objeto: a sequência guarda o estado, e cada teste precisa da sua.
  const comNova = () => ({
    'GET /notificacoes/resumo/': sequencia(resumo(1, 'n-1'), resumo(2, 'n-2')),
    'GET /notificacoes/?limite=1': { itens: [notificacao(2)], tem_mais: true },
  })

  it('CA-24: ao chegar uma notificação com o aviso ligado, aparece o aviso flutuante', async () => {
    usarRelogioSimulado()
    simularApi({ ...COMO_DIRETOR, ...comNova(), 'GET /notificacoes/preferencias/': LIGADAS })
    abrir('/')
    await esperarRespostas()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()

    await passar(60_000)
    await esperarRespostas()

    const aviso = screen.getByRole('status')
    expect(aviso).toHaveTextContent('Título 2')
    expect(aviso).toHaveTextContent('Texto 2')
    expect(sinoComNaoLidas(2)).toBeInTheDocument()
  })

  it('o aviso flutuante some sozinho depois de alguns segundos', async () => {
    usarRelogioSimulado()
    simularApi({ ...COMO_DIRETOR, ...comNova(), 'GET /notificacoes/preferencias/': LIGADAS })
    abrir('/')
    await esperarRespostas()
    await passar(60_000)
    await esperarRespostas()
    expect(screen.getByRole('status')).toBeInTheDocument()

    await passar(5_999)
    expect(screen.getByRole('status')).toBeInTheDocument()
    await passar(1)

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(vi.getTimerCount()).toBe(1) // só o intervalo do sino
  })

  it('CA-18: com o aviso desligado não mostra o aviso, e o indicador continua aparecendo', async () => {
    usarRelogioSimulado()
    const chamadas = simularApi({ ...COMO_DIRETOR, ...comNova(), 'GET /notificacoes/preferencias/': SEM_AVISO })
    abrir('/')
    await esperarRespostas()

    await passar(60_000)
    await esperarRespostas()

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(sinoComNaoLidas(2)).toBeInTheDocument()
    expect(consultas(chamadas, '/notificacoes/?limite=1')).toBe(0)
  })

  it('a primeira consulta não gera aviso: só a mudança entre duas consultas', async () => {
    usarRelogioSimulado()
    const chamadas = simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': resumo(4, 'n-4'),
      'GET /notificacoes/preferencias/': LIGADAS,
    })

    abrir('/')
    await esperarRespostas()

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(consultas(chamadas, '/notificacoes/preferencias/')).toBe(0)
  })

  it('consulta igual à anterior não gera aviso', async () => {
    usarRelogioSimulado()
    simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': resumo(4, 'n-4'),
      'GET /notificacoes/preferencias/': LIGADAS,
      'GET /notificacoes/?limite=1': { itens: [notificacao(4)], tem_mais: false },
    })
    abrir('/')
    await esperarRespostas()

    await passar(120_000)
    await esperarRespostas()

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('mostra o texto do aviso como texto, sem interpretar HTML', async () => {
    usarRelogioSimulado()
    simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': sequencia(resumo(1, 'n-1'), resumo(2, 'n-2')),
      'GET /notificacoes/preferencias/': LIGADAS,
      'GET /notificacoes/?limite=1': {
        itens: [notificacao(2, { titulo: '<b>negrito</b>', texto: '<img src=x onerror=alert(1)>' })],
        tem_mais: false,
      },
    })
    abrir('/')
    await esperarRespostas()
    await passar(60_000)
    await esperarRespostas()

    const aviso = screen.getByRole('status')
    expect(aviso).toHaveTextContent('<b>negrito</b>')
    expect(aviso.querySelector('b, img')).toBeNull()
  })

  it('se não conseguir buscar a preferência ou o conteúdo, não mostra aviso nem alerta', async () => {
    usarRelogioSimulado()
    simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': sequencia(resumo(1, 'n-1'), resumo(2, 'n-2')),
      'GET /notificacoes/preferencias/': erro(500, 'INTERNAL_ERROR'),
    })
    abrir('/')
    await esperarRespostas()

    await passar(60_000)
    await esperarRespostas()

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(sinoComNaoLidas(2)).toBeInTheDocument()
  })
})

describe('caixa de entrada', () => {
  const PRIMEIRA_PAGINA = {
    itens: [notificacao(3), notificacao(2, { lida_em: '2026-11-13T11:00:00-03:00' })],
    tem_mais: false,
  }

  it('abre ao clicar no sino e lista as notificações, com as não lidas destacadas', async () => {
    const chamadas = simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': resumo(1, 'n-3'),
      'GET /notificacoes/?limite=20': PRIMEIRA_PAGINA,
    })
    abrir('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Notificações, 1 não lidas' }))

    const caixa = await screen.findByRole('region', { name: 'Caixa de notificações' })

    const itens = within(caixa).getAllByRole('listitem')
    expect(itens).toHaveLength(2)
    expect(itens[0]).toHaveTextContent('Título 3')
    expect(itens[0]).toHaveTextContent('Texto 3')
    expect(itens[0]).toHaveAttribute('data-lida', 'false')
    expect(within(itens[0]).getByText('Nova')).toBeInTheDocument()
    expect(itens[1]).toHaveAttribute('data-lida', 'true')
    expect(within(itens[1]).queryByText('Nova')).not.toBeInTheDocument()
    expect(consultas(chamadas, '/notificacoes/?limite=20')).toBe(1)
  })

  it('a caixa vazia diz que não há notificações', async () => {
    simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': resumo(0, null),
      'GET /notificacoes/?limite=20': { itens: [], tem_mais: false },
    })
    abrir('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Notificações' }))

    expect(await screen.findByText('Nenhuma notificação.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Carregar mais' })).not.toBeInTheDocument()
  })

  it('"Fechar" esconde a caixa e clicar de novo no sino a reabre', async () => {
    simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': resumo(0, null),
      'GET /notificacoes/?limite=20': { itens: [], tem_mais: false },
    })
    abrir('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Notificações' }))
    await screen.findByRole('region', { name: 'Caixa de notificações' })

    await userEvent.click(screen.getByRole('button', { name: 'Fechar' }))
    expect(screen.queryByRole('region', { name: 'Caixa de notificações' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Notificações' }))
    expect(await screen.findByRole('region', { name: 'Caixa de notificações' })).toBeInTheDocument()
  })

  it('"Carregar mais" pede a página seguinte a partir do último ID e junta à lista', async () => {
    const chamadas = simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': resumo(0, 'n-4'),
      'GET /notificacoes/?limite=20': { itens: [notificacao(4), notificacao(3)], tem_mais: true },
      'GET /notificacoes/?limite=20&antes=n-3': { itens: [notificacao(2), notificacao(1)], tem_mais: false },
    })
    abrir('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Notificações' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Carregar mais' }))

    const caixa = await screen.findByRole('region', { name: 'Caixa de notificações' })
    await within(caixa).findByText('Título 1')

    expect(within(caixa).getAllByRole('listitem').map((i) => i.textContent)).toEqual([
      expect.stringContaining('Título 4'),
      expect.stringContaining('Título 3'),
      expect.stringContaining('Título 2'),
      expect.stringContaining('Título 1'),
    ])
    expect(consultas(chamadas, '/notificacoes/?limite=20&antes=n-3')).toBe(1)
    expect(screen.queryByRole('button', { name: 'Carregar mais' })).not.toBeInTheDocument()
  })

  it('clicar numa notificação a marca como lida, atualiza o indicador e leva ao item', async () => {
    const chamadas = simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': sequencia(resumo(2, 'n-3'), resumo(1, 'n-3')),
      'GET /notificacoes/?limite=20': { itens: [notificacao(3), notificacao(2)], tem_mais: false },
      'POST /notificacoes/n-3/ler/': notificacao(3, { lida_em: '2026-11-13T12:00:00-03:00' }),
      'GET /notificacoes/preferencias/': LIGADAS,
    })
    abrir('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Notificações, 2 não lidas' }))

    await userEvent.click(await screen.findByRole('button', { name: /Título 3/ }))

    expect(await screen.findByRole('heading', { name: 'Preferências de alerta' })).toBeInTheDocument()
    expect(chamadas.some((c) => c.metodo === 'POST' && c.caminho === '/notificacoes/n-3/ler/')).toBe(true)
    expect(await screen.findByRole('button', { name: 'Notificações, 1 não lidas' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Caixa de notificações' })).not.toBeInTheDocument()
  })

  it('o caminho que não é do site não é aberto, mas a notificação fica lida', async () => {
    const chamadas = simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': resumo(1, 'n-1'),
      'GET /notificacoes/?limite=20': {
        itens: [notificacao(1, { caminho: 'https://outro.exemplo/roubo' })],
        tem_mais: false,
      },
      'POST /notificacoes/n-1/ler/': notificacao(1, { lida_em: '2026-11-13T12:00:00-03:00' }),
    })
    abrir('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Notificações, 1 não lidas' }))

    await userEvent.click(await screen.findByRole('button', { name: /Título 1/ }))

    expect(chamadas.some((c) => c.metodo === 'POST' && c.caminho === '/notificacoes/n-1/ler/')).toBe(true)
    expect(screen.getByText('Olá, Bia Diretora')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Preferências de alerta' })).not.toBeInTheDocument()
  })

  it('"Marcar todas como lidas" marca todas e zera o indicador', async () => {
    const chamadas = simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': sequencia(resumo(2, 'n-2'), resumo(0, 'n-2')),
      'GET /notificacoes/?limite=20': { itens: [notificacao(2), notificacao(1)], tem_mais: false },
      'POST /notificacoes/ler-todas/': { marcadas: 2 },
    })
    abrir('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Notificações, 2 não lidas' }))
    const caixa = await screen.findByRole('region', { name: 'Caixa de notificações' })
    await within(caixa).findByText('Título 2')

    await userEvent.click(within(caixa).getByRole('button', { name: 'Marcar todas como lidas' }))

    expect(await screen.findByRole('button', { name: 'Notificações' })).not.toHaveTextContent(/\d/)
    expect(within(caixa).queryByText('Nova')).not.toBeInTheDocument()
    expect(within(caixa).getAllByRole('listitem').map((i) => i.getAttribute('data-lida'))).toEqual(['true', 'true'])
    expect(chamadas.some((c) => c.metodo === 'POST' && c.caminho === '/notificacoes/ler-todas/')).toBe(true)
  })

  it('mostra o erro quando a caixa não carrega', async () => {
    simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': resumo(1, 'n-1'),
      'GET /notificacoes/?limite=20': erro(500, 'INTERNAL_ERROR', 'caixa fora do ar'),
    })
    abrir('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Notificações, 1 não lidas' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('caixa fora do ar')
  })

  it('mostra o erro quando não consegue marcar como lida e não sai da tela', async () => {
    simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': resumo(1, 'n-1'),
      'GET /notificacoes/?limite=20': { itens: [notificacao(1)], tem_mais: false },
      'POST /notificacoes/n-1/ler/': erro(500, 'INTERNAL_ERROR', 'não deu'),
    })
    abrir('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Notificações, 1 não lidas' }))

    await userEvent.click(await screen.findByRole('button', { name: /Título 1/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('não deu')
    expect(screen.getByRole('region', { name: 'Caixa de notificações' })).toBeInTheDocument()
  })

  it('mostra o erro quando "carregar mais" ou "marcar todas" falham', async () => {
    simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': resumo(1, 'n-2'),
      'GET /notificacoes/?limite=20': { itens: [notificacao(2)], tem_mais: true },
      'GET /notificacoes/?limite=20&antes=n-2': erro(500, 'INTERNAL_ERROR', 'sem mais'),
      'POST /notificacoes/ler-todas/': erro(500, 'INTERNAL_ERROR', 'sem marcar'),
    })
    abrir('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Notificações, 1 não lidas' }))

    await userEvent.click(await screen.findByRole('button', { name: 'Carregar mais' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('sem mais')

    await userEvent.click(screen.getByRole('button', { name: 'Marcar todas como lidas' }))
    expect(await screen.findByText('sem marcar')).toBeInTheDocument()
  })

  it('mostra o texto da notificação como texto, sem interpretar HTML', async () => {
    simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': resumo(1, 'n-1'),
      'GET /notificacoes/?limite=20': {
        itens: [notificacao(1, { titulo: '<script>x</script>', texto: '<a href="http://x">link</a>' })],
        tem_mais: false,
      },
    })
    abrir('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Notificações, 1 não lidas' }))

    const caixa = await screen.findByRole('region', { name: 'Caixa de notificações' })

    expect(await within(caixa).findByText(/<script>x<\/script>/)).toBeInTheDocument()
    expect(caixa.querySelector('script, a')).toBeNull()
  })
})

describe('tela de preferências (CA-16, CA-17, CA-19)', () => {
  it('mostra as duas chaves com os valores da API', async () => {
    simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': resumo(0, null),
      'GET /notificacoes/preferencias/': { aviso_na_tela: false, email_informativos: true },
    })

    abrir('/preferencias')

    expect(await screen.findByRole('heading', { name: 'Preferências de alerta' })).toBeInTheDocument()
    expect(await screen.findByRole('checkbox', { name: 'Aviso na tela' })).not.toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'E-mail dos avisos informativos' })).toBeChecked()
  })

  it('CA-16: as duas nascem ligadas', async () => {
    simularApi({ ...COMO_DIRETOR, 'GET /notificacoes/resumo/': resumo(0, null), 'GET /notificacoes/preferencias/': LIGADAS })

    abrir('/preferencias')

    expect(await screen.findByRole('checkbox', { name: 'Aviso na tela' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'E-mail dos avisos informativos' })).toBeChecked()
  })

  it('CA-17: salvar envia as duas chaves e confirma', async () => {
    document.cookie = 'csrftoken=token-do-cookie'
    const chamadas = simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': resumo(0, null),
      'GET /notificacoes/preferencias/': LIGADAS,
      'PUT /notificacoes/preferencias/': { aviso_na_tela: false, email_informativos: true },
    })
    abrir('/preferencias')

    await userEvent.click(await screen.findByRole('checkbox', { name: 'Aviso na tela' }))
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByText('Preferências salvas.')).toBeInTheDocument()
    const envio = chamadas.find((c) => c.metodo === 'PUT')!
    expect(envio.corpo).toEqual({ aviso_na_tela: false, email_informativos: true })
    expect(envio.cabecalhos['X-CSRFToken']).toBe('token-do-cookie')
    expect(screen.getByRole('checkbox', { name: 'Aviso na tela' })).not.toBeChecked()
  })

  it('mostra o erro quando não consegue salvar e não diz que salvou', async () => {
    simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': resumo(0, null),
      'GET /notificacoes/preferencias/': LIGADAS,
      'PUT /notificacoes/preferencias/': erro(400, 'VALIDATION_ERROR', 'inválido'),
    })
    abrir('/preferencias')

    await userEvent.click(await screen.findByRole('checkbox', { name: 'E-mail dos avisos informativos' }))
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Confira os campos destacados.')
    expect(screen.queryByText('Preferências salvas.')).not.toBeInTheDocument()
  })

  it('mostra o erro quando as preferências não carregam', async () => {
    simularApi({
      ...COMO_DIRETOR,
      'GET /notificacoes/resumo/': resumo(0, null),
      'GET /notificacoes/preferencias/': erro(500, 'INTERNAL_ERROR', 'fora do ar'),
    })

    abrir('/preferencias')

    expect(await screen.findByRole('alert')).toHaveTextContent('fora do ar')
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  })

  it('CA-19: só há duas chaves, nenhuma desliga o registro, e diz que o que pede ação sempre chega', async () => {
    simularApi({ ...COMO_DIRETOR, 'GET /notificacoes/resumo/': resumo(0, null), 'GET /notificacoes/preferencias/': LIGADAS })

    abrir('/preferencias')

    await screen.findByRole('checkbox', { name: 'Aviso na tela' })
    expect(screen.getAllByRole('checkbox')).toHaveLength(2)
    expect(screen.getByText(/pedem uma ação/i)).toHaveTextContent(/sempre/i)
  })

  it('quem não está logado vai para a tela de entrar', async () => {
    simularApi(SEM_SESSAO)

    abrir('/preferencias')

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument()
  })

  it('o link Preferências, na moldura, abre a tela', async () => {
    simularApi({ ...COMO_DIRETOR, 'GET /notificacoes/resumo/': resumo(0, null), 'GET /notificacoes/preferencias/': LIGADAS })
    abrir('/')

    await userEvent.click(await screen.findByRole('link', { name: 'Preferências' }))

    expect(await screen.findByRole('heading', { name: 'Preferências de alerta' })).toBeInTheDocument()
  })
})

describe('dados atuais depois de abrir uma notificação', () => {
  const TESOUREIRO = { id: 'ca-1', nome: 'Tesoureiro', ativo: true }
  const DIRETORIA = { id: 'ca-2', nome: 'Diretor', ativo: true }
  const FINANCEIRO = { id: 's-1', nome: 'Financeiro', ativo: true }
  const COM_CONVITES = [{ codigo: 'convites.gerenciar', nome: 'Gerenciar convites', origens: [] }]
  const NA_CAIXA = {
    'GET /notificacoes/resumo/': resumo(1, 'n-1'),
    'GET /notificacoes/?limite=20': { itens: [notificacao(1, { caminho: '/' })], tem_mais: false },
    'POST /notificacoes/n-1/ler/': notificacao(1, { caminho: '/', lida_em: '2026-11-13T12:00:00-03:00' }),
  }

  async function abrirANotificacao() {
    await userEvent.click(await screen.findByRole('button', { name: 'Notificações, 1 não lidas' }))
    await userEvent.click(await screen.findByRole('button', { name: /Título 1/ }))
  }

  it('o diretor sem cargo que abre a notificação de classificação passa a ver o cargo e os setores', async () => {
    simularApi({
      ...SEM_GOOGLE,
      ...NA_CAIXA,
      'GET /acesso/sessao/': sequencia<unknown>({ usuario: DIRETOR }, { usuario: { ...DIRETOR, tem_cargo: true } }),
      'GET /permissoes/minhas/': { cargo: TESOUREIRO, setores: [FINANCEIRO], permissoes: [] },
    })
    abrir('/')
    expect(await screen.findByText(/aguarda a classificação/i)).toBeInTheDocument()

    await abrirANotificacao()

    expect(await screen.findByText('Cargo: Tesoureiro')).toBeInTheDocument()
    expect(screen.getByText('Setores: Financeiro')).toBeInTheDocument()
    expect(screen.queryByText(/aguarda a classificação/i)).not.toBeInTheDocument()
  })

  it('o diretor que perdeu o cargo deixa de ver o cargo e os setores', async () => {
    simularApi({
      ...SEM_GOOGLE,
      ...NA_CAIXA,
      'GET /acesso/sessao/': sequencia<unknown>(
        { usuario: { ...DIRETOR, tem_cargo: true } },
        { usuario: { ...DIRETOR, tem_cargo: false } },
      ),
      'GET /permissoes/minhas/': { cargo: TESOUREIRO, setores: [FINANCEIRO], permissoes: [] },
    })
    abrir('/')
    expect(await screen.findByText('Cargo: Tesoureiro')).toBeInTheDocument()

    await abrirANotificacao()

    expect(await screen.findByText(/aguarda a classificação/i)).toBeInTheDocument()
    expect(screen.queryByText('Cargo: Tesoureiro')).not.toBeInTheDocument()
    expect(screen.queryByText(/Setores:/)).not.toBeInTheDocument()
  })

  it('o diretor reclassificado, que continua com cargo, passa a ver o cargo novo', async () => {
    simularApi({
      ...SEM_GOOGLE,
      ...NA_CAIXA,
      'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
      'GET /permissoes/minhas/': sequencia<unknown>(
        { cargo: TESOUREIRO, setores: [FINANCEIRO], permissoes: [] },
        { cargo: DIRETORIA, setores: [], permissoes: [] },
      ),
    })
    abrir('/')
    expect(await screen.findByText('Cargo: Tesoureiro')).toBeInTheDocument()

    await abrirANotificacao()

    expect(await screen.findByText('Cargo: Diretor')).toBeInTheDocument()
    expect(screen.getByText('Setores: nenhum')).toBeInTheDocument()
  })

  it('o menu da moldura acompanha: o atalho Convites some quando a permissão é revogada', async () => {
    simularApi({
      ...SEM_GOOGLE,
      ...NA_CAIXA,
      'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
      'GET /permissoes/minhas/': sequencia<unknown>(
        { cargo: TESOUREIRO, setores: [], permissoes: COM_CONVITES },
        { cargo: TESOUREIRO, setores: [], permissoes: [] },
      ),
    })
    abrir('/')
    expect(await screen.findByRole('link', { name: 'Convites' })).toBeInTheDocument()

    await abrirANotificacao()

    expect(await screen.findByText('Nenhuma permissão concedida ainda.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Convites' })).not.toBeInTheDocument()
  })

  it('o menu acompanha: quem ganhou o papel de admin passa a ver os atalhos de administração', async () => {
    simularApi({
      ...SEM_GOOGLE,
      ...NA_CAIXA,
      'GET /acesso/sessao/': sequencia<unknown>({ usuario: DIRETOR }, { usuario: { ...DIRETOR, admin: true } }),
    })
    abrir('/')
    await screen.findByText(/aguarda a classificação/i)
    expect(screen.queryByRole('navigation', { name: 'Administração' })).not.toBeInTheDocument()

    await abrirANotificacao()

    expect(await screen.findByRole('navigation', { name: 'Administração' })).toBeInTheDocument()
  })

  it('se a sessão não puder ser recarregada, a notificação continua aberta e nada quebra', async () => {
    simularApi({
      ...SEM_GOOGLE,
      ...NA_CAIXA,
      'GET /acesso/sessao/': sequencia<unknown>({ usuario: DIRETOR }, erro(500, 'INTERNAL_ERROR')),
    })
    abrir('/')
    await screen.findByText(/aguarda a classificação/i)

    await abrirANotificacao()

    expect(await screen.findByRole('button', { name: 'Notificações, 1 não lidas' })).toBeInTheDocument()
    expect(screen.getByText(/aguarda a classificação/i)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
