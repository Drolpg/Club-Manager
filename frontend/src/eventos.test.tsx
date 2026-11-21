import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import App from './App'
import { ADMIN, DIRETOR, SEM_GOOGLE, erro, simularApi } from './test/api'

function abrir(caminho: string) {
  return render(
    <MemoryRouter initialEntries={[caminho]}>
      <App />
    </MemoryRouter>,
  )
}

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

const COMO_ADMIN = { 'GET /acesso/sessao/': { usuario: ADMIN }, ...SEM_GOOGLE, ...RESUMO }

const BIA = { id: 'u-1', nome: 'Bia Diretora' }
const CAIO = { id: 'u-2', nome: 'Caio Eventos' }

function mesAtual(deslocamento = 0): string {
  const hoje = new Date()
  const data = new Date(hoje.getFullYear(), hoje.getMonth() + deslocamento, 1)
  return `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, '0')}`
}

function evento(id: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    titulo: `Evento ${id}`,
    inicio: `${mesAtual()}-12T19:30:00-03:00`,
    local: 'Campo do bairro',
    categoria_nome: 'Jogo',
    situacao: 'PUBLICADO',
    ...extra,
  }
}

function detalhe(extra: Record<string, unknown> = {}) {
  return {
    ...evento('ev-1'),
    descricao: 'Jogo de fim de ano',
    categoria_id: 'cat-1',
    envolve_custo: true,
    criado_em: '2026-11-20T10:00:00-03:00',
    proponente: BIA,
    solicitacao_do_evento: { id: 'sol-1', situacao: 'APROVADA' },
    orcamento: { solicitacao_id: 'sol-2', situacao: 'APROVADA' },
    presencas: { vou: [CAIO], nao_vou: [], sem_resposta: [BIA], minha: null },
    realizacao: null,
    cancelamento: null,
    acoes: [],
    ...extra,
  }
}

function solicitacao(id: string, tipo: string) {
  return {
    id,
    tipo,
    tipo_nome: tipo,
    tem_valor: tipo === 'financeiro.gasto',
    situacao: 'APROVADA',
    solicitante: BIA,
    aprovador_indicado: null,
    numero_da_versao_atual: 1,
    criada_em: '2026-11-20T10:00:00Z',
    atualizada_em: '2026-11-20T10:00:00Z',
    versoes: [
      {
        numero: 1,
        conteudo: {},
        valor: null,
        resumo: 'Evento ev-1',
        autor: BIA,
        justificativa: '',
        criada_em: '2026-11-20T10:00:00Z',
        decisao: {
          tipo: 'APROVAR',
          aprovador: CAIO,
          motivo_id: 'm-1',
          motivo_texto: `Motivo de ${id}`,
          texto: '',
          mensagem: '',
          teto_sugerido: null,
          aprovacao_propria: false,
          criada_em: '2026-11-20T11:00:00Z',
        },
      },
    ],
    acoes: [],
  }
}

const DO_DETALHE = {
  'GET /eventos/ev-1/historico/': [{ acao: 'EVENTO_PROPOSTO', ator: BIA, justificativa: '', criado_em: '2026-11-20T10:00:00Z' }],
  'GET /aprovacoes/solicitacoes/sol-1/': solicitacao('sol-1', 'eventos.evento'),
  'GET /aprovacoes/solicitacoes/sol-2/': solicitacao('sol-2', 'financeiro.gasto'),
  'GET /financeiro/saidas/?evento_id=ev-1': {
    itens: [{ id: 'sai-1', situacao: 'AGUARDANDO_ENVIO', valor_aprovado: '400.00', total_enviado: '0.00' }],
    tem_mais: false,
  },
}

