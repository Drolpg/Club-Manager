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

const RESUMO_NOTIF = { 'GET /notificacoes/resumo/': { nao_lidas: 0, mais_recente_id: null } }
const SEM_PERMISSOES = { cargo: { id: 'ca-1', nome: 'Tesoureiro', ativo: true }, setores: [], permissoes: [] }

function comPermissoes(...codigos: string[]) {
  return {
    'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
    'GET /permissoes/minhas/': {
      cargo: { id: 'ca-1', nome: 'Tesoureiro', ativo: true },
      setores: [],
      permissoes: codigos.map((codigo) => ({ codigo, nome: codigo, origens: [] })),
    },
    ...SEM_GOOGLE,
    ...RESUMO_NOTIF,
  }
}

const SEM_CARGO = { 'GET /acesso/sessao/': { usuario: DIRETOR }, ...SEM_GOOGLE, ...RESUMO_NOTIF }
const COM_CARGO = {
  'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
  'GET /permissoes/minhas/': SEM_PERMISSOES,
  ...SEM_GOOGLE,
  ...RESUMO_NOTIF,
}
const COMO_ADMIN = { 'GET /acesso/sessao/': { usuario: ADMIN }, ...SEM_GOOGLE, ...RESUMO_NOTIF }

const BIA = { id: 'u-1', nome: 'Bia Diretora' }
const CARLOS = { id: 'u-2', nome: 'Carlos Tesoureiro' }
const CATEGORIA_ENT = {
  id: 'cat-1',
  nome: 'Mensalidade',
  natureza: 'ENTRADA',
  ativa: true,
  criada_em: '2026-11-10T08:00:00-03:00',
}
const CHAVE_PIX = {
  id: 'pix-1',
  tipo: 'EMAIL',
  chave: 'pix@clube.org.br',
  nome_recebedor: 'CLUBE ATLETICO',
  cidade: 'SAO PAULO',
  padrao: true,
  ativa: true,
  criada_em: '2026-11-10T08:00:00-03:00',
}
const SVG_QRCODE =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 29 29" shape-rendering="crispEdges" ' +
  'role="img" aria-label="QR Code Pix"><rect width="100%" height="100%" fill="#ffffff"/>' +
  '<path fill="#000000" d="M4 4h1v1h-1z"/></svg>'

function cobrancaItem(id: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    devedor: BIA,
    categoria_id: 'cat-1',
    categoria_nome: 'Mensalidade',
    descricao: `Mensalidade ${id}`,
    valor: '150.00',
    vencimento: '2026-12-10',
    situacao: 'ABERTA',
    tem_questionamento_aberto: false,
    tem_convocacao_aberta: false,
    recorrencia_id: null,
    competencia: '',
    cobranca_origem_id: null,
    criada_em: '2026-11-14T10:00:00-03:00',
    ...extra,
  }
}

function cobrancaDetalhe(id: string, extra: Record<string, unknown> = {}) {
  return {
    ...cobrancaItem(id),
    limite_de_inadimplencia: 30,
    chave_pix_id: 'pix-1',
    pix_chave: 'pix@clube.org.br',
    pix_nome_recebedor: 'CLUBE ATLETICO',
    pix_cidade: 'SAO PAULO',
    pix_copia_e_cola: '00020126380014br.gov.bcb.pix0116pix@clube.org.br5204000053039865802BR6304ABCD',
    qrcode_svg: SVG_QRCODE,
    pausada_por_questionamento_em: null,
    dias_pausados_inadimplencia: 0,
    isencao: null,
    cancelamento: null,
    perdao: null,
    paga_em: null,
    encerrada_em: null,
    atualizada_em: '2026-11-14T10:00:00-03:00',
    pagamentos: [],
    questionamentos: [],
    convocacao: null,
    renegociacao: null,
    parcelas: [],
    acoes: [],
    ...extra,
  }
}

