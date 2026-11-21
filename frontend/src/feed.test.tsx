import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import App from './App'
import { ADMIN, DIRETOR, SEM_GOOGLE, erro, simularApi } from './test/api'

const BIA = { id: 'u-1', nome: 'Bia Diretora' }
const CAIO = { id: 'u-2', nome: 'Caio Autor' }
const ZERO = { CIENTE: 0, DE_ACORDO: 0, DUVIDA: 0, COMEMORACAO: 0 }
const QUEM_VAZIO = { CIENTE: [], DE_ACORDO: [], DUVIDA: [], COMEMORACAO: [] }
const RESUMO = { 'GET /notificacoes/resumo/': { nao_lidas: 0, mais_recente_id: null } }

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

const FEED = 'GET /comunicacao/comunicados/'
const SESSAO = comPermissoes()
const COMO_ADMIN = { 'GET /acesso/sessao/': { usuario: ADMIN }, ...SEM_GOOGLE, ...RESUMO }

function abrir(caminho: string) {
  return render(
    <MemoryRouter initialEntries={[caminho]}>
      <App />
    </MemoryRouter>,
  )
}

function comunicado(id: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    tipo: 'COMUNICADO',
    titulo: `Aviso ${id}`,
    texto: `Texto do aviso ${id}`,
    autor: CAIO,
    situacao: 'PUBLICADO',
    fixado: false,
    fixado_em: null,
    publicado_em: '2026-11-20T10:00:00-03:00',
    editado: false,
    editado_em: null,
    despublicado: null,
    documentos: [],
    reacoes: { contagem: ZERO, minha: null, quem: QUEM_VAZIO },
    total_de_comentarios: 0,
    acoes: ['reagir', 'comentar'],
    ...extra,
  }
}

function comentario(id: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    autor: BIA,
    texto: `Comentário ${id}`,
    situacao: 'VISIVEL',
    criado_em: '2026-11-20T11:00:00-03:00',
    editado: false,
    editado_em: null,
    oculto: null,
    acoes: [],
    ...extra,
  }
}

describe('menu da comunicação', () => {
  it('quem lê gestão vê o Feed, e não vê Publicar sem a permissão', async () => {
    simularApi({ ...SESSAO, 'GET /comunicacao/comunicados/': { fixados: [], itens: [], tem_mais: false } })

    abrir('/feed')

    const menu = await screen.findByRole('navigation', { name: 'Comunicação' })
    expect(within(menu).getByRole('link', { name: 'Feed' })).toHaveAttribute('href', '/feed')
    expect(within(menu).queryByRole('link', { name: 'Publicar comunicado' })).not.toBeInTheDocument()
  })

  it('quem tem a permissão vê Publicar comunicado, e o admin também', async () => {
    simularApi({
      ...comPermissoes('comunicacao.publicar'),
      'GET /comunicacao/comunicados/': { fixados: [], itens: [], tem_mais: false },
    })
    const { unmount } = abrir('/feed')
    const menu = await screen.findByRole('navigation', { name: 'Comunicação' })
    expect(await within(menu).findByRole('link', { name: 'Publicar comunicado' })).toHaveAttribute(
      'href',
      '/feed/novo',
    )
    unmount()

    simularApi({ ...COMO_ADMIN, [FEED]: { fixados: [], itens: [], tem_mais: false } })
    abrir('/feed')
    const menuDoAdmin = await screen.findByRole('navigation', { name: 'Comunicação' })
    expect(within(menuDoAdmin).getByRole('link', { name: 'Publicar comunicado' })).toBeInTheDocument()
  })

  it('quem não tem cargo não vê o menu e volta para o início', async () => {
    simularApi({
      'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: false } },
      ...SEM_GOOGLE,
      ...RESUMO,
    })

    abrir('/feed')

    await waitFor(() =>
      expect(screen.queryByRole('navigation', { name: 'Comunicação' })).not.toBeInTheDocument(),
    )
    expect(screen.queryByRole('heading', { name: 'Feed' })).not.toBeInTheDocument()
  })
})