describe('calendário', () => {
  it('mostra os cards do mês, marca o realizado, abre o detalhe e navega entre meses', async () => {
    const chamadas = simularApi({
      ...comPermissoes(),
      [`GET /eventos/calendario/?mes=${mesAtual()}`]: [
        evento('ev-1'),
        evento('ev-2', { titulo: 'Reunião geral', situacao: 'REALIZADO', categoria_nome: 'Reunião' }),
      ],
      [`GET /eventos/calendario/?mes=${mesAtual(1)}`]: [],
    })
    const user = userEvent.setup()

    abrir('/eventos')

    const card = await screen.findByRole('link', { name: /Evento ev-1/ })
    expect(card).toHaveAttribute('href', '/eventos/ev-1')
    expect(card).toHaveTextContent('19:30')
    expect(card).toHaveTextContent('Campo do bairro')
    expect(card).toHaveTextContent('Jogo')
    expect(screen.getByRole('link', { name: /Reunião geral/ })).toHaveTextContent('Realizado')

    await user.click(screen.getByRole('button', { name: 'Próximo mês' }))
    await waitFor(() =>
      expect(chamadas.some((c) => c.caminho === `/eventos/calendario/?mes=${mesAtual(1)}`)).toBe(true),
    )
    expect(await screen.findByText('Nenhum evento neste mês.')).toBeInTheDocument()
  })

  it('mostra o menu de eventos, com propor só para quem pode', async () => {
    simularApi({ ...comPermissoes('eventos.propor'), [`GET /eventos/calendario/?mes=${mesAtual()}`]: [] })

    abrir('/eventos')

    const menu = await screen.findByRole('navigation', { name: 'Eventos' })
    expect(within(menu).getByRole('link', { name: 'Calendário' })).toBeInTheDocument()
    expect(within(menu).getByRole('link', { name: 'Histórico' })).toBeInTheDocument()
    expect(await within(menu).findByRole('link', { name: 'Propor evento' })).toBeInTheDocument()
    expect(within(menu).queryByRole('link', { name: 'Categorias de evento' })).not.toBeInTheDocument()
  })
})

describe('histórico', () => {
  it('lista todos, filtra por situação e carrega mais', async () => {
    const item = (id: string) => ({ ...evento(id), categoria_id: 'cat-1', envolve_custo: false, proponente_id: 'u-1' })
    const chamadas = simularApi({
      ...comPermissoes(),
      'GET /eventos/categorias/': [{ id: 'cat-1', nome: 'Jogo', ativa: true }],
      'GET /eventos/?limite=20': { itens: [item('ev-1')], tem_mais: true },
      'GET /eventos/?antes=ev-1&limite=20': { itens: [item('ev-2')], tem_mais: false },
      'GET /eventos/?situacao=CANCELADO&limite=20': { itens: [], tem_mais: false },
    })
    const user = userEvent.setup()

    abrir('/eventos/historico')

    expect(await screen.findByRole('link', { name: 'Evento ev-1' })).toHaveAttribute('href', '/eventos/ev-1')
    await user.click(screen.getByRole('button', { name: 'Carregar mais' }))
    expect(await screen.findByRole('link', { name: 'Evento ev-2' })).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Situação'), 'CANCELADO')
    await waitFor(() =>
      expect(chamadas.some((c) => c.caminho === '/eventos/?situacao=CANCELADO&limite=20')).toBe(true),
    )
  })
})

