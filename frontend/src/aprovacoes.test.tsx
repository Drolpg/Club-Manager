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
    const solicitacoes = within(menu).getByRole('link', { name: 'Solicitações' })
    expect(solicitacoes).toHaveAttribute('href', '/solicitacoes')
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
      'GET /aprovacoes/solicitacoes/?tipo=teste.pedido&situacao=APROVADA&limite=20': {
        itens: [],
        tem_mais: false,
      },
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
        chamou(
          chamadas,
          'GET',
          '/aprovacoes/solicitacoes/?tipo=teste.pedido&situacao=APROVADA&minhas=1&limite=20',
        ),
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
    simularApi({
      ...COM_CARGO,
      'GET /aprovacoes/tipos/': TIPOS,
      [`GET ${LISTA}`]: erro(403, 'PERMISSION_DENIED'),
    })

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

const MOTIVOS = {
  'GET /aprovacoes/motivos/?tipo_de_decisao=solicitacao.aprovar': [
    { id: 'm-a', tipo_de_decisao: 'solicitacao.aprovar', texto: 'Dentro do orçamento', ativo: true },
  ],
  'GET /aprovacoes/motivos/?tipo_de_decisao=solicitacao.contestar': [
    { id: 'm-c', tipo_de_decisao: 'solicitacao.contestar', texto: 'Valor acima do necessário', ativo: true },
  ],
  'GET /aprovacoes/motivos/?tipo_de_decisao=solicitacao.recusar': [
    { id: 'm-r', tipo_de_decisao: 'solicitacao.recusar', texto: 'Sem caixa disponível', ativo: true },
  ],
}

function comAcoes(acoes: string[], extra: Record<string, unknown> = {}) {
  return {
    ...COM_CARGO,
    ...MOTIVOS,
    'GET /aprovacoes/solicitacoes/s-1/': { ...DETALHE, acoes, ...extra },
    'GET /aprovacoes/solicitacoes/s-1/historico/': HISTORICO,
  }
}

function postado(chamadas: Chamada[], acao: string) {
  return chamadas.find((c) => c.metodo === 'POST' && c.caminho === `/aprovacoes/solicitacoes/s-1/${acao}/`)
}