describe('feed', () => {
  it('mostra os fixados no topo e carrega mais pelo cursor do último item', async () => {
    const chamadas = simularApi({
      ...SESSAO,
      'GET /comunicacao/comunicados/': {
        fixados: [comunicado('fix', { fixado: true })],
        itens: [comunicado('c3'), comunicado('c2')],
        tem_mais: true,
      },
      'GET /comunicacao/comunicados/?antes=c2': { fixados: [], itens: [comunicado('c1')], tem_mais: false },
    })
    const user = userEvent.setup()

    abrir('/feed')

    const fixados = await screen.findByRole('region', { name: 'Fixados' })
    expect(within(fixados).getByRole('article', { name: 'Aviso fix' })).toBeInTheDocument()
    const titulos = screen.getAllByRole('article').map((a) => a.getAttribute('aria-label'))
    expect(titulos).toEqual(['Aviso fix', 'Aviso c3', 'Aviso c2'])

    await user.click(screen.getByRole('button', { name: 'Carregar mais' }))

    expect(await screen.findByRole('article', { name: 'Aviso c1' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Carregar mais' })).not.toBeInTheDocument()
    expect(chamadas.map((c) => c.caminho)).toContain('/comunicacao/comunicados/?antes=c2')
  })

  it('cada item mostra tipo, autor, texto, editado, documentos e contagens', async () => {
    simularApi({
      ...SESSAO,
      'GET /comunicacao/comunicados/': {
        fixados: [],
        itens: [
          comunicado('c1', {
            tipo: 'PAUTA',
            editado: true,
            documentos: [{ id: 'd-1', titulo: 'Estatuto', tipo: 'DOCUMENTO', situacao: 'VIGENTE' }],
            reacoes: { contagem: { ...ZERO, CIENTE: 2 }, minha: null },
            total_de_comentarios: 3,
          }),
        ],
        tem_mais: false,
      },
    })

    abrir('/feed')

    const item = await screen.findByRole('article', { name: 'Aviso c1' })
    expect(within(item).getByText(/Pauta/)).toBeInTheDocument()
    expect(within(item).getByText(/Caio Autor/)).toBeInTheDocument()
    expect(within(item).getByText('Texto do aviso c1')).toBeInTheDocument()
    expect(within(item).getByText(/editado/i)).toBeInTheDocument()
    expect(within(item).getByRole('link', { name: 'Estatuto' })).toHaveAttribute(
      'href',
      '/api/v1/comunicacao/documentos/d-1/arquivo/',
    )
    expect(within(item).getByRole('button', { name: 'Ciente 2' })).toBeInTheDocument()
    expect(within(item).getByRole('link', { name: '3 comentários' })).toHaveAttribute('href', '/feed/c1')
  })

  it('marca, troca e retira a reação, atualizando a contagem', async () => {
    const chamadas = simularApi({
      ...SESSAO,
      'GET /comunicacao/comunicados/': { fixados: [], itens: [comunicado('c1')], tem_mais: false },
      'POST /comunicacao/comunicados/c1/reacao/': (() => {
        const respostas = [
          { contagem: { ...ZERO, CIENTE: 1 }, minha: 'CIENTE', quem: {} },
          { contagem: { ...ZERO, DUVIDA: 1 }, minha: 'DUVIDA', quem: {} },
          { contagem: ZERO, minha: null, quem: {} },
        ]
        return () => respostas.shift()
      })(),
    })
    const user = userEvent.setup()

    abrir('/feed')

    await user.click(await screen.findByRole('button', { name: 'Ciente 0' }))
    const ciente = await screen.findByRole('button', { name: 'Ciente 1' })
    expect(ciente).toHaveAttribute('aria-pressed', 'true')

    await user.click(screen.getByRole('button', { name: 'Dúvida 0' }))
    const duvida = await screen.findByRole('button', { name: 'Dúvida 1' })
    expect(duvida).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Ciente 0' })).toHaveAttribute('aria-pressed', 'false')

    await user.click(duvida)
    expect(await screen.findByRole('button', { name: 'Dúvida 0' })).toHaveAttribute('aria-pressed', 'false')
    const reacoes = chamadas.filter((c) => c.metodo === 'POST')
    expect(reacoes.map((c) => c.corpo)).toEqual([{ tipo: 'CIENTE' }, { tipo: 'DUVIDA' }, { tipo: 'DUVIDA' }])
  })

  it('só mostra os botões de reação quando `acoes` traz reagir', async () => {
    simularApi({
      ...SESSAO,
      'GET /comunicacao/comunicados/': {
        fixados: [],
        itens: [comunicado('c1', { acoes: [] })],
        tem_mais: false,
      },
    })

    abrir('/feed')

    const item = await screen.findByRole('article', { name: 'Aviso c1' })
    expect(within(item).queryByRole('button')).not.toBeInTheDocument()
  })

  it('mostra o erro do envelope quando a reação é recusada', async () => {
    simularApi({
      ...SESSAO,
      'GET /comunicacao/comunicados/': { fixados: [], itens: [comunicado('c1')], tem_mais: false },
      'POST /comunicacao/comunicados/c1/reacao/': erro(422, 'COMUNICADO_NAO_PUBLICADO'),
    })
    const user = userEvent.setup()

    abrir('/feed')
    await user.click(await screen.findByRole('button', { name: 'Ciente 0' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('O comunicado não está publicado.')
  })

  it('o texto com HTML aparece como texto e nada é executado ou criado (CA-31)', async () => {
    const html = '<script>window.invadido = true</script><img src=x onerror="window.invadido = true">'
    simularApi({
      ...SESSAO,
      'GET /comunicacao/comunicados/': {
        fixados: [],
        itens: [comunicado('c1', { titulo: html, texto: html })],
        tem_mais: false,
      },
    })

    const { container } = abrir('/feed')

    await waitFor(() => expect(screen.getAllByText(html).length).toBeGreaterThan(0))
    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect((window as unknown as { invadido?: boolean }).invadido).toBeUndefined()
  })

  it('o link Despublicados aparece para quem publica e leva à lista', async () => {
    simularApi({
      ...comPermissoes('comunicacao.publicar'),
      'GET /comunicacao/comunicados/': { fixados: [], itens: [], tem_mais: false },
      'GET /comunicacao/comunicados/despublicados/': {
        itens: [
          comunicado('c9', {
            situacao: 'DESPUBLICADO',
            despublicado: { em: '2026-11-21T09:00:00-03:00', por: CAIO, motivo: 'Data errada' },
            acoes: ['republicar'],
          }),
        ],
        tem_mais: false,
      },
      'POST /comunicacao/comunicados/c9/republicar/': comunicado('c9'),
    })
    const user = userEvent.setup()

    abrir('/feed')
    await user.click(await screen.findByRole('link', { name: 'Despublicados' }))

    const item = await screen.findByRole('article', { name: 'Aviso c9' })
    expect(within(item).getByText(/Data errada/)).toBeInTheDocument()
    await user.click(within(item).getByRole('button', { name: 'Republicar' }))
    await waitFor(() => expect(screen.queryByRole('article', { name: 'Aviso c9' })).not.toBeInTheDocument())
  })
})

describe('formulário de comunicado', () => {
  it('publica com tipo, título, texto e os documentos vigentes escolhidos', async () => {
    const chamadas = simularApi({
      ...comPermissoes('comunicacao.publicar'),
      'GET /comunicacao/documentos/': {
        itens: [
          { id: 'd-1', titulo: 'Estatuto', tipo: 'DOCUMENTO', situacao: 'VIGENTE', versao_atual: 1 },
          { id: 'd-2', titulo: 'Ata de outubro', tipo: 'ATA', situacao: 'VIGENTE', versao_atual: 1 },
        ],
        tem_mais: false,
      },
      'GET /comunicacao/referencias/': {
        categorias: [],
        tipos: [
          { codigo: 'COMUNICADO', rotulo: 'Comunicado' },
          { codigo: 'PAUTA', rotulo: 'Pauta' },
        ],
        reacoes: [],
      },
      'POST /comunicacao/comunicados/': comunicado('n1'),
      'GET /comunicacao/comunicados/n1/': comunicado('n1'),
      'GET /comunicacao/comunicados/n1/comentarios/': { itens: [], tem_mais: false },
    })
    const user = userEvent.setup()

    abrir('/feed/novo')

    await user.selectOptions(await screen.findByLabelText('Tipo'), 'PAUTA')
    await user.type(screen.getByLabelText('Título'), 'Pauta de novembro')
    await user.type(screen.getByLabelText('Texto'), '1. Orçamento')
    await user.click(await screen.findByRole('checkbox', { name: 'Ata de outubro' }))
    await user.click(screen.getByRole('button', { name: 'Publicar' }))

    expect(await screen.findByRole('heading', { name: 'Aviso n1' })).toBeInTheDocument()
    const envio = chamadas.find((c) => c.metodo === 'POST' && c.caminho === '/comunicacao/comunicados/')
    expect(envio?.corpo).toEqual({
      tipo: 'PAUTA',
      titulo: 'Pauta de novembro',
      texto: '1. Orçamento',
      documentos_ids: ['d-2'],
    })
  })

  it('mostra o erro de cada campo vindo da API', async () => {
    simularApi({
      ...comPermissoes('comunicacao.publicar'),
      'GET /comunicacao/documentos/': { itens: [], tem_mais: false },
      'GET /comunicacao/referencias/': { categorias: [], tipos: [], reacoes: [] },
      'POST /comunicacao/comunicados/': erro(400, 'VALIDATION_ERROR', 'inválido', {
        titulo: ['Informe o título.'],
      }),
    })
    const user = userEvent.setup()

    abrir('/feed/novo')
    await user.click(await screen.findByRole('button', { name: 'Publicar' }))

    expect(await screen.findByText('Informe o título.')).toBeInTheDocument()
  })

  it('na edição traz os dados e mantém marcados os documentos já ligados', async () => {
    const chamadas = simularApi({
      ...SESSAO,
      'GET /comunicacao/comunicados/c1/': comunicado('c1', {
        acoes: ['editar_comunicado', 'reagir', 'comentar'],
        documentos: [{ id: 'd-1', titulo: 'Estatuto', tipo: 'DOCUMENTO', situacao: 'ARQUIVADO' }],
      }),
      'GET /comunicacao/comunicados/c1/comentarios/': { itens: [], tem_mais: false },
      'GET /comunicacao/documentos/': { itens: [], tem_mais: false },
      'GET /comunicacao/referencias/': { categorias: [], tipos: [], reacoes: [] },
      'POST /comunicacao/comunicados/c1/editar/': comunicado('c1', { titulo: 'Novo título' }),
    })
    const user = userEvent.setup()

    abrir('/feed/c1/editar')

    const titulo = await screen.findByLabelText('Título')
    expect(titulo).toHaveValue('Aviso c1')
    expect(await screen.findByRole('checkbox', { name: 'Estatuto (arquivado)' })).toBeChecked()
    await user.clear(titulo)
    await user.type(titulo, 'Novo título')
    await user.click(screen.getByRole('button', { name: 'Salvar edição' }))

    await waitFor(() =>
      expect(chamadas.find((c) => c.caminho === '/comunicacao/comunicados/c1/editar/')?.corpo).toEqual({
        titulo: 'Novo título',
        texto: 'Texto do aviso c1',
        documentos_ids: ['d-1'],
      }),
    )
  })
})

describe('detalhe do comunicado', () => {
  const ROTAS = (extra: Record<string, unknown> = {}) => ({
    ...SESSAO,
    'GET /comunicacao/comunicados/c1/': comunicado('c1'),
    'GET /comunicacao/comunicados/c1/comentarios/': { itens: [], tem_mais: false },
    ...extra,
  })

  it('mostra quem reagiu por tipo', async () => {
    simularApi(
      ROTAS({
        'GET /comunicacao/comunicados/c1/': comunicado('c1', {
          reacoes: {
            contagem: { ...ZERO, CIENTE: 1, DUVIDA: 1 },
            minha: null,
            quem: { CIENTE: [BIA], DE_ACORDO: [], DUVIDA: [CAIO], COMEMORACAO: [] },
          },
        }),
      }),
    )

    abrir('/feed/c1')

    const quem = await screen.findByRole('region', { name: 'Quem reagiu' })
    expect(within(quem).getByText(/Ciente: Bia Diretora/)).toBeInTheDocument()
    expect(within(quem).getByText(/Dúvida: Caio Autor/)).toBeInTheDocument()
  })

  it('publica um comentário e ele entra na lista', async () => {
    const chamadas = simularApi(
      ROTAS({ 'POST /comunicacao/comunicados/c1/comentarios/': comentario('k1', { texto: 'Concordo' }) }),
    )
    const user = userEvent.setup()

    abrir('/feed/c1')
    await user.type(await screen.findByLabelText('Seu comentário'), 'Concordo')
    await user.click(screen.getByRole('button', { name: 'Comentar' }))

    expect(await screen.findByText('Concordo')).toBeInTheDocument()
    expect(chamadas.find((c) => c.metodo === 'POST')?.corpo).toEqual({ texto: 'Concordo' })
  })

  it('não mostra o formulário de comentário sem `comentar` em `acoes`', async () => {
    simularApi(ROTAS({ 'GET /comunicacao/comunicados/c1/': comunicado('c1', { acoes: [] }) }))

    abrir('/feed/c1')

    await screen.findByRole('heading', { name: 'Aviso c1' })
    expect(screen.queryByLabelText('Seu comentário')).not.toBeInTheDocument()
  })

  it('o autor edita o próprio comentário e ele ganha a marca "editado"', async () => {
    const chamadas = simularApi(
      ROTAS({
        'GET /comunicacao/comunicados/c1/comentarios/': {
          itens: [comentario('k1', { acoes: ['editar_comentario', 'ocultar_comentario'] })],
          tem_mais: false,
        },
        'POST /comunicacao/comentarios/k1/editar/': comentario('k1', { texto: 'Novo texto', editado: true }),
      }),
    )
    const user = userEvent.setup()

    abrir('/feed/c1')
    const item = await screen.findByRole('listitem', { name: 'Comentário de Bia Diretora' })
    await user.click(within(item).getByRole('button', { name: 'Editar' }))
    const campo = within(item).getByLabelText('Editar comentário')
    await user.clear(campo)
    await user.type(campo, 'Novo texto')
    await user.click(within(item).getByRole('button', { name: 'Salvar' }))

    expect(await within(item).findByText('Novo texto')).toBeInTheDocument()
    expect(within(item).getByText(/editado/i)).toBeInTheDocument()
    expect(chamadas.find((c) => c.caminho === '/comunicacao/comentarios/k1/editar/')?.corpo).toEqual({
      texto: 'Novo texto',
    })
  })

  it('quem gerencia oculta o comentário de outra pessoa com motivo', async () => {
    const chamadas = simularApi(
      ROTAS({
        'GET /comunicacao/comunicados/c1/comentarios/': {
          itens: [comentario('k1', { autor: CAIO, acoes: ['ocultar_comentario'] })],
          tem_mais: false,
        },
        'POST /comunicacao/comentarios/k1/ocultar/': comentario('k1', {
          autor: CAIO,
          situacao: 'OCULTO',
          oculto: { em: null, por: BIA, pela_gerencia: true, motivo: 'Fora do assunto' },
          acoes: ['reexibir_comentario'],
        }),
      }),
    )
    const user = userEvent.setup()

    abrir('/feed/c1')
    const item = await screen.findByRole('listitem', { name: 'Comentário de Caio Autor' })
    await user.type(within(item).getByLabelText('Motivo da ocultação'), 'Fora do assunto')
    await user.click(within(item).getByRole('button', { name: 'Ocultar' }))

    expect(await within(item).findByText(/Fora do assunto/)).toBeInTheDocument()
    expect(chamadas.find((c) => c.caminho === '/comunicacao/comentarios/k1/ocultar/')?.corpo).toEqual({
      motivo: 'Fora do assunto',
    })
  })

  it('o autor oculta o próprio comentário sem motivo', async () => {
    const chamadas = simularApi(
      ROTAS({
        'GET /comunicacao/comunicados/c1/comentarios/': {
          itens: [comentario('k1', { acoes: ['editar_comentario', 'ocultar_comentario'] })],
          tem_mais: false,
        },
        'POST /comunicacao/comentarios/k1/ocultar/': comentario('k1', {
          situacao: 'OCULTO',
          oculto: { em: null, por: BIA, pela_gerencia: false, motivo: '' },
          acoes: ['reexibir_comentario'],
        }),
      }),
    )
    const user = userEvent.setup()

    abrir('/feed/c1')
    const item = await screen.findByRole('listitem', { name: 'Comentário de Bia Diretora' })
    expect(within(item).queryByLabelText('Motivo da ocultação')).not.toBeInTheDocument()
    await user.click(within(item).getByRole('button', { name: 'Ocultar' }))

    expect(await within(item).findByRole('button', { name: 'Reexibir' })).toBeInTheDocument()
    expect(chamadas.find((c) => c.caminho === '/comunicacao/comentarios/k1/ocultar/')?.corpo).toEqual({
      motivo: '',
    })
  })

  it('o comentário oculto aparece esmaecido, com a marca e o motivo, para quem pode vê-lo', async () => {
    simularApi(
      ROTAS({
        'GET /comunicacao/comunicados/c1/comentarios/': {
          itens: [
            comentario('k1', {
              autor: CAIO,
              situacao: 'OCULTO',
              oculto: { em: null, por: BIA, pela_gerencia: true, motivo: 'Fora do assunto' },
              acoes: ['reexibir_comentario'],
            }),
          ],
          tem_mais: false,
        },
      }),
    )

    abrir('/feed/c1')

    const item = await screen.findByRole('listitem', { name: 'Comentário de Caio Autor' })
    expect(item).toHaveClass('comentario-oculto')
    expect(within(item).getByText('Oculto')).toBeInTheDocument()
    expect(within(item).getByText(/Fora do assunto/)).toBeInTheDocument()
    expect(within(item).getByRole('button', { name: 'Reexibir' })).toBeInTheDocument()
  })

  it('carrega mais comentários pelo cursor do último', async () => {
    const chamadas = simularApi(
      ROTAS({
        'GET /comunicacao/comunicados/c1/comentarios/': { itens: [comentario('k1')], tem_mais: true },
        'GET /comunicacao/comunicados/c1/comentarios/?depois=k1': {
          itens: [comentario('k2')],
          tem_mais: false,
        },
      }),
    )
    const user = userEvent.setup()

    abrir('/feed/c1')
    await user.click(await screen.findByRole('button', { name: 'Carregar mais comentários' }))

    expect(await screen.findByText('Comentário k2')).toBeInTheDocument()
    expect(screen.getByText('Comentário k1')).toBeInTheDocument()
    expect(chamadas.map((c) => c.caminho)).toContain('/comunicacao/comunicados/c1/comentarios/?depois=k1')
  })

  it('despublica com motivo e mostra o aviso de despublicado', async () => {
    let despublicado = false
    const chamadas = simularApi(
      ROTAS({
        'GET /comunicacao/comunicados/c1/': () =>
          despublicado
            ? comunicado('c1', {
                situacao: 'DESPUBLICADO',
                despublicado: { em: null, por: CAIO, motivo: 'Data errada' },
                acoes: ['republicar'],
              })
            : comunicado('c1', {
                acoes: ['despublicar', 'editar_comunicado', 'fixar', 'reagir', 'comentar'],
              }),
        'POST /comunicacao/comunicados/c1/despublicar/': () => {
          despublicado = true
          return comunicado('c1', {
            situacao: 'DESPUBLICADO',
            despublicado: { em: null, por: CAIO, motivo: 'Data errada' },
            acoes: ['republicar'],
          })
        },
      }),
    )
    const user = userEvent.setup()

    abrir('/feed/c1')
    const formulario = await screen.findByRole('form', { name: 'Despublicar comunicado' })
    await user.type(within(formulario).getByLabelText('Motivo'), 'Data errada')
    await user.click(within(formulario).getByRole('button', { name: 'Despublicar' }))

    expect(await screen.findByText(/Despublicado por Caio Autor/)).toBeInTheDocument()
    expect(screen.getByText(/Data errada/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Republicar' })).toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Despublicar comunicado' })).not.toBeInTheDocument()
    expect(chamadas.find((c) => c.caminho === '/comunicacao/comunicados/c1/despublicar/')?.corpo).toEqual({
      motivo: 'Data errada',
    })
  })

  it('fixa e desafixa pelos botões que `acoes` autoriza', async () => {
    let fixado = false
    simularApi(
      ROTAS({
        'GET /comunicacao/comunicados/c1/': () =>
          comunicado('c1', { fixado, acoes: fixado ? ['desafixar'] : ['fixar'] }),
        'POST /comunicacao/comunicados/c1/fixar/': () => {
          fixado = true
          return comunicado('c1', { fixado: true, acoes: ['desafixar'] })
        },
      }),
    )
    const user = userEvent.setup()

    abrir('/feed/c1')
    await user.click(await screen.findByRole('button', { name: 'Fixar' }))

    expect(await screen.findByRole('button', { name: 'Desafixar' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Fixar' })).not.toBeInTheDocument()
  })

  it('sem nenhuma ação em `acoes`, não há botão de gestão nem link de edição', async () => {
    simularApi(ROTAS({ 'GET /comunicacao/comunicados/c1/': comunicado('c1', { acoes: [] }) }))

    abrir('/feed/c1')

    await screen.findByRole('heading', { name: 'Aviso c1' })
    for (const nome of ['Fixar', 'Desafixar', 'Republicar', 'Despublicar']) {
      expect(screen.queryByRole('button', { name: nome })).not.toBeInTheDocument()
    }
    expect(screen.queryByRole('link', { name: 'Editar comunicado' })).not.toBeInTheDocument()
  })

  it('comunicado inexistente mostra o erro do envelope', async () => {
    simularApi({ ...SESSAO, 'GET /comunicacao/comunicados/zz/': erro(404, 'NOT_FOUND') })

    abrir('/feed/zz')

    expect(await screen.findByRole('alert')).toHaveTextContent('Não encontrado.')
  })

  it('o texto do comentário com HTML aparece como texto', async () => {
    const html = '<b>negrito</b><script>window.invadido = true</script>'
    simularApi(
      ROTAS({
        'GET /comunicacao/comunicados/c1/comentarios/': {
          itens: [comentario('k1', { texto: html })],
          tem_mais: false,
        },
      }),
    )

    const { container } = abrir('/feed/c1')

    expect(await screen.findByText(html)).toBeInTheDocument()
    expect(container.querySelector('b')).toBeNull()
    expect(container.querySelector('script')).toBeNull()
  })
})
