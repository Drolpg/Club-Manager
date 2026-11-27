import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { DIRETOR, SEM_GOOGLE, erro, simularApi, type Chamada } from './test/api'

const RESUMO = { 'GET /notificacoes/resumo/': { nao_lidas: 0, mais_recente_id: null } }
const SEM_PAINEL = {
  'GET /relatorios/dashboard/': [500, { error: { code: 'INTERNAL_ERROR', message: 'x', details: null } }],
}
const MINHAS = {
  'GET /permissoes/minhas/': {
    cargo: { id: 'ca-1', nome: 'Diretor', ativo: true },
    setores: [],
    permissoes: [],
  },
}
const MEUS_DADOS = { codigo: 'MEUS_DADOS', nome: 'Meus dados', formatos: ['CSV'], parametros: 'NENHUM' }
const DO_CLUBE = [
  { codigo: 'EXTRATO', nome: 'Extrato', formatos: ['PDF', 'CSV'], parametros: 'PERIODO' },
  { codigo: 'INADIMPLENCIA', nome: 'Inadimplência', formatos: ['PDF', 'CSV'], parametros: 'NENHUM' },
  {
    codigo: 'PRESTACAO_DE_CONTAS',
    nome: 'Prestação de contas',
    formatos: ['PDF', 'CSV'],
    parametros: 'PERIODO_E_PENDENTES',
  },
  { codigo: 'FLUXO_DE_CAIXA', nome: 'Fluxo de caixa', formatos: ['PDF', 'CSV'], parametros: 'MESES' },
  MEUS_DADOS,
]
const VAZIA = { itens: [], tem_mais: false }
const NOMES: Record<string, string> = Object.fromEntries(DO_CLUBE.map((t) => [t.codigo, t.nome]))

function pedido(extra: Record<string, unknown>) {
  return {
    id: 'p-1',
    tipo: 'EXTRATO',
    tipo_nome: 'Extrato',
    formato: 'PDF',
    parametros: { de: '2026-10-01', ate: '2026-10-31' },
    situacao: 'NA_FILA',
    pedido_em: '2026-11-20T10:00:00-03:00',
    concluido_em: null,
    expira_em: null,
    disponivel: false,
    codigo_da_falha: '',
    ...extra,
  }
}

function comCargo(rotas: Record<string, unknown>) {
  return simularApi({
    'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
    'GET /relatorios/tipos/': DO_CLUBE,
    'GET /relatorios/pedidos/': VAZIA,
    ...MINHAS,
    ...SEM_PAINEL,
    ...SEM_GOOGLE,
    ...RESUMO,
    ...rotas,
  })
}

function abrir(caminho = '/relatorios') {
  render(
    <MemoryRouter initialEntries={[caminho]}>
      <App />
    </MemoryRouter>,
  )
}

/** Espera os tipos chegarem da API antes de escolher: o `select` aparece antes das opções. */
async function escolher(codigo: string) {
  await screen.findByRole('option', { name: NOMES[codigo] })
  await userEvent.selectOptions(screen.getByLabelText('Relatório'), codigo)
}

function pedidos(chamadas: Chamada[]) {
  return chamadas.filter((c) => c.metodo === 'POST' && c.caminho === '/relatorios/pedidos/')
}

afterEach(() => {
  vi.useRealTimers()
})

