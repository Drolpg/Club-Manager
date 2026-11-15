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
const SEM_CARGO = { 'GET /acesso/sessao/': { usuario: DIRETOR }, ...SEM_GOOGLE, ...RESUMO_NOTIF }
const COMO_ADMIN = { 'GET /acesso/sessao/': { usuario: ADMIN }, ...SEM_GOOGLE, ...RESUMO_NOTIF }

function comPermissoes(...codigos: string[]) {
  return {
    'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
    'GET /permissoes/minhas/': {
      cargo: { id: 'ca-1', nome: 'Tesoureiro', ativo: true },
      setores: [{ id: 'set-1', nome: 'Logística', ativo: true }],
      permissoes: codigos.map((codigo) => ({ codigo, nome: codigo, origens: [] })),
    },
    ...SEM_GOOGLE,
    ...RESUMO_NOTIF,
  }
}

const BIA = { id: 'u-1', nome: 'Bia Diretora' }
const CARLOS = { id: 'u-2', nome: 'Carlos Tesoureiro' }
const DORA = { id: 'u-3', nome: 'Dora Fiscal' }

const REFS_GASTOS = {
  categorias_saida: [{ id: 'cat-s1', nome: 'Transporte' }],
  categorias_entrada: [{ id: 'cat-e1', nome: 'Diversos' }],
  setores: [{ id: 'set-1', nome: 'Logística' }],
  aprovadores_gastos: [CARLOS, DORA],
  diretores_ativos: [BIA, CARLOS, DORA],
}

const CAIXA = {
  total_entradas_validadas: '2000.00',
  total_saidas_liquidadas: '450.00',
  total_comprometido: '300.00',
}

function saidaItem(id: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    solicitacao_id: `sol-${id}`,
    versao_aprovada: 1,
    solicitante: BIA,
    categoria_id: 'cat-s1',
    categoria_nome: 'Transporte',
    setor_id: 'set-1',
    setor_nome: 'Logística',
    evento_id: null,
    descricao: `Fretamento ${id}`,
    valor_aprovado: '500.00',
    valor_aprovado_total: '500.00',
    total_enviado: '0.00',
    total_gasto: null,
    total_devolvido_validado: '0.00',
    total_devolvido_pendente: '0.00',
    valor_nao_reembolsado: '0.00',
    situacao: 'AGUARDANDO_ENVIO',
    em_atraso: false,
    tem_complemento_aprovado_para_enviar: false,
    tem_complemento_em_andamento: false,
    primeiro_envio_em: null,
    criada_em: '2026-11-10T10:00:00-03:00',
    atualizada_em: '2026-11-10T10:00:00-03:00',
    ...extra,
  }
}

