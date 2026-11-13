import { apiDelete, apiGet, apiPost } from './client'

export interface Usuario {
  id: string
  nome: string
  nome_de_usuario: string
  email: string
  admin: boolean
  situacao: 'AGUARDANDO_VERIFICACAO' | 'ATIVO' | 'INATIVO'
  tem_cargo: boolean
}

export interface Convite {
  id: string
  situacao: 'ATIVO' | 'USADO' | 'EXPIRADO' | 'REVOGADO'
  gerado_por: { id: string; nome: string }
  gerado_em: string
  expira_em: string
  usado_em: string | null
  revogado_em: string | null
}

export interface ConviteGerado extends Convite {
  link: string
}

export interface DadosDeCadastro {
  token: string
  nome: string
  nome_de_usuario: string
  telefone: string
  email: string
  senha: string
}

export interface RegistroDoHistorico {
  acao: string
  ator: { id: string; nome: string } | null
  justificativa: string
  criado_em: string
}

export type AcaoDeUsuario = 'desativar' | 'reativar' | 'tornar-admin' | 'remover-admin'

interface Sessao {
  usuario: Usuario | null
}

const base = '/acesso'

export const acesso = {
  configuracao: () => apiGet<{ google_client_id: string | null }>(`${base}/configuracao/`),
  sessao: () => apiGet<Sessao>(`${base}/sessao/`),
  entrar: (identificador: string, senha: string) => apiPost<Sessao>(`${base}/sessao/`, { identificador, senha }),
  entrarComGoogle: (credencial: string) => apiPost<Sessao>(`${base}/sessao/google/`, { credencial }),
  sair: () => apiDelete<null>(`${base}/sessao/`),

  consultarConvite: (token: string) => apiPost<null>(`${base}/convites/consultar/`, { token }),
  cadastrar: (dados: DadosDeCadastro) => apiPost<{ situacao: string }>(`${base}/cadastros/`, dados),
  cadastrarComGoogle: (dados: Omit<DadosDeCadastro, 'email'> & { credencial: string }) =>
    apiPost<Sessao>(`${base}/cadastros/google/`, dados),
  verificar: (token: string) => apiPost<null>(`${base}/verificacoes/`, { token }),
  reenviarVerificacao: (identificador: string) =>
    apiPost<null>(`${base}/verificacoes/reenviar/`, { identificador }),

  recuperarSenha: (email: string) => apiPost<null>(`${base}/senhas/recuperar/`, { email }),
  redefinirSenha: (token: string, senha: string) => apiPost<null>(`${base}/senhas/redefinir/`, { token, senha }),

  convites: () => apiGet<Convite[]>(`${base}/convites/`),
  gerarConvite: () => apiPost<ConviteGerado>(`${base}/convites/`),
  regenerarConvite: (id: string) => apiPost<ConviteGerado>(`${base}/convites/${id}/regenerar/`),
  revogarConvite: (id: string) => apiPost<Convite>(`${base}/convites/${id}/revogar/`),

  usuarios: () => apiGet<Usuario[]>(`${base}/usuarios/`),
  acaoDeUsuario: (id: string, acao: AcaoDeUsuario) => apiPost<Usuario>(`${base}/usuarios/${id}/${acao}/`),
  historicoDeUsuario: (id: string) => apiGet<RegistroDoHistorico[]>(`${base}/usuarios/${id}/historico/`),
}
