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

const COMO_DIRETOR = { 'GET /acesso/sessao/': { usuario: DIRETOR }, ...SEM_GOOGLE }
const SEM_PERMISSAO = { cargo: null, setores: [], permissoes: [] }
const COMO_ADMIN = { 'GET /acesso/sessao/': { usuario: ADMIN }, ...SEM_GOOGLE }

const TESOUREIRO = { id: 'ca-1', nome: 'Tesoureiro', ativo: true }
const SECRETARIO = { id: 'ca-2', nome: 'Secretário', ativo: false }
const FINANCEIRO = { id: 's-1', nome: 'Financeiro', ativo: true }
const FUTEBOL = { id: 's-2', nome: 'Futebol', ativo: true }

const CATALOGO = [
  { codigo: 'convites.gerenciar', nome: 'Gerenciar convites', descricao: 'Gerar, listar e revogar convites.' },
  { codigo: 'acesso.total', nome: 'Acesso total', descricao: 'Todas as permissões do catálogo.' },
]

const CONCESSAO = {
  id: 'co-1',
  permissao: 'convites.gerenciar',
  alvo_tipo: 'CARGO',
  alvo: { id: 'ca-1', nome: 'Tesoureiro' },
  concedida_em: '2026-11-13T10:00:00-03:00',
  revogada_em: null,
}

function chamou(chamadas: Chamada[], metodo: string, caminho: string) {
  return chamadas.find((c) => c.metodo === metodo && c.caminho === caminho)
}

afterEach(() => {
  vi.unstubAllGlobals()
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
})

describe('menu do admin e página inicial (CA-26)', () => {
  it('o admin vê os atalhos de cargos, setores e permissões', async () => {
    simularApi(COMO_ADMIN)

    abrir('/')

    expect(await screen.findByRole('link', { name: 'Cargos' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Setores' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Permissões' })).toBeInTheDocument()
  })

  it('o diretor com cargo vê o próprio cargo, setores e permissões', async () => {
    simularApi({
      'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
      ...SEM_GOOGLE,
      'GET /permissoes/minhas/': {
        cargo: TESOUREIRO,
        setores: [FINANCEIRO, FUTEBOL],
        permissoes: [{ codigo: 'convites.gerenciar', nome: 'Gerenciar convites', origens: [] }],
      },
    })

    abrir('/')

    expect(await screen.findByText('Cargo: Tesoureiro')).toBeInTheDocument()
    expect(screen.getByText('Setores: Financeiro, Futebol')).toBeInTheDocument()
    expect(screen.getByText('Gerenciar convites')).toBeInTheDocument()
    expect(screen.queryByText(/aguarda a classificação/i)).not.toBeInTheDocument()
  })

  it('o diretor com cargo e sem permissão vê que ainda não tem nenhuma', async () => {
    simularApi({
      'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
      ...SEM_GOOGLE,
      'GET /permissoes/minhas/': { cargo: TESOUREIRO, setores: [], permissoes: [] },
    })

    abrir('/')

    expect(await screen.findByText('Nenhuma permissão concedida ainda.')).toBeInTheDocument()
    expect(screen.getByText('Setores: nenhum')).toBeInTheDocument()
  })

  it('o diretor sem cargo continua aguardando a classificação e não consulta as permissões', async () => {
    const chamadas = simularApi(COMO_DIRETOR)

    abrir('/')

    expect(await screen.findByText(/aguarda a classificação/i)).toBeInTheDocument()
    expect(chamou(chamadas, 'GET', '/permissoes/minhas/')).toBeUndefined()
  })

  it('mostra o erro quando as permissões não carregam', async () => {
    simularApi({
      'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
      ...SEM_GOOGLE,
      'GET /permissoes/minhas/': erro(500, 'INTERNAL_ERROR', 'falhou'),
    })

    abrir('/')

    expect(await screen.findByRole('alert')).toHaveTextContent('falhou')
  })

  it.each(['/admin/cargos', '/admin/setores', '/admin/permissoes', '/admin/usuarios/u-1'])(
    'o diretor que abre %s volta para a página inicial',
    async (caminho) => {
      simularApi({ ...COMO_DIRETOR, 'GET /permissoes/minhas/': SEM_PERMISSAO })

      abrir(caminho)

      expect(await screen.findByText(/aguarda a classificação/i)).toBeInTheDocument()
    },
  )
})