function saidaDetalhe(id: string, extra: Record<string, unknown> = {}) {
  return {
    ...saidaItem(id),
    itens: [{ descricao: 'Ônibus ida e volta', valor: '500.00' }],
    liquidacao_justificativa: '',
    liquidada_por: null,
    liquidada_em: null,
    cancelada_em: null,
    cotacao: { id: 'cot-1', nome: 'orcamento.pdf', disponivel: true },
    envios: [],
    prestacoes: [],
    devolucoes: [],
    complementos: [],
    estorno: null,
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

describe('menu e proteção das rotas de gastos e saídas', () => {
  it('diretor sem cargo não vê navegação de saídas e é redirecionado', async () => {
    simularApi(SEM_CARGO)

    abrir('/saidas')

    expect(await screen.findByText(/aguarda a classificação/)).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Saídas e gastos' })).not.toBeInTheDocument()
  })

  it('diretor com cargo vê Saídas e gastos e Pedir gasto sem quebrar menu Financeiro', async () => {
    simularApi({
      ...comPermissoes(),
      'GET /financeiro/caixa/': CAIXA,
      'GET /financeiro/referencias-gastos/': REFS_GASTOS,
      'GET /financeiro/saidas/?limite=20': { itens: [], tem_mais: false },
      'GET /financeiro/estornos/?limite=20': { itens: [], tem_mais: false },
    })

    abrir('/saidas')

    const navSaidas = await screen.findByRole('navigation', { name: 'Saídas e gastos' })
    expect(within(navSaidas).getByRole('link', { name: 'Saídas e gastos' })).toHaveAttribute('href', '/saidas')
    expect(within(navSaidas).getByRole('link', { name: 'Pedir gasto' })).toHaveAttribute('href', '/gastos/novo')
  })
})

describe('pedir gasto e acompanhamento do caixa nas aprovações', () => {
  it('calcula soma dos itens em tempo real, anexa cotação e envia solicitação com aprovador indicado', async () => {
    const chamadas = simularApi({
      ...comPermissoes('gastos.aprovar'),
      'GET /financeiro/referencias-gastos/': REFS_GASTOS,
      'POST /financeiro/cotacoes/': [201, { id: 'cot-1', nome: 'cot.pdf', mime: 'application/pdf', tamanho: 40, criada_em: '2026-11-15T10:00:00Z' }],
      'POST /financeiro/gastos/': [
        201,
        {
          id: 'sol-99',
          tipo: 'financeiro.gasto',
          situacao: 'EM_ANALISE',
          solicitante_id: 'u-1',
          aprovador_indicado_id: 'u-2',
          versao_atual: 1,
          valor: '350.00',
          resumo: 'Viagem sub-20',
          conteudo: {},
        },
      ],
      'GET /aprovacoes/solicitacoes/sol-99/': {
        id: 'sol-99',
        tipo: 'financeiro.gasto',
        tipo_nome: 'Solicitação de gasto',
        tem_valor: true,
        situacao: 'EM_ANALISE',
        solicitante: BIA,
        aprovador_indicado: CARLOS,
        numero_da_versao_atual: 1,
        criada_em: '2026-11-15T10:00:00Z',
        atualizada_em: '2026-11-15T10:00:00Z',
        versoes: [
          {
            numero: 1,
            conteudo: {
              descricao: 'Viagem sub-20',
              categoria_id: 'cat-s1',
              categoria_nome: 'Transporte',
              setor_id: 'set-1',
              setor_nome: 'Logística',
              itens: [
                { descricao: 'Ônibus', valor: '250.00' },
                { descricao: 'Pedágio', valor: '100.00' },
              ],
              cotacao_id: 'cot-1',
              cotacao_nome: 'cot.pdf',
              saida_origem_id: null,
              evento_id: null,
            },
            valor: '350.00',
            resumo: 'Viagem sub-20',
            autor: BIA,
            justificativa: '',
            criada_em: '2026-11-15T10:00:00Z',
            decisao: null,
          },
        ],
        acoes: [],
      },
      'GET /aprovacoes/solicitacoes/sol-99/historico/': [],
      'GET /financeiro/caixa/': CAIXA,
    })
    const user = userEvent.setup()

    abrir('/gastos/novo')

    await user.type(await screen.findByLabelText('Descrição geral'), 'Viagem sub-20')
    await user.selectOptions(screen.getByLabelText('Categoria de saída'), 'cat-s1')
    await user.selectOptions(screen.getByLabelText('Setor'), 'set-1')
    await user.type(screen.getByLabelText('Descrição do item 1'), 'Ônibus')
    await user.type(screen.getByLabelText('Valor do item 1 (R$)'), '250.00')
    await user.click(screen.getByRole('button', { name: 'Adicionar item' }))
    await user.type(screen.getByLabelText('Descrição do item 2'), 'Pedágio')
    await user.type(screen.getByLabelText('Valor do item 2 (R$)'), '100.00')
    expect(screen.getByText(/Total calculado: R\$ 350,00/)).toBeInTheDocument()

    const arquivo = new File(['%PDF-1.4'], 'cot.pdf', { type: 'application/pdf' })
    await user.upload(screen.getByLabelText('Cotação (PDF ou imagem, opcional)'), arquivo)
    await user.selectOptions(screen.getByLabelText('Aprovador indicado (opcional)'), 'u-2')
    await user.click(screen.getByRole('button', { name: 'Enviar solicitação' }))

    await waitFor(() => expect(chamou(chamadas, 'POST', '/financeiro/cotacoes/')).toBe(true))
    expect(chamadas.find((c) => c.caminho === '/financeiro/gastos/' && c.metodo === 'POST')?.corpo).toEqual({
      descricao: 'Viagem sub-20',
      categoria_id: 'cat-s1',
      setor_id: 'set-1',
      itens: [
        { descricao: 'Ônibus', valor: '250.00' },
        { descricao: 'Pedágio', valor: '100.00' },
      ],
      cotacao_id: 'cot-1',
      aprovador_indicado_id: 'u-2',
    })

    // Após navegar para /solicitacoes/sol-99 (EM_ANALISE), exibe Visão do caixa e tabela estruturada.
    expect(await screen.findByRole('region', { name: 'Visão do caixa' })).toHaveTextContent('R$ 2.000,00')
    expect(screen.getByRole('region', { name: 'Visão do caixa' })).toHaveTextContent('R$ 300,00')
    expect(screen.getByRole('link', { name: /Abrir cotação/ })).toHaveAttribute(
      'href',
      '/api/v1/financeiro/cotacoes/cot-1/',
    )
  })

  it('reenvia solicitação financeiro.gasto contestada usando editor estruturado em vez de JSON', async () => {
    const chamadas = simularApi({
      ...comPermissoes(),
      'GET /financeiro/referencias-gastos/': REFS_GASTOS,
      'GET /aprovacoes/solicitacoes/sol-88/': {
        id: 'sol-88',
        tipo: 'financeiro.gasto',
        tipo_nome: 'Solicitação de gasto',
        tem_valor: true,
        situacao: 'CONTESTADA',
        solicitante: BIA,
        aprovador_indicado: null,
        numero_da_versao_atual: 1,
        criada_em: '2026-11-15T10:00:00Z',
        atualizada_em: '2026-11-15T10:00:00Z',
        versoes: [
          {
            numero: 1,
            conteudo: {
              descricao: 'Compra antiga',
              categoria_id: 'cat-s1',
              categoria_nome: 'Transporte',
              setor_id: 'set-1',
              setor_nome: 'Logística',
              itens: [{ descricao: 'Van', valor: '400.00' }],
              cotacao_id: null,
              cotacao_nome: '',
              saida_origem_id: null,
              evento_id: null,
            },
            valor: '400.00',
            resumo: 'Compra antiga',
            autor: BIA,
            justificativa: '',
            criada_em: '2026-11-15T10:00:00Z',
            decisao: null,
          },
        ],
        acoes: ['reenviar'],
      },
      'GET /aprovacoes/solicitacoes/sol-88/historico/': [],
      'POST /aprovacoes/solicitacoes/sol-88/reenviar/': { id: 'sol-88', situacao: 'EM_ANALISE' },
    })
    const user = userEvent.setup()

    abrir('/solicitacoes/sol-88')

    await user.click(await screen.findByRole('button', { name: 'Reenviar' }))
    const form = screen.getByRole('form', { name: 'Reenviar' })
    expect(within(form).queryByLabelText('Conteúdo (JSON)')).not.toBeInTheDocument()
    const campoValor = within(form).getByLabelText('Valor do item 1 (R$)')
    await user.clear(campoValor)
    await user.type(campoValor, '320.00')
    await user.click(within(form).getByRole('button', { name: 'Confirmar' }))

    await waitFor(() =>
      expect(chamadas.find((c) => c.caminho === '/aprovacoes/solicitacoes/sol-88/reenviar/')?.corpo).toEqual({
        conteudo: {
          descricao: 'Compra antiga',
          categoria_id: 'cat-s1',
          setor_id: 'set-1',
          itens: [{ descricao: 'Van', valor: '320.00' }],
          cotacao_id: null,
        },
      }),
    )
  })
})

describe('painel de saídas, filas e estornos', () => {
  it('exibe visão do caixa, filas operacionais, badge Em atraso e lista estornos', async () => {
    const chamadas = simularApi({
      ...comPermissoes(),
      'GET /financeiro/caixa/': CAIXA,
      'GET /financeiro/referencias-gastos/': REFS_GASTOS,
      'GET /financeiro/saidas/?limite=20': {
        itens: [
          saidaItem('s-1', {
            situacao: 'RECURSO_ENVIADO',
            total_enviado: '500.00',
            em_atraso: true,
          }),
        ],
        tem_mais: false,
      },
      'GET /financeiro/saidas/?pendentes_envio=1&limite=20': {
        itens: [saidaItem('s-2')],
        tem_mais: false,
      },
      'GET /financeiro/estornos/?limite=20': {
        itens: [
          {
            id: 'est-1',
            alvo_tipo: 'COBRANCA',
            alvo_id: 'cob-9',
            valor: '90.00',
            motivo_id: 'm-est',
            motivo_texto: 'Erro de lançamento',
            justificativa: 'Lançado duas vezes',
            registrado_por: CARLOS,
            registrado_em: '2026-11-15T11:00:00Z',
          },
        ],
        tem_mais: false,
      },
    })
    const user = userEvent.setup()

    abrir('/saidas')

    const caixa = await screen.findByRole('region', { name: 'Visão do caixa' })
    expect(caixa).toHaveTextContent('R$ 2.000,00')
    expect(caixa).toHaveTextContent('R$ 450,00')
    expect(caixa).toHaveTextContent('R$ 300,00')

    expect(await screen.findByText('Em atraso')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Fretamento s-1' })).toHaveAttribute('href', '/saidas/s-1')

    const estornos = screen.getByRole('region', { name: 'Estornos registrados' })
    expect(within(estornos).getByText(/Lançado duas vezes/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Aguardando envio' }))
    expect(await screen.findByRole('link', { name: 'Fretamento s-2' })).toBeInTheDocument()
    expect(chamou(chamadas, 'GET', '/financeiro/saidas/?pendentes_envio=1&limite=20')).toBe(true)
  })
})

describe('detalhe da saída e todas as ações do fluxo M7', () => {
  it('executa cancelamento pré-envio via aprovações e exibe histórico', async () => {
    const chamadas = simularApi({
      ...comPermissoes(),
      'GET /financeiro/saidas/s-1/': saidaDetalhe('s-1', { acoes: [] }),
      'GET /financeiro/saidas/s-1/historico/': [
        { acao: 'SAIDA_ABERTA', ator: CARLOS, justificativa: '', dados: {}, criado_em: '2026-11-14T10:00:00Z' },
      ],
      'POST /aprovacoes/solicitacoes/sol-s-1/cancelar/': { id: 'sol-s-1', situacao: 'CANCELADA' },
    })
    const user = userEvent.setup()

    abrir('/saidas/s-1')

    await user.click(await screen.findByRole('button', { name: 'Cancelar solicitação' }))
    const form = screen.getByRole('form', { name: 'Cancelar solicitação' })
    await user.type(within(form).getByLabelText('Motivo do cancelamento'), 'Evento adiado')
    await user.click(within(form).getByRole('button', { name: 'Confirmar' }))

    expect(chamadas.find((c) => c.caminho === '/aprovacoes/solicitacoes/sol-s-1/cancelar/')?.corpo).toEqual({
      motivo: 'Evento adiado',
    })
  })

  it('executa envio, prestação, devolução, complemento, liquidação e estorno comandados por acoes', async () => {
    const chamadas = simularApi({
      ...COMO_ADMIN,
      'GET /financeiro/referencias-gastos/': REFS_GASTOS,
      'GET /aprovacoes/motivos/?tipo_de_decisao=financeiro.prestacao_devolver': [
        { id: 'm-dp', tipo_de_decisao: 'financeiro.prestacao_devolver', texto: 'Nota ilegível', ativo: true },
      ],
      'GET /aprovacoes/motivos/?tipo_de_decisao=financeiro.estornar': [
        { id: 'm-est', tipo_de_decisao: 'financeiro.estornar', texto: 'Lançamento duplicado', ativo: true },
      ],
      'GET /financeiro/saidas/s-5/': saidaDetalhe('s-5', {
        situacao: 'EM_CONFERENCIA',
        total_enviado: '500.00',
        total_gasto: '530.00',
        em_atraso: true,
        envios: [
          {
            id: 'env-1',
            valor: '500.00',
            complemento_id: null,
            enviado_por: CARLOS,
            enviado_em: '2026-11-10T10:00:00Z',
            comprovante_disponivel: true,
            comprovante_nome: 'ted.pdf',
          },
        ],
        prestacoes: [
          {
            id: 'pr-1',
            valor: '530.00',
            descricao: 'Combustível subiu',
            registrada_por: BIA,
            registrada_em: '2026-11-12T10:00:00Z',
            situacao: 'VIGENTE',
            comprovante_disponivel: true,
            comprovante_nome: 'nf.png',
            devolvida_por: null,
            motivo_devolucao_texto: '',
            texto_devolucao: '',
            devolvida_em: null,
          },
        ],
        acoes: [
          'enviar_recurso',
          'prestar_contas',
          'devolver_prestacao',
          'devolver_sobra',
          'pedir_complemento',
          'liquidar',
          'estornar',
        ],
      }),
      'GET /financeiro/saidas/s-5/historico/': [],
      'POST /financeiro/saidas/s-5/envios/': [201, saidaDetalhe('s-5', { situacao: 'RECURSO_ENVIADO' })],
      'POST /financeiro/saidas/s-5/prestacoes/': [201, saidaDetalhe('s-5', { situacao: 'EM_CONFERENCIA' })],
      'POST /financeiro/saidas/s-5/devolver-prestacao/': saidaDetalhe('s-5', { situacao: 'RECURSO_ENVIADO' }),
      'POST /financeiro/saidas/s-5/devolucoes/': [201, { id: 'ent-d1' }],
      'POST /financeiro/saidas/s-5/complementos/': [201, { id: 'cmp-1', solicitacao_id: 'sol-cmp-1' }],
      'POST /financeiro/saidas/s-5/liquidar/': saidaDetalhe('s-5', { situacao: 'LIQUIDADA' }),
      'POST /financeiro/saidas/s-5/estornar/': [201, { id: 'est-2', registro: saidaDetalhe('s-5', { situacao: 'ESTORNADA' }) }],
    })
    const user = userEvent.setup()

    abrir('/saidas/s-5')

    expect(await screen.findByRole('link', { name: /Comprovante do envio/ })).toHaveAttribute(
      'href',
      '/api/v1/financeiro/saidas/s-5/envios/env-1/comprovante/',
    )
    expect(screen.getByRole('link', { name: /Comprovante da prestação/ })).toHaveAttribute(
      'href',
      '/api/v1/financeiro/saidas/s-5/prestacoes/pr-1/comprovante/',
    )

    // Enviar recurso com comprovante.
    await user.click(screen.getByRole('button', { name: 'Enviar recurso' }))
    const fEnv = screen.getByRole('form', { name: 'Enviar recurso' })
    await user.type(within(fEnv).getByLabelText('Valor enviado (R$)'), '500.00')
    await user.upload(
      within(fEnv).getByLabelText('Comprovante do envio (obrigatório)'),
      new File(['%PDF'], 'ted.pdf', { type: 'application/pdf' }),
    )
    await user.click(within(fEnv).getByRole('button', { name: 'Confirmar' }))
    expect(chamou(chamadas, 'POST', '/financeiro/saidas/s-5/envios/')).toBe(true)

    // Prestar contas.
    await user.click(screen.getByRole('button', { name: 'Prestar contas' }))
    const fPrest = screen.getByRole('form', { name: 'Prestar contas' })
    await user.type(within(fPrest).getByLabelText('Total gasto (R$)'), '530.00')
    await user.type(within(fPrest).getByLabelText('Descrição / justificativa'), 'Pedágio extra')
    await user.click(within(fPrest).getByRole('button', { name: 'Confirmar' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/saidas/s-5/prestacoes/')?.corpo).toMatchObject({
      valor: '530.00',
      descricao: 'Pedágio extra',
    })

    // Devolver prestação.
    await user.click(screen.getByRole('button', { name: 'Devolver prestação' }))
    const fDevP = screen.getByRole('form', { name: 'Devolver prestação' })
    await within(fDevP).findByRole('option', { name: 'Nota ilegível' })
    await user.selectOptions(within(fDevP).getByLabelText('Motivo'), 'm-dp')
    await user.type(within(fDevP).getByLabelText('Texto (opcional)'), 'Reenvie a nota')
    await user.click(within(fDevP).getByRole('button', { name: 'Confirmar' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/saidas/s-5/devolver-prestacao/')?.corpo).toEqual({
      motivo_id: 'm-dp',
      texto: 'Reenvie a nota',
    })

    // Devolver sobra.
    await user.click(screen.getByRole('button', { name: 'Devolver sobra' }))
    const fSob = screen.getByRole('form', { name: 'Devolver sobra' })
    await user.type(within(fSob).getByLabelText('Valor devolvido (R$)'), '20.00')
    await user.type(within(fSob).getByLabelText('Evidência em texto'), 'Pix troco')
    await user.click(within(fSob).getByRole('button', { name: 'Confirmar' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/saidas/s-5/devolucoes/')?.corpo).toMatchObject({
      valor: '20.00',
      evidencia_texto: 'Pix troco',
    })

    // Pedir complemento.
    await user.click(screen.getByRole('button', { name: 'Pedir complemento' }))
    const fComp = screen.getByRole('form', { name: 'Pedir complemento' })
    await user.type(within(fComp).getByLabelText('Descrição do item 1'), 'Diferença diesel')
    await user.type(within(fComp).getByLabelText('Valor do item 1 (R$)'), '30.00')
    await user.click(within(fComp).getByRole('button', { name: 'Confirmar' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/saidas/s-5/complementos/')?.corpo).toMatchObject({
      itens: [{ descricao: 'Diferença diesel', valor: '30.00' }],
    })

    // Liquidar.
    await user.click(screen.getByRole('button', { name: 'Liquidar' }))
    const fLiq = screen.getByRole('form', { name: 'Liquidar' })
    await user.type(within(fLiq).getByLabelText('Justificativa (obrigatória se houver excesso sem reembolso)'), 'Sem reembolso')
    await user.click(within(fLiq).getByRole('button', { name: 'Confirmar' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/saidas/s-5/liquidar/')?.corpo).toEqual({
      justificativa: 'Sem reembolso',
    })

    // Estornar saída.
    await user.click(screen.getByRole('button', { name: 'Estornar' }))
    const fEst = screen.getByRole('form', { name: 'Estornar' })
    await within(fEst).findByRole('option', { name: 'Lançamento duplicado' })
    await user.selectOptions(within(fEst).getByLabelText('Motivo'), 'm-est')
    await user.type(within(fEst).getByLabelText('Justificativa'), 'Saída em duplicidade')
    await user.click(within(fEst).getByRole('button', { name: 'Confirmar' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/saidas/s-5/estornar/')?.corpo).toEqual({
      motivo_id: 'm-est',
      justificativa: 'Saída em duplicidade',
    })
  })
})

describe('estorno de entradas e cobranças', () => {
  it('permite estornar entrada validada e mostra resumo de estorno na lista', async () => {
    const chamadas = simularApi({
      ...comPermissoes('financeiro.estornar'),
      'GET /financeiro/categorias/?natureza=ENTRADA': [{ id: 'cat-1', nome: 'Patrocínio', natureza: 'ENTRADA', ativa: true, criada_em: '2026-11-10Z' }],
      'GET /financeiro/entradas/resumo/': { quantidade: 1, total: '750.00' },
      'GET /financeiro/entradas/?limite=20': {
        itens: [
          {
            id: 'ent-9',
            tipo: 'SEM_DEVEDOR',
            categoria_id: 'cat-1',
            categoria_nome: 'Patrocínio',
            saida_id: null,
            valor: '750.00',
            data: '2026-11-14',
            origem: 'Patrocínio Central',
            evidencia_texto: 'TED',
            comprovante_disponivel: false,
            comprovante_nome: '',
            registrada_por: CARLOS,
            situacao: 'VALIDADA',
            decidido_por: DORA,
            motivo_texto: 'Ok',
            decisao_texto: '',
            registrada_em: '2026-11-14T10:00:00Z',
            decidido_em: '2026-11-14T11:00:00Z',
            estorno: null,
            acoes: ['estornar'],
          },
        ],
        tem_mais: false,
      },
      'GET /aprovacoes/motivos/?tipo_de_decisao=financeiro.estornar': [
        { id: 'm-est', tipo_de_decisao: 'financeiro.estornar', texto: 'Erro de valor', ativo: true },
      ],
      'POST /financeiro/entradas/ent-9/estornar/': [
        201,
        {
          id: 'est-e1',
          alvo_tipo: 'ENTRADA',
          alvo_id: 'ent-9',
          valor: '750.00',
          motivo_id: 'm-est',
          motivo_texto: 'Erro de valor',
          justificativa: 'Estornar lançamento errado',
          registrado_por: BIA,
          registrado_em: '2026-11-15T10:00:00Z',
          registro: { id: 'ent-9', situacao: 'ESTORNADA' },
        },
      ],
    })
    const user = userEvent.setup()

    abrir('/entradas')

    await user.click(await screen.findByRole('button', { name: 'Estornar' }))
    const form = screen.getByRole('form', { name: 'Estornar entrada' })
    await within(form).findByRole('option', { name: 'Erro de valor' })
    await user.selectOptions(within(form).getByLabelText('Motivo'), 'm-est')
    await user.type(within(form).getByLabelText('Justificativa'), 'Estornar lançamento errado')
    await user.click(within(form).getByRole('button', { name: 'Confirmar' }))

    expect(chamadas.find((c) => c.caminho === '/financeiro/entradas/ent-9/estornar/')?.corpo).toEqual({
      motivo_id: 'm-est',
      justificativa: 'Estornar lançamento errado',
    })
  })

  it('permite estornar cobrança paga, oculta recibo quando estornada e exibe bloco de estorno', async () => {
    const cob10Base = {
      id: 'cob-10',
      devedor: BIA,
      categoria_id: 'cat-1',
      categoria_nome: 'Mensalidade',
      descricao: 'Mensalidade Outubro',
      valor: '150.00',
      vencimento: '2026-12-10',
      situacao: 'PAGA',
      tem_questionamento_aberto: false,
      tem_convocacao_aberta: false,
      recorrencia_id: null,
      competencia: '',
      cobranca_origem_id: null,
      criada_em: '2026-11-10T10:00:00Z',
      limite_de_inadimplencia: 30,
      chave_pix_id: 'pix-1',
      pix_chave: 'pix@clube.org.br',
      pix_nome_recebedor: 'CLUBE',
      pix_cidade: 'SP',
      pix_copia_e_cola: '0002',
      qrcode_svg: '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
      pausada_por_questionamento_em: null,
      dias_pausados_inadimplencia: 0,
      isencao: null,
      cancelamento: null,
      perdao: null,
      paga_em: '2026-11-12T10:00:00Z',
      encerrada_em: '2026-11-12T10:00:00Z',
      atualizada_em: '2026-11-12T10:00:00Z',
      pagamentos: [],
      questionamentos: [],
      convocacao: null,
      renegociacao: null,
      parcelas: [],
      estorno: null,
      acoes: ['estornar'],
    }
    const estornoCob10 = {
      id: 'est-c2',
      valor: '150.00',
      motivo_texto: 'Erro de conciliação',
      justificativa: 'Estorno cob-10',
      registrado_por: BIA,
      registrado_em: '2026-11-15T10:00:00Z',
    }
    const chamadas = simularApi({
      ...comPermissoes('financeiro.estornar'),
      'GET /financeiro/cobrancas/cob-9/': {
        ...cob10Base,
        id: 'cob-9',
        descricao: 'Mensalidade Setembro',
        situacao: 'ESTORNADA',
        paga_em: null,
        encerrada_em: '2026-11-15T10:00:00Z',
        atualizada_em: '2026-11-15T10:00:00Z',
        estorno: {
          id: 'est-c1',
          valor: '150.00',
          motivo_texto: 'Erro de conciliação',
          justificativa: 'Pagamento não caiu na conta',
          registrado_por: CARLOS,
          registrado_em: '2026-11-15T10:00:00Z',
        },
        acoes: [],
      },
      'GET /financeiro/cobrancas/cob-9/historico/': [],
      'GET /financeiro/cobrancas/cob-10/': cob10Base,
      'GET /financeiro/cobrancas/cob-10/historico/': [],
      'GET /aprovacoes/motivos/?tipo_de_decisao=financeiro.estornar': [
        { id: 'm-est', tipo_de_decisao: 'financeiro.estornar', texto: 'Erro de conciliação', ativo: true },
      ],
      'POST /financeiro/cobrancas/cob-10/estornar/': [
        201,
        {
          ...estornoCob10,
          alvo_tipo: 'COBRANCA',
          alvo_id: 'cob-10',
          motivo_id: 'm-est',
          registro: { ...cob10Base, situacao: 'ESTORNADA', estorno: estornoCob10, acoes: [] },
        },
      ],
    })
    const user = userEvent.setup()

    const { unmount } = abrir('/cobrancas/cob-9')

    expect(await screen.findByText('Estornada')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Baixar recibo (PDF)' })).not.toBeInTheDocument()
    const secEst = screen.getByRole('region', { name: 'Estorno' })
    expect(within(secEst).getByText(/Pagamento não caiu na conta/)).toBeInTheDocument()
    unmount()

    abrir('/cobrancas/cob-10')
    await user.click(await screen.findByRole('button', { name: 'Estornar' }))
    const fEst = screen.getByRole('form', { name: 'Estornar' })
    await within(fEst).findByRole('option', { name: 'Erro de conciliação' })
    await user.selectOptions(within(fEst).getByLabelText('Motivo'), 'm-est')
    await user.type(within(fEst).getByLabelText('Justificativa'), 'Estorno cob-10')
    await user.click(within(fEst).getByRole('button', { name: 'Confirmar' }))

    expect(chamadas.find((c) => c.caminho === '/financeiro/cobrancas/cob-10/estornar/')?.corpo).toEqual({
      motivo_id: 'm-est',
      justificativa: 'Estorno cob-10',
    })
  })

  it('exibe mensagens amigáveis da API para erros de saídas e gastos', async () => {
    simularApi({
      ...comPermissoes(),
      'GET /financeiro/referencias-gastos/': REFS_GASTOS,
      'POST /financeiro/gastos/': erro(422, 'APROVADOR_INVALIDO'),
    })
    const user = userEvent.setup()

    abrir('/gastos/novo')
    await user.type(await screen.findByLabelText('Descrição geral'), 'Teste')
    await user.selectOptions(screen.getByLabelText('Categoria de saída'), 'cat-s1')
    await user.selectOptions(screen.getByLabelText('Setor'), 'set-1')
    await user.type(screen.getByLabelText('Descrição do item 1'), 'Item')
    await user.type(screen.getByLabelText('Valor do item 1 (R$)'), '10.00')
    await user.click(screen.getByRole('button', { name: 'Enviar solicitação' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Escolha outro diretor ativo com cargo como aprovador indicado.',
    )
  })

  it('cobre filtros completos, filas, paginação e erro na listagem de saídas e estornos', async () => {
    const est1 = {
      id: 'est-1',
      alvo_tipo: 'COBRANCA',
      alvo_id: 'cob-9',
      valor: '90.00',
      motivo_id: 'm-est',
      motivo_texto: 'Erro',
      justificativa: 'Primeiro estorno',
      registrado_por: CARLOS,
      registrado_em: '2026-11-15T11:00:00Z',
    }
    const est2 = { ...est1, id: 'est-2', alvo_tipo: 'SAIDA', justificativa: 'Segundo estorno' }
    const chamadas = simularApi({
      ...comPermissoes(),
      'GET /financeiro/caixa/': CAIXA,
      'GET /financeiro/referencias-gastos/': REFS_GASTOS,
      'GET /financeiro/saidas/?limite=20': { itens: [saidaItem('s-1')], tem_mais: true },
      'GET /financeiro/saidas/?antes=s-1&limite=20': { itens: [saidaItem('s-2')], tem_mais: false },
      'GET /financeiro/saidas/?pendentes_prestacao=1&limite=20': { itens: [saidaItem('s-3')], tem_mais: false },
      'GET /financeiro/saidas/?atrasadas=1&limite=20': { itens: [saidaItem('s-4')], tem_mais: false },
      'GET /financeiro/saidas/?situacao=AGUARDANDO_ENVIO&limite=20': { itens: [], tem_mais: false },
      'GET /financeiro/saidas/?situacao=AGUARDANDO_ENVIO&categoria_id=cat-s1&limite=20': {
        itens: [],
        tem_mais: false,
      },
      'GET /financeiro/saidas/?situacao=AGUARDANDO_ENVIO&categoria_id=cat-s1&setor_id=set-1&limite=20': {
        itens: [],
        tem_mais: false,
      },
      'GET /financeiro/saidas/?situacao=AGUARDANDO_ENVIO&categoria_id=cat-s1&setor_id=set-1&solicitante_id=u-1&limite=20':
        { itens: [], tem_mais: false },
      'GET /financeiro/saidas/?situacao=AGUARDANDO_ENVIO&categoria_id=cat-s1&setor_id=set-1&solicitante_id=u-1&de=2026-11-01&limite=20':
        { itens: [], tem_mais: false },
      'GET /financeiro/saidas/?situacao=AGUARDANDO_ENVIO&categoria_id=cat-s1&setor_id=set-1&solicitante_id=u-1&de=2026-11-01&ate=2026-11-30&limite=20':
        { itens: [], tem_mais: false },
      'GET /financeiro/estornos/?limite=20': { itens: [est1], tem_mais: true },
      'GET /financeiro/estornos/?antes=est-1&limite=20': { itens: [est2], tem_mais: false },
      'GET /financeiro/estornos/?alvo_tipo=SAIDA&limite=20': { itens: [est2], tem_mais: false },
    })
    const user = userEvent.setup()

    const { unmount } = abrir('/saidas')

    expect(await screen.findByRole('link', { name: 'Fretamento s-1' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Carregar mais' }))
    expect(await screen.findByRole('link', { name: 'Fretamento s-2' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Prestações pendentes' }))
    expect(await screen.findByRole('link', { name: 'Fretamento s-3' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Em atraso' }))
    expect(await screen.findByRole('link', { name: 'Fretamento s-4' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Todas' }))
    expect(await screen.findByRole('link', { name: 'Fretamento s-1' })).toBeInTheDocument()

    const formFiltros = screen.getByRole('form', { name: 'Filtrar saídas' })
    await user.selectOptions(within(formFiltros).getByLabelText('Situação'), 'AGUARDANDO_ENVIO')
    await user.selectOptions(within(formFiltros).getByLabelText('Categoria'), 'cat-s1')
    await user.selectOptions(within(formFiltros).getByLabelText('Setor'), 'set-1')
    await user.selectOptions(within(formFiltros).getByLabelText('Solicitante'), 'u-1')
    await user.type(within(formFiltros).getByLabelText('De'), '2026-11-01')
    await user.type(within(formFiltros).getByLabelText('Até'), '2026-11-30')
    expect(await screen.findByText('Nenhuma saída encontrada.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Carregar mais estornos' }))
    expect(await screen.findByText(/Segundo estorno/)).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Alvo do estorno'), 'SAIDA')
    expect(
      chamou(chamadas, 'GET', '/financeiro/estornos/?alvo_tipo=SAIDA&limite=20'),
    ).toBe(true)
    unmount()

    simularApi({
      ...comPermissoes(),
      'GET /financeiro/caixa/': erro(500, 'INTERNAL_ERROR', 'Falha no caixa'),
      'GET /financeiro/referencias-gastos/': REFS_GASTOS,
      'GET /financeiro/saidas/?limite=20': erro(500, 'INTERNAL_ERROR', 'Falha ao carregar saídas'),
      'GET /financeiro/estornos/?limite=20': erro(500, 'INTERNAL_ERROR', 'Falha ao carregar estornos'),
    })
    abrir('/saidas')
    expect(await screen.findByRole('alert')).toHaveTextContent(/Falha/)
  })

  it('cobre anexos FormData em prestação e devolução, complemento no envio, seções e 404 na saída', async () => {
    const chamadas = simularApi({
      ...COMO_ADMIN,
      'GET /financeiro/referencias-gastos/': REFS_GASTOS,
      'GET /financeiro/saidas/s-det/': saidaDetalhe('s-det', {
        situacao: 'ESTORNADA',
        em_atraso: true,
        envios: [],
        prestacoes: [
          {
            id: 'pr-dev',
            valor: '480.00',
            descricao: 'Recibo anterior',
            registrada_por: BIA,
            registrada_em: '2026-11-11T10:00:00Z',
            situacao: 'DEVOLVIDA',
            comprovante_disponivel: false,
            comprovante_nome: '',
            devolvida_por: CARLOS,
            motivo_devolucao_texto: 'Faltou assinatura',
            texto_devolucao: 'Assine e reenvie',
            devolvida_em: '2026-11-11T12:00:00Z',
          },
        ],
        devolucoes: [
          {
            id: 'dev-1',
            valor: '20.00',
            data: '2026-11-12',
            situacao: 'EM_VALIDACAO',
            comprovante_disponivel: true,
            comprovante_nome: 'pix.png',
            registrada_em: '2026-11-12T10:00:00Z',
          },
        ],
        complementos: [
          {
            id: 'cmp-ok',
            solicitacao_id: 'sol-cmp-ok',
            valor: '50.00',
            situacao: 'APROVADO',
            envio_id: null,
          },
        ],
        estorno: {
          id: 'est-s',
          valor: '500.00',
          motivo_texto: 'Cancelamento operacional',
          justificativa: 'Estornado no encerramento',
          registrado_por: CARLOS,
          registrado_em: '2026-11-15T10:00:00Z',
        },
        acoes: ['enviar_recurso', 'prestar_contas', 'devolver_sobra'],
      }),
      'GET /financeiro/saidas/s-det/historico/': [
        { acao: 'SAIDA_LIQUIDADA', ator: null, justificativa: 'Ajuste final', dados: {}, criado_em: '2026-11-15T09:00:00Z' },
      ],
      'POST /financeiro/saidas/s-det/envios/': [201, saidaDetalhe('s-det', { acoes: ['prestar_contas', 'devolver_sobra'] })],
      'POST /financeiro/saidas/s-det/prestacoes/': [201, saidaDetalhe('s-det', { acoes: ['devolver_sobra'] })],
      'POST /financeiro/saidas/s-det/devolucoes/': [201, { id: 'dev-2' }],
      'GET /financeiro/saidas/inexistente/': erro(404, 'NOT_FOUND'),
      'GET /financeiro/saidas/inexistente/historico/': erro(404, 'NOT_FOUND'),
    })
    const user = userEvent.setup()

    const { unmount } = abrir('/saidas/s-det')

    expect(await screen.findByText(/Faltou assinatura/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Abrir comprovante' })).toHaveAttribute(
      'href',
      '/api/v1/financeiro/entradas/dev-1/comprovante/',
    )
    expect(screen.getByRole('link', { name: 'Validar nas entradas' })).toHaveAttribute('href', '/entradas')
    expect(screen.getByRole('link', { name: 'Ver solicitação' })).toHaveAttribute('href', '/solicitacoes/sol-cmp-ok')
    expect(screen.getByRole('region', { name: 'Estorno' })).toHaveTextContent('Estornado no encerramento')
    expect(screen.getByRole('region', { name: 'Histórico' })).toHaveTextContent('Sistema : Ajuste final')

    // Submete enviar_recurso sem arquivo para validar alerta e Fecha formulário.
    await user.click(screen.getByRole('button', { name: 'Enviar recurso' }))
    const fEnv = screen.getByRole('form', { name: 'Enviar recurso' })
    await user.click(within(fEnv).getByRole('button', { name: 'Confirmar' }))
    expect(await within(fEnv).findByRole('alert')).toHaveTextContent('Anexe o comprovante do envio.')
    await user.type(within(fEnv).getByLabelText('Valor enviado (R$)'), '50.00')
    await user.selectOptions(within(fEnv).getByLabelText('Complemento'), 'cmp-ok')
    await user.upload(
      within(fEnv).getByLabelText('Comprovante do envio (obrigatório)'),
      new File(['%PDF'], 'comp.pdf', { type: 'application/pdf' }),
    )
    await user.click(within(fEnv).getByRole('button', { name: 'Confirmar' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/saidas/s-det/envios/')?.corpo).toMatchObject({
      valor: '50.00',
      complemento_id: 'cmp-ok',
      comprovante: 'comp.pdf',
    })

    // Prestar contas com comprovante (FormData).
    await user.click(screen.getByRole('button', { name: 'Prestar contas' }))
    const fPrest = screen.getByRole('form', { name: 'Prestar contas' })
    await user.type(within(fPrest).getByLabelText('Total gasto (R$)'), '480.00')
    await user.type(within(fPrest).getByLabelText('Descrição / justificativa'), 'Nota anexa')
    await user.upload(
      within(fPrest).getByLabelText('Comprovante (opcional)'),
      new File(['%PDF'], 'nf.pdf', { type: 'application/pdf' }),
    )
    await user.click(within(fPrest).getByRole('button', { name: 'Confirmar' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/saidas/s-det/prestacoes/')?.corpo).toMatchObject({
      valor: '480.00',
      comprovante: 'nf.pdf',
    })

    // Devolver sobra com data e comprovante (FormData) e testar botão Fechar.
    await user.click(screen.getByRole('button', { name: 'Devolver sobra' }))
    const fSob = screen.getByRole('form', { name: 'Devolver sobra' })
    await user.type(within(fSob).getByLabelText('Valor devolvido (R$)'), '20.00')
    await user.type(within(fSob).getByLabelText('Data (opcional)'), '2026-11-15')
    await user.type(within(fSob).getByLabelText('Evidência em texto'), 'Pix com anexo')
    await user.upload(
      within(fSob).getByLabelText('Comprovante (opcional)'),
      new File(['%PDF'], 'sobra.pdf', { type: 'application/pdf' }),
    )
    await user.click(within(fSob).getByRole('button', { name: 'Confirmar' }))
    expect(chamadas.find((c) => c.caminho === '/financeiro/saidas/s-det/devolucoes/')?.corpo).toMatchObject({
      valor: '20.00',
      data: '2026-11-15',
      comprovante: 'sobra.pdf',
    })
    await user.click(screen.getByRole('button', { name: 'Devolver sobra' }))
    await user.click(within(screen.getByRole('form', { name: 'Devolver sobra' })).getByRole('button', { name: 'Fechar' }))
    expect(screen.queryByRole('form', { name: 'Devolver sobra' })).not.toBeInTheDocument()
    unmount()

    abrir('/saidas/inexistente')
    expect(await screen.findByRole('alert')).toHaveTextContent('Não encontrado.')
  })

  it('permite remover item ao pedir gasto e editar solicitação financeiro.gasto com justificativa', async () => {
    const chamadas = simularApi({
      ...COMO_ADMIN,
      'GET /financeiro/referencias-gastos/': REFS_GASTOS,
      'GET /aprovacoes/solicitacoes/sol-89/': {
        id: 'sol-89',
        tipo: 'financeiro.gasto',
        tipo_nome: 'Solicitação de gasto',
        tem_valor: true,
        situacao: 'EM_ANALISE',
        solicitante: BIA,
        aprovador_indicado: null,
        numero_da_versao_atual: 1,
        criada_em: '2026-11-15T10:00:00Z',
        atualizada_em: '2026-11-15T10:00:00Z',
        versoes: [
          {
            numero: 1,
            conteudo: {
              descricao: 'Gasto editável',
              categoria_id: 'cat-s1',
              categoria_nome: 'Transporte',
              setor_id: 'set-1',
              setor_nome: 'Logística',
              itens: [{ descricao: 'Van', valor: '100.00' }],
              cotacao_id: null,
              cotacao_nome: '',
              saida_origem_id: null,
              evento_id: null,
            },
            valor: '100.00',
            resumo: 'Gasto editável',
            autor: BIA,
            justificativa: '',
            criada_em: '2026-11-15T10:00:00Z',
            decisao: null,
          },
        ],
        acoes: ['editar'],
      },
      'GET /aprovacoes/solicitacoes/sol-89/historico/': [],
      'GET /financeiro/caixa/': CAIXA,
      'POST /aprovacoes/solicitacoes/sol-89/editar/': { id: 'sol-89', situacao: 'EM_ANALISE' },
    })
    const user = userEvent.setup()

    const { unmount } = abrir('/gastos/novo')
    await user.click(await screen.findByRole('button', { name: 'Adicionar item' }))
    expect(screen.getByLabelText('Descrição do item 2')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Remover item 2' }))
    expect(screen.queryByLabelText('Descrição do item 2')).not.toBeInTheDocument()
    unmount()

    abrir('/solicitacoes/sol-89')
    await user.click(await screen.findByRole('button', { name: 'Editar' }))
    const form = screen.getByRole('form', { name: 'Editar' })
    await within(form).findByRole('option', { name: 'Transporte' })
    await user.type(within(form).getByLabelText('Justificativa (opcional)'), 'Ajuste de categoria')
    await user.click(within(form).getByRole('button', { name: 'Confirmar' }))

    await waitFor(() =>
      expect(chamadas.find((c) => c.caminho === '/aprovacoes/solicitacoes/sol-89/editar/')?.corpo).toMatchObject({
        justificativa: 'Ajuste de categoria',
      }),
    )
  })
})
