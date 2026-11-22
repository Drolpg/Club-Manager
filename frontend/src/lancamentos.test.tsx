import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import App from './App'
import { DIRETOR, SEM_GOOGLE, simularApi } from './test/api'

const RESUMO = { 'GET /notificacoes/resumo/': { nao_lidas: 0, mais_recente_id: null } }
const COMO_DIRETOR = {
  'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
  'GET /permissoes/minhas/': {
    cargo: { id: 'ca-1', nome: 'Diretor', ativo: true },
    setores: [],
    permissoes: [],
  },
  'GET /relatorios/dashboard/': [500, { error: { code: 'INTERNAL_ERROR', message: 'x', details: null } }],
  ...SEM_GOOGLE,
  ...RESUMO,
}
const SEM_CARGO = {
  'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: false } },
  'GET /relatorios/dashboard/': [500, { error: { code: 'INTERNAL_ERROR', message: 'x', details: null } }],
  ...SEM_GOOGLE,
  ...RESUMO,
}
const CATEGORIAS = {
  'GET /financeiro/categorias/?todas=1': [
    { id: 'cat-m', nome: 'Mensalidade', natureza: 'ENTRADA', ativa: true },
    { id: 'cat-a', nome: 'Arbitragem', natureza: 'SAIDA', ativa: false },
  ],
}

function item(extra: Record<string, unknown>) {
  return {
    subtipo: null,
    data_referencia: '2026-11-10',
    descricao: 'Mensalidade',
    categoria: { id: 'cat-m', nome: 'Mensalidade' },
    contraparte: 'Bia Diretora',
    valor: '100.00',
    valor_realizado: null,
    estado: 'EM_ABERTO',
    situacao: 'ABERTA',
    realizado_em: null,
    original: null,
    ...extra,
  }
}

const PAGINA = {
  itens: [
    item({
      tipo: 'ESTORNO',
      id: 'es-1',
      valor: '-100.00',
      estado: 'REALIZADO',
      situacao: '',
      original: { tipo: 'COBRANCA', id: 'c-1' },
      descricao: 'Estorno de: Mensalidade',
      realizado_em: '2026-11-12',
    }),
    item({
      tipo: 'COBRANCA',
      id: 'c-1',
      estado: 'ESTORNADO',
      situacao: 'ESTORNADA',
      realizado_em: '2026-11-11',
    }),
    item({
      tipo: 'ENTRADA',
      id: 'en-1',
      subtipo: 'SEM_DEVEDOR',
      descricao: 'Patrocinador',
      contraparte: 'Patrocinador',
      valor: '1000.00',
      estado: 'REALIZADO',
      situacao: 'VALIDADA',
    }),
    item({
      tipo: 'ENTRADA',
      id: 'dv-1',
      subtipo: 'DEVOLUCAO',
      descricao: 'Sobra',
      contraparte: 'Sobra',
      valor: '50.00',
      estado: 'REALIZADO',
      situacao: 'VALIDADA',
      original: { tipo: 'SAIDA', id: 's-1' },
    }),
    item({
      tipo: 'SAIDA',
      id: 's-1',
      descricao: 'Arbitragem',
      categoria: { id: 'cat-a', nome: 'Arbitragem' },
      contraparte: 'Caio — Futebol',
      valor: '300.00',
      valor_realizado: '150.00',
      estado: 'REALIZADO',
      situacao: 'LIQUIDADA',
    }),
  ],
  tem_mais: true,
}

function abrir(caminho: string) {
  return render(
    <MemoryRouter initialEntries={[caminho]}>
      <App />
    </MemoryRouter>,
  )
}

