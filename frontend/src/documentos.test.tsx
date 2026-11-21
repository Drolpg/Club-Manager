import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import App from './App'
import { ADMIN, DIRETOR, SEM_GOOGLE, erro, simularApi } from './test/api'

const BIA = { id: 'u-1', nome: 'Bia Diretora' }
const CAIO = { id: 'u-2', nome: 'Caio Autor' }
const RESUMO = { 'GET /notificacoes/resumo/': { nao_lidas: 0, mais_recente_id: null } }
const LISTA = 'GET /comunicacao/documentos/'
const CATEGORIAS = [
  { id: 'c-1', nome: 'Institucional' },
  { id: 'c-2', nome: 'Financeiro' },
]

function comPermissoes(...codigos: string[]) {
  return {
    'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
    'GET /permissoes/minhas/': {
      cargo: { id: 'ca-1', nome: 'Diretor', ativo: true },
      setores: [],
      permissoes: codigos.map((codigo) => ({ codigo, nome: codigo, origens: [] })),
    },
    ...SEM_GOOGLE,
    ...RESUMO,
  }
}

const SESSAO = comPermissoes()
const COMO_ADMIN = { 'GET /acesso/sessao/': { usuario: ADMIN }, ...SEM_GOOGLE, ...RESUMO }
const CATEGORIAS_ATIVAS = CATEGORIAS.map((c) => ({ ...c, ativa: true }))

function abrir(caminho: string) {
  return render(
    <MemoryRouter initialEntries={[caminho]}>
      <App />
    </MemoryRouter>,
  )
}

function documento(id: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    tipo: 'DOCUMENTO',
    titulo: `Documento ${id}`,
    descricao: '',
    categoria: CATEGORIAS[0],
    data_da_reuniao: null,
    enviado_por: BIA,
    situacao: 'VIGENTE',
    versao_atual: 1,
    arquivo: { nome: 'estatuto.pdf', mime: 'application/pdf', tamanho: 1024 },
    criado_em: '2026-11-20T10:00:00-03:00',
    acoes: [],
    ...extra,
  }
}

function detalhe(id: string, extra: Record<string, unknown> = {}) {
  return {
    ...documento(id),
    versoes: [
      {
        numero: 1,
        motivo: '',
        enviada_por: BIA,
        enviada_em: '2026-11-20T10:00:00-03:00',
        situacao: 'VIGENTE',
        nome: 'estatuto.pdf',
        mime: 'application/pdf',
        tamanho: 1024,
      },
    ],
    comunicados: [],
    ...extra,
  }
}

const PDF = () => new File(['%PDF-1.4'], 'estatuto.pdf', { type: 'application/pdf' })

describe('menu e rotas de documentos', () => {
  it('quem lê gestão vê o link Documentos, e só o admin vê Categorias de documento', async () => {
    simularApi({ ...SESSAO, [LISTA]: { itens: [], tem_mais: false }, 'GET /comunicacao/categorias/': [] })
    const { unmount } = abrir('/documentos')
    const menu = await screen.findByRole('navigation', { name: 'Comunicação' })
    expect(within(menu).getByRole('link', { name: 'Documentos' })).toHaveAttribute('href', '/documentos')
    expect(within(menu).queryByRole('link', { name: 'Categorias de documento' })).not.toBeInTheDocument()
    unmount()

    simularApi({ ...COMO_ADMIN, [LISTA]: { itens: [], tem_mais: false }, 'GET /comunicacao/categorias/': [] })
    abrir('/documentos')
    const menuDoAdmin = await screen.findByRole('navigation', { name: 'Comunicação' })
    expect(within(menuDoAdmin).getByRole('link', { name: 'Categorias de documento' })).toHaveAttribute(
      'href',
      '/admin/categorias-de-documento',
    )
  })

  it('a tela de categorias é só do admin', async () => {
    simularApi({ ...SESSAO, 'GET /comunicacao/categorias/?todas=1': [] })

    abrir('/admin/categorias-de-documento')

    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Categorias de documento' })).toBeNull())
  })
})

