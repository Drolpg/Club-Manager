import { apiGet, apiPost, apiPut } from './client'

/** Uma notificação como a caixa mostra. O texto é sempre exibido como texto, nunca como HTML. */
export interface Notificacao {
  id: string
  tipo: string
  pede_acao: boolean
  titulo: string
  texto: string
  caminho: string
  criada_em: string
  lida_em: string | null
}

export interface PaginaDaCaixa {
  itens: Notificacao[]
  tem_mais: boolean
}

export interface Resumo {
  nao_lidas: number
  mais_recente_id: string | null
}

export interface Preferencias {
  aviso_na_tela: boolean
  email_informativos: boolean
}

const base = '/notificacoes'

/** Quantas notificações a caixa pede por vez (a API aceita de 1 a 50). */
export const POR_PAGINA = 20

export const notificacoes = {
  resumo: () => apiGet<Resumo>(`${base}/resumo/`),
  /** As da caixa, da mais recente para a mais antiga. `antes` é o ID da última já recebida. */
  caixa: (antes?: string, limite = POR_PAGINA) =>
    apiGet<PaginaDaCaixa>(`${base}/?limite=${limite}${antes ? `&antes=${encodeURIComponent(antes)}` : ''}`),
  ler: (id: string) => apiPost<Notificacao>(`${base}/${id}/ler/`),
  lerTodas: () => apiPost<{ marcadas: number }>(`${base}/ler-todas/`),
  preferencias: () => apiGet<Preferencias>(`${base}/preferencias/`),
  salvarPreferencias: (preferencias: Preferencias) => apiPut<Preferencias>(`${base}/preferencias/`, preferencias),
}