describe('ações no detalhe (CA-03, CA-07 a CA-16)', () => {
  it('mostra só os botões que vieram em acoes', async () => {
    simularApi(comAcoes(['aprovar', 'contestar', 'recusar']))

    abrir('/solicitacoes/s-1')

    const acoes = await screen.findByRole('region', { name: 'Ações' })
    expect(within(acoes).getAllByRole('button').map((b) => b.textContent)).toEqual([
      'Aprovar',
      'Contestar',
      'Recusar',
    ])
  })

  it('sem nenhuma ação, a seção de ações não aparece', async () => {
    simularApi(comAcoes([]))

    abrir('/solicitacoes/s-1')

    await screen.findByRole('region', { name: 'Versão 1' })
    expect(screen.queryByRole('region', { name: 'Ações' })).not.toBeInTheDocument()
  })

  it('aprova com o motivo escolhido no seletor e o texto, e recarrega o detalhe', async () => {
    const chamadas = simularApi({
      ...comAcoes(['aprovar']),
      'POST /aprovacoes/solicitacoes/s-1/aprovar/': DETALHE,
    })
    const usuario = userEvent.setup()
    abrir('/solicitacoes/s-1')

    await usuario.click(await screen.findByRole('button', { name: 'Aprovar' }))
    const formulario = screen.getByRole('form', { name: 'Aprovar' })
    await within(formulario).findByRole('option', { name: 'Dentro do orçamento' })
    await usuario.selectOptions(within(formulario).getByLabelText('Motivo'), 'm-a')
    await usuario.type(within(formulario).getByLabelText('Texto (opcional)'), 'Pode comprar.')
    await usuario.click(within(formulario).getByRole('button', { name: 'Confirmar' }))

    await waitFor(() =>
      expect(postado(chamadas, 'aprovar')?.corpo).toEqual({ motivo_id: 'm-a', texto: 'Pode comprar.' }),
    )
    await waitFor(() =>
      expect(chamadas.filter((c) => c.caminho === '/aprovacoes/solicitacoes/s-1/')).toHaveLength(2),
    )
  })

  it('contesta com motivo, mensagem e teto sugerido', async () => {
    const chamadas = simularApi({
      ...comAcoes(['contestar']),
      'POST /aprovacoes/solicitacoes/s-1/contestar/': DETALHE,
    })
    const usuario = userEvent.setup()
    abrir('/solicitacoes/s-1')

    await usuario.click(await screen.findByRole('button', { name: 'Contestar' }))
    const formulario = screen.getByRole('form', { name: 'Contestar' })
    await within(formulario).findByRole('option', { name: 'Valor acima do necessário' })
    await usuario.selectOptions(within(formulario).getByLabelText('Motivo'), 'm-c')
    await usuario.type(within(formulario).getByLabelText('Mensagem ao solicitante'), 'Pesquise mais.')
    await usuario.type(within(formulario).getByLabelText('Teto sugerido (opcional)'), '90.00')
    await usuario.click(within(formulario).getByRole('button', { name: 'Confirmar' }))

    await waitFor(() =>
      expect(postado(chamadas, 'contestar')?.corpo).toEqual({
        motivo_id: 'm-c',
        texto: '',
        mensagem: 'Pesquise mais.',
        teto_sugerido: '90.00',
      }),
    )
  })

  it('sem valor no tipo, a contestação não pede teto', async () => {
    simularApi(comAcoes(['contestar'], { tem_valor: false }))
    const usuario = userEvent.setup()
    abrir('/solicitacoes/s-1')

    await usuario.click(await screen.findByRole('button', { name: 'Contestar' }))

    const formulario = screen.getByRole('form', { name: 'Contestar' })
    expect(within(formulario).queryByLabelText('Teto sugerido (opcional)')).not.toBeInTheDocument()
  })

  it('recusa com o motivo da lista de recusa', async () => {
    const chamadas = simularApi({
      ...comAcoes(['recusar']),
      'POST /aprovacoes/solicitacoes/s-1/recusar/': DETALHE,
    })
    const usuario = userEvent.setup()
    abrir('/solicitacoes/s-1')

    await usuario.click(await screen.findByRole('button', { name: 'Recusar' }))
    const formulario = screen.getByRole('form', { name: 'Recusar' })
    await within(formulario).findByRole('option', { name: 'Sem caixa disponível' })
    await usuario.selectOptions(within(formulario).getByLabelText('Motivo'), 'm-r')
    await usuario.click(within(formulario).getByRole('button', { name: 'Confirmar' }))

    await waitFor(() => expect(postado(chamadas, 'recusar')?.corpo).toEqual({ motivo_id: 'm-r', texto: '' }))
  })

  it('mostra o erro da API e os erros por campo', async () => {
    simularApi({
      ...comAcoes(['contestar']),
      'POST /aprovacoes/solicitacoes/s-1/contestar/': erro(400, 'VALIDATION_ERROR', 'inválido', {
        mensagem: ['Este campo é obrigatório.'],
      }),
    })
    const usuario = userEvent.setup()
    abrir('/solicitacoes/s-1')

    await usuario.click(await screen.findByRole('button', { name: 'Contestar' }))
    const formulario = screen.getByRole('form', { name: 'Contestar' })
    await within(formulario).findByRole('option', { name: 'Valor acima do necessário' })
    await usuario.click(within(formulario).getByRole('button', { name: 'Confirmar' }))

    expect(await within(formulario).findByRole('alert')).toHaveTextContent('Confira os campos destacados.')
    expect(within(formulario).getByText('Este campo é obrigatório.')).toBeInTheDocument()
  })

  it('mostra a recusa de quem não pode decidir', async () => {
    simularApi({
      ...comAcoes(['aprovar']),
      'POST /aprovacoes/solicitacoes/s-1/aprovar/': erro(
        403,
        'SOLICITANTE_NAO_DECIDE',
        'Quem enviou a solicitação não pode decidi-la.',
      ),
    })
    const usuario = userEvent.setup()
    abrir('/solicitacoes/s-1')

    await usuario.click(await screen.findByRole('button', { name: 'Aprovar' }))
    const formulario = screen.getByRole('form', { name: 'Aprovar' })
    await within(formulario).findByRole('option', { name: 'Dentro do orçamento' })
    await usuario.selectOptions(within(formulario).getByLabelText('Motivo'), 'm-a')
    await usuario.click(within(formulario).getByRole('button', { name: 'Confirmar' }))

    expect(await within(formulario).findByRole('alert')).toHaveTextContent(
      'Quem enviou a solicitação não pode decidi-la.',
    )
  })

  it('retira com uma confirmação', async () => {
    const chamadas = simularApi({
      ...comAcoes(['retirar']),
      'POST /aprovacoes/solicitacoes/s-1/retirar/': DETALHE,
    })
    const usuario = userEvent.setup()
    abrir('/solicitacoes/s-1')

    await usuario.click(await screen.findByRole('button', { name: 'Retirar' }))
    const formulario = screen.getByRole('form', { name: 'Retirar' })
    await usuario.click(within(formulario).getByRole('button', { name: 'Confirmar' }))

    await waitFor(() => expect(postado(chamadas, 'retirar')?.corpo).toEqual({}))
  })

  it('cancela com motivo e reabre com justificativa', async () => {
    const chamadas = simularApi({
      ...comAcoes(['reabrir', 'cancelar']),
      'POST /aprovacoes/solicitacoes/s-1/cancelar/': DETALHE,
      'POST /aprovacoes/solicitacoes/s-1/reabrir/': DETALHE,
    })
    const usuario = userEvent.setup()
    abrir('/solicitacoes/s-1')

    await usuario.click(await screen.findByRole('button', { name: 'Cancelar' }))
    const cancelar = screen.getByRole('form', { name: 'Cancelar' })
    await usuario.type(within(cancelar).getByLabelText('Motivo do cancelamento'), 'Não precisa mais')
    await usuario.click(within(cancelar).getByRole('button', { name: 'Confirmar' }))
    await waitFor(() => expect(postado(chamadas, 'cancelar')?.corpo).toEqual({ motivo: 'Não precisa mais' }))

    await usuario.click(await screen.findByRole('button', { name: 'Reabrir' }))
    const reabrir = screen.getByRole('form', { name: 'Reabrir' })
    await usuario.type(within(reabrir).getByLabelText('Justificativa'), 'Agora tem caixa')
    await usuario.click(within(reabrir).getByRole('button', { name: 'Confirmar' }))
    await waitFor(() =>
      expect(postado(chamadas, 'reabrir')?.corpo).toEqual({ justificativa: 'Agora tem caixa' }),
    )
  })

  it('reenvia o conteúdo editado, que começa com o da versão atual', async () => {
    const chamadas = simularApi({
      ...comAcoes(['reenviar']),
      'POST /aprovacoes/solicitacoes/s-1/reenviar/': DETALHE,
    })
    const usuario = userEvent.setup()
    abrir('/solicitacoes/s-1')

    await usuario.click(await screen.findByRole('button', { name: 'Reenviar' }))
    const formulario = screen.getByRole('form', { name: 'Reenviar' })
    const campo = within(formulario).getByLabelText('Conteúdo (JSON)') as HTMLTextAreaElement
    expect(JSON.parse(campo.value)).toEqual({ descricao: 'Bolas oficiais' })
    await usuario.clear(campo)
    await usuario.type(campo, '{{"descricao": "Bolas e coletes"}')
    await usuario.click(within(formulario).getByRole('button', { name: 'Confirmar' }))

    await waitFor(() =>
      expect(postado(chamadas, 'reenviar')?.corpo).toEqual({ conteudo: { descricao: 'Bolas e coletes' } }),
    )
  })

  it('conteúdo que não é JSON não é enviado', async () => {
    const chamadas = simularApi(comAcoes(['editar']))
    const usuario = userEvent.setup()
    abrir('/solicitacoes/s-1')

    await usuario.click(await screen.findByRole('button', { name: 'Editar' }))
    const formulario = screen.getByRole('form', { name: 'Editar' })
    const campo = within(formulario).getByLabelText('Conteúdo (JSON)')
    await usuario.clear(campo)
    await usuario.type(campo, 'não é json')
    await usuario.click(within(formulario).getByRole('button', { name: 'Confirmar' }))

    const alerta = await within(formulario).findByRole('alert')
    expect(alerta).toHaveTextContent('O conteúdo precisa ser um JSON válido.')
    expect(postado(chamadas, 'editar')).toBeUndefined()
  })
})

