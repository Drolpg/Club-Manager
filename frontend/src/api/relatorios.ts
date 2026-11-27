// Chamadas da API de relatórios (`/api/v1/relatorios/`): o perfil. Só leitura; o site só mostra.

import { apiGet, apiPost } from './client'

const base = '/relatorios/perfil'

export interface DadosDoPerfil {
  id: string
  nome: string
  nome_de_usuario: string
  email: string
  telefone: string
  ativo: boolean
  admin: boolean
  cadastrado_em: string
  cargo: string | null
  setores: string[]
}

export interface PagamentoDoPerfil {
  forma: string
  data_pagamento: string
  situacao: string
}

export interface CobrancaDoPerfil {
  id: string
  descricao: string
  categoria_nome: string
  valor: string
  vencimento: string
  situacao: string
  pagamentos: PagamentoDoPerfil[]
}

export interface EventoDoPerfil {
  id: string
  titulo: string
  inicio: string
  local: string
  categoria_nome: string
  situacao: string
  papel: 'PROPONENTE' | 'PRESENCA' | 'PROPONENTE_E_PRESENCA'
  resposta: 'VOU' | 'NAO_VOU' | null
}

export interface Pagina<T> {
  itens: T[]
  tem_mais: boolean
}

/** `notificacoes` só vem no próprio perfil: quem vê o de outro (o admin) nunca recebe a caixa dele. */
export interface Perfil {
  dados: DadosDoPerfil
  cobrancas: Pagina<CobrancaDoPerfil>
  eventos: Pagina<EventoDoPerfil>
  notificacoes?: { nao_lidas: number }
}

function caminho(alvoId: string | undefined, secao = ''): string {
  return alvoId ? `${base}/${alvoId}/${secao}` : `${base}/${secao}`
}

function cursor(antes?: string): string {
  return antes ? `?${new URLSearchParams({ antes })}` : ''
}

/** Sem `alvoId`, o próprio perfil; com ele, o de outro usuário (só o admin). */
export const relatorios = {
  perfil: (alvoId?: string) => apiGet<Perfil>(caminho(alvoId)),
  cobrancas: (alvoId: string | undefined, antes?: string) =>
    apiGet<Pagina<CobrancaDoPerfil>>(`${caminho(alvoId, 'cobrancas/')}${cursor(antes)}`),
  eventos: (alvoId: string | undefined, antes?: string) =>
    apiGet<Pagina<EventoDoPerfil>>(`${caminho(alvoId, 'eventos/')}${cursor(antes)}`),
}

// Dashboard (`/relatorios/dashboard/`): os números chegam prontos, em texto; o site só formata (RNF-01).

export interface QuantidadeETotal {
  quantidade: number
  total: string
}

export interface MinhasCobrancasDoPainel {
  em_aberto: QuantidadeETotal
  atrasadas: QuantidadeETotal
  em_validacao: QuantidadeETotal
  proxima: { id: string; descricao: string; valor: string; vencimento: string } | null
}

export interface DashboardCompleto {
  tipo: 'COMPLETO'
  mes: string
  meses: { de: string; ate: string }
  do_mes: {
    entradas: string
    saidas: string
    resultado: string
    saldo_acumulado: string
    a_receber: QuantidadeETotal
  }
  hoje: {
    data: string
    comprometido: string
    saldo_livre: string
    pendencias_de_validacao: { pagamentos: QuantidadeETotal; entradas: QuantidadeETotal }
    pendencias_de_aprovacao: {
      minha_fila: number
      por_tipo: { tipo: string; nome: string; quantidade: number }[]
    }
    prestacoes_pendentes: { aguardando: number; em_atraso: number; em_conferencia: number }
    inadimplencia: { cobrancas: number; devedores: number; total: string }
  }
  proximos_eventos: { id: string; titulo: string; inicio: string; categoria_nome: string }[]
  ultimos_comunicados: { id: string; tipo: string; titulo: string; publicado_em: string; fixado: boolean }[]
  minhas_cobrancas: MinhasCobrancasDoPainel
}

export interface DashboardBasico {
  tipo: 'BASICO'
  classificacao_pendente: boolean
  minhas_cobrancas: MinhasCobrancasDoPainel
  notificacoes_nao_lidas: number
}

export type Dashboard = DashboardCompleto | DashboardBasico

/** Sem `mes` (AAAA-MM), o corrente. A API decide entre o completo e o básico. */
export function dashboard(mes?: string) {
  return apiGet<Dashboard>(`/relatorios/dashboard/${mes ? `?${new URLSearchParams({ mes })}` : ''}`)
}

// Relatórios em PDF e CSV: pedir, acompanhar e baixar os próprios pedidos.

export type FormaDosParametros = 'PERIODO' | 'PERIODO_E_PENDENTES' | 'MESES' | 'NENHUM'

export interface TipoDeRelatorio {
  codigo: string
  nome: string
  formatos: string[]
  parametros: FormaDosParametros
}

export type SituacaoDoPedido = 'NA_FILA' | 'GERANDO' | 'PRONTO' | 'FALHOU' | 'EXPIRADO'

export interface PedidoDeRelatorio {
  id: string
  tipo: string
  tipo_nome: string
  formato: string
  parametros: Record<string, unknown>
  situacao: SituacaoDoPedido
  pedido_em: string
  concluido_em: string | null
  expira_em: string | null
  disponivel: boolean
  codigo_da_falha: string
}

export interface NovoPedido {
  tipo: string
  formato: string
  parametros: Record<string, unknown>
}

export const pedidosDeRelatorio = {
  tipos: () => apiGet<TipoDeRelatorio[]>('/relatorios/tipos/'),
  listar: (antes?: string) =>
    apiGet<Pagina<PedidoDeRelatorio>>(
      `/relatorios/pedidos/${antes ? `?${new URLSearchParams({ antes })}` : ''}`,
    ),
  pedir: (novo: NovoPedido) => apiPost<PedidoDeRelatorio>('/relatorios/pedidos/', novo),
  /** O endereço do arquivo: o navegador baixa com a sessão; a API confere que o pedido é de quem pede. */
  arquivo: (id: string) => `/api/v1/relatorios/pedidos/${id}/arquivo/`,
}
