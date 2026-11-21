import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import App from './App'
import { ADMIN, DIRETOR, SEM_GOOGLE, erro, simularApi } from './test/api'

const RESUMO = { 'GET /notificacoes/resumo/': { nao_lidas: 0, mais_recente_id: null } }
const COMO_DIRETOR = {
  'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
  'GET /permissoes/minhas/': {
    cargo: { id: 'ca-1', nome: 'Diretor', ativo: true },
    setores: [],
    permissoes: [],
  },
  ...SEM_GOOGLE,
  ...RESUMO,
}
const SEM_CARGO = {
  'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: false } },
  ...SEM_GOOGLE,
  ...RESUMO,
}
const COMO_ADMIN = { 'GET /acesso/sessao/': { usuario: ADMIN }, ...SEM_GOOGLE, ...RESUMO }

function abrir(caminho: string) {
  return render(
    <MemoryRouter initialEntries={[caminho]}>
      <App />
    </MemoryRouter>,
  )
}

function dados(extra: Record<string, unknown> = {}) {
  return {
    id: 'u-1',
    nome: 'Bia Diretora',
    nome_de_usuario: 'bia',
    email: 'bia@exemplo.com',
    telefone: '11988887777',
    ativo: true,
    admin: false,
    cadastrado_em: '2026-11-01T10:00:00-03:00',
    cargo: 'Diretor',
    setores: ['Financeiro'],
    ...extra,
  }
}

function cobranca(id: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    descricao: `Mensalidade ${id}`,
    categoria_nome: 'Mensalidade',
    valor: '150.00',
    vencimento: '2026-12-10',
    situacao: 'ABERTA',
    pagamentos: [],
    ...extra,
  }
}

function evento(id: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    titulo: `Evento ${id}`,
    inicio: '2026-12-12T19:30:00-03:00',
    local: 'Campo',
    categoria_nome: 'Jogo',
    situacao: 'PUBLICADO',
    papel: 'PROPONENTE',
    resposta: null,
    ...extra,
  }
}

function perfil(extra: Record<string, unknown> = {}) {
  return {
    dados: dados(),
    cobrancas: { itens: [cobranca('c1')], tem_mais: false },
    eventos: { itens: [evento('e1')], tem_mais: false },
    notificacoes: { nao_lidas: 3 },
    ...extra,
  }
}

describe('menu', () => {
  it('todo usuário logado vê Meu perfil, inclusive sem cargo', async () => {
    simularApi({ ...SEM_CARGO, 'GET /relatorios/perfil/': perfil({ notificacoes: { nao_lidas: 0 } }) })

    abrir('/perfil')

    expect(await screen.findByRole('link', { name: 'Meu perfil' })).toHaveAttribute('href', '/perfil')
  })
})

