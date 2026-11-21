// Chamadas da API de comunicação (`/api/v1/comunicacao/`). O site só chama e mostra: quem pode o quê vem em
// `acoes`, e o texto livre é mostrado como texto (R9).

import { apiGet, apiPost, apiPostForm } from './client'

const base = '/comunicacao'

export type TipoDeComunicado = 'COMUNICADO' | 'PAUTA'
export type TipoDeReacao = 'CIENTE' | 'DE_ACORDO' | 'DUVIDA' | 'COMEMORACAO'
export const TIPOS_DE_REACAO: TipoDeReacao[] = ['CIENTE', 'DE_ACORDO', 'DUVIDA', 'COMEMORACAO']
export type AcaoDoComunicado =
  | 'editar_comunicado'
  | 'despublicar'
  | 'republicar'
  | 'fixar'
  | 'desafixar'
  | 'reagir'
  | 'retirar_reacao'
  | 'comentar'
export type AcaoDoComentario = 'editar_comentario' | 'ocultar_comentario' | 'reexibir_comentario'
export type AcaoDoDocumento = 'nova_versao' | 'arquivar' | 'desarquivar'

export interface Pessoa {
  id: string
  nome: string
}

export interface ItemDeReferencia {
  codigo: string
  rotulo: string
}

export interface Referencias {
  categorias: { id: string; nome: string }[]
  tipos: ItemDeReferencia[]
  reacoes: ItemDeReferencia[]
}

export interface DocumentoDoComunicado {
  id: string
  titulo: string
  tipo: 'DOCUMENTO' | 'ATA'
  situacao: 'VIGENTE' | 'ARQUIVADO'
}

export interface Reacoes {
  contagem: Record<TipoDeReacao, number>
  minha: TipoDeReacao | null
  quem?: Record<TipoDeReacao, Pessoa[]>
}

export interface Comunicado {
  id: string
  tipo: TipoDeComunicado
  titulo: string
  texto: string
  autor: Pessoa
  situacao: 'PUBLICADO' | 'DESPUBLICADO'
  fixado: boolean
  fixado_em: string | null
  publicado_em: string
  editado: boolean
  editado_em: string | null
  despublicado: { em: string | null; por: Pessoa | null; motivo: string } | null
  documentos: DocumentoDoComunicado[]
  reacoes: Reacoes
  total_de_comentarios: number
  acoes: AcaoDoComunicado[]
}

export interface PaginaDoFeed {
  fixados: Comunicado[]
  itens: Comunicado[]
  tem_mais: boolean
}

export interface PaginaDeComunicados {
  itens: Comunicado[]
  tem_mais: boolean
}

export interface Comentario {
  id: string
  autor: Pessoa
  texto: string
  situacao: 'VISIVEL' | 'OCULTO'
  criado_em: string
  editado: boolean
  editado_em: string | null
  oculto: { em: string | null; por: Pessoa | null; pela_gerencia: boolean; motivo: string } | null
  acoes: AcaoDoComentario[]
}

export interface PaginaDeComentarios {
  itens: Comentario[]
  tem_mais: boolean
}

export interface DadosDoComunicado {
  titulo: string
  texto: string
  documentos_ids: string[]
}

export interface Arquivo {
  nome: string
  mime: string
  tamanho: number
}

export interface Documento {
  id: string
  tipo: 'DOCUMENTO' | 'ATA'
  titulo: string
  descricao: string
  categoria: { id: string; nome: string } | null
  data_da_reuniao: string | null
  enviado_por: Pessoa
  situacao: 'VIGENTE' | 'ARQUIVADO'
  versao_atual: number
  arquivo: Arquivo
  criado_em: string
  acoes: AcaoDoDocumento[]
}

export interface VersaoDoDocumento extends Arquivo {
  numero: number
  motivo: string
  enviada_por: Pessoa
  enviada_em: string
  situacao: 'VIGENTE' | 'SUBSTITUIDA'
}

export interface DetalheDoDocumento extends Documento {
  versoes: VersaoDoDocumento[]
  comunicados: { id: string; titulo: string }[]
}

export interface PaginaDeDocumentos {
  itens: Documento[]
  tem_mais: boolean
}

export interface FiltrosDeDocumentos {
  categoria_id?: string
  tipo?: string
  titulo?: string
  arquivados?: boolean
  antes?: string
}

export interface CategoriaDeDocumento {
  id: string
  nome: string
  ativa: boolean
}

function consulta(parametros: Record<string, string | boolean | undefined>): string {
  const busca = new URLSearchParams()
  for (const [chave, valor] of Object.entries(parametros)) {
    if (valor === undefined || valor === '' || valor === false) continue
    busca.set(chave, valor === true ? '1' : valor)
  }
  const texto = busca.toString()
  return texto ? `?${texto}` : ''
}