describe('proposta', () => {
  it('envia os dados, com o aprovador indicado quando pedido, e abre o detalhe', async () => {
    const chamadas = simularApi({
      ...comPermissoes('eventos.propor', 'eventos.aprovar'),
      'GET /eventos/referencias/': {
        categorias: [{ id: 'cat-1', nome: 'Jogo' }],
        aprovadores_eventos: [CAIO],
        precisa_indicar_aprovador: true,
      },
      'POST /eventos/': [201, detalhe({ situacao: 'EM_APROVACAO' })],
      'GET /eventos/ev-1/': detalhe({ situacao: 'EM_APROVACAO' }),
      ...DO_DETALHE,
    })
    const user = userEvent.setup()

    abrir('/eventos/novo')

    await user.type(await screen.findByLabelText('Título'), 'Amistoso')
    await user.type(screen.getByLabelText('Local'), 'Campo')
    await user.type(screen.getByLabelText('Data e hora'), '2026-12-12T19:30')
    await user.selectOptions(screen.getByLabelText('Categoria'), 'cat-1')
    await user.click(screen.getByLabelText('Envolve custo'))
    await user.selectOptions(screen.getByLabelText('Aprovador indicado'), 'u-2')
    await user.click(screen.getByRole('button', { name: 'Propor evento' }))

    await waitFor(() =>
      expect(chamadas.find((c) => c.metodo === 'POST' && c.caminho === '/eventos/')?.corpo).toEqual({
        titulo: 'Amistoso',
        descricao: '',
        inicio: '2026-12-12T19:30',
        local: 'Campo',
        categoria_id: 'cat-1',
        envolve_custo: true,
        aprovador_indicado_id: 'u-2',
      }),
    )
    expect(await screen.findByRole('heading', { name: 'Evento ev-1' })).toBeInTheDocument()
  })

  it('mostra os erros por campo', async () => {
    simularApi({
      ...comPermissoes('eventos.propor'),
      'GET /eventos/referencias/': {
        categorias: [{ id: 'cat-1', nome: 'Jogo' }],
        aprovadores_eventos: [],
        precisa_indicar_aprovador: false,
      },
      'POST /eventos/': erro(400, 'VALIDATION_ERROR', 'inválido', { titulo: ['Este campo é obrigatório.'] }),
    })
    const user = userEvent.setup()

    abrir('/eventos/novo')

    expect(screen.queryByLabelText('Aprovador indicado')).not.toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: 'Propor evento' }))
    expect(await screen.findByText('Este campo é obrigatório.')).toBeInTheDocument()
  })
})

