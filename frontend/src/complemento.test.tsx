import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import App from './App'
import { DIRETOR, SEM_GOOGLE, simularApi } from './test/api'

// RF-079: o complemento contestado e reenviado pela tela continua ligado à saída de origem.

const BIA = { id: 'u-1', nome: 'Bia Diretora' }

const SESSAO = {
  'GET /acesso/sessao/': { usuario: { ...DIRETOR, tem_cargo: true } },
  'GET /permissoes/minhas/': {
    cargo: { id: 'ca-1', nome: 'Tesoureiro', ativo: true },
    setores: [],
    permissoes: [],
  },
  'GET /notificacoes/resumo/': { nao_lidas: 0, mais_recente_id: null },
  ...SEM_GOOGLE,
}

const REFS_GASTOS = {
  categorias_saida: [{ id: 'cat-s1', nome: 'Transporte' }],
  categorias_entrada: [],
  setores: [{ id: 'set-1', nome: 'Logística' }],
  aprovadores_gastos: [],
  diretores_ativos: [BIA],
}

function complementoContestado(saidaOrigemId: string | null) {
  return {
    id: 'sol-77',
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
          descricao: 'Complemento: fretamento',
          categoria_id: 'cat-s1',
          categoria_nome: 'Transporte',
          setor_id: 'set-1',
          setor_nome: 'Logística',
          itens: [{ descricao: 'Diferença', valor: '80.00' }],
          cotacao_id: null,
          cotacao_nome: '',
          saida_origem_id: saidaOrigemId,
        },
        valor: '80.00',
        resumo: 'Complemento: fretamento',
        autor: BIA,
        justificativa: '',
        criada_em: '2026-11-15T10:00:00Z',
        decisao: null,
      },
    ],
    acoes: ['reenviar'],
  }
}

async function reenviar(saidaOrigemId: string | null) {
  const chamadas = simularApi({
    ...SESSAO,
    'GET /financeiro/referencias-gastos/': REFS_GASTOS,
    'GET /aprovacoes/solicitacoes/sol-77/': complementoContestado(saidaOrigemId),
    'GET /aprovacoes/solicitacoes/sol-77/historico/': [],
    'POST /aprovacoes/solicitacoes/sol-77/reenviar/': { id: 'sol-77', situacao: 'EM_ANALISE' },
  })
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={['/solicitacoes/sol-77']}>
      <App />
    </MemoryRouter>,
  )
  await user.click(await screen.findByRole('button', { name: 'Reenviar' }))
  const form = screen.getByRole('form', { name: 'Reenviar' })
  await user.click(within(form).getByRole('button', { name: 'Confirmar' }))
  let corpo: unknown
  await waitFor(() => {
    corpo = chamadas.find((c) => c.caminho === '/aprovacoes/solicitacoes/sol-77/reenviar/')?.corpo
    expect(corpo).toBeDefined()
  })
  return corpo as { conteudo: Record<string, unknown> }
}

describe('reenvio de complemento pela tela de aprovações', () => {
  it('preserva o saida_origem_id da versão atual', async () => {
    const corpo = await reenviar('sai-9')

    expect(corpo.conteudo.saida_origem_id).toBe('sai-9')
    expect(corpo.conteudo).not.toHaveProperty('evento_id')
  })

  it('não acrescenta o campo num gasto comum', async () => {
    const corpo = await reenviar(null)

    expect(corpo.conteudo).not.toHaveProperty('saida_origem_id')
  })
})