/** O arquivo da versão vigente, ou o de uma versão antiga: pela rota autenticada, sem URL pública. */
export function enderecoDoArquivo(documentoId: string, numero?: number): string {
  const versao = numero === undefined ? '' : `versoes/${numero}/`
  return `/api/v1${base}/documentos/${documentoId}/${versao}arquivo/`
}

function formulario(campos: Record<string, string | File | null | undefined>): FormData {
  const dados = new FormData()
  for (const [chave, valor] of Object.entries(campos)) {
    if (valor !== null && valor !== undefined) dados.set(chave, valor)
  }
  return dados
}

export const comunicacao = {
  referencias: () => apiGet<Referencias>(`${base}/referencias/`),

  feed: (antes?: string) => apiGet<PaginaDoFeed>(`${base}/comunicados/${consulta({ antes })}`),
  despublicados: (antes?: string) =>
    apiGet<PaginaDeComunicados>(`${base}/comunicados/despublicados/${consulta({ antes })}`),
  detalhe: (id: string) => apiGet<Comunicado>(`${base}/comunicados/${id}/`),
  publicar: (dados: DadosDoComunicado & { tipo: string }) =>
    apiPost<Comunicado>(`${base}/comunicados/`, dados),
  editar: (id: string, dados: DadosDoComunicado) =>
    apiPost<Comunicado>(`${base}/comunicados/${id}/editar/`, dados),
  despublicar: (id: string, motivo: string) =>
    apiPost<Comunicado>(`${base}/comunicados/${id}/despublicar/`, { motivo }),
  republicar: (id: string) => apiPost<Comunicado>(`${base}/comunicados/${id}/republicar/`),
  fixar: (id: string) => apiPost<Comunicado>(`${base}/comunicados/${id}/fixar/`),
  desafixar: (id: string) => apiPost<Comunicado>(`${base}/comunicados/${id}/desafixar/`),

  reagir: (id: string, tipo: TipoDeReacao) => apiPost<Reacoes>(`${base}/comunicados/${id}/reacao/`, { tipo }),
  retirarReacao: (id: string) => apiPost<Reacoes>(`${base}/comunicados/${id}/reacao/retirar/`),

  comentarios: (id: string, depois?: string) =>
    apiGet<PaginaDeComentarios>(`${base}/comunicados/${id}/comentarios/${consulta({ depois })}`),
  comentar: (id: string, texto: string) =>
    apiPost<Comentario>(`${base}/comunicados/${id}/comentarios/`, { texto }),
  editarComentario: (id: string, texto: string) =>
    apiPost<Comentario>(`${base}/comentarios/${id}/editar/`, { texto }),
  ocultarComentario: (id: string, motivo: string) =>
    apiPost<Comentario>(`${base}/comentarios/${id}/ocultar/`, { motivo }),
  reexibirComentario: (id: string) => apiPost<Comentario>(`${base}/comentarios/${id}/reexibir/`),

  documentos: (filtros: FiltrosDeDocumentos = {}) =>
    apiGet<PaginaDeDocumentos>(`${base}/documentos/${consulta({ ...filtros })}`),
  detalheDoDocumento: (id: string) => apiGet<DetalheDoDocumento>(`${base}/documentos/${id}/`),
  enviarDocumento: (dados: {
    titulo: string
    descricao: string
    categoria_id: string
    arquivo: File | null
  }) =>
    apiPostForm<DetalheDoDocumento>(`${base}/documentos/`, formulario(dados)),
  registrarAta: (dados: {
    titulo: string
    descricao: string
    data_da_reuniao: string
    arquivo: File | null
  }) =>
    apiPostForm<DetalheDoDocumento>(`${base}/documentos/atas/`, formulario(dados)),
  novaVersao: (id: string, dados: { motivo: string; arquivo: File | null }) =>
    apiPostForm<DetalheDoDocumento>(`${base}/documentos/${id}/versoes/`, formulario(dados)),
  arquivar: (id: string) => apiPost<DetalheDoDocumento>(`${base}/documentos/${id}/arquivar/`),
  desarquivar: (id: string) => apiPost<DetalheDoDocumento>(`${base}/documentos/${id}/desarquivar/`),

  categorias: (todas = false) =>
    apiGet<CategoriaDeDocumento[]>(`${base}/categorias/${consulta({ todas })}`),
  criarCategoria: (nome: string) => apiPost<CategoriaDeDocumento>(`${base}/categorias/`, { nome }),
  editarCategoria: (id: string, nome: string) =>
    apiPost<CategoriaDeDocumento>(`${base}/categorias/${id}/editar/`, { nome }),
  desativarCategoria: (id: string) => apiPost<CategoriaDeDocumento>(`${base}/categorias/${id}/desativar/`),
  reativarCategoria: (id: string) => apiPost<CategoriaDeDocumento>(`${base}/categorias/${id}/reativar/`),
}