const TIPOS_DE_DECISAO = [
  { codigo: 'solicitacao.aprovar', nome: 'Aprovar solicitação' },
  { codigo: 'solicitacao.recusar', nome: 'Recusar solicitação' },
]

function motivosDoAdmin(lista: unknown) {
  return {
    ...COMO_ADMIN,
    'GET /aprovacoes/tipos-de-decisao/': TIPOS_DE_DECISAO,
    'GET /aprovacoes/motivos/?todos=1': lista,
  }
}

const ATIVO = {
  id: 'm-1',
  tipo_de_decisao: 'solicitacao.aprovar',
  texto: 'Dentro do orçamento',
  ativo: true,
}
const INATIVO = { id: 'm-2', tipo_de_decisao: 'solicitacao.recusar', texto: 'Pedido duplicado', ativo: false }

describe('motivos de decisão (CA-29 a CA-31)', () => {
  it('o admin vê o atalho e os motivos por tipo de decisão, com os inativos marcados', async () => {
    simularApi(motivosDoAdmin([ATIVO, INATIVO]))

    abrir('/admin/motivos')

    const menu = await screen.findByRole('navigation', { name: 'Aprovações' })
    const atalho = within(menu).getByRole('link', { name: 'Motivos de decisão' })
    expect(atalho).toHaveAttribute('href', '/admin/motivos')
    const aprovar = await screen.findByRole('region', { name: 'Aprovar solicitação' })
    expect(within(aprovar).getByText('Dentro do orçamento')).toBeInTheDocument()
    expect(within(aprovar).getByRole('button', { name: 'Desativar' })).toBeInTheDocument()
    const recusar = screen.getByRole('region', { name: 'Recusar solicitação' })
    expect(within(recusar).getByText('Pedido duplicado')).toBeInTheDocument()
    expect(within(recusar).getByText('Inativo')).toBeInTheDocument()
    expect(within(recusar).getByRole('button', { name: 'Reativar' })).toBeInTheDocument()
  })

  it('cria um motivo no tipo escolhido e recarrega a lista', async () => {
    let consultas = 0
    const chamadas = simularApi({
      ...motivosDoAdmin(() => (consultas++ === 0 ? [] : [ATIVO])),
      'POST /aprovacoes/motivos/': [201, ATIVO],
    })
    const usuario = userEvent.setup()
    abrir('/admin/motivos')

    await screen.findByRole('region', { name: 'Aprovar solicitação' })
    await usuario.selectOptions(screen.getByLabelText('Tipo de decisão'), 'solicitacao.aprovar')
    await usuario.type(screen.getByLabelText('Novo motivo'), 'Dentro do orçamento')
    await usuario.click(screen.getByRole('button', { name: 'Criar' }))

    expect(await screen.findByText('Dentro do orçamento')).toBeInTheDocument()
    expect(chamadas.find((c) => c.metodo === 'POST')?.corpo).toEqual({
      tipo_de_decisao: 'solicitacao.aprovar',
      texto: 'Dentro do orçamento',
    })
  })

  it('edita o texto, desativa e reativa', async () => {
    const chamadas = simularApi({
      ...motivosDoAdmin([ATIVO, INATIVO]),
      'POST /aprovacoes/motivos/m-1/editar/': { ...ATIVO, texto: 'Cabe no orçamento' },
      'POST /aprovacoes/motivos/m-1/desativar/': { ...ATIVO, ativo: false },
      'POST /aprovacoes/motivos/m-2/reativar/': { ...INATIVO, ativo: true },
    })
    const usuario = userEvent.setup()
    abrir('/admin/motivos')

    const aprovar = await screen.findByRole('region', { name: 'Aprovar solicitação' })
    await usuario.click(within(aprovar).getByRole('button', { name: 'Editar' }))
    const campo = within(aprovar).getByLabelText('Texto do motivo')
    await usuario.clear(campo)
    await usuario.type(campo, 'Cabe no orçamento')
    await usuario.click(within(aprovar).getByRole('button', { name: 'Salvar' }))
    await usuario.click(await within(aprovar).findByRole('button', { name: 'Desativar' }))
    const recusar = screen.getByRole('region', { name: 'Recusar solicitação' })
    await usuario.click(within(recusar).getByRole('button', { name: 'Reativar' }))

    await waitFor(() =>
      expect(chamadas.filter((c) => c.metodo === 'POST').map((c) => [c.caminho, c.corpo])).toEqual([
        ['/aprovacoes/motivos/m-1/editar/', { texto: 'Cabe no orçamento' }],
        ['/aprovacoes/motivos/m-1/desativar/', {}],
        ['/aprovacoes/motivos/m-2/reativar/', {}],
      ]),
    )
  })

  it('mostra o motivo repetido', async () => {
    simularApi({
      ...motivosDoAdmin([ATIVO]),
      'POST /aprovacoes/motivos/': erro(409, 'MOTIVO_JA_EXISTE', 'Já existe um motivo com este texto.'),
    })
    const usuario = userEvent.setup()
    abrir('/admin/motivos')

    await screen.findByRole('region', { name: 'Aprovar solicitação' })
    await usuario.selectOptions(screen.getByLabelText('Tipo de decisão'), 'solicitacao.aprovar')
    await usuario.type(screen.getByLabelText('Novo motivo'), 'dentro do orçamento')
    await usuario.click(screen.getByRole('button', { name: 'Criar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Já existe um motivo com este texto.')
  })

  it('quem não é admin não abre a tela nem vê o atalho', async () => {
    simularApi(COM_CARGO)

    abrir('/admin/motivos')

    const menu = await screen.findByRole('navigation', { name: 'Aprovações' })
    expect(within(menu).queryByRole('link', { name: 'Motivos de decisão' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Motivos de decisão' })).not.toBeInTheDocument()
  })
})