describe('lista de documentos', () => {
  const ROTAS = (extra: Record<string, unknown> = {}) => ({
    ...SESSAO,
    'GET /comunicacao/categorias/': CATEGORIAS_ATIVAS,
    ...extra,
  })

  it('mostra tipo, categoria, versão, quem enviou e o download da vigente', async () => {
    simularApi(
      ROTAS({
        [LISTA]: {
          itens: [
            documento('d1', { versao_atual: 2 }),
            documento('d2', {
              tipo: 'ATA',
              titulo: 'Ata de outubro',
              categoria: null,
              data_da_reuniao: '2026-10-30',
            }),
          ],
          tem_mais: false,
        },
      }),
    )

    abrir('/documentos')

    const item = await screen.findByRole('article', { name: 'Documento d1' })
    expect(within(item).getByText(/Institucional/)).toBeInTheDocument()
    expect(within(item).getByText(/versão 2/i)).toBeInTheDocument()
    expect(within(item).getByText(/Bia Diretora/)).toBeInTheDocument()
    expect(within(item).getByRole('link', { name: 'Baixar' })).toHaveAttribute(
      'href',
      '/api/v1/comunicacao/documentos/d1/arquivo/',
    )
    expect(within(item).getByRole('link', { name: 'Documento d1' })).toHaveAttribute('href', '/documentos/d1')
    const ata = screen.getByRole('article', { name: 'Ata de outubro' })
    expect(within(ata).getByText(/^Ata ·/)).toBeInTheDocument()
    expect(within(ata).getByText(/30\/10\/2026/)).toBeInTheDocument()
  })

  it.each([
    ['Categoria', 'c-2', '?categoria_id=c-2'],
    ['Tipo', 'ATA', '?tipo=ATA'],
  ])('o filtro %s refaz a consulta', async (rotulo, valor, consulta) => {
    const chamadas = simularApi(
      ROTAS({
        [LISTA]: { itens: [documento('d1')], tem_mais: false },
        [`${LISTA}${consulta}`]: { itens: [documento('d9', { titulo: 'Filtrado' })], tem_mais: false },
      }),
    )
    const user = userEvent.setup()

    abrir('/documentos')
    await screen.findByRole('article', { name: 'Documento d1' })
    await user.selectOptions(screen.getByLabelText(rotulo), valor)

    expect(await screen.findByRole('article', { name: 'Filtrado' })).toBeInTheDocument()
    expect(chamadas.map((c) => c.caminho)).toContain(`/comunicacao/documentos/${consulta}`)
  })

  it('os filtros de título e de arquivados refazem a consulta', async () => {
    const chamadas = simularApi(
      ROTAS({
        [LISTA]: { itens: [documento('d1')], tem_mais: false },
        [`${LISTA}?titulo=est`]: { itens: [documento('d3', { titulo: 'Estatuto' })], tem_mais: false },
        [`${LISTA}?arquivados=1`]: {
          itens: [documento('d4', { titulo: 'Antigo', situacao: 'ARQUIVADO' })],
          tem_mais: false,
        },
      }),
    )
    const user = userEvent.setup()

    abrir('/documentos')
    await screen.findByRole('article', { name: 'Documento d1' })
    await user.click(screen.getByLabelText('Título'))
    await user.paste('est')
    expect(await screen.findByRole('article', { name: 'Estatuto' })).toBeInTheDocument()
    await user.clear(screen.getByLabelText('Título'))
    await user.click(screen.getByLabelText('Arquivados'))

    const antigo = await screen.findByRole('article', { name: 'Antigo' })
    expect(within(antigo).getByText(/Arquivado/)).toBeInTheDocument()
    expect(chamadas.map((c) => c.caminho)).toContain('/comunicacao/documentos/?arquivados=1')
  })

  it('carrega mais pelo cursor do último', async () => {
    const chamadas = simularApi(
      ROTAS({
        [LISTA]: { itens: [documento('d2')], tem_mais: true },
        [`${LISTA}?antes=d2`]: { itens: [documento('d1')], tem_mais: false },
      }),
    )
    const user = userEvent.setup()

    abrir('/documentos')
    await user.click(await screen.findByRole('button', { name: 'Carregar mais' }))

    expect(await screen.findByRole('article', { name: 'Documento d1' })).toBeInTheDocument()
    expect(chamadas.map((c) => c.caminho)).toContain('/comunicacao/documentos/?antes=d2')
  })

  it('sem permissão de enviar nem de registrar ata, não há formulário de envio', async () => {
    simularApi(ROTAS({ [LISTA]: { itens: [], tem_mais: false } }))

    abrir('/documentos')

    await screen.findByText('Nenhum documento encontrado.')
    expect(screen.queryByRole('form', { name: 'Enviar documento' })).not.toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Registrar ata' })).not.toBeInTheDocument()
  })
})

