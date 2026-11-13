import { apiGet, apiPost, apiPut } from './client'

export type TipoDeItem = 'cargos' | 'setores'
export type TipoDeAlvo = 'CARGO' | 'SETOR' | 'USUARIO'

/** Um cargo ou um setor. */
export interface Item {
  id: string
  nome: string
  ativo: boolean
}

export interface PermissaoDoCatalogo {
  codigo: string
  nome: string
  descricao: string
}

export interface Concessao {
  id: string
  permissao: string
  alvo_tipo: TipoDeAlvo
  alvo: { id: string; nome: string }
  concedida_em: string
  revogada_em: string | null
}

export interface Origem {
  tipo: 'ADMIN' | 'CARGO' | 'SETOR' | 'INDIVIDUAL' | 'ACESSO_TOTAL'
  id: string | null
  nome: string | null
}

export interface PermissaoDoUsuario {
  codigo: string
  nome: string
  origens: Origem[]
}

export interface DetalheDoUsuario {
  cargo: Item | null
  setores: Item[]
  permissoes: PermissaoDoUsuario[]
}

/** A permissão especial que dá todas as permissões do catálogo, menos as que ficam fora dela. */
export const ACESSO_TOTAL = 'acesso.total'

const base = '/permissoes'

export const permissoes = {
  itens: (tipo: TipoDeItem) => apiGet<Item[]>(`${base}/${tipo}/`),
  criar: (tipo: TipoDeItem, nome: string) => apiPost<Item>(`${base}/${tipo}/`, { nome }),
  renomear: (tipo: TipoDeItem, id: string, nome: string) => apiPost<Item>(`${base}/${tipo}/${id}/renomear/`, { nome }),
  desativar: (tipo: TipoDeItem, id: string) => apiPost<Item>(`${base}/${tipo}/${id}/desativar/`),
  reativar: (tipo: TipoDeItem, id: string) => apiPost<Item>(`${base}/${tipo}/${id}/reativar/`),

  catalogo: () => apiGet<PermissaoDoCatalogo[]>(`${base}/catalogo/`),
  concessoes: () => apiGet<Concessao[]>(`${base}/concessoes/`),
  conceder: (permissao: string, alvo_tipo: TipoDeAlvo, alvo_id: string) =>
    apiPost<Concessao>(`${base}/concessoes/`, { permissao, alvo_tipo, alvo_id }),
  revogar: (id: string) => apiPost<Concessao>(`${base}/concessoes/${id}/revogar/`),

  detalheDoUsuario: (id: string) => apiGet<DetalheDoUsuario>(`${base}/usuarios/${id}/`),
  classificar: (id: string, cargo_id: string | null, setor_ids: string[]) =>
    apiPut<DetalheDoUsuario>(`${base}/usuarios/${id}/classificacao/`, { cargo_id, setor_ids }),
  minhas: () => apiGet<DetalheDoUsuario>(`${base}/minhas/`),
}
