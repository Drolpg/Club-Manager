import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import App from './App'
import { DIRETOR, SEM_GOOGLE, erro, simularApi } from './test/api'

const RESUMO = { 'GET /notificacoes/resumo/': { nao_lidas: 0, mais_recente_id: null } }
const MINHAS = {
  'GET /permissoes/minhas/': {
    cargo: { id: 'ca-1', nome: 'Tesoureiro', ativo: true },
    setores: [],
    permissoes: [],
  },
}
const COMO_DIRETOR = {
  'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
  ...MINHAS,
  ...SEM_GOOGLE,
  ...RESUMO,
}
const SEM_CARGO = {
  'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: false } },
  ...SEM_GOOGLE,
  ...RESUMO,
}

const resumo = (quantidade: number, total: string) => ({ quantidade, total })
const MINHAS_COBRANCAS = {
  em_aberto: resumo(2, '300.00'),
  atrasadas: resumo(1, '150.00'),
  em_validacao: resumo(0, '0.00'),
  proxima: { id: 'c-9', descricao: 'Mensalidade de dezembro', valor: '150.00', vencimento: '2026-12-10' },
}

function completo(mes = '2026-11', entradas = '1100.00') {
  return {
    tipo: 'COMPLETO',
    mes,
    meses: { de: '2026-09', ate: '2026-11' },
    do_mes: {
      entradas,
      saidas: '300.00',
      resultado: '800.00',
      saldo_acumulado: '1250.00',
      a_receber: resumo(3, '450.00'),
    },
    hoje: {
      data: '2026-11-22',
      comprometido: '500.00',
      saldo_livre: '750.00',
      pendencias_de_validacao: { pagamentos: resumo(1, '80.00'), entradas: resumo(2, '350.00') },
      pendencias_de_aprovacao: {
        minha_fila: 4,
        por_tipo: [{ tipo: 'financeiro.gasto', nome: 'Gasto', quantidade: 5 }],
      },
      prestacoes_pendentes: { aguardando: 2, em_atraso: 1, em_conferencia: 1 },
      inadimplencia: { cobrancas: 3, devedores: 2, total: '175.00' },
    },
    proximos_eventos: [
      { id: 'e-1', titulo: 'Amistoso', inicio: '2026-11-29T15:00:00-03:00', categoria_nome: 'Jogo' },
    ],
    ultimos_comunicados: [
      {
        id: 'k-1',
        tipo: 'COMUNICADO',
        titulo: 'Assembleia',
        publicado_em: '2026-11-20T10:00:00-03:00',
        fixado: true,
      },
    ],
    minhas_cobrancas: MINHAS_COBRANCAS,
  }
}

const BASICO = {
  tipo: 'BASICO',
  classificacao_pendente: true,
  minhas_cobrancas: MINHAS_COBRANCAS,
  notificacoes_nao_lidas: 3,
}

function abrir(caminho = '/') {
  return render(
    <MemoryRouter initialEntries={[caminho]}>
      <App />
    </MemoryRouter>,
  )
}