describe('detalhe', () => {
  it('mostra dados, solicitações com decisões, orçamento, presenças e histórico, sem ações', async () => {
    simularApi({ ...comPermissoes(), 'GET /eventos/ev-1/': detalhe(), ...DO_DETALHE })

    abrir('/eventos/ev-1')

    expect(await screen.findByRole('heading', { name: 'Evento ev-1' })).toBeInTheDocument()
    expect(screen.getByText('Jogo de fim de ano')).toBeInTheDocument()
    expect(screen.getByText(/Proposto por Bia Diretora/)).toBeInTheDocument()
    expect(await screen.findByText(/Motivo de sol-1/)).toBeInTheDocument()
    expect(await screen.findByText(/Motivo de sol-2/)).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: /Ver a saída/ })).toHaveAttribute('href', '/saidas/sai-1')
    const quadro = screen.getByRole('region', { name: 'Presenças' })
    expect(within(quadro).getByText(/Vão: Caio Eventos/)).toBeInTheDocument()
    expect(within(quadro).getByText(/Não responderam: Bia Diretora/)).toBeInTheDocument()
    expect(await screen.findByText(/EVENTO_PROPOSTO|Evento proposto/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Vou' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cancelar evento' })).not.toBeInTheDocument()
  })

  it('responde presença, realiza e cancela conforme as ações', async () => {
    const chamadas = simularApi({
      ...comPermissoes(),
      'GET /eventos/ev-1/': detalhe({ acoes: ['confirmar_realizacao', 'cancelar', 'responder_presenca'] }),
      'POST /eventos/ev-1/presenca/': { vou: [CAIO, BIA], nao_vou: [], sem_resposta: [], minha: 'VOU' },
      'POST /eventos/ev-1/realizar/': detalhe({ situacao: 'REALIZADO' }),
      'POST /eventos/ev-1/cancelar/': detalhe({ situacao: 'CANCELADO' }),
      ...DO_DETALHE,
    })
    const user = userEvent.setup()

    abrir('/eventos/ev-1')

    await user.click(await screen.findByRole('button', { name: 'Vou' }))
    await waitFor(() =>
      expect(chamadas.find((c) => c.caminho === '/eventos/ev-1/presenca/')?.corpo).toEqual({ resposta: 'VOU' }),
    )

    const realizar = screen.getByRole('form', { name: 'Confirmar realização' })
    await user.type(within(realizar).getByLabelText('Data em que aconteceu'), '2026-11-19')
    await user.type(within(realizar).getByLabelText('Motivo da data diferente'), 'Antecipado')
    await user.click(within(realizar).getByRole('button', { name: 'Confirmar realização' }))
    await waitFor(() =>
      expect(chamadas.find((c) => c.caminho === '/eventos/ev-1/realizar/')?.corpo).toEqual({
        data: '2026-11-19',
        motivo: 'Antecipado',
      }),
    )

    const cancelar = screen.getByRole('form', { name: 'Cancelar evento' })
    await user.type(within(cancelar).getByLabelText('Motivo do cancelamento'), 'Chuva')
    await user.click(within(cancelar).getByRole('button', { name: 'Cancelar evento' }))
    await waitFor(() =>
      expect(chamadas.find((c) => c.caminho === '/eventos/ev-1/cancelar/')?.corpo).toEqual({ motivo: 'Chuva' }),
    )
  })

  it('abre o orçamento com itens e reabre o recusado', async () => {
    const chamadas = simularApi({
      ...comPermissoes('eventos.aprovar'),
      'GET /eventos/ev-1/': detalhe({ situacao: 'RECUSADO', orcamento: null, acoes: ['reabrir', 'vincular_orcamento'] }),
      'GET /financeiro/referencias-gastos/': {
        categorias_saida: [{ id: 'cat-s1', nome: 'Eventos' }],
        categorias_entrada: [],
        setores: [{ id: 'set-1', nome: 'Eventos' }],
        aprovadores_gastos: [],
        diretores_ativos: [],
      },
      'POST /eventos/ev-1/orcamento/': [201, detalhe()],
      'POST /eventos/ev-1/reabrir/': detalhe({ situacao: 'EM_APROVACAO' }),
      ...DO_DETALHE,
      'GET /financeiro/saidas/?evento_id=ev-1': { itens: [], tem_mais: false },
    })
    const user = userEvent.setup()

    abrir('/eventos/ev-1')

    const orcamento = await screen.findByRole('form', { name: 'Abrir orçamento' })
    expect(within(orcamento).getByLabelText('Descrição do orçamento')).toHaveValue('Orçamento: Evento ev-1')
    await user.selectOptions(await within(orcamento).findByLabelText('Setor'), 'set-1')
    await user.type(within(orcamento).getByLabelText('Descrição do item 1'), 'Arbitragem')
    await user.type(within(orcamento).getByLabelText('Valor do item 1 (R$)'), '400.00')
    await user.click(within(orcamento).getByRole('button', { name: 'Abrir orçamento' }))
    await waitFor(() =>
      expect(chamadas.find((c) => c.caminho === '/eventos/ev-1/orcamento/')?.corpo).toEqual({
        descricao: 'Orçamento: Evento ev-1',
        categoria_id: 'cat-s1',
        setor_id: 'set-1',
        itens: [{ descricao: 'Arbitragem', valor: '400.00' }],
      }),
    )

    const reabrir = screen.getByRole('form', { name: 'Reabrir evento' })
    await user.type(within(reabrir).getByLabelText('Justificativa'), 'Mudamos o local')
    await user.click(within(reabrir).getByRole('button', { name: 'Reabrir evento' }))
    await waitFor(() =>
      expect(chamadas.find((c) => c.caminho === '/eventos/ev-1/reabrir/')?.corpo).toEqual({
        justificativa: 'Mudamos o local',
      }),
    )
  })

  it('edita com os dados atuais e a justificativa', async () => {
    const chamadas = simularApi({
      ...comPermissoes('eventos.propor'),
      'GET /eventos/ev-1/': detalhe({ acoes: ['editar'] }),
      'GET /eventos/referencias/': {
        categorias: [{ id: 'cat-1', nome: 'Jogo' }],
        aprovadores_eventos: [],
        precisa_indicar_aprovador: false,
      },
      'POST /eventos/ev-1/editar/': detalhe({ situacao: 'EM_APROVACAO' }),
      ...DO_DETALHE,
    })
    const user = userEvent.setup()

    abrir('/eventos/ev-1')

    await user.click(await screen.findByRole('link', { name: 'Editar evento' }))
    const titulo = await screen.findByLabelText('Título')
    expect(titulo).toHaveValue('Evento ev-1')
    expect(screen.getByLabelText('Data e hora')).toHaveValue(`${mesAtual()}-12T19:30`)
    await user.clear(titulo)
    await user.type(titulo, 'Amistoso remarcado')
    await user.type(screen.getByLabelText('Justificativa (obrigatória se recusado)'), 'Nova data')
    await user.click(screen.getByRole('button', { name: 'Salvar edição' }))

    await waitFor(() =>
      expect(chamadas.find((c) => c.caminho === '/eventos/ev-1/editar/')?.corpo).toEqual({
        titulo: 'Amistoso remarcado',
        descricao: 'Jogo de fim de ano',
        inicio: `${mesAtual()}-12T19:30`,
        local: 'Campo do bairro',
        categoria_id: 'cat-1',
        envolve_custo: true,
        justificativa: 'Nova data',
      }),
    )
  })

  it('mostra textos livres como texto', async () => {
    simularApi({ ...comPermissoes(), 'GET /eventos/ev-1/': detalhe({ titulo: '<b>x</b>' }), ...DO_DETALHE })

    abrir('/eventos/ev-1')

    expect(await screen.findByRole('heading', { name: '<b>x</b>' })).toBeInTheDocument()
  })
})