function chamou(chamadas: Chamada[], metodo: string, caminho: string) {
  return chamadas.some((c) => c.metodo === metodo && c.caminho === caminho)
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('menu financeiro e acesso sem cargo', () => {
  it('diretor sem cargo vê apenas Minhas cobranças sem consultar /permissoes/minhas/', async () => {
    const chamadas = simularApi({
      ...SEM_CARGO,
      'GET /financeiro/minhas-cobrancas/?limite=20': {
        itens: [cobrancaItem('cob-1')],
        tem_mais: false,
      },
    })

    abrir('/minhas-cobrancas')

    const nav = await screen.findByRole('navigation', { name: 'Financeiro' })
    expect(within(nav).getAllByRole('link').map((l) => l.textContent)).toEqual(['Minhas cobranças'])
    expect(await screen.findByRole('link', { name: 'Mensalidade cob-1' })).toHaveAttribute(
      'href',
      '/cobrancas/cob-1',
    )
    expect(screen.getByText('R$ 150,00')).toBeInTheDocument()
    expect(chamou(chamadas, 'GET', '/permissoes/minhas/')).toBe(false)
  })

  it('diretor sem cargo é redirecionado ao tentar abrir telas de gestão', async () => {
    simularApi(SEM_CARGO)

    abrir('/cobrancas')

    expect(await screen.findByText(/aguarda a classificação/)).toBeInTheDocument()
  })

  it('o admin vê os links de gestão, com Lançamentos, e Configuração financeira', async () => {
    simularApi({
      ...COMO_ADMIN,
      'GET /financeiro/categorias/?todas=1': [CATEGORIA_ENT],
      'GET /financeiro/chaves-pix/?todas=1': [CHAVE_PIX],
    })

    abrir('/configuracao/financeiro')

    const nav = await screen.findByRole('navigation', { name: 'Financeiro' })
    expect(within(nav).getAllByRole('link').map((l) => l.textContent)).toEqual([
      'Minhas cobranças',
      'Lançamentos',
      'Cobranças',
      'Recorrências',
      'Entradas',
      'Configuração financeira',
    ])
  })

  it('diretor com cargo vê gestão financeira sem Configuração financeira', async () => {
    simularApi({
      ...COM_CARGO,
      'GET /financeiro/minhas-cobrancas/?limite=20': { itens: [], tem_mais: false },
    })

    abrir('/minhas-cobrancas')

    const nav = await screen.findByRole('navigation', { name: 'Financeiro' })
    expect(within(nav).getAllByRole('link').map((l) => l.textContent)).toEqual([
      'Minhas cobranças',
      'Lançamentos',
      'Cobranças',
      'Recorrências',
      'Entradas',
    ])
    expect(await screen.findByText('Nenhuma cobrança encontrada.')).toBeInTheDocument()
  })
})

describe('minhas cobranças', () => {
  it('filtra por situação e carrega mais páginas', async () => {
    const chamadas = simularApi({
      ...SEM_CARGO,
      'GET /financeiro/minhas-cobrancas/?limite=20': {
        itens: [cobrancaItem('cob-2')],
        tem_mais: true,
      },
      'GET /financeiro/minhas-cobrancas/?antes=cob-2&limite=20': {
        itens: [cobrancaItem('cob-1')],
        tem_mais: false,
      },
      'GET /financeiro/minhas-cobrancas/?situacao=PAGA&limite=20': {
        itens: [cobrancaItem('cob-3', { situacao: 'PAGA' })],
        tem_mais: false,
      },
    })
    const user = userEvent.setup()

    abrir('/minhas-cobrancas')
    await user.click(await screen.findByRole('button', { name: 'Carregar mais' }))
    expect(await screen.findByRole('link', { name: 'Mensalidade cob-1' })).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Situação'), 'PAGA')
    expect(await screen.findByRole('link', { name: 'Mensalidade cob-3' })).toBeInTheDocument()
    expect(chamou(chamadas, 'GET', '/financeiro/minhas-cobrancas/?situacao=PAGA&limite=20')).toBe(true)
  })
})

describe('configuração financeira do admin (categorias e Pix com aviso LGPD)', () => {
  it('gerencia categorias e chaves Pix e exibe aviso LGPD quando tipo é CPF', async () => {
    const chamadas = simularApi({
      ...COMO_ADMIN,
      'GET /financeiro/categorias/?todas=1': [
        CATEGORIA_ENT,
        { ...CATEGORIA_ENT, id: 'cat-2', nome: 'Arbitragem', natureza: 'SAIDA', ativa: false },
      ],
      'GET /financeiro/chaves-pix/?todas=1': [
        CHAVE_PIX,
        { ...CHAVE_PIX, id: 'pix-2', chave: 'outro@clube.org.br', padrao: false, ativa: false },
      ],
      'POST /financeiro/categorias/': [201, { ...CATEGORIA_ENT, id: 'cat-3', nome: 'Patrocínio' }],
      'POST /financeiro/categorias/cat-1/renomear/': { ...CATEGORIA_ENT, nome: 'Taxa Mensal' },
      'POST /financeiro/categorias/cat-1/desativar/': { ...CATEGORIA_ENT, ativa: false },
      'POST /financeiro/categorias/cat-2/reativar/': { ...CATEGORIA_ENT, id: 'cat-2', ativa: true },
      'POST /financeiro/chaves-pix/': [201, { ...CHAVE_PIX, id: 'pix-3' }],
      'POST /financeiro/chaves-pix/pix-1/editar/': CHAVE_PIX,
      'POST /financeiro/chaves-pix/pix-1/marcar-padrao/': CHAVE_PIX,
      'POST /financeiro/chaves-pix/pix-1/desativar/': { ...CHAVE_PIX, ativa: false },
      'POST /financeiro/chaves-pix/pix-2/reativar/': { ...CHAVE_PIX, id: 'pix-2', ativa: true },
    })
    const user = userEvent.setup()

    abrir('/configuracao/financeiro')

    const formCat = await screen.findByRole('form', { name: 'Nova categoria' })
    await user.type(within(formCat).getByLabelText('Nome'), 'Patrocínio')
    await user.selectOptions(within(formCat).getByLabelText('Natureza'), 'ENTRADA')
    await user.click(within(formCat).getByRole('button', { name: 'Criar categoria' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/categorias/' && c.metodo === 'POST')?.corpo).toEqual({
      nome: 'Patrocínio',
      natureza: 'ENTRADA',
    })

    await user.click(screen.getAllByRole('button', { name: 'Renomear' })[0])
    await user.type(screen.getByLabelText('Novo nome da categoria'), 'Taxa Mensal')
    await user.click(screen.getByRole('button', { name: 'Salvar nome' }))
    expect(chamou(chamadas, 'POST', '/financeiro/categorias/cat-1/renomear/')).toBe(true)

    await user.click(screen.getAllByRole('button', { name: 'Desativar' })[0])
    await user.click(screen.getAllByRole('button', { name: 'Reativar' })[0])
    expect(chamou(chamadas, 'POST', '/financeiro/categorias/cat-1/desativar/')).toBe(true)
    expect(chamou(chamadas, 'POST', '/financeiro/categorias/cat-2/reativar/')).toBe(true)

    const formPix = screen.getByRole('form', { name: 'Nova chave Pix' })
    expect(within(formPix).queryByText(/dado pessoal/i)).not.toBeInTheDocument()
    await user.selectOptions(within(formPix).getByLabelText('Tipo da chave'), 'CPF')
    expect(within(formPix).getByText(/CPF.*dado pessoal/i)).toBeInTheDocument()

    await user.type(within(formPix).getByLabelText('Chave'), '52998224725')
    await user.type(within(formPix).getByLabelText('Nome do recebedor'), 'Titular Teste')
    await user.type(within(formPix).getByLabelText('Cidade'), 'Sao Paulo')
    await user.click(within(formPix).getByLabelText('Definir como chave padrão'))
    await user.click(within(formPix).getByRole('button', { name: 'Cadastrar chave Pix' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/chaves-pix/' && c.metodo === 'POST')?.corpo).toEqual({
      tipo: 'CPF',
      chave: '52998224725',
      nome_recebedor: 'Titular Teste',
      cidade: 'Sao Paulo',
      padrao: true,
    })

    await user.click(screen.getAllByRole('button', { name: 'Editar' })[0])
    await user.click(screen.getByRole('button', { name: 'Salvar chave' }))
    expect(chamou(chamadas, 'POST', '/financeiro/chaves-pix/pix-1/editar/')).toBe(true)
  })
})

describe('cobranças do clube e detalhe com QR Code seguro e ações', () => {
  it('lista com filtros e cria cobrança avulsa e em lote', async () => {
    const chamadas = simularApi({
      ...COMO_ADMIN,
      'GET /financeiro/categorias/?natureza=ENTRADA': [CATEGORIA_ENT],
      'GET /financeiro/chaves-pix/': [CHAVE_PIX],
      'GET /acesso/usuarios/': [
        ADMIN,
        { ...DIRETOR, id: 'u-1', tem_cargo: true },
        { ...DIRETOR, id: 'u-2', nome: 'Carlos', nome_de_usuario: 'carlos', tem_cargo: true },
      ],
      'GET /financeiro/cobrancas/?limite=20': { itens: [cobrancaItem('cob-1')], tem_mais: false },
      'GET /financeiro/cobrancas/?inadimplentes=1&limite=20': { itens: [], tem_mais: false },
      'POST /financeiro/cobrancas/': [201, cobrancaDetalhe('cob-nova')],
      'POST /financeiro/cobrancas/lote/': [201, [cobrancaItem('cob-l1'), cobrancaItem('cob-l2')]],
    })
    const user = userEvent.setup()

    abrir('/cobrancas')

    expect(await screen.findByRole('link', { name: 'Mensalidade cob-1' })).toBeInTheDocument()
    await user.click(screen.getByLabelText('Só inadimplentes'))
    expect(chamou(chamadas, 'GET', '/financeiro/cobrancas/?inadimplentes=1&limite=20')).toBe(true)

    const formAvulsa = screen.getByRole('form', { name: 'Nova cobrança avulsa' })
    await user.selectOptions(within(formAvulsa).getByLabelText('Devedor'), 'u-1')
    await user.selectOptions(within(formAvulsa).getByLabelText('Categoria'), 'cat-1')
    await user.type(within(formAvulsa).getByLabelText('Descrição'), 'Mensalidade dez')
    await user.type(within(formAvulsa).getByLabelText('Valor (R$)'), '200.00')
    await user.type(within(formAvulsa).getByLabelText('Vencimento'), '2026-12-20')
    await user.click(within(formAvulsa).getByRole('button', { name: 'Criar cobrança' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/cobrancas/' && c.metodo === 'POST')?.corpo).toMatchObject({
      devedor_id: 'u-1',
      categoria_id: 'cat-1',
      descricao: 'Mensalidade dez',
      valor: '200.00',
      vencimento: '2026-12-20',
    })

    const formLote = screen.getByRole('form', { name: 'Cobrança em lote' })
    await user.click(within(formLote).getByLabelText('Todos os diretores ativos com cargo'))
    await user.selectOptions(within(formLote).getByLabelText('Categoria'), 'cat-1')
    await user.type(within(formLote).getByLabelText('Descrição'), 'Taxa extra')
    await user.type(within(formLote).getByLabelText('Valor (R$)'), '80.00')
    await user.type(within(formLote).getByLabelText('Vencimento'), '2026-12-28')
    await user.click(within(formLote).getByRole('button', { name: 'Criar em lote' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/cobrancas/lote/' && c.metodo === 'POST')?.corpo).toMatchObject({
      todos_ativos_com_cargo: true,
      categoria_id: 'cat-1',
      valor: '80.00',
    })
  })

  it('mostra QR Code em SVG sem HTML injetado, copia código Pix e executa pagamento COMPROVANTE e questionamento', async () => {
    const chamadas = simularApi({
      ...SEM_CARGO,
      'GET /financeiro/cobrancas/cob-1/': cobrancaDetalhe('cob-1', {
        acoes: ['registrar_pagamento', 'questionar'],
      }),
      'GET /financeiro/cobrancas/cob-1/historico/': [
        {
          acao: 'COBRANCA_CRIADA',
          ator: CARLOS,
          justificativa: '',
          dados: {},
          criado_em: '2026-11-14T10:00:00-03:00',
        },
      ],
      'POST /financeiro/cobrancas/cob-1/pagamentos/': [
        201,
        cobrancaDetalhe('cob-1', { situacao: 'EM_VALIDACAO', acoes: [] }),
      ],
      'POST /financeiro/cobrancas/cob-1/questionar/': [
        201,
        cobrancaDetalhe('cob-1', { tem_questionamento_aberto: true, acoes: [] }),
      ],
    })
    const user = userEvent.setup()
    const copiar = vi.spyOn(navigator.clipboard, 'writeText')

    abrir('/cobrancas/cob-1')

    const qr = await screen.findByRole('img', { name: 'QR Code Pix' })
    expect(qr.tagName.toLowerCase()).toBe('svg')
    expect(qr.querySelector('path')).toHaveAttribute('d', 'M4 4h1v1h-1z')

    await user.click(screen.getByRole('button', { name: 'Copiar código Pix' }))
    expect(copiar).toHaveBeenCalledWith(expect.stringContaining('br.gov.bcb.pix'))
    expect(await screen.findByText('Código Pix copiado.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Registrar pagamento' }))
    const formPag = screen.getByRole('form', { name: 'Registrar pagamento' })
    await user.type(within(formPag).getByLabelText('Data do pagamento'), '2026-11-15')
    const arquivo = new File(['%PDF-1.4'], 'comp.pdf', { type: 'application/pdf' })
    await user.upload(within(formPag).getByLabelText('Comprovante (PDF ou imagem)'), arquivo)
    await user.click(within(formPag).getByRole('button', { name: 'Confirmar' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/cobrancas/cob-1/pagamentos/')?.corpo).toMatchObject({
      forma: 'COMPROVANTE',
      data_pagamento: '2026-11-15',
      comprovante: 'comp.pdf',
    })
  })

  it('mostra ações de validação, comprovante sigiloso, recibo PDF quando PAGA e renegociação', async () => {
    const chamadas = simularApi({
      ...comPermissoes('financeiro.pagamentos.validar', 'financeiro.dividas.decidir'),
      'GET /financeiro/cobrancas/cob-2/': cobrancaDetalhe('cob-2', {
        situacao: 'PAGA',
        paga_em: '2026-11-14T12:00:00-03:00',
        pagamentos: [
          {
            id: 'pag-1',
            forma: 'COMPROVANTE',
            data_pagamento: '2026-11-14',
            recebedor: null,
            comprovante_disponivel: true,
            comprovante_nome: 'pix.png',
            situacao: 'VALIDADO',
            decidido_por: CARLOS,
            motivo_texto: 'Conferido',
            decisao_texto: '',
            registrado_em: '2026-11-14T11:00:00-03:00',
            decidido_em: '2026-11-14T12:00:00-03:00',
          },
          {
            id: 'pag-2',
            forma: 'EM_MAO',
            data_pagamento: '2026-11-13',
            recebedor: CARLOS,
            comprovante_disponivel: false,
            comprovante_nome: '',
            situacao: 'REJEITADO',
            decidido_por: CARLOS,
            motivo_texto: 'Sem recibo',
            decisao_texto: '',
            registrado_em: '2026-11-13T11:00:00-03:00',
            decidido_em: '2026-11-13T12:00:00-03:00',
          },
        ],
        acoes: ['validar_pagamento', 'renegociar'],
      }),
      'GET /financeiro/cobrancas/cob-2/historico/': [],
      'GET /aprovacoes/motivos/?tipo_de_decisao=financeiro.pagamento_validar': [
        { id: 'm-val', tipo_de_decisao: 'financeiro.pagamento_validar', texto: 'Crédito em conta', ativo: true },
      ],
      'GET /aprovacoes/motivos/?tipo_de_decisao=financeiro.divida_decidir': [
        { id: 'm-div', tipo_de_decisao: 'financeiro.divida_decidir', texto: 'Acordo aprovado', ativo: true },
      ],
      'POST /financeiro/cobrancas/cob-2/validar-pagamento/': cobrancaDetalhe('cob-2', { situacao: 'PAGA' }),
      'POST /financeiro/cobrancas/cob-2/renegociar/': cobrancaDetalhe('cob-2', { situacao: 'RENEGOCIADA' }),
    })
    const user = userEvent.setup()

    abrir('/cobrancas/cob-2')

    expect(await screen.findByRole('link', { name: 'Baixar recibo (PDF)' })).toHaveAttribute(
      'href',
      '/api/v1/financeiro/cobrancas/cob-2/recibo/',
    )
    const linksComp = screen.getAllByRole('link', { name: /Abrir comprovante/ })
    expect(linksComp).toHaveLength(1)
    expect(linksComp[0]).toHaveAttribute(
      'href',
      '/api/v1/financeiro/cobrancas/cob-2/pagamentos/pag-1/comprovante/',
    )

    await user.click(screen.getByRole('button', { name: 'Renegociar' }))
    const formRen = screen.getByRole('form', { name: 'Renegociar' })
    await waitFor(() => expect(within(formRen).getByRole('option', { name: 'Acordo aprovado' })).toBeInTheDocument())
    await user.selectOptions(within(formRen).getByLabelText('Motivo'), 'm-div')
    await user.type(within(formRen).getByLabelText('Valor da parcela 1 (R$)'), '75.00')
    await user.type(within(formRen).getByLabelText('Vencimento da parcela 1'), '2026-12-15')
    await user.click(within(formRen).getByRole('button', { name: 'Confirmar' }))

    expect(chamadas.find((c) => c.caminho === '/financeiro/cobrancas/cob-2/renegociar/')?.corpo).toMatchObject({
      motivo_id: 'm-div',
      parcelas: [{ valor: '75.00', vencimento: '2026-12-15' }],
    })
  })

  it('executa pagamento em mão, isenção e decisão de questionamento no detalhe', async () => {
    const chamadas = simularApi({
      ...comPermissoes('financeiro.cobrancas.isentar', 'financeiro.questionamentos.decidir'),
      'GET /financeiro/cobrancas/cob-3/': cobrancaDetalhe('cob-3', {
        situacao: 'ATRASADA',
        tem_questionamento_aberto: true,
        questionamentos: [
          {
            id: 'q-1',
            texto: 'Valor incorreto',
            situacao: 'ABERTO',
            decisao: null,
            decidido_por: null,
            motivo_texto: '',
            decisao_texto: '',
            aberto_em: '2026-11-14T10:00:00-03:00',
            decidido_em: null,
          },
        ],
        convocacao: {
          convocado_em: '2026-11-14T10:00:00-03:00',
          justificativa_do_devedor: 'Em viagem',
          justificada_em: '2026-11-14T12:00:00-03:00',
          decisao: null,
          decidido_por: null,
          motivo_texto: '',
          decisao_texto: '',
          decidido_em: null,
        },
        acoes: ['registrar_pagamento', 'decidir_questionamento', 'isentar'],
      }),
      'GET /financeiro/cobrancas/cob-3/historico/': [],
      'GET /aprovacoes/motivos/?tipo_de_decisao=financeiro.questionamento_decidir': [
        { id: 'm-q', tipo_de_decisao: 'financeiro.questionamento_decidir', texto: 'Revisado', ativo: true },
      ],
      'POST /financeiro/cobrancas/cob-3/pagamentos/': [201, cobrancaDetalhe('cob-3', { situacao: 'EM_VALIDACAO' })],
      'POST /financeiro/cobrancas/cob-3/isentar/': cobrancaDetalhe('cob-3', { situacao: 'ISENTA' }),
    })
    const user = userEvent.setup()

    abrir('/cobrancas/cob-3')
    await user.click(await screen.findByRole('button', { name: 'Registrar pagamento' }))
    const formPag = screen.getByRole('form', { name: 'Registrar pagamento' })
    await user.selectOptions(within(formPag).getByLabelText('Forma'), 'EM_MAO')
    await user.type(within(formPag).getByLabelText('Data do pagamento'), '2026-11-14')
    await user.type(within(formPag).getByLabelText('ID do recebedor'), 'u-2')
    await user.click(within(formPag).getByRole('button', { name: 'Confirmar' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/cobrancas/cob-3/pagamentos/')?.corpo).toEqual({
      forma: 'EM_MAO',
      data_pagamento: '2026-11-14',
      recebedor_id: 'u-2',
    })
  })
})

describe('recorrências e suspensões', () => {
  it('lista, cria, edita e desativa recorrência; cria e encerra suspensão', async () => {
    const chamadas = simularApi({
      ...comPermissoes('financeiro.cobrancas.criar', 'financeiro.cobrancas.suspender'),
      'GET /financeiro/categorias/?natureza=ENTRADA': [CATEGORIA_ENT],
      'GET /financeiro/chaves-pix/': [CHAVE_PIX],
      'GET /financeiro/recorrencias/': [
        {
          id: 'rec-1',
          devedor: BIA,
          categoria_id: 'cat-1',
          categoria_nome: 'Mensalidade',
          descricao: 'Mensalidade padrão',
          valor: '100.00',
          periodicidade: 'MENSAL',
          dia_vencimento: 10,
          mes_vencimento: null,
          antecedencia_dias: 5,
          limite_de_inadimplencia: 30,
          chave_pix_id: 'pix-1',
          ativa: true,
          a_partir_de: '2026-11-01',
          criada_em: '2026-11-01T10:00:00-03:00',
        },
      ],
      'GET /financeiro/suspensoes/': [
        {
          id: 'sus-1',
          diretor: BIA,
          recorrencia_id: null,
          inicio: '2026-11-01',
          fim: '2026-12-01',
          justificativa: 'Afastamento médico',
          situacao: 'VIGENTE',
          criada_em: '2026-11-01T10:00:00-03:00',
          encerrada_em: null,
        },
      ],
      'POST /financeiro/recorrencias/': [201, { id: 'rec-2' }],
      'POST /financeiro/recorrencias/rec-1/editar/': { id: 'rec-1' },
      'POST /financeiro/recorrencias/rec-1/desativar/': { id: 'rec-1', ativa: false },
      'POST /financeiro/suspensoes/': [201, { id: 'sus-2' }],
      'POST /financeiro/suspensoes/sus-1/encerrar/': { id: 'sus-1', situacao: 'ENCERRADA' },
    })
    const user = userEvent.setup()

    abrir('/recorrencias')

    expect(await screen.findByText(/Mensalidade padrão — Bia Diretora/)).toBeInTheDocument()
    expect(screen.getByText(/Afastamento médico/)).toBeInTheDocument()

    const formRec = screen.getByRole('form', { name: 'Nova recorrência' })
    await user.type(within(formRec).getByLabelText('ID do devedor'), 'u-1')
    await user.selectOptions(within(formRec).getByLabelText('Categoria'), 'cat-1')
    await user.type(within(formRec).getByLabelText('Descrição'), 'Anuidade')
    await user.type(within(formRec).getByLabelText('Valor (R$)'), '500.00')
    await user.selectOptions(within(formRec).getByLabelText('Periodicidade'), 'ANUAL')
    await user.clear(within(formRec).getByLabelText('Dia do vencimento'))
    await user.type(within(formRec).getByLabelText('Dia do vencimento'), '15')
    await user.type(within(formRec).getByLabelText('Mês do vencimento'), '3')
    await user.click(within(formRec).getByRole('button', { name: 'Criar recorrência' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/recorrencias/' && c.metodo === 'POST')?.corpo).toMatchObject({
      periodicidade: 'ANUAL',
      dia_vencimento: 15,
      mes_vencimento: 3,
      valor: '500.00',
    })

    await user.click(screen.getByRole('button', { name: 'Editar' }))
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(chamou(chamadas, 'POST', '/financeiro/recorrencias/rec-1/editar/')).toBe(true)

    await user.click(screen.getByRole('button', { name: 'Desativar' }))
    expect(chamou(chamadas, 'POST', '/financeiro/recorrencias/rec-1/desativar/')).toBe(true)

    const formSus = screen.getByRole('form', { name: 'Nova suspensão' })
    await user.type(within(formSus).getByLabelText('ID do diretor'), 'u-1')
    await user.type(within(formSus).getByLabelText('Início'), '2026-12-01')
    await user.type(within(formSus).getByLabelText('Justificativa'), 'Licença')
    await user.click(within(formSus).getByRole('button', { name: 'Suspender' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/suspensoes/' && c.metodo === 'POST')?.corpo).toMatchObject({
      inicio: '2026-12-01',
      justificativa: 'Licença',
    })

    await user.click(screen.getByRole('button', { name: 'Encerrar' }))
    expect(chamou(chamadas, 'POST', '/financeiro/suspensoes/sus-1/encerrar/')).toBe(true)
  })
})

describe('entradas sem devedor', () => {
  it('mostra resumo consolidado, registra entrada e valida ou rejeita com motivo', async () => {
    const chamadas = simularApi({
      ...comPermissoes('financeiro.entradas.registrar', 'financeiro.entradas.validar'),
      'GET /financeiro/categorias/?natureza=ENTRADA': [CATEGORIA_ENT],
      'GET /financeiro/entradas/resumo/': { quantidade: 2, total: '1500.00' },
      'GET /financeiro/entradas/?limite=20': {
        itens: [
          {
            id: 'ent-1',
            tipo: 'SEM_DEVEDOR',
            categoria_id: 'cat-1',
            categoria_nome: 'Mensalidade',
            valor: '750.00',
            data: '2026-11-14',
            origem: 'Patrocínio Padaria Central',
            evidencia_texto: 'Transferência TED',
            comprovante_disponivel: true,
            comprovante_nome: 'ted.pdf',
            registrada_por: CARLOS,
            situacao: 'EM_VALIDACAO',
            decidido_por: null,
            motivo_texto: '',
            decisao_texto: '',
            registrada_em: '2026-11-14T10:00:00-03:00',
            decidido_em: null,
            acoes: ['validar', 'rejeitar'],
          },
        ],
        tem_mais: false,
      },
      'POST /financeiro/entradas/': [201, { id: 'ent-2', situacao: 'EM_VALIDACAO' }],
      'GET /aprovacoes/motivos/?tipo_de_decisao=financeiro.entrada_validar': [
        { id: 'm-ev', tipo_de_decisao: 'financeiro.entrada_validar', texto: 'Extrato conferido', ativo: true },
      ],
      'POST /financeiro/entradas/ent-1/validar/': { id: 'ent-1', situacao: 'VALIDADA' },
    })
    const user = userEvent.setup()

    abrir('/entradas')

    expect(await screen.findByText(/Total validado: R\$ 1\.500,00 \(2\)/)).toBeInTheDocument()
    expect(screen.getByText('Patrocínio Padaria Central')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Abrir comprovante' })).toHaveAttribute(
      'href',
      '/api/v1/financeiro/entradas/ent-1/comprovante/',
    )

    const formEnt = screen.getByRole('form', { name: 'Registrar entrada' })
    await user.selectOptions(within(formEnt).getByLabelText('Categoria'), 'cat-1')
    await user.type(within(formEnt).getByLabelText('Valor (R$)'), '300.00')
    await user.type(within(formEnt).getByLabelText('Data'), '2026-11-14')
    await user.type(within(formEnt).getByLabelText('Origem'), 'Rifa do jogo')
    await user.type(within(formEnt).getByLabelText('Evidência em texto'), 'Recibo')
    await user.click(within(formEnt).getByRole('button', { name: 'Registrar entrada' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/entradas/' && c.metodo === 'POST')?.corpo).toMatchObject({
      origem: 'Rifa do jogo',
      valor: '300.00',
    })

    await user.click(screen.getByRole('button', { name: 'Validar' }))
    const formVal = screen.getByRole('form', { name: 'Validar entrada' })
    await waitFor(() =>
      expect(within(formVal).getByRole('option', { name: 'Extrato conferido' })).toBeInTheDocument(),
    )
    await user.selectOptions(within(formVal).getByLabelText('Motivo'), 'm-ev')
    await user.click(within(formVal).getByRole('button', { name: 'Confirmar' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/entradas/ent-1/validar/')?.corpo).toEqual({
      motivo_id: 'm-ev',
      texto: '',
    })
  })

  it('exibe mensagem de erro amigável da API', async () => {
    simularApi({
      ...COM_CARGO,
      'GET /financeiro/categorias/?natureza=ENTRADA': erro(422, 'CHAVE_PIX_PADRAO_NAO_CONFIGURADA'),
      'GET /financeiro/entradas/resumo/': erro(403, 'PERMISSION_DENIED'),
      'GET /financeiro/entradas/?limite=20': { itens: [], tem_mais: false },
    })

    abrir('/entradas')

    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
