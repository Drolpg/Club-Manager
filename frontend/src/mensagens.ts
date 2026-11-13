import { ApiError } from './api/client'

// Texto mostrado para cada código de erro estável da API. Código sem texto próprio usa a mensagem da API.
const TEXTO: Record<string, string> = {
  CREDENCIAIS_INVALIDAS: 'Usuário ou senha inválidos.',
  MUITAS_TENTATIVAS: 'Muitas tentativas. Espere alguns minutos e tente de novo.',
  EMAIL_NAO_VERIFICADO: 'Falta verificar o seu e-mail para entrar.',
  CONVITE_INVALIDO: 'Convite inválido ou expirado.',
  NOME_DE_USUARIO_EM_USO: 'Este nome de usuário já está em uso.',
  EMAIL_EM_USO: 'Este e-mail já está em uso.',
  VALIDATION_ERROR: 'Confira os campos destacados.',
  LINK_INVALIDO: 'Este link é inválido ou venceu.',
  GOOGLE_INVALIDO: 'Não foi possível confirmar a sua conta Google.',
  ACESSO_SO_POR_CONVITE: 'O acesso é só por convite. Peça um ao administrador.',
  CONTA_JA_EXISTE: 'Já existe uma conta com este e-mail. Entre por ela.',
  NAO_PODE_ALTERAR_A_SI_MESMO: 'Esta ação precisa ser feita por outro admin.',
  NETWORK_ERROR: 'Não foi possível falar com o servidor. Confira a sua conexão.',
}

export function mensagemDoErro(erro: unknown): string {
  if (erro instanceof ApiError) return TEXTO[erro.code] ?? erro.message
  return 'Algo deu errado. Tente de novo.'
}

/** Os motivos por campo de um `VALIDATION_ERROR`, já como lista de textos. */
export function errosPorCampo(erro: unknown): Record<string, string[]> {
  if (!(erro instanceof ApiError) || erro.code !== 'VALIDATION_ERROR') return {}
  if (typeof erro.details !== 'object' || erro.details === null) return {}
  const campos: Record<string, string[]> = {}
  for (const [campo, valor] of Object.entries(erro.details as Record<string, unknown>)) {
    const itens = Array.isArray(valor) ? valor : [valor]
    campos[campo] = itens.map((item) =>
      typeof item === 'object' && item !== null && 'message' in item
        ? String((item as { message: unknown }).message)
        : String(item),
    )
  }
  return campos
}

export const SITUACAO_DO_USUARIO: Record<string, string> = {
  AGUARDANDO_VERIFICACAO: 'Aguardando verificação',
  ATIVO: 'Ativo',
  INATIVO: 'Inativo',
}

export const SITUACAO_DO_CONVITE: Record<string, string> = {
  ATIVO: 'Ativo',
  USADO: 'Usado',
  EXPIRADO: 'Expirado',
  REVOGADO: 'Revogado',
}