describe('categorias de evento', () => {
  it('o admin cria, renomeia, desativa e reativa', async () => {
    const chamadas = simularApi({
      ...COMO_ADMIN,
      'GET /eventos/categorias/?todas=1': [
        { id: 'cat-1', nome: 'Jogo', ativa: true },
        { id: 'cat-2', nome: 'Antiga', ativa: false },
      ],
      'POST /eventos/categorias/': [201, { id: 'cat-3', nome: 'Treino', ativa: true }],
      'POST /eventos/categorias/cat-1/editar/': { id: 'cat-1', nome: 'Jogo oficial', ativa: true },
      'POST /eventos/categorias/cat-1/desativar/': { id: 'cat-1', nome: 'Jogo', ativa: false },
      'POST /eventos/categorias/cat-2/reativar/': { id: 'cat-2', nome: 'Antiga', ativa: true },
    })
    const user = userEvent.setup()

    abrir('/admin/categorias-de-evento')

    await user.type(await screen.findByLabelText('Nova categoria'), 'Treino')
    await user.click(screen.getByRole('button', { name: 'Criar categoria' }))
    await waitFor(() =>
      expect(chamadas.find((c) => c.caminho === '/eventos/categorias/' && c.metodo === 'POST')?.corpo).toEqual({
        nome: 'Treino',
      }),
    )
    const jogo = screen.getByRole('listitem', { name: 'Jogo' })
    await user.clear(within(jogo).getByLabelText('Nome de Jogo'))
    await user.type(within(jogo).getByLabelText('Nome de Jogo'), 'Jogo oficial')
    await user.click(within(jogo).getByRole('button', { name: 'Renomear' }))
    await user.click(within(jogo).getByRole('button', { name: 'Desativar' }))
    const antiga = screen.getByRole('listitem', { name: 'Antiga' })
    await user.click(within(antiga).getByRole('button', { name: 'Reativar' }))
    await waitFor(() => expect(chamadas.some((c) => c.caminho === '/eventos/categorias/cat-2/reativar/')).toBe(true))
    expect(chamadas.find((c) => c.caminho === '/eventos/categorias/cat-1/editar/')?.corpo).toEqual({
      nome: 'Jogo oficial',
    })
    expect(chamadas.some((c) => c.caminho === '/eventos/categorias/cat-1/desativar/')).toBe(true)
  })
})
