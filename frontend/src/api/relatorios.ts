// Chamadas da API de relatórios (`/api/v1/relatorios/`): o perfil. Só leitura; o site só mostra.

import { apiGet } from './client'

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