describe('lista de lançamentos', () => {
  it('o link "Lançamentos" aparece só para quem tem cargo', async () => {
    simularApi(COMO_DIRETOR)
    abrir('/')
    const menu = await screen.findByRole('navigation', { name: 'Financeiro' })
    expect(within(menu).getByRole('link', { name: 'Lançamentos' })).toHaveAttribute('href', '/lancamentos')
  })

  it('CA-17: o sem cargo não vê o link e é mandado de volta', async () => {
    simularApi(SEM_CARGO)
    abrir('/lancamentos')
    expect(await screen.findByText(/aguarda a classificação/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Lançamentos' })).not.toBeInTheDocument()
  })

  it('CA-14 e CA-16: mostra os quatro tipos, com os links para o detalhe de cada um', async () => {
    simularApi({ ...COMO_DIRETOR, ...CATEGORIAS, 'GET /financeiro/lancamentos/': PAGINA })
    abrir('/lancamentos')

    const tabela = await screen.findByRole('table', { name: 'Lançamentos' })
    const linhas = within(tabela).getAllByRole('row').slice(1)
    expect(linhas).toHaveLength(5)
    expect(within(linhas[0]).getByText('-R$ 100,00')).toBeInTheDocument()
    expect(within(linhas[0]).getByRole('link', { name: 'Estorno de: Mensalidade' })).toHaveAttribute(
      'href',
      '/cobrancas/c-1',
    )
    const destino = (linha: HTMLElement, nome: string) =>
      within(linha).getByRole('link', { name: nome }).getAttribute('href')
    expect(destino(linhas[1], 'Mensalidade')).toBe('/cobrancas/c-1')
    expect(destino(linhas[2], 'Patrocinador')).toBe('/entradas/en-1')
    expect(within(linhas[3]).getByRole('link', { name: 'Sobra' })).toHaveAttribute('href', '/saidas/s-1')
    expect(within(linhas[4]).getByRole('link', { name: 'Arbitragem' })).toHaveAttribute('href', '/saidas/s-1')
    expect(within(linhas[4]).getByText(/R\$ 150,00/)).toBeInTheDocument()
    expect(within(linhas[1]).getByText('Estornado')).toBeInTheDocument()
  })

  it('CA-15: os filtros vão para a API, inclusive os que chegam pela URL do dashboard', async () => {
    const chamadas = simularApi({
      ...COMO_DIRETOR,
      ...CATEGORIAS,
      'GET /financeiro/lancamentos/?de=2026-11-01&ate=2026-11-30': PAGINA,
      [`GET /financeiro/lancamentos/?de=2026-11-01&ate=2026-11-30&tipo=SAIDA&estado=REALIZADO` +
      `&categoria_id=cat-a`]: { itens: [], tem_mais: false },
    })
    abrir('/lancamentos?de=2026-11-01&ate=2026-11-30')

    await screen.findByRole('table', { name: 'Lançamentos' })
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Tipo' }), 'SAIDA')
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Estado' }), 'REALIZADO')
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Categoria' }), 'cat-a')
    await userEvent.click(screen.getByRole('button', { name: 'Filtrar' }))

    expect(await screen.findByText('Nenhum lançamento com esses filtros.')).toBeInTheDocument()
    expect(chamadas.some((c) => c.caminho.includes('categoria_id=cat-a'))).toBe(true)
    expect(screen.getByRole('option', { name: 'Arbitragem (desativada)' })).toBeInTheDocument()
  })

  it('"Carregar mais" pede a página seguinte pelo cursor do último item', async () => {
    simularApi({
      ...COMO_DIRETOR,
      ...CATEGORIAS,
      'GET /financeiro/lancamentos/': PAGINA,
      'GET /financeiro/lancamentos/?antes=SAIDA%3As-1': {
        itens: [item({ tipo: 'COBRANCA', id: 'c-0', descricao: 'Mais antiga' })],
        tem_mais: false,
      },
    })
    abrir('/lancamentos')

    await userEvent.click(await screen.findByRole('button', { name: 'Carregar mais' }))

    expect(await screen.findByRole('link', { name: 'Mais antiga' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Carregar mais' })).not.toBeInTheDocument()
  })
})

const ENTRADA = {
  id: 'en-1',
  tipo: 'SEM_DEVEDOR',
  categoria_id: 'cat-p',
  categoria_nome: 'Patrocínio',
  saida_id: null,
  valor: '1000.00',
  data: '2026-11-05',
  origem: 'Patrocinador',
  evidencia_texto: 'TED 123',
  comprovante_disponivel: true,
  comprovante_nome: 'ted.pdf',
  registrada_por: { id: 'u-5', nome: 'Fin' },
  situacao: 'VALIDADA',
  decidido_por: { id: 'u-6', nome: 'Val' },
  motivo_texto: 'Conferido',
  decisao_texto: '',
  registrada_em: '2026-11-05T10:00:00-03:00',
  decidido_em: '2026-11-06T10:00:00-03:00',
  estorno: null,
  acoes: [],
}

describe('detalhe da entrada (D9)', () => {
  it('CA-16: mostra os dados, o histórico e o comprovante quando a API o oferece', async () => {
    simularApi({
      ...COMO_DIRETOR,
      'GET /financeiro/entradas/en-1/': ENTRADA,
      'GET /financeiro/entradas/en-1/historico/': [
        {
          acao: 'ENTRADA_REGISTRADA',
          ator: { id: 'u-5', nome: 'Fin' },
          justificativa: '',
          dados: {},
          criado_em: '2026-11-05T10:00:00-03:00',
        },
      ],
    })
    abrir('/entradas/en-1')

    expect(await screen.findByRole('heading', { name: /entrada/i })).toBeInTheDocument()
    expect(screen.getByText('R$ 1.000,00')).toBeInTheDocument()
    expect(screen.getByText('TED 123')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /ted\.pdf/ })).toHaveAttribute(
      'href',
      '/api/v1/financeiro/entradas/en-1/comprovante/',
    )
    expect(within(screen.getByRole('region', { name: 'Histórico' })).getByText(/Fin/)).toBeInTheDocument()
  })

  it('sem o comprovante disponível, não há link; a devolução aponta para a saída', async () => {
    simularApi({
      ...COMO_DIRETOR,
      'GET /financeiro/entradas/dv-1/': {
        ...ENTRADA,
        id: 'dv-1',
        tipo: 'DEVOLUCAO',
        saida_id: 's-1',
        comprovante_disponivel: false,
        comprovante_nome: '',
      },
      'GET /financeiro/entradas/dv-1/historico/': [],
    })
    abrir('/entradas/dv-1')

    const origem = await screen.findByRole('link', { name: /saída de origem/i })
    expect(origem).toHaveAttribute('href', '/saidas/s-1')
    expect(screen.queryByRole('link', { name: /comprovante/i })).not.toBeInTheDocument()
  })
})
