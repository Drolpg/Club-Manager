import { render, screen, waitFor, within } from '@testing-library/react'
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

const RESUMO = { 'GET /notificacoes/resumo/': { nao_lidas: 0, mais_recente_id: null } }
const SEM_PERMISSAO = { cargo: { id: 'ca-1', nome: 'Diretor', ativo: true }, setores: [], permissoes: [] }
const COM_CARGO = {
  'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
  'GET /permissoes/minhas/': SEM_PERMISSAO,
  ...SEM_GOOGLE,
  ...RESUMO,
}
const SEM_CARGO = { 'GET /acesso/sessao/': { usuario: DIRETOR }, ...SEM_GOOGLE, ...RESUMO }
const COMO_ADMIN = { 'GET /acesso/sessao/': { usuario: ADMIN }, ...SEM_GOOGLE, ...RESUMO }

const BIA = { id: 'u-1', nome: 'Bia Diretora' }
const DORA = { id: 'u-2', nome: 'Dora Aprovadora' }
const TIPOS = [{ codigo: 'teste.pedido', nome: 'Pedido de teste', tem_valor: true }]

function item(id: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    tipo: 'teste.pedido',
    tipo_nome: 'Pedido de teste',
    situacao: 'EM_ANALISE',
    solicitante: BIA,
    resumo: `Pedido ${id}`,
    valor: '1234.50',
    numero_da_versao_atual: 1,
    aguardando_desde: '2026-11-10T09:00:00-03:00',
    criada_em: '2026-11-10T09:00:00-03:00',
    atualizada_em: '2026-11-10T09:00:00-03:00',
    ...extra,
  }
}

const LISTA = '/aprovacoes/solicitacoes/?limite=20'

