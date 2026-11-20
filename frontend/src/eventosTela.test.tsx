import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import App from './App'
import { DIRETOR, SEM_GOOGLE, simularApi } from './test/api'

// Detalhes de tela do M8 pedidos depois do roteiro no navegador (2026-11-20).

const BIA = { id: 'u-1', nome: 'Bia Diretora' }
const CAIO = { id: 'u-2', nome: 'Caio Eventos' }

const SESSAO = {
  'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
  'GET /permissoes/minhas/': { cargo: { id: 'ca-1', nome: 'Diretor', ativo: true }, setores: [], permissoes: [] },
  'GET /notificacoes/resumo/': { nao_lidas: 0, mais_recente_id: null },
  ...SEM_GOOGLE,
}

function mesAtual(deslocamento = 0): string {
  const hoje = new Date()
  const data = new Date(hoje.getFullYear(), hoje.getMonth() + deslocamento, 1)
  return `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, '0')}`
}

function detalhe(extra: Record<string, unknown> = {}) {
  return {
    id: 'ev-1',
    titulo: 'Amistoso',
    descricao: '',
    inicio: `${mesAtual()}-12T19:30:00-03:00`,
    local: 'Campo',
    categoria_id: 'cat-1',
    categoria_nome: 'Jogo',
    envolve_custo: false,
    situacao: 'PUBLICADO',
    criado_em: '2026-11-20T10:00:00-03:00',
    proponente: BIA,
    solicitacao_do_evento: { id: 'sol-1', situacao: 'APROVADA' },
    orcamento: null,
    presencas: { vou: [CAIO], nao_vou: [], sem_resposta: [BIA], minha: null },
    realizacao: null,
    cancelamento: null,
    acoes: [],
    ...extra,
  }
}

function solicitacao(situacao: string) {
  return {
    id: 'sol-1',
    tipo: 'eventos.evento',
    tipo_nome: 'Evento',
    tem_valor: false,
    situacao,
    solicitante: BIA,
    aprovador_indicado: null,
    numero_da_versao_atual: 1,
    criada_em: '2026-11-20T10:00:00Z',
    atualizada_em: '2026-11-20T10:00:00Z',
    versoes: [],
    acoes: [],
  }
}

function abrir(caminho: string) {
  return render(
    <MemoryRouter initialEntries={[caminho]}>
      <App />
    </MemoryRouter>,
  )
}

describe('detalhe do evento', () => {
  it('depois de confirmar a realização, recarrega a solicitação do evento', async () => {
    let encerrada = false
    const chamadas = simularApi({
      ...SESSAO,
      'GET /eventos/ev-1/': () => detalhe(encerrada ? { situacao: 'REALIZADO' } : { acoes: ['confirmar_realizacao'] }),
      'GET /eventos/ev-1/historico/': [],
      'GET /aprovacoes/solicitacoes/sol-1/': () => solicitacao(encerrada ? 'ENCERRADA' : 'APROVADA'),
      'POST /eventos/ev-1/realizar/': () => {
        encerrada = true
        return detalhe({ situacao: 'REALIZADO' })
      },
    })
    const user = userEvent.setup()

    abrir('/eventos/ev-1')

    const secao = await screen.findByRole('region', { name: 'Solicitação do evento' })
    expect(await within(secao).findByText(/Aprovada/)).toBeInTheDocument()
    const formulario = screen.getByRole('form', { name: 'Confirmar realização' })
    await user.click(within(formulario).getByRole('button', { name: 'Confirmar realização' }))

    expect(await within(secao).findByText(/Encerrada/)).toBeInTheDocument()
    expect(chamadas.filter((c) => c.caminho === '/aprovacoes/solicitacoes/sol-1/').length).toBeGreaterThan(1)
  })

  it('os botões de presença mostram a resposta atual e acompanham a mudança', async () => {
    simularApi({
      ...SESSAO,
      'GET /eventos/ev-1/': detalhe({
        acoes: ['responder_presenca'],
        presencas: { vou: [BIA], nao_vou: [], sem_resposta: [], minha: 'VOU' },
      }),
      'GET /eventos/ev-1/historico/': [],
      'GET /aprovacoes/solicitacoes/sol-1/': solicitacao('APROVADA'),
      'POST /eventos/ev-1/presenca/': { vou: [], nao_vou: [BIA], sem_resposta: [], minha: 'NAO_VOU' },
    })
    const user = userEvent.setup()

    abrir('/eventos/ev-1')

    const vou = await screen.findByRole('button', { name: 'Vou' })
    const naoVou = screen.getByRole('button', { name: 'Não vou' })
    expect(vou).toHaveAttribute('aria-pressed', 'true')
    expect(vou).toHaveClass('marcado')
    expect(naoVou).toHaveAttribute('aria-pressed', 'false')
    expect(naoVou).not.toHaveClass('marcado')

    await user.click(naoVou)

    await waitFor(() => expect(naoVou).toHaveAttribute('aria-pressed', 'true'))
    expect(naoVou).toHaveClass('marcado')
    expect(vou).toHaveAttribute('aria-pressed', 'false')
  })

  it.each(['EM_APROVACAO', 'RECUSADO', 'CANCELADO'])('o quadro de presenças não aparece em %s', async (situacao) => {
    simularApi({
      ...SESSAO,
      'GET /eventos/ev-1/': detalhe({ situacao }),
      'GET /eventos/ev-1/historico/': [],
      'GET /aprovacoes/solicitacoes/sol-1/': solicitacao('EM_ANALISE'),
    })

    abrir('/eventos/ev-1')

    expect(await screen.findByRole('heading', { name: 'Amistoso' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Presenças' })).not.toBeInTheDocument()
  })

  it.each(['PUBLICADO', 'REALIZADO'])('o quadro de presenças aparece em %s', async (situacao) => {
    simularApi({
      ...SESSAO,
      'GET /eventos/ev-1/': detalhe({ situacao }),
      'GET /eventos/ev-1/historico/': [],
      'GET /aprovacoes/solicitacoes/sol-1/': solicitacao('APROVADA'),
    })

    abrir('/eventos/ev-1')

    expect(await screen.findByRole('region', { name: 'Presenças' })).toBeInTheDocument()
  })
})

describe('calendário sem eventos', () => {
  it('mantém a grade do mês e os botões de mês mesmo sem eventos', async () => {
    simularApi({ ...SESSAO, [`GET /eventos/calendario/?mes=${mesAtual()}`]: [] })

    abrir('/eventos')

    expect(await screen.findByText('Nenhum evento neste mês.')).toBeInTheDocument()
    const grade = screen.getByRole('grid')
    expect(grade).toHaveClass('calendario')
    expect(within(grade).getAllByRole('columnheader')).toHaveLength(7)
    expect(within(grade).getAllByRole('gridcell').length).toBeGreaterThanOrEqual(28)
    expect(screen.getByRole('button', { name: 'Próximo mês' }).closest('.navegacao-do-mes')).not.toBeNull()
  })

  it('a grade e a barra do mês têm a mesma largura explícita, que não depende do conteúdo', async () => {
    simularApi({ ...SESSAO, [`GET /eventos/calendario/?mes=${mesAtual()}`]: [] })

    abrir('/eventos')

    expect(await screen.findByText('Nenhum evento neste mês.')).toBeInTheDocument()
    const barra = screen.getByRole('button', { name: 'Próximo mês' }).closest('.navegacao-do-mes')
    expect(barra).toHaveClass('largura-do-calendario')
    expect(screen.getByRole('grid')).toHaveClass('largura-do-calendario')
  })
})