describe.each([
  ['cargos', 'Cargos', 'Novo cargo', 'cargo', '/admin/cargos'],
  ['setores', 'Setores', 'Novo setor', 'setor', '/admin/setores'],
])('%s', (rota, titulo, rotuloNovo, item, caminho) => {
  const base = `/permissoes/${rota}/`
  const ATIVO = { id: 'i-1', nome: 'Alfa', ativo: true }
  const INATIVO = { id: 'i-2', nome: 'Beta', ativo: false }
  const LISTA = { ...COMO_ADMIN, [`GET ${base}`]: [ATIVO, INATIVO] }

  it('lista com a situação de cada um', async () => {
    simularApi(LISTA)

    abrir(caminho)

    expect(await screen.findByRole('heading', { name: titulo })).toBeInTheDocument()
    await screen.findByText('Alfa')
    const linhas = screen.getAllByRole('row')
    expect(within(linhas[1]).getByText('Alfa')).toBeInTheDocument()
    expect(within(linhas[1]).getByText('Ativo')).toBeInTheDocument()
    expect(within(linhas[2]).getByText('Inativo')).toBeInTheDocument()
  })

  it('cria um novo e esvazia o campo', async () => {
    const chamadas = simularApi({ ...LISTA, [`POST ${base}`]: [201, { id: 'i-3', nome: 'Gama', ativo: true }] })
    abrir(caminho)

    await userEvent.type(await screen.findByLabelText(rotuloNovo), 'Gama')
    await userEvent.click(screen.getByRole('button', { name: 'Criar' }))

    await waitFor(() => expect(chamou(chamadas, 'POST', base)?.corpo).toEqual({ nome: 'Gama' }))
    await waitFor(() => expect(screen.getByLabelText(rotuloNovo)).toHaveValue(''))
  })

  it('mostra o erro de nome repetido', async () => {
    simularApi({ ...LISTA, [`POST ${base}`]: erro(409, 'NOME_EM_USO') })
    abrir(caminho)

    await userEvent.type(await screen.findByLabelText(rotuloNovo), 'alfa')
    await userEvent.click(screen.getByRole('button', { name: 'Criar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Já existe um item com este nome.')
  })

  it('renomeia', async () => {
    const chamadas = simularApi({ ...LISTA, [`POST ${base}i-1/renomear/`]: { ...ATIVO, nome: 'Alfa 2' } })
    abrir(caminho)
    const linha = (await screen.findByText('Alfa')).closest('tr')!

    await userEvent.click(within(linha).getByRole('button', { name: 'Renomear' }))
    const campo = within(linha).getByLabelText('Novo nome')
    await userEvent.clear(campo)
    await userEvent.type(campo, 'Alfa 2')
    await userEvent.click(within(linha).getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(chamou(chamadas, 'POST', `${base}i-1/renomear/`)?.corpo).toEqual({ nome: 'Alfa 2' }))
    expect(screen.queryByLabelText('Novo nome')).not.toBeInTheDocument()
  })

  it('cancela a renomeação sem chamar a API', async () => {
    const chamadas = simularApi(LISTA)
    abrir(caminho)
    const linha = (await screen.findByText('Alfa')).closest('tr')!

    await userEvent.click(within(linha).getByRole('button', { name: 'Renomear' }))
    await userEvent.click(within(linha).getByRole('button', { name: 'Cancelar' }))

    expect(chamadas.some((c) => c.metodo === 'POST')).toBe(false)
    expect(screen.getByText('Alfa')).toBeInTheDocument()
  })

  it('desativa um sem uso', async () => {
    const chamadas = simularApi({ ...LISTA, [`POST ${base}i-1/desativar/`]: { ...ATIVO, ativo: false } })
    abrir(caminho)
    const linha = (await screen.findByText('Alfa')).closest('tr')!

    await userEvent.click(within(linha).getByRole('button', { name: 'Desativar' }))

    await waitFor(() => expect(chamou(chamadas, 'POST', `${base}i-1/desativar/`)).toBeDefined())
  })

  it('CA-05: mostra quantos usuários impedem a desativação', async () => {
    const codigo = `${item.toUpperCase()}_EM_USO`
    simularApi({ ...LISTA, [`POST ${base}i-1/desativar/`]: erro(422, codigo, 'mensagem da API', { usuarios: 2 }) })
    abrir(caminho)
    const linha = (await screen.findByText('Alfa')).closest('tr')!

    await userEvent.click(within(linha).getByRole('button', { name: 'Desativar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      `2 usuários ativos têm este ${item}. Reclassifique-os antes de desativar.`,
    )
  })

  it('usa o singular quando é um usuário só', async () => {
    const codigo = `${item.toUpperCase()}_EM_USO`
    simularApi({ ...LISTA, [`POST ${base}i-1/desativar/`]: erro(422, codigo, 'mensagem da API', { usuarios: 1 }) })
    abrir(caminho)
    const linha = (await screen.findByText('Alfa')).closest('tr')!

    await userEvent.click(within(linha).getByRole('button', { name: 'Desativar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(`1 usuário ativo tem este ${item}.`)
  })

  it('reativa um inativo', async () => {
    const chamadas = simularApi({ ...LISTA, [`POST ${base}i-2/reativar/`]: { ...INATIVO, ativo: true } })
    abrir(caminho)
    const linha = (await screen.findByText('Beta')).closest('tr')!

    await userEvent.click(within(linha).getByRole('button', { name: 'Reativar' }))

    await waitFor(() => expect(chamou(chamadas, 'POST', `${base}i-2/reativar/`)).toBeDefined())
  })
})

describe('permissões', () => {
  const ROTAS = {
    ...COMO_ADMIN,
    'GET /permissoes/catalogo/': CATALOGO,
    'GET /permissoes/concessoes/': [CONCESSAO],
    'GET /permissoes/cargos/': [TESOUREIRO, SECRETARIO],
    'GET /permissoes/setores/': [FINANCEIRO],
    'GET /acesso/usuarios/': [ADMIN, DIRETOR],
  }

  it('CA-13: mostra o catálogo com a descrição e as concessões ativas', async () => {
    simularApi(ROTAS)

    abrir('/admin/permissoes')

    expect(await screen.findByText(/Gerar, listar e revogar convites\./)).toBeInTheDocument()
    expect(screen.getByText(/Todas as permissões do catálogo\./)).toBeInTheDocument()
    const linha = (await screen.findByText('Cargo: Tesoureiro')).closest('tr')!
    expect(within(linha).getByText('Gerenciar convites')).toBeInTheDocument()
  })

  it('concede a um cargo ativo', async () => {
    const chamadas = simularApi({ ...ROTAS, 'POST /permissoes/concessoes/': [201, { ...CONCESSAO, id: 'co-2' }] })
    abrir('/admin/permissoes')

    await userEvent.selectOptions(await screen.findByLabelText('Permissão'), 'convites.gerenciar')
    const alvos = screen.getByLabelText('Cargo')
    expect(within(alvos).queryByRole('option', { name: 'Secretário' })).not.toBeInTheDocument()
    await userEvent.selectOptions(alvos, 'ca-1')
    await userEvent.click(screen.getByRole('button', { name: 'Conceder' }))

    await waitFor(() =>
      expect(chamou(chamadas, 'POST', '/permissoes/concessoes/')?.corpo).toEqual({
        permissao: 'convites.gerenciar',
        alvo_tipo: 'CARGO',
        alvo_id: 'ca-1',
      }),
    )
    expect(screen.queryByText('Esta concessão já existia.')).not.toBeInTheDocument()
  })

  it('concede a um setor e a uma pessoa ativa', async () => {
    const chamadas = simularApi({ ...ROTAS, 'POST /permissoes/concessoes/': [201, { ...CONCESSAO, id: 'co-2' }] })
    abrir('/admin/permissoes')
    await userEvent.selectOptions(await screen.findByLabelText('Permissão'), 'convites.gerenciar')

    await userEvent.selectOptions(screen.getByLabelText('Conceder a'), 'SETOR')
    await userEvent.selectOptions(screen.getByLabelText('Setor'), 's-1')
    await userEvent.click(screen.getByRole('button', { name: 'Conceder' }))
    await userEvent.selectOptions(screen.getByLabelText('Conceder a'), 'USUARIO')
    await userEvent.selectOptions(screen.getByLabelText('Usuário'), 'u-1')
    await userEvent.click(screen.getByRole('button', { name: 'Conceder' }))

    await waitFor(() => expect(chamadas.filter((c) => c.metodo === 'POST').map((c) => c.corpo)).toEqual([
      { permissao: 'convites.gerenciar', alvo_tipo: 'SETOR', alvo_id: 's-1' },
      { permissao: 'convites.gerenciar', alvo_tipo: 'USUARIO', alvo_id: 'u-1' },
    ]))
  })

  it('CA-23: avisa que a concessão já existia', async () => {
    simularApi({ ...ROTAS, 'POST /permissoes/concessoes/': CONCESSAO })
    abrir('/admin/permissoes')

    await userEvent.selectOptions(await screen.findByLabelText('Permissão'), 'convites.gerenciar')
    await userEvent.selectOptions(screen.getByLabelText('Cargo'), 'ca-1')
    await userEvent.click(screen.getByRole('button', { name: 'Conceder' }))

    expect(await screen.findByText('Esta concessão já existia.')).toBeInTheDocument()
  })

  it('mostra o erro de acesso total para um cargo', async () => {
    simularApi({ ...ROTAS, 'POST /permissoes/concessoes/': erro(422, 'ACESSO_TOTAL_SO_PARA_USUARIO') })
    abrir('/admin/permissoes')

    await userEvent.selectOptions(await screen.findByLabelText('Permissão'), 'acesso.total')
    await userEvent.selectOptions(screen.getByLabelText('Cargo'), 'ca-1')
    await userEvent.click(screen.getByRole('button', { name: 'Conceder' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('O acesso total só pode ser concedido a uma pessoa.')
  })

  it('revoga uma concessão', async () => {
    const chamadas = simularApi({
      ...ROTAS,
      'POST /permissoes/concessoes/co-1/revogar/': { ...CONCESSAO, revogada_em: '2026-11-13T11:00:00-03:00' },
    })
    abrir('/admin/permissoes')
    const linha = (await screen.findByText('Cargo: Tesoureiro')).closest('tr')!

    await userEvent.click(within(linha).getByRole('button', { name: 'Revogar' }))

    await waitFor(() => expect(chamou(chamadas, 'POST', '/permissoes/concessoes/co-1/revogar/')).toBeDefined())
  })

  it('mostra o erro de uma concessão já revogada', async () => {
    simularApi({ ...ROTAS, 'POST /permissoes/concessoes/co-1/revogar/': erro(422, 'CONCESSAO_JA_REVOGADA') })
    abrir('/admin/permissoes')
    const linha = (await screen.findByText('Cargo: Tesoureiro')).closest('tr')!

    await userEvent.click(within(linha).getByRole('button', { name: 'Revogar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Esta concessão já foi revogada.')
  })
})

describe('usuário', () => {
  const DETALHE = {
    cargo: TESOUREIRO,
    setores: [FINANCEIRO],
    permissoes: [
      {
        codigo: 'convites.gerenciar',
        nome: 'Gerenciar convites',
        origens: [
          { tipo: 'CARGO', id: 'ca-1', nome: 'Tesoureiro' },
          { tipo: 'SETOR', id: 's-1', nome: 'Financeiro' },
          { tipo: 'INDIVIDUAL', id: null, nome: null },
        ],
      },
    ],
  }
  const SEM_CLASSIFICACAO = { cargo: null, setores: [], permissoes: [] }
  const HISTORICO = [
    { acao: 'USUARIO_CLASSIFICADO', ator: { id: 'u-0', nome: 'Ana Admin' }, justificativa: '', criado_em: '2026-11-13T10:00:00-03:00' },
    { acao: 'ADMIN_CRIADO_POR_COMANDO', ator: null, justificativa: '', criado_em: '2026-11-12T10:00:00-03:00' },
  ]

  function rotas(detalhe: unknown, extras: Record<string, unknown> = {}, usuario = DIRETOR) {
    return {
      ...COMO_ADMIN,
      'GET /permissoes/usuarios/u-1/': detalhe,
      'GET /permissoes/cargos/': [TESOUREIRO, SECRETARIO, { id: 'ca-3', nome: 'Diretor', ativo: true }],
      'GET /permissoes/setores/': [FINANCEIRO, FUTEBOL, { id: 's-3', nome: 'Antigo', ativo: false }],
      'GET /acesso/usuarios/': [ADMIN, usuario],
      'GET /permissoes/concessoes/': [],
      'GET /acesso/usuarios/u-1/historico/': HISTORICO,
      ...extras,
    }
  }

  it('CA-25: mostra cada permissão com todas as origens', async () => {
    simularApi(rotas(DETALHE))

    abrir('/admin/usuarios/u-1')

    expect(await screen.findByRole('heading', { name: 'Bia Diretora' })).toBeInTheDocument()
    expect(
      screen.getByText('pelo cargo Tesoureiro; pelo setor Financeiro; concedida a ele', { exact: false }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Cargo')).toHaveValue('ca-1')
    expect(screen.getByRole('checkbox', { name: 'Financeiro' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Futebol' })).not.toBeChecked()
    expect(screen.queryByRole('checkbox', { name: 'Antigo' })).not.toBeInTheDocument()
  })

  it('o usuário sem permissão mostra que não tem nenhuma', async () => {
    simularApi(rotas(SEM_CLASSIFICACAO))

    abrir('/admin/usuarios/u-1')

    expect(await screen.findByText('Nenhuma permissão.')).toBeInTheDocument()
    expect(screen.getByLabelText('Cargo')).toHaveValue('')
  })

  it('CA-07: classifica com um cargo e dois setores', async () => {
    const chamadas = simularApi(rotas(SEM_CLASSIFICACAO, { 'PUT /permissoes/usuarios/u-1/classificacao/': DETALHE }))
    abrir('/admin/usuarios/u-1')

    await userEvent.selectOptions(await screen.findByLabelText('Cargo'), 'ca-1')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Financeiro' }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Futebol' }))
    await userEvent.click(screen.getByRole('button', { name: 'Salvar classificação' }))

    await waitFor(() =>
      expect(chamou(chamadas, 'PUT', '/permissoes/usuarios/u-1/classificacao/')?.corpo).toEqual({
        cargo_id: 'ca-1',
        setor_ids: ['s-1', 's-2'],
      }),
    )
  })

  it('CA-09: tirar o cargo envia cargo nulo e nenhum setor', async () => {
    const chamadas = simularApi(rotas(DETALHE, { 'PUT /permissoes/usuarios/u-1/classificacao/': SEM_CLASSIFICACAO }))
    abrir('/admin/usuarios/u-1')

    await userEvent.selectOptions(await screen.findByLabelText('Cargo'), '')
    expect(screen.getByRole('checkbox', { name: 'Financeiro' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Salvar classificação' }))

    await waitFor(() =>
      expect(chamou(chamadas, 'PUT', '/permissoes/usuarios/u-1/classificacao/')?.corpo).toEqual({
        cargo_id: null,
        setor_ids: [],
      }),
    )
  })

  it('mostra o erro de cargo inativo', async () => {
    simularApi(rotas(DETALHE, { 'PUT /permissoes/usuarios/u-1/classificacao/': erro(422, 'CARGO_INATIVO') }))
    abrir('/admin/usuarios/u-1')

    await userEvent.click(await screen.findByRole('button', { name: 'Salvar classificação' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Este cargo está inativo.')
  })

  it('CA-10: usuário inativo não tem formulário de classificação', async () => {
    simularApi(rotas(SEM_CLASSIFICACAO, {}, { ...DIRETOR, situacao: 'INATIVO' }))

    abrir('/admin/usuarios/u-1')

    expect(await screen.findByText('Só usuário ativo pode ser classificado.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Salvar classificação' })).not.toBeInTheDocument()
  })

  it('concede o acesso total', async () => {
    const chamadas = simularApi(rotas(DETALHE, { 'POST /permissoes/concessoes/': [201, CONCESSAO] }))
    abrir('/admin/usuarios/u-1')

    expect(await screen.findByText('Acesso total: não concedido.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Conceder acesso total' }))

    await waitFor(() =>
      expect(chamou(chamadas, 'POST', '/permissoes/concessoes/')?.corpo).toEqual({
        permissao: 'acesso.total',
        alvo_tipo: 'USUARIO',
        alvo_id: 'u-1',
      }),
    )
  })

  it('revoga o acesso total que a pessoa já tem', async () => {
    const total = { ...CONCESSAO, id: 'co-9', permissao: 'acesso.total', alvo_tipo: 'USUARIO', alvo: { id: 'u-1', nome: 'Bia Diretora' } }
    const chamadas = simularApi(
      rotas(DETALHE, {
        'GET /permissoes/concessoes/': [CONCESSAO, total],
        'POST /permissoes/concessoes/co-9/revogar/': total,
      }),
    )
    abrir('/admin/usuarios/u-1')

    expect(await screen.findByText('Acesso total: concedido.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Revogar acesso total' }))

    await waitFor(() => expect(chamou(chamadas, 'POST', '/permissoes/concessoes/co-9/revogar/')).toBeDefined())
  })

  it('CA-30: mostra o histórico com o nome de quem agiu e "Sistema" para o que não tem ator', async () => {
    simularApi(rotas(DETALHE))

    abrir('/admin/usuarios/u-1')

    await screen.findByText('Admin criado no servidor')
    const [, primeira, segunda] = screen.getAllByRole('row')
    expect(within(primeira).getByText('Classificado')).toBeInTheDocument()
    expect(within(primeira).getByText('Ana Admin')).toBeInTheDocument()
    expect(within(segunda).getByText('Admin criado no servidor')).toBeInTheDocument()
    expect(within(segunda).getByText('Sistema')).toBeInTheDocument()
  })

  it('mostra o erro quando o usuário não existe', async () => {
    simularApi(rotas(erro(404, 'NOT_FOUND')))

    abrir('/admin/usuarios/u-1')

    expect(await screen.findByRole('alert')).toHaveTextContent('Não encontrado.')
  })

  it('a lista de usuários leva ao detalhe', async () => {
    simularApi({ ...COMO_ADMIN, 'GET /acesso/usuarios/': [ADMIN, DIRETOR] })

    abrir('/admin/usuarios')

    expect(await screen.findByRole('link', { name: 'Bia Diretora' })).toHaveAttribute('href', '/admin/usuarios/u-1')
  })
})

describe('convites para quem tem a permissão convites.gerenciar (CA-27)', () => {
  const PODE_CONVIDAR = {
    codigo: 'convites.gerenciar',
    nome: 'Gerenciar convites',
    origens: [{ tipo: 'INDIVIDUAL', id: null, nome: null }],
  }
  const COM_PERMISSAO = { ...SEM_PERMISSAO, permissoes: [PODE_CONVIDAR] }
  const CONVITE = {
    id: 'c-1',
    situacao: 'ATIVO',
    gerado_por: { id: 'u-1', nome: 'Bia Diretora' },
    gerado_em: '2026-11-12T10:00:00-03:00',
    expira_em: '2026-11-13T10:00:00-03:00',
    usado_em: null,
    revogado_em: null,
  }
  const COMO_CONVIDADOR = { ...COMO_DIRETOR, 'GET /permissoes/minhas/': COM_PERMISSAO }
  const COM_CARGO = { 'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } }, ...SEM_GOOGLE }

  it('mostra o atalho de convites e nenhum de usuários', async () => {
    simularApi({
      ...COM_CARGO,
      'GET /permissoes/minhas/': { ...COM_PERMISSAO, cargo: TESOUREIRO },
    })

    abrir('/')

    expect(await screen.findByRole('link', { name: 'Convites' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Usuários' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Cargos' })).not.toBeInTheDocument()
  })

  it('o diretor com cargo e sem a permissão não vê o atalho de convites', async () => {
    simularApi({ ...COM_CARGO, 'GET /permissoes/minhas/': { ...SEM_PERMISSAO, cargo: TESOUREIRO } })

    abrir('/')

    expect(await screen.findByText('Cargo: Tesoureiro')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Convites' })).not.toBeInTheDocument()
  })

  it('quem tem a permissão por concessão individual, sem cargo, abre os convites pelo endereço', async () => {
    simularApi({ ...COMO_CONVIDADOR, 'GET /acesso/convites/': [] })

    abrir('/admin/convites')

    expect(await screen.findByRole('heading', { name: 'Convites' })).toBeInTheDocument()
  })

  it('lista, gera, regenera e revoga convites', async () => {
    const chamadas = simularApi({
      ...COMO_CONVIDADOR,
      'GET /acesso/convites/': [CONVITE],
      'POST /acesso/convites/': [201, { ...CONVITE, id: 'c-2', link: 'https://clube.exemplo/convite/novo' }],
      'POST /acesso/convites/c-1/regenerar/': [201, { ...CONVITE, id: 'c-3', link: 'https://clube.exemplo/convite/outro' }],
      'POST /acesso/convites/c-1/revogar/': { ...CONVITE, situacao: 'REVOGADO' },
    })

    abrir('/admin/convites')

    expect(await screen.findByRole('heading', { name: 'Convites' })).toBeInTheDocument()
    await screen.findByText('Bia Diretora')
    await userEvent.click(screen.getByRole('button', { name: 'Gerar convite' }))
    expect(await screen.findByDisplayValue('https://clube.exemplo/convite/novo')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Regenerar' }))
    expect(await screen.findByDisplayValue('https://clube.exemplo/convite/outro')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Revogar' }))
    await waitFor(() => expect(chamou(chamadas, 'POST', '/acesso/convites/c-1/revogar/')).toBeDefined())
  })

  it('a lista de usuários continua só do admin', async () => {
    const chamadas = simularApi(COMO_CONVIDADOR)

    abrir('/admin/usuarios')

    expect(await screen.findByText(/aguarda a classificação/i)).toBeInTheDocument()
    expect(chamou(chamadas, 'GET', '/acesso/usuarios/')).toBeUndefined()
  })

  it('o diretor sem a permissão que abre os convites volta para a página inicial', async () => {
    const chamadas = simularApi({ ...COMO_DIRETOR, 'GET /permissoes/minhas/': SEM_PERMISSAO })

    abrir('/admin/convites')

    expect(await screen.findByText(/aguarda a classificação/i)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Convites' })).not.toBeInTheDocument()
    expect(chamou(chamadas, 'GET', '/acesso/convites/')).toBeUndefined()
  })

  it('volta para a página inicial quando as permissões não carregam', async () => {
    simularApi({ ...COMO_DIRETOR, 'GET /permissoes/minhas/': erro(500, 'INTERNAL_ERROR') })

    abrir('/admin/convites')

    expect(await screen.findByText(/aguarda a classificação/i)).toBeInTheDocument()
  })

  it('o admin continua abrindo os convites sem consultar as permissões', async () => {
    const chamadas = simularApi({ ...COMO_ADMIN, 'GET /acesso/convites/': [] })

    abrir('/admin/convites')

    expect(await screen.findByRole('heading', { name: 'Convites' })).toBeInTheDocument()
    expect(chamou(chamadas, 'GET', '/permissoes/minhas/')).toBeUndefined()
  })
})