function chamou(chamadas: Chamada[], metodo: string, caminho: string) {
  return chamadas.some((c) => c.metodo === metodo && c.caminho === caminho)
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('menu e guarda das telas de aprovações', () => {
  it('o diretor com cargo vê os atalhos da fila e das solicitações', async () => {
    simularApi(COM_CARGO)

    abrir('/')

    const menu = await screen.findByRole('navigation', { name: 'Aprovações' })
    expect(within(menu).getByRole('link', { name: 'Fila de pendências' })).toHaveAttribute('href', '/fila')
    expect(within(menu).getByRole('link', { name: 'Solicitações' })).toHaveAttribute('href', '/solicitacoes')
  })

  it('o admin também vê os atalhos', async () => {
    simularApi(COMO_ADMIN)

    abrir('/')

    const menu = await screen.findByRole('navigation', { name: 'Aprovações' })
    expect(within(menu).getByRole('link', { name: 'Solicitações' })).toBeInTheDocument()
  })

  it('o diretor sem cargo não vê os atalhos nem abre as telas', async () => {
    simularApi(SEM_CARGO)

    abrir('/solicitacoes')

    expect(await screen.findByText(/aguarda a classificação/)).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Aprovações' })).not.toBeInTheDocument()
  })
})

describe('lista de solicitações (CA-27)', () => {
  it('mostra as solicitações com tipo, situação, valor e solicitante', async () => {
    simularApi({
      ...COM_CARGO,
      'GET /aprovacoes/tipos/': TIPOS,
      [`GET ${LISTA}`]: { itens: [item('s-2', { situacao: 'APROVADA' }), item('s-1')], tem_mais: false },
    })

    abrir('/solicitacoes')

    const link = await screen.findByRole('link', { name: 'Pedido s-2' })
    expect(link).toHaveAttribute('href', '/solicitacoes/s-2')
    const linha = link.closest('tr') as HTMLElement
    expect(within(linha).getByText('Aprovada')).toBeInTheDocument()
    expect(within(linha).getByText('Pedido de teste')).toBeInTheDocument()
    expect(within(linha).getByText('R$ 1.234,50')).toBeInTheDocument()
    expect(within(linha).getByText('Bia Diretora')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Carregar mais' })).not.toBeInTheDocument()
  })

  it('filtra por situação, por tipo e pelas minhas', async () => {
    const chamadas = simularApi({
      ...COM_CARGO,
      'GET /aprovacoes/tipos/': TIPOS,
      [`GET ${LISTA}`]: { itens: [item('s-1')], tem_mais: false },
      'GET /aprovacoes/solicitacoes/?situacao=APROVADA&limite=20': {
        itens: [item('s-9', { situacao: 'APROVADA' })],
        tem_mais: false,
      },
      'GET /aprovacoes/solicitacoes/?tipo=teste.pedido&situacao=APROVADA&limite=20': { itens: [], tem_mais: false },
      'GET /aprovacoes/solicitacoes/?tipo=teste.pedido&situacao=APROVADA&minhas=1&limite=20': {
        itens: [],
        tem_mais: false,
      },
    })
    const usuario = userEvent.setup()
    abrir('/solicitacoes')
    await screen.findByRole('link', { name: 'Pedido s-1' })

    await usuario.selectOptions(screen.getByLabelText('Situação'), 'APROVADA')
    expect(await screen.findByRole('link', { name: 'Pedido s-9' })).toBeInTheDocument()
    await usuario.selectOptions(screen.getByLabelText('Tipo'), 'teste.pedido')
    expect(await screen.findByText('Nenhuma solicitação encontrada.')).toBeInTheDocument()
    await usuario.click(screen.getByLabelText('Só as minhas'))

    await waitFor(() =>
      expect(
        chamou(chamadas, 'GET', '/aprovacoes/solicitacoes/?tipo=teste.pedido&situacao=APROVADA&minhas=1&limite=20'),
      ).toBe(true),
    )
  })

  it('carrega a página seguinte a partir da última recebida', async () => {
    simularApi({
      ...COM_CARGO,
      'GET /aprovacoes/tipos/': TIPOS,
      [`GET ${LISTA}`]: { itens: [item('s-3'), item('s-2')], tem_mais: true },
      'GET /aprovacoes/solicitacoes/?antes=s-2&limite=20': { itens: [item('s-1')], tem_mais: false },
    })
    const usuario = userEvent.setup()
    abrir('/solicitacoes')

    await usuario.click(await screen.findByRole('button', { name: 'Carregar mais' }))

    expect(await screen.findByRole('link', { name: 'Pedido s-1' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Pedido s-3' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Carregar mais' })).not.toBeInTheDocument()
  })

  it('mostra o erro da API', async () => {
    simularApi({ ...COM_CARGO, 'GET /aprovacoes/tipos/': TIPOS, [`GET ${LISTA}`]: erro(403, 'PERMISSION_DENIED') })

    abrir('/solicitacoes')

    expect(await screen.findByRole('alert')).toHaveTextContent('Você não tem permissão para fazer isso.')
  })
})

describe('fila de pendências (CA-26)', () => {
  it('mostra as solicitações na ordem da API, com o tempo de espera', async () => {
    simularApi({ ...COM_CARGO, 'GET /aprovacoes/fila/': [item('s-1'), item('s-2')] })

    abrir('/fila')

    const links = await screen.findAllByRole('link', { name: /^Pedido s-/ })
    expect(links.map((l) => l.textContent)).toEqual(['Pedido s-1', 'Pedido s-2'])
    expect(screen.getByRole('columnheader', { name: 'Aguardando desde' })).toBeInTheDocument()
  })

  it('avisa quando não há nada para decidir', async () => {
    simularApi({ ...COM_CARGO, 'GET /aprovacoes/fila/': [] })

    abrir('/fila')

    expect(await screen.findByText('Nada para decidir agora.')).toBeInTheDocument()
  })
})

const DETALHE = {
  id: 's-1',
  tipo: 'teste.pedido',
  tipo_nome: 'Pedido de teste',
  tem_valor: true,
  situacao: 'EM_ANALISE',
  solicitante: BIA,
  aprovador_indicado: DORA,
  numero_da_versao_atual: 2,
  criada_em: '2026-11-10T09:00:00-03:00',
  atualizada_em: '2026-11-11T09:00:00-03:00',
  acoes: [],
  versoes: [
    {
      numero: 1,
      conteudo: { descricao: 'Bolas de treino', itens: [{ nome: '<b>Bola</b>', valor: '150.00' }] },
      valor: '150.00',
      resumo: 'Bolas de treino',
      autor: BIA,
      justificativa: '',
      criada_em: '2026-11-10T09:00:00-03:00',
      decisao: {
        tipo: 'CONTESTAR',
        aprovador: DORA,
        motivo_id: 'm-1',
        motivo_texto: 'Valor acima do necessário',
        texto: 'Veja o teto.',
        mensagem: 'Pesquise mais duas lojas.',
        teto_sugerido: '90.00',
        aprovacao_propria: false,
        criada_em: '2026-11-10T15:00:00-03:00',
      },
    },
    {
      numero: 2,
      conteudo: { descricao: 'Bolas oficiais' },
      valor: '90.00',
      resumo: 'Bolas oficiais',
      autor: BIA,
      justificativa: '',
      criada_em: '2026-11-11T09:00:00-03:00',
      decisao: null,
    },
  ],
}

const HISTORICO = [
  { acao: 'SOLICITACAO_REENVIADA', ator: BIA, justificativa: '', criado_em: '2026-11-11T09:00:00-03:00' },
  {
    acao: 'SOLICITACAO_CONTESTADA',
    ator: DORA,
    justificativa: 'Valor acima do necessário',
    criado_em: '2026-11-10T15:00:00-03:00',
  },
  { acao: 'SOLICITACAO_ENVIADA', ator: BIA, justificativa: '', criado_em: '2026-11-10T09:00:00-03:00' },
]

const NO_DETALHE = {
  'GET /aprovacoes/solicitacoes/s-1/': DETALHE,
  'GET /aprovacoes/solicitacoes/s-1/historico/': HISTORICO,
}

describe('detalhe da solicitação (CA-28)', () => {
  it('mostra o cabeçalho, a indicação e todas as versões, da mais nova para a mais antiga', async () => {
    simularApi({ ...COM_CARGO, ...NO_DETALHE })

    abrir('/solicitacoes/s-1')

    expect(await screen.findByRole('heading', { name: 'Bolas oficiais' })).toBeInTheDocument()
    expect(screen.getByText('Em análise')).toBeInTheDocument()
    expect(screen.getByText('Solicitante: Bia Diretora')).toBeInTheDocument()
    expect(screen.getByText('Aprovador indicado: Dora Aprovadora')).toBeInTheDocument()
    const versoes = screen.getAllByRole('region', { name: /^Versão / })
    expect(versoes.map((v) => v.getAttribute('aria-label'))).toEqual(['Versão 2', 'Versão 1'])
    expect(within(versoes[0]).getByText('R$ 90,00')).toBeInTheDocument()
    expect(within(versoes[0]).getByText('Sem decisão ainda.')).toBeInTheDocument()
  })

  it('mostra a decisão de cada versão com aprovador, motivo, texto, mensagem e teto', async () => {
    simularApi({ ...COM_CARGO, ...NO_DETALHE })

    abrir('/solicitacoes/s-1')

    const primeira = await screen.findByRole('region', { name: 'Versão 1' })
    const decisao = within(primeira).getByRole('group', { name: 'Decisão' })
    expect(decisao).toHaveTextContent('Contestada por Dora Aprovadora')
    expect(decisao).toHaveTextContent('Motivo: Valor acima do necessário')
    expect(decisao).toHaveTextContent('Veja o teto.')
    expect(decisao).toHaveTextContent('Mensagem: Pesquise mais duas lojas.')
    expect(decisao).toHaveTextContent('Teto sugerido: R$ 90,00')
  })

  it('mostra o conteúdo de forma genérica, sempre como texto', async () => {
    simularApi({ ...COM_CARGO, ...NO_DETALHE })

    abrir('/solicitacoes/s-1')

    const primeira = await screen.findByRole('region', { name: 'Versão 1' })
    expect(within(primeira).getByText('descricao')).toBeInTheDocument()
    expect(within(primeira).getByText('Bolas de treino')).toBeInTheDocument()
    expect(within(primeira).getByText('<b>Bola</b>')).toBeInTheDocument()
    expect(primeira.querySelector('b')).toBeNull()
  })

  it('mostra o histórico com quem fez e o motivo', async () => {
    simularApi({ ...COM_CARGO, ...NO_DETALHE })

    abrir('/solicitacoes/s-1')

    const historico = await screen.findByRole('region', { name: 'Histórico' })
    const itens = await within(historico).findAllByRole('listitem')
    expect(itens.map((i) => i.textContent)).toEqual([
      expect.stringContaining('Reenviada — Bia Diretora'),
      expect.stringContaining('Contestada — Dora Aprovadora: Valor acima do necessário'),
      expect.stringContaining('Enviada — Bia Diretora'),
    ])
  })

  it('mostra o erro de solicitação inexistente', async () => {
    simularApi({
      ...COM_CARGO,
      'GET /aprovacoes/solicitacoes/s-9/': erro(404, 'NOT_FOUND'),
      'GET /aprovacoes/solicitacoes/s-9/historico/': erro(404, 'NOT_FOUND'),
    })

    abrir('/solicitacoes/s-9')

    expect(await screen.findByRole('alert')).toHaveTextContent('Não encontrado.')
  })
})