describe('perfil próprio', () => {
  it('mostra as quatro seções', async () => {
    simularApi({
      ...COMO_DIRETOR,
      'GET /relatorios/perfil/': perfil({
        cobrancas: {
          itens: [
            cobranca('c1', {
              situacao: 'EM_VALIDACAO',
              pagamentos: [{ forma: 'COMPROVANTE', data_pagamento: '2026-11-20', situacao: 'EM_VALIDACAO' }],
            }),
          ],
          tem_mais: false,
        },
        eventos: { itens: [evento('e1', { papel: 'PRESENCA', resposta: 'VOU' })], tem_mais: false },
      }),
    })

    abrir('/perfil')

    const dadosSecao = await screen.findByRole('region', { name: 'Dados' })
    expect(within(dadosSecao).getByText('Bia Diretora')).toBeInTheDocument()
    expect(within(dadosSecao).getByText(/bia@exemplo.com/)).toBeInTheDocument()
    expect(within(dadosSecao).getByText(/Cargo: Diretor/)).toBeInTheDocument()
    expect(within(dadosSecao).getByText(/Financeiro/)).toBeInTheDocument()

    const pagamentos = screen.getByRole('region', { name: 'Histórico de pagamentos' })
    expect(within(pagamentos).getByText(/Mensalidade c1/)).toBeInTheDocument()
    expect(within(pagamentos).getByText(/R\$ 150,00/)).toBeInTheDocument()
    expect(within(pagamentos).getByText(/10\/12\/2026/)).toBeInTheDocument()
    expect(within(pagamentos).getByText(/Comprovante/)).toBeInTheDocument()
    expect(within(pagamentos).getByRole('link', { name: 'Abrir cobrança' })).toHaveAttribute(
      'href',
      '/cobrancas/c1',
    )

    const eventos = screen.getByRole('region', { name: 'Eventos relacionados' })
    expect(within(eventos).getByRole('link', { name: 'Evento e1' })).toHaveAttribute('href', '/eventos/e1')
    expect(within(eventos).getByText(/Vou/)).toBeInTheDocument()

    const notificacoes = screen.getByRole('region', { name: 'Notificações' })
    expect(within(notificacoes).getByText(/3 não lidas/)).toBeInTheDocument()
    expect(within(notificacoes).getByRole('link', { name: 'Preferências de alerta' })).toHaveAttribute(
      'href',
      '/preferencias',
    )
  })

  it('usuário sem cargo vê os dados e as seções vazias, sem erro', async () => {
    simularApi({
      ...SEM_CARGO,
      'GET /relatorios/perfil/': perfil({
        dados: dados({ cargo: null, setores: [] }),
        cobrancas: { itens: [], tem_mais: false },
        eventos: { itens: [], tem_mais: false },
      }),
    })

    abrir('/perfil')

    expect(await screen.findByText('Nenhuma cobrança.')).toBeInTheDocument()
    expect(screen.getByText('Nenhum evento.')).toBeInTheDocument()
    expect(screen.getByText(/Sem cargo/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('carrega mais cobranças e mais eventos pelo cursor do último', async () => {
    const chamadas = simularApi({
      ...COMO_DIRETOR,
      'GET /relatorios/perfil/': perfil({
        cobrancas: { itens: [cobranca('c2')], tem_mais: true },
        eventos: { itens: [evento('e2')], tem_mais: true },
      }),
      'GET /relatorios/perfil/cobrancas/?antes=c2': { itens: [cobranca('c1')], tem_mais: false },
      'GET /relatorios/perfil/eventos/?antes=e2': { itens: [evento('e1')], tem_mais: false },
    })
    const user = userEvent.setup()

    abrir('/perfil')
    await user.click(await screen.findByRole('button', { name: 'Carregar mais cobranças' }))
    await user.click(screen.getByRole('button', { name: 'Carregar mais eventos' }))

    expect(await screen.findByText(/Mensalidade c1/)).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'Evento e1' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Carregar mais/ })).not.toBeInTheDocument()
    expect(chamadas.map((c) => c.caminho)).toEqual(
      expect.arrayContaining([
        '/relatorios/perfil/cobrancas/?antes=c2',
        '/relatorios/perfil/eventos/?antes=e2',
      ]),
    )
  })

  it('o texto com HTML aparece como texto', async () => {
    const html = '<b>negrito</b><script>window.invadido = true</script>'
    simularApi({
      ...COMO_DIRETOR,
      'GET /relatorios/perfil/': perfil({
        dados: dados({ nome: html }),
        cobrancas: { itens: [cobranca('c1', { descricao: html })], tem_mais: false },
      }),
    })

    const { container } = abrir('/perfil')

    await waitFor(() => expect(screen.getAllByText(html).length).toBeGreaterThan(0))
    expect(container.querySelector('b')).toBeNull()
    expect(container.querySelector('script')).toBeNull()
  })

  it('mostra o erro do envelope quando a consulta falha', async () => {
    simularApi({ ...COMO_DIRETOR, 'GET /relatorios/perfil/': erro(403, 'PERMISSION_DENIED') })

    abrir('/perfil')

    expect(await screen.findByRole('alert')).toHaveTextContent('Você não tem permissão para fazer isso.')
  })
})

describe('telefone', () => {
  it('troca o telefone enviando só o campo telefone', async () => {
    const chamadas = simularApi({
      ...COMO_DIRETOR,
      'GET /relatorios/perfil/': perfil(),
      'POST /acesso/telefone/': { telefone: '21912345678' },
    })
    const user = userEvent.setup()

    abrir('/perfil')
    const formulario = await screen.findByRole('form', { name: 'Telefone' })
    const campo = within(formulario).getByLabelText('Telefone')
    expect(campo).toHaveValue('11988887777')
    await user.clear(campo)
    await user.type(campo, '(21) 91234-5678')
    await user.click(within(formulario).getByRole('button', { name: 'Salvar telefone' }))

    expect(await screen.findByText('Telefone atualizado.')).toBeInTheDocument()
    const envio = chamadas.find((c) => c.metodo === 'POST')
    expect(envio?.corpo).toEqual({ telefone: '(21) 91234-5678' })
    expect(Object.keys(envio?.corpo as object)).toEqual(['telefone'])
  })

  it('mostra o erro de validação no campo', async () => {
    simularApi({
      ...COMO_DIRETOR,
      'GET /relatorios/perfil/': perfil(),
      'POST /acesso/telefone/': erro(400, 'VALIDATION_ERROR', 'inválido', {
        telefone: ['Informe um telefone com 8 a 15 dígitos.'],
      }),
    })
    const user = userEvent.setup()

    abrir('/perfil')
    const formulario = await screen.findByRole('form', { name: 'Telefone' })
    await user.clear(within(formulario).getByLabelText('Telefone'))
    await user.click(within(formulario).getByRole('button', { name: 'Salvar telefone' }))

    expect(await screen.findByText('Informe um telefone com 8 a 15 dígitos.')).toBeInTheDocument()
    expect(screen.queryByText('Telefone atualizado.')).not.toBeInTheDocument()
  })
})

describe('perfil visto pelo admin', () => {
  const ROTAS = {
    ...COMO_ADMIN,
    'GET /relatorios/perfil/u-2/': {
      dados: dados({ id: 'u-2', nome: 'Caio Diretor', email: 'caio@exemplo.com' }),
      cobrancas: { itens: [cobranca('c9')], tem_mais: true },
      eventos: { itens: [], tem_mais: false },
    },
  }

  it('não mostra notificações nem o formulário, e avisa que a consulta fica registrada', async () => {
    simularApi(ROTAS)

    abrir('/admin/usuarios/u-2/perfil')

    expect(await screen.findByText('Caio Diretor')).toBeInTheDocument()
    expect(screen.getByText(/consulta fica registrada/i)).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Notificações' })).not.toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Telefone' })).not.toBeInTheDocument()
    expect(screen.getByText(/11988887777/)).toBeInTheDocument()
  })

  it('carrega mais cobranças pela rota do usuário', async () => {
    const chamadas = simularApi({
      ...ROTAS,
      'GET /relatorios/perfil/u-2/cobrancas/?antes=c9': { itens: [cobranca('c8')], tem_mais: false },
    })
    const user = userEvent.setup()

    abrir('/admin/usuarios/u-2/perfil')
    await user.click(await screen.findByRole('button', { name: 'Carregar mais cobranças' }))

    expect(await screen.findByText(/Mensalidade c8/)).toBeInTheDocument()
    expect(chamadas.map((c) => c.caminho)).toContain('/relatorios/perfil/u-2/cobrancas/?antes=c9')
  })

  it('quem não é admin é barrado na rota do admin', async () => {
    simularApi(COMO_DIRETOR)

    abrir('/admin/usuarios/u-2/perfil')

    await waitFor(() => expect(screen.queryByRole('region', { name: 'Dados' })).not.toBeInTheDocument())
    expect(screen.queryByText(/consulta fica registrada/i)).not.toBeInTheDocument()
  })

  it('a tela do usuário do admin tem o link Ver perfil', async () => {
    simularApi({
      ...COMO_ADMIN,
      'GET /acesso/usuarios/': [{ ...DIRETOR, id: 'u-2', nome: 'Caio Diretor', tem_cargo: true }],
      'GET /permissoes/usuarios/u-2/': { cargo: null, setores: [], permissoes: [] },
      'GET /permissoes/cargos/': [],
      'GET /permissoes/setores/': [],
      'GET /permissoes/concessoes/': [],
      'GET /acesso/usuarios/u-2/historico/': [],
    })

    abrir('/admin/usuarios/u-2')

    expect(await screen.findByRole('link', { name: 'Ver perfil' })).toHaveAttribute(
      'href',
      '/admin/usuarios/u-2/perfil',
    )
  })
})
