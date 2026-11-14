import { apiGet } from './client'

/** Quem fez algo: só o ID e o nome. */
export interface Pessoa {
  id: string
  nome: string
}

export type Situacao =
  | 'EM_ANALISE'
  | 'RETIRADA'
  | 'CONTESTADA'
  | 'RECUSADA'
  | 'APROVADA'
  | 'EM_EXECUCAO'
  | 'ENCERRADA'
  | 'CANCELADA'

/** Os comandos que a API pode oferecer no campo `acoes` do detalhe; os nomes são os das rotas. */
export type Acao = 'retirar' | 'reenviar' | 'reabrir' | 'editar' | 'cancelar' | 'aprovar' | 'contestar' | 'recusar'

export interface TipoDeSolicitacao {
  codigo: string
  nome: string
  tem_valor: boolean
}

/** Dinheiro vem da API como texto com duas casas ("150.00"); o site nunca o converte em número. */
export interface ItemDaLista {
  id: string
  tipo: string
  tipo_nome: string
  situacao: Situacao
  solicitante: Pessoa
  resumo: string
  valor: string | null
  numero_da_versao_atual: number
  aguardando_desde: string
  criada_em: string
  atualizada_em: string
}

export interface PaginaDaLista {
  itens: ItemDaLista[]
  tem_mais: boolean
}

export interface Decisao {
  tipo: 'APROVAR' | 'CONTESTAR' | 'RECUSAR'
  aprovador: Pessoa
  motivo_id: string
  motivo_texto: string
  texto: string
  mensagem: string
  teto_sugerido: string | null
  aprovacao_propria: boolean
  criada_em: string
}

export interface Versao {
  numero: number
  /** O conteúdo é do módulo dono do tipo; o site o mostra como texto, sem interpretar. */
  conteudo: unknown
  valor: string | null
  resumo: string
  autor: Pessoa
  justificativa: string
  criada_em: string
  decisao: Decisao | null
}

export interface DetalheDaSolicitacao {
  id: string
  tipo: string
  tipo_nome: string
  tem_valor: boolean
  situacao: Situacao
  solicitante: Pessoa
  aprovador_indicado: Pessoa | null
  numero_da_versao_atual: number
  criada_em: string
  atualizada_em: string
  versoes: Versao[]
  /** O que quem está logado pode fazer agora. O site só mostra estes botões; a API confere de novo. */
  acoes: Acao[]
}

export interface RegistroDoHistorico {
  acao: string
  ator: Pessoa | null
  justificativa: string
  criado_em: string
}

export interface FiltrosDaLista {
  tipo?: string
  situacao?: string
  minhas?: boolean
  antes?: string
}

/** Por página, na lista (a API aceita de 1 a 50). */
export const POR_PAGINA = 20

const base = '/aprovacoes'

function consultaDaLista(filtros: FiltrosDaLista): string {
  // A ordem dos parâmetros é fixa, para a mesma busca virar sempre o mesmo endereço.
  const parametros = new URLSearchParams()
  if (filtros.tipo) parametros.set('tipo', filtros.tipo)
  if (filtros.situacao) parametros.set('situacao', filtros.situacao)
  if (filtros.minhas) parametros.set('minhas', '1')
  if (filtros.antes) parametros.set('antes', filtros.antes)
  parametros.set('limite', String(POR_PAGINA))
  return parametros.toString()
}

export const aprovacoes = {
  tipos: () => apiGet<TipoDeSolicitacao[]>(`${base}/tipos/`),
  lista: (filtros: FiltrosDaLista = {}) =>
    apiGet<PaginaDaLista>(`${base}/solicitacoes/?${consultaDaLista(filtros)}`),
  fila: () => apiGet<ItemDaLista[]>(`${base}/fila/`),
  detalhe: (id: string) => apiGet<DetalheDaSolicitacao>(`${base}/solicitacoes/${id}/`),
  historico: (id: string) => apiGet<RegistroDoHistorico[]>(`${base}/solicitacoes/${id}/historico/`),
}