describe('Relatórios', () => {
  it('aparece no menu de todo usuário logado, e o sem cargo só pode pedir "Meus dados"', async () => {
    simularApi({
      'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: false } },
      'GET /relatorios/tipos/': [MEUS_DADOS],
      'GET /relatorios/pedidos/': VAZIA,
      ...SEM_PAINEL,
      ...SEM_GOOGLE,
      ...RESUMO,
    })
    abrir('/')

    await userEvent.click(await screen.findByRole('link', { name: 'Relatórios' }))

    const tipo = await screen.findByLabelText('Relatório')
    expect(within(tipo).getAllByRole('option').map((o) => o.textContent)).toEqual(['Meus dados'])
    const formatos = within(screen.getByLabelText('Formato')).getAllByRole('option')
    expect(formatos.map((o) => o.textContent)).toEqual(['CSV'])
    expect(screen.getByText(/disponível por 7 dias/)).toBeInTheDocument()
  })

  it('pede o extrato do mês em PDF', async () => {
    const chamadas = comCargo({ 'POST /relatorios/pedidos/': [202, pedido({})] })
    abrir()

    await escolher('EXTRATO')
    await userEvent.type(screen.getByLabelText('Mês'), '2026-10')
    await userEvent.click(screen.getByRole('button', { name: 'Pedir' }))

    expect(await screen.findByText(/Pedido na fila/)).toBeInTheDocument()
    expect(pedidos(chamadas)[0].corpo).toEqual({
      tipo: 'EXTRATO',
      formato: 'PDF',
      parametros: { mes: '2026-10' },
    })
  })

  it('pede a prestação de contas de um período, só pendentes, em CSV', async () => {
    const chamadas = comCargo({ 'POST /relatorios/pedidos/': [202, pedido({})] })
    abrir()

    await escolher('PRESTACAO_DE_CONTAS')
    await userEvent.selectOptions(screen.getByLabelText('Formato'), 'CSV')
    await userEvent.type(screen.getByLabelText('De'), '2026-10-01')
    await userEvent.type(screen.getByLabelText('Até'), '2026-10-31')
    await userEvent.click(screen.getByLabelText('Só pendentes'))
    await userEvent.click(screen.getByRole('button', { name: 'Pedir' }))

    await screen.findByText(/Pedido na fila/)
    expect(pedidos(chamadas)[0].corpo).toEqual({
      tipo: 'PRESTACAO_DE_CONTAS',
      formato: 'CSV',
      parametros: { de: '2026-10-01', ate: '2026-10-31', so_pendentes: true },
    })
  })

  it('pede o fluxo de caixa em meses e a inadimplência sem parâmetros', async () => {
    const chamadas = comCargo({ 'POST /relatorios/pedidos/': [202, pedido({})] })
    abrir()

    await escolher('FLUXO_DE_CAIXA')
    await userEvent.type(screen.getByLabelText('Do mês'), '2026-09')
    await userEvent.type(screen.getByLabelText('Até o mês'), '2026-11')
    await userEvent.click(screen.getByRole('button', { name: 'Pedir' }))
    await screen.findByText(/Pedido na fila/)
    await userEvent.selectOptions(screen.getByLabelText('Relatório'), 'INADIMPLENCIA')
    expect(screen.queryByLabelText('Mês')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Pedir' }))

    await vi.waitFor(() => expect(pedidos(chamadas)).toHaveLength(2))
    expect(pedidos(chamadas).map((c) => c.corpo)).toEqual([
      { tipo: 'FLUXO_DE_CAIXA', formato: 'PDF', parametros: { de: '2026-09', ate: '2026-11' } },
      { tipo: 'INADIMPLENCIA', formato: 'PDF', parametros: {} },
    ])
  })

  it('mostra o erro do campo, a falta de permissão e o limite de pedidos', async () => {
    let vez = 0
    const respostas = [
      erro(400, 'VALIDATION_ERROR', 'x', { mes: ['Escolha o mês corrente ou um anterior.'] }),
      erro(403, 'PERMISSION_DENIED'),
      erro(409, 'PEDIDOS_EM_ANDAMENTO'),
    ]
    comCargo({ 'POST /relatorios/pedidos/': () => respostas[vez++] })
    abrir()

    await escolher('EXTRATO')
    await userEvent.type(screen.getByLabelText('Mês'), '2026-12')
    const pedir = screen.getByRole('button', { name: 'Pedir' })
    await userEvent.click(pedir)
    expect(await screen.findByText('Escolha o mês corrente ou um anterior.')).toBeInTheDocument()
    await userEvent.click(pedir)
    expect(await screen.findByText('Você não tem permissão para fazer isso.')).toBeInTheDocument()
    await userEvent.click(pedir)
    expect(await screen.findByText(/três relatórios na fila ou sendo gerados/)).toBeInTheDocument()
  })

  it('lista os próprios pedidos, baixa o pronto e pede de novo o que expirou ou falhou', async () => {
    const pronto = pedido({
      id: 'p-pronto',
      situacao: 'PRONTO',
      disponivel: true,
      concluido_em: '2026-11-20T10:01:00-03:00',
      expira_em: '2026-11-27T10:01:00-03:00',
    })
    const expirado = pedido({
      id: 'p-exp',
      situacao: 'EXPIRADO',
      tipo: 'INADIMPLENCIA',
      tipo_nome: 'Inadimplência',
      parametros: {},
    })
    const falhou = pedido({ id: 'p-fal', situacao: 'FALHOU', formato: 'CSV' })
    const chamadas = comCargo({
      'GET /relatorios/pedidos/': { itens: [pronto, expirado, falhou], tem_mais: false },
      'POST /relatorios/pedidos/': [202, pedido({ id: 'p-novo' })],
    })
    abrir()

    const lista = await screen.findByRole('table', { name: 'Meus relatórios' })
    const linhas = within(lista).getAllByRole('row').slice(1)
    expect(within(linhas[0]).getByText('Pronto')).toBeInTheDocument()
    expect(within(linhas[0]).getByText('01/10/2026 a 31/10/2026')).toBeInTheDocument()
    expect(within(linhas[0]).getByText(/27\/11\/2026/)).toBeInTheDocument()
    expect(within(linhas[0]).getByRole('link', { name: 'Baixar' })).toHaveAttribute(
      'href',
      '/api/v1/relatorios/pedidos/p-pronto/arquivo/',
    )
    for (const linha of linhas.slice(1)) {
      expect(within(linha).queryByRole('link', { name: 'Baixar' })).not.toBeInTheDocument()
    }
    expect(within(linhas[1]).getByText('Expirado')).toBeInTheDocument()
    expect(within(linhas[2]).getByText('Falhou')).toBeInTheDocument()

    await userEvent.click(within(linhas[1]).getByRole('button', { name: 'Pedir de novo' }))
    await vi.waitFor(() => expect(pedidos(chamadas)).toHaveLength(1))
    expect(pedidos(chamadas)[0].corpo).toEqual({ tipo: 'INADIMPLENCIA', formato: 'PDF', parametros: {} })
  })

  it('consulta a cada 3 segundos enquanto há pedido em andamento e para quando acaba', async () => {
    vi.useFakeTimers()
    let vez = 0
    const listas = [
      { itens: [pedido({ situacao: 'NA_FILA' })], tem_mais: false },
      { itens: [pedido({ situacao: 'GERANDO' })], tem_mais: false },
      {
        itens: [pedido({ situacao: 'PRONTO', disponivel: true, expira_em: '2026-11-27T10:00:00-03:00' })],
        tem_mais: false,
      },
    ]
    const proxima = () => listas[Math.min(vez++, listas.length - 1)]
    const chamadas = comCargo({ 'GET /relatorios/pedidos/': proxima })
    abrir()
    const passar = async (ms: number) => {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(ms)
      })
    }
    const consultas = () =>
      chamadas.filter((c) => c.caminho === '/relatorios/pedidos/' && c.metodo === 'GET').length

    await passar(0)
    expect(consultas()).toBe(1)
    await passar(3000)
    expect(consultas()).toBe(2)
    await passar(3000)
    expect(consultas()).toBe(3)
    expect(screen.getByRole('link', { name: 'Baixar' })).toBeInTheDocument()
    await passar(9000)
    expect(consultas()).toBe(3)
  })
})