describe('dashboard completo', () => {
  it('CA-09: mostra os números do mês, os de hoje, eventos, comunicados e minhas cobranças', async () => {
    simularApi({ ...COMO_DIRETOR, 'GET /relatorios/dashboard/': completo() })
    abrir()

    const mes = await screen.findByRole('region', { name: 'Números do mês' })
    expect(within(mes).getByText('R$ 1.100,00')).toBeInTheDocument()
    expect(within(mes).getByText('R$ 1.250,00')).toBeInTheDocument()
    expect(within(mes).getByRole('link', { name: /ver os lançamentos do mês/i })).toHaveAttribute(
      'href',
      '/lancamentos?de=2026-11-01&ate=2026-11-30',
    )
    const hoje = screen.getByRole('region', { name: /hoje/i })
    expect(within(hoje).getByText(/22\/11\/2026/)).toBeInTheDocument()
    expect(within(hoje).getByText('R$ 750,00')).toBeInTheDocument()
    expect(within(hoje).getByRole('link', { name: /4 na sua fila/i })).toHaveAttribute('href', '/fila')
    expect(within(hoje).getByRole('link', { name: /3 cobranças inadimplentes/i })).toHaveAttribute(
      'href',
      '/cobrancas?inadimplentes=1',
    )
    expect(within(hoje).getByRole('link', { name: /2 aguardando prestação/i })).toHaveAttribute(
      'href',
      '/saidas?fila=prestacao',
    )
    expect(screen.getByRole('link', { name: 'Amistoso' })).toHaveAttribute('href', '/eventos/e-1')
    const comunicado = screen.getByRole('link', { name: 'Assembleia' })
    expect(comunicado).toHaveAttribute('href', '/feed/k-1')
    expect(screen.getByText('fixado')).toBeInTheDocument()
    const minhas = screen.getByRole('region', { name: 'Minhas cobranças' })
    expect(within(minhas).getByText(/Mensalidade de dezembro/)).toBeInTheDocument()
  })

  it('CA-09: trocar o mês pede o mês novo e só os números do mês mudam', async () => {
    const chamadas = simularApi({
      ...COMO_DIRETOR,
      'GET /relatorios/dashboard/': completo(),
      'GET /relatorios/dashboard/?mes=2026-10': completo('2026-10', '40.00'),
    })
    abrir()

    const seletor = await screen.findByRole('combobox', { name: 'Mês' })
    expect(within(seletor).getAllByRole('option').map((o) => o.textContent)).toEqual([
      '11/2026',
      '10/2026',
      '09/2026',
    ])
    await userEvent.selectOptions(seletor, '2026-10')

    expect(await screen.findByText('R$ 40,00')).toBeInTheDocument()
    expect(chamadas.some((c) => c.caminho === '/relatorios/dashboard/?mes=2026-10')).toBe(true)
    expect(screen.getByText('R$ 750,00')).toBeInTheDocument()
  })

  it('D10: mantém o bloco "Meu acesso" do diretor com cargo', async () => {
    simularApi({ ...COMO_DIRETOR, 'GET /relatorios/dashboard/': completo() })
    abrir()

    expect(await screen.findByText('Cargo: Tesoureiro')).toBeInTheDocument()
    expect(screen.getByText('Nenhuma permissão concedida ainda.')).toBeInTheDocument()
  })

  it('um erro do painel aparece no bloco dele sem esconder o resto', async () => {
    simularApi({ ...COMO_DIRETOR, 'GET /relatorios/dashboard/': erro(500, 'INTERNAL_ERROR', 'Falhou.') })
    abrir()

    expect(await screen.findByText(/não foi possível carregar o painel/i)).toBeInTheDocument()
    expect(await screen.findByText('Cargo: Tesoureiro')).toBeInTheDocument()
  })
})

describe('dashboard básico', () => {
  it('CA-11: o sem cargo vê o aviso, as próprias cobranças e as não lidas, sem número do clube', async () => {
    simularApi({ ...SEM_CARGO, 'GET /relatorios/dashboard/': BASICO })
    abrir()

    expect(await screen.findByText(/aguarda a classificação/i)).toBeInTheDocument()
    const minhas = await screen.findByRole('region', { name: 'Minhas cobranças' })
    expect(within(minhas).getByText(/2 em aberto/)).toBeInTheDocument()
    expect(within(minhas).getByRole('link', { name: /minhas cobranças/i })).toHaveAttribute(
      'href',
      '/minhas-cobrancas',
    )
    expect(screen.getByText(/3 notificações não lidas/)).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Números do mês' })).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Mês' })).not.toBeInTheDocument()
  })
})

describe('links do dashboard já filtrados', () => {
  it('a tela de cobranças abre só com os inadimplentes', async () => {
    const chamadas = simularApi({ ...COMO_DIRETOR })
    abrir('/cobrancas?inadimplentes=1')

    expect(await screen.findByRole('checkbox', { name: /só inadimplentes/i })).toBeChecked()
    const cobrancas = chamadas.filter((c) => c.caminho.startsWith('/financeiro/cobrancas/'))
    expect(cobrancas.some((c) => c.caminho.includes('inadimplentes=1'))).toBe(true)
  })

  it('a tela de saídas abre na fila de prestações pendentes', async () => {
    const chamadas = simularApi({ ...COMO_DIRETOR })
    abrir('/saidas?fila=prestacao')

    await screen.findByRole('heading', { name: /saídas/i })
    const saidas = chamadas.filter((c) => c.caminho.startsWith('/financeiro/saidas/'))
    expect(saidas.some((c) => c.caminho.includes('pendentes_prestacao=1'))).toBe(true)
  })
})