describe('envio de documento e de ata', () => {
  it('mostra o aviso de dado pessoal e envia título, descrição, categoria e arquivo', async () => {
    const chamadas = simularApi({
      ...comPermissoes('comunicacao.enviar_documentos'),
      'GET /comunicacao/categorias/': CATEGORIAS_ATIVAS,
      [LISTA]: { itens: [], tem_mais: false },
      'POST /comunicacao/documentos/': [201, detalhe('d7', { titulo: 'Estatuto novo' })],
      'GET /comunicacao/documentos/d7/': detalhe('d7', { titulo: 'Estatuto novo' }),
    })
    const user = userEvent.setup()

    abrir('/documentos')

    const formulario = await screen.findByRole('form', { name: 'Enviar documento' })
    expect(within(formulario).getByText(/visível a todos os diretores/i)).toBeInTheDocument()
    expect(within(formulario).getByText(/dado pessoal/i)).toBeInTheDocument()
    await user.type(within(formulario).getByLabelText('Título'), 'Estatuto novo')
    await user.type(within(formulario).getByLabelText('Descrição'), 'Em cartório')
    await user.selectOptions(within(formulario).getByLabelText('Categoria'), 'c-1')
    await user.upload(within(formulario).getByLabelText('Arquivo'), PDF())
    await user.click(within(formulario).getByRole('button', { name: 'Enviar documento' }))

    expect(await screen.findByRole('heading', { name: 'Estatuto novo' })).toBeInTheDocument()
    expect(chamadas.find((c) => c.metodo === 'POST')?.corpo).toEqual({
      titulo: 'Estatuto novo',
      descricao: 'Em cartório',
      categoria_id: 'c-1',
      arquivo: 'estatuto.pdf',
    })
  })

  it('o aviso fica acima do campo de arquivo', async () => {
    simularApi({
      ...comPermissoes('comunicacao.enviar_documentos'),
      'GET /comunicacao/categorias/': CATEGORIAS_ATIVAS,
      [LISTA]: { itens: [], tem_mais: false },
    })

    abrir('/documentos')

    const formulario = await screen.findByRole('form', { name: 'Enviar documento' })
    const aviso = within(formulario).getByText(/dado pessoal/i)
    const arquivo = within(formulario).getByLabelText('Arquivo')
    expect(aviso.compareDocumentPosition(arquivo) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('mostra a mensagem de documento quando o arquivo é recusado', async () => {
    simularApi({
      ...comPermissoes('comunicacao.enviar_documentos'),
      'GET /comunicacao/categorias/': CATEGORIAS_ATIVAS,
      [LISTA]: { itens: [], tem_mais: false },
      'POST /comunicacao/documentos/': erro(400, 'VALIDATION_ERROR', 'inválido', {
        arquivo: ['O documento excede o limite de 5 MB.'],
      }),
    })
    const user = userEvent.setup()

    abrir('/documentos')
    const formulario = await screen.findByRole('form', { name: 'Enviar documento' })
    await user.upload(within(formulario).getByLabelText('Arquivo'), PDF())
    await user.click(within(formulario).getByRole('button', { name: 'Enviar documento' }))

    expect(await screen.findByText('O documento excede o limite de 5 MB.')).toBeInTheDocument()
  })

  it('o formulário da ata exige a permissão de registrar atas e envia a data da reunião', async () => {
    const chamadas = simularApi({
      ...comPermissoes('comunicacao.registrar_atas'),
      'GET /comunicacao/categorias/': CATEGORIAS_ATIVAS,
      [LISTA]: { itens: [], tem_mais: false },
      'POST /comunicacao/documentos/atas/': [
        201,
        detalhe('a1', {
          tipo: 'ATA',
          titulo: 'Ata de outubro',
          categoria: null,
          data_da_reuniao: '2026-10-30',
        }),
      ],
      'GET /comunicacao/documentos/a1/': detalhe('a1', {
        tipo: 'ATA',
        titulo: 'Ata de outubro',
        categoria: null,
        data_da_reuniao: '2026-10-30',
      }),
    })
    const user = userEvent.setup()

    abrir('/documentos')

    await screen.findByRole('form', { name: 'Registrar ata' })
    expect(screen.queryByRole('form', { name: 'Enviar documento' })).not.toBeInTheDocument()
    const formulario = screen.getByRole('form', { name: 'Registrar ata' })
    await user.type(within(formulario).getByLabelText('Título'), 'Ata de outubro')
    await user.type(within(formulario).getByLabelText('Data da reunião'), '2026-10-30')
    await user.upload(within(formulario).getByLabelText('Arquivo'), PDF())
    await user.click(within(formulario).getByRole('button', { name: 'Registrar ata' }))

    expect(await screen.findByRole('heading', { name: 'Ata de outubro' })).toBeInTheDocument()
    expect(chamadas.find((c) => c.metodo === 'POST')?.corpo).toEqual({
      titulo: 'Ata de outubro',
      descricao: '',
      data_da_reuniao: '2026-10-30',
      arquivo: 'estatuto.pdf',
    })
  })

  it('mostra o erro da data futura da ata', async () => {
    simularApi({
      ...comPermissoes('comunicacao.registrar_atas'),
      'GET /comunicacao/categorias/': CATEGORIAS_ATIVAS,
      [LISTA]: { itens: [], tem_mais: false },
      'POST /comunicacao/documentos/atas/': erro(422, 'DATA_FUTURA'),
    })
    const user = userEvent.setup()

    abrir('/documentos')
    const formulario = await screen.findByRole('form', { name: 'Registrar ata' })
    await user.click(within(formulario).getByRole('button', { name: 'Registrar ata' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('A data da reunião não pode estar no futuro.')
  })
})

describe('detalhe do documento', () => {
  const DOIS = detalhe('d1', {
    versao_atual: 2,
    versoes: [
      {
        numero: 1,
        motivo: '',
        enviada_por: BIA,
        enviada_em: '2026-11-19T10:00:00-03:00',
        situacao: 'SUBSTITUIDA',
        nome: 'v1.pdf',
        mime: 'application/pdf',
        tamanho: 10,
      },
      {
        numero: 2,
        motivo: 'Correção de data',
        enviada_por: CAIO,
        enviada_em: '2026-11-20T10:00:00-03:00',
        situacao: 'VIGENTE',
        nome: 'v2.pdf',
        mime: 'application/pdf',
        tamanho: 20,
      },
    ],
    comunicados: [{ id: 'k1', titulo: 'Reunião de sábado' }],
  })

  it('lista as versões com o download de cada uma e os comunicados que indexam o documento', async () => {
    simularApi({ ...SESSAO, 'GET /comunicacao/documentos/d1/': DOIS })

    abrir('/documentos/d1')

    const versoes = await screen.findByRole('region', { name: 'Versões' })
    const itens = within(versoes).getAllByRole('listitem')
    expect(itens).toHaveLength(2)
    expect(within(itens[0]).getByText(/Substituída/)).toBeInTheDocument()
    expect(within(itens[0]).getByRole('link', { name: 'Baixar' })).toHaveAttribute(
      'href',
      '/api/v1/comunicacao/documentos/d1/versoes/1/arquivo/',
    )
    expect(within(itens[1]).getByText(/Vigente/)).toBeInTheDocument()
    expect(within(itens[1]).getByText(/Correção de data/)).toBeInTheDocument()
    expect(within(itens[1]).getByRole('link', { name: 'Baixar' })).toHaveAttribute(
      'href',
      '/api/v1/comunicacao/documentos/d1/versoes/2/arquivo/',
    )
    const indexam = screen.getByRole('region', { name: 'Comunicados que indexam' })
    const link = within(indexam).getByRole('link', { name: 'Reunião de sábado' })
    expect(link).toHaveAttribute('href', '/feed/k1')
  })

  it('envia nova versão com motivo e atualiza as versões', async () => {
    const chamadas = simularApi({
      ...SESSAO,
      'GET /comunicacao/documentos/d1/': detalhe('d1', { acoes: ['nova_versao', 'arquivar'] }),
      'POST /comunicacao/documentos/d1/versoes/': [201, DOIS],
    })
    const user = userEvent.setup()

    abrir('/documentos/d1')
    const formulario = await screen.findByRole('form', { name: 'Nova versão' })
    await user.type(within(formulario).getByLabelText('Motivo'), 'Correção de data')
    await user.upload(within(formulario).getByLabelText('Arquivo'), PDF())
    await user.click(within(formulario).getByRole('button', { name: 'Enviar nova versão' }))

    expect(await screen.findByText(/Correção de data/)).toBeInTheDocument()
    expect(chamadas.find((c) => c.metodo === 'POST')?.corpo).toEqual({
      motivo: 'Correção de data',
      arquivo: 'estatuto.pdf',
    })
  })

  it('arquiva e desarquiva pelos botões que `acoes` autoriza', async () => {
    let arquivado = false
    simularApi({
      ...SESSAO,
      'GET /comunicacao/documentos/d1/': () =>
        detalhe(
          'd1',
          arquivado ? { situacao: 'ARQUIVADO', acoes: ['desarquivar'] } : { acoes: ['arquivar'] },
        ),
      'POST /comunicacao/documentos/d1/arquivar/': () => {
        arquivado = true
        return detalhe('d1', { situacao: 'ARQUIVADO', acoes: ['desarquivar'] })
      },
    })
    const user = userEvent.setup()

    abrir('/documentos/d1')
    await user.click(await screen.findByRole('button', { name: 'Arquivar' }))

    expect(await screen.findByRole('button', { name: 'Desarquivar' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Arquivar' })).not.toBeInTheDocument()
    expect(screen.getByText(/Arquivado/)).toBeInTheDocument()
  })

  it('sem ações em `acoes`, não há formulário nem botão de gestão', async () => {
    simularApi({ ...SESSAO, 'GET /comunicacao/documentos/d1/': detalhe('d1') })

    abrir('/documentos/d1')

    await screen.findByRole('heading', { name: 'Documento d1' })
    expect(screen.queryByRole('form', { name: 'Nova versão' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Arquivar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Desarquivar' })).not.toBeInTheDocument()
  })

  it('o erro do envelope aparece, por exemplo no documento arquivado', async () => {
    simularApi({
      ...SESSAO,
      'GET /comunicacao/documentos/d1/': detalhe('d1', { acoes: ['nova_versao'] }),
      'POST /comunicacao/documentos/d1/versoes/': erro(422, 'DOCUMENTO_ARQUIVADO'),
    })
    const user = userEvent.setup()

    abrir('/documentos/d1')
    const formulario = await screen.findByRole('form', { name: 'Nova versão' })
    await user.click(within(formulario).getByRole('button', { name: 'Enviar nova versão' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('O documento está arquivado.')
  })

  it('documento inexistente mostra o erro do envelope', async () => {
    simularApi({ ...SESSAO, 'GET /comunicacao/documentos/zz/': erro(404, 'NOT_FOUND') })

    abrir('/documentos/zz')

    expect(await screen.findByRole('alert')).toHaveTextContent('Não encontrado.')
  })

  it('o texto do título e da descrição com HTML aparece como texto', async () => {
    const html = '<b>negrito</b><script>window.invadido = true</script>'
    simularApi({
      ...SESSAO,
      'GET /comunicacao/documentos/d1/': detalhe('d1', { titulo: html, descricao: html }),
    })

    const { container } = abrir('/documentos/d1')

    await waitFor(() => expect(screen.getAllByText(html).length).toBeGreaterThan(0))
    expect(container.querySelector('b')).toBeNull()
    expect(container.querySelector('script')).toBeNull()
  })
})

describe('categorias de documento', () => {
  it('o admin cria, renomeia, desativa e reativa', async () => {
    const chamadas = simularApi({
      ...COMO_ADMIN,
      'GET /comunicacao/categorias/?todas=1': [{ id: 'c-1', nome: 'Institucional', ativa: true }],
      'POST /comunicacao/categorias/': [201, { id: 'c-9', nome: 'Jurídico', ativa: true }],
      'POST /comunicacao/categorias/c-1/editar/': { id: 'c-1', nome: 'Legal', ativa: true },
      'POST /comunicacao/categorias/c-1/desativar/': { id: 'c-1', nome: 'Legal', ativa: false },
      'POST /comunicacao/categorias/c-1/reativar/': { id: 'c-1', nome: 'Legal', ativa: true },
    })
    const user = userEvent.setup()

    abrir('/admin/categorias-de-documento')

    await user.type(await screen.findByLabelText('Nova categoria'), 'Jurídico')
    await user.click(screen.getByRole('button', { name: 'Criar categoria' }))
    expect(await screen.findByRole('listitem', { name: 'Jurídico' })).toBeInTheDocument()

    const linha = screen.getByRole('listitem', { name: 'Institucional' })
    const nome = within(linha).getByLabelText('Nome de Institucional')
    await user.clear(nome)
    await user.type(nome, 'Legal')
    await user.click(within(linha).getByRole('button', { name: 'Renomear' }))
    const renomeada = await screen.findByRole('listitem', { name: 'Legal' })
    await user.click(within(renomeada).getByRole('button', { name: 'Desativar' }))
    expect(await within(renomeada).findByText('Inativa')).toBeInTheDocument()
    await user.click(within(renomeada).getByRole('button', { name: 'Reativar' }))
    await waitFor(() => expect(within(renomeada).queryByText('Inativa')).not.toBeInTheDocument())
    const criacao = chamadas.find((c) => c.caminho === '/comunicacao/categorias/')
    expect(criacao?.corpo).toEqual({ nome: 'Jurídico' })
    expect(chamadas.find((c) => c.caminho === '/comunicacao/categorias/c-1/editar/')?.corpo).toEqual({
      nome: 'Legal',
    })
  })

  it('o nome repetido mostra a mensagem da API, que fala de documento', async () => {
    simularApi({
      ...COMO_ADMIN,
      'GET /comunicacao/categorias/?todas=1': [],
      'POST /comunicacao/categorias/': erro(
        409,
        'CATEGORIA_JA_EXISTE',
        'Já existe uma categoria de documento com esse nome.',
      ),
    })
    const user = userEvent.setup()

    abrir('/admin/categorias-de-documento')
    await user.type(await screen.findByLabelText('Nova categoria'), 'Institucional')
    await user.click(screen.getByRole('button', { name: 'Criar categoria' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Já existe uma categoria de documento com esse nome.',
    )
  })
})
