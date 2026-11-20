// Chamadas da API de eventos (`/api/v1/eventos/`). O site só chama e mostra: quem pode o quê vem em `acoes`.

import { apiGet, apiPost } from './client'

const base = '/eventos'

export type SituacaoDoEvento = 'EM_APROVACAO' | 'PUBLICADO' | 'RECUSADO' | 'REALIZADO' | 'CANCELADO'
export type Resposta = 'VOU' | 'NAO_VOU'
export type AcaoDoEvento =
  | 'editar'
  | 'reabrir'
  | 'vincular_orcamento'
  | 'confirmar_realizacao'
  | 'cancelar'
  | 'responder_presenca'

export interface Pessoa {
  id: string
  nome: string
}

export interface Item {
  id: string
  nome: string
}

export interface Referencias {
  categorias: Item[]
  aprovadores_eventos: Pessoa[]
  precisa_indicar_aprovador: boolean
}

export interface EventoNoCalendario {
  id: string
  titulo: string
  inicio: string
  local: string
  categoria_nome: string
  situacao: SituacaoDoEvento
}

export interface EventoDaLista extends EventoNoCalendario {
  categoria_id: string
  envolve_custo: boolean
  proponente_id: string
}

export interface PaginaDeEventos {
  itens: EventoDaLista[]
  tem_mais: boolean
}

export interface Presencas {
  vou: Pessoa[]
  nao_vou: Pessoa[]
  sem_resposta: Pessoa[]
  minha: Resposta | null
}

export interface DetalheDoEvento {
  id: string
  titulo: string
  descricao: string
  inicio: string
  local: string
  categoria_id: string
  categoria_nome: string
  envolve_custo: boolean
  situacao: SituacaoDoEvento
  criado_em: string
  proponente: Pessoa
  solicitacao_do_evento: { id: string; situacao: string }
  orcamento: { solicitacao_id: string; situacao: string } | null
  presencas: Presencas
  realizacao: { data: string; motivo: string; por: Pessoa | null; em: string } | null
  cancelamento: { motivo: string; por: Pessoa | null; pelo_sistema: boolean; em: string } | null
  acoes: AcaoDoEvento[]
}

export interface RegistroDoHistorico {
  acao: string
  ator: Pessoa | null
  justificativa: string
  criado_em: string
}

export interface CategoriaDeEvento {
  id: string
  nome: string
  ativa: boolean
}

export interface DadosDoEvento {
  titulo: string
  descricao: string
  inicio: string
  local: string
  categoria_id: string
  envolve_custo: boolean
}

export interface ItemDoOrcamento {
  descricao: string
  valor: string
}

export interface DadosDoOrcamento {
  descricao: string
  categoria_id: string
  setor_id: string
  itens: ItemDoOrcamento[]
  cotacao_id?: string | null
  aprovador_indicado_id?: string | null
}

export interface FiltrosDoHistorico {
  situacao?: string
  categoria_id?: string
  de?: string
  ate?: string
  antes?: string
}

/** A saída do orçamento, quando já existe, pela rota do financeiro. */
export interface SaidaDoEvento {
  id: string
  situacao: string
  valor_aprovado: string
  total_enviado: string
}

export const POR_PAGINA = 20

function consulta(filtros: FiltrosDoHistorico): string {
  const parametros = new URLSearchParams()
  for (const [chave, valor] of Object.entries(filtros)) if (valor) parametros.set(chave, valor)
  parametros.set('limite', String(POR_PAGINA))
  return parametros.toString()
}

export const eventos = {
  referencias: () => apiGet<Referencias>(`${base}/referencias/`),
  calendario: (mes: string) => apiGet<EventoNoCalendario[]>(`${base}/calendario/?mes=${mes}`),
  historico: (filtros: FiltrosDoHistorico = {}) => apiGet<PaginaDeEventos>(`${base}/?${consulta(filtros)}`),
  detalhe: (id: string) => apiGet<DetalheDoEvento>(`${base}/${id}/`),
  registros: (id: string) => apiGet<RegistroDoHistorico[]>(`${base}/${id}/historico/`),
  propor: (dados: DadosDoEvento & { aprovador_indicado_id?: string | null }) =>
    apiPost<DetalheDoEvento>(`${base}/`, dados),
  editar: (id: string, dados: DadosDoEvento & { justificativa: string }) =>
    apiPost<DetalheDoEvento>(`${base}/${id}/editar/`, dados),
  reabrir: (id: string, justificativa: string) =>
    apiPost<DetalheDoEvento>(`${base}/${id}/reabrir/`, { justificativa }),
  abrirOrcamento: (id: string, dados: DadosDoOrcamento) =>
    apiPost<DetalheDoEvento>(`${base}/${id}/orcamento/`, dados),
  responder: (id: string, resposta: Resposta) => apiPost<Presencas>(`${base}/${id}/presenca/`, { resposta }),
  realizar: (id: string, data: string | null, motivo: string) =>
    apiPost<DetalheDoEvento>(`${base}/${id}/realizar/`, { data, motivo }),
  cancelar: (id: string, motivo: string) => apiPost<DetalheDoEvento>(`${base}/${id}/cancelar/`, { motivo }),
  saidas: (id: string) =>
    apiGet<{ itens: SaidaDoEvento[] }>(`/financeiro/saidas/?${new URLSearchParams({ evento_id: id })}`),

  categorias: (todas = false) => apiGet<CategoriaDeEvento[]>(`${base}/categorias/${todas ? '?todas=1' : ''}`),
  criarCategoria: (nome: string) => apiPost<CategoriaDeEvento>(`${base}/categorias/`, { nome }),
  editarCategoria: (id: string, nome: string) =>
    apiPost<CategoriaDeEvento>(`${base}/categorias/${id}/editar/`, { nome }),
  desativarCategoria: (id: string) => apiPost<CategoriaDeEvento>(`${base}/categorias/${id}/desativar/`),
  reativarCategoria: (id: string) => apiPost<CategoriaDeEvento>(`${base}/categorias/${id}/reativar/`),
}
