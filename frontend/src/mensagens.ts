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
  CSRF_FAILED: 'A página ficou desatualizada. Recarregue e tente de novo.',
  NOME_EM_USO: 'Já existe um item com este nome.',
  JA_ESTA_ATIVO: 'Este item já está ativo.',
  JA_ESTA_INATIVO: 'Este item já está inativo.',
  CARGO_INATIVO: 'Este cargo está inativo. Reative-o ou escolha outro.',
  SETOR_INATIVO: 'Há um setor inativo na lista. Reative-o ou escolha outro.',
  USUARIO_NAO_ESTA_ATIVO: 'Só usuário ativo pode ser classificado.',
  ACESSO_TOTAL_SO_PARA_USUARIO: 'O acesso total só pode ser concedido a uma pessoa.',
  CONCESSAO_JA_REVOGADA: 'Esta concessão já foi revogada.',
  PERMISSION_DENIED: 'Você não tem permissão para fazer isso.',
  NOT_FOUND: 'Não encontrado.',
  NETWORK_ERROR: 'Não foi possível falar com o servidor. Confira a sua conexão.',
}

// Desativar um cargo ou setor que usuários ativos têm: a API informa a quantidade em `details.usuarios`.
const ITEM_EM_USO: Record<string, string> = { CARGO_EM_USO: 'cargo', SETOR_EM_USO: 'setor' }

function mensagemDeItemEmUso(erro: ApiError): string | null {
  const item = ITEM_EM_USO[erro.code]
  const quantidade = (erro.details as { usuarios?: unknown } | null)?.usuarios
  if (!item || typeof quantidade !== 'number') return null
  const quem = quantidade === 1 ? '1 usuário ativo tem' : `${quantidade} usuários ativos têm`
  return `${quem} este ${item}. Reclassifique-os antes de desativar.`
}

export function mensagemDoErro(erro: unknown): string {
  if (erro instanceof ApiError) return mensagemDeItemEmUso(erro) ?? TEXTO[erro.code] ?? erro.message
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

export const ROTULO_DO_ALVO: Record<string, string> = { CARGO: 'Cargo', SETOR: 'Setor', USUARIO: 'Usuário' }

/** De onde vem uma permissão, em linguagem de gente (CA-25). */
export function descreverOrigem(origem: { tipo: string; nome: string | null }): string {
  switch (origem.tipo) {
    case 'ADMIN':
      return 'por ser admin'
    case 'CARGO':
      return `pelo cargo ${origem.nome}`
    case 'SETOR':
      return `pelo setor ${origem.nome}`
    case 'INDIVIDUAL':
      return 'concedida a ele'
    case 'ACESSO_TOTAL':
      return 'pelo acesso total'
    default:
      return origem.tipo
  }
}

const ACAO_AUDITADA: Record<string, string> = {
  CARGO_CRIADO: 'Cargo criado',
  CARGO_RENOMEADO: 'Cargo renomeado',
  CARGO_DESATIVADO: 'Cargo desativado',
  CARGO_REATIVADO: 'Cargo reativado',
  SETOR_CRIADO: 'Setor criado',
  SETOR_RENOMEADO: 'Setor renomeado',
  SETOR_DESATIVADO: 'Setor desativado',
  SETOR_REATIVADO: 'Setor reativado',
  USUARIO_CLASSIFICADO: 'Classificado',
  CLASSIFICACAO_REMOVIDA: 'Cargo retirado',
  PERMISSAO_CONCEDIDA: 'Permissão concedida',
  PERMISSAO_REVOGADA: 'Permissão revogada',
  USUARIO_DESATIVADO: 'Desativado',
  USUARIO_REATIVADO: 'Reativado',
  PAPEL_DE_ADMIN_DADO: 'Papel de admin dado',
  PAPEL_DE_ADMIN_REMOVIDO: 'Papel de admin retirado',
  ADMIN_CRIADO_POR_COMANDO: 'Admin criado no servidor',
  CONVITE_GERADO: 'Convite gerado',
  CONVITE_REVOGADO: 'Convite revogado',
}

/** O texto de uma ação da auditoria. Ação sem texto próprio aparece com o código. */
export function rotuloDaAcao(acao: string): string {
  return ACAO_AUDITADA[acao] ?? acao
}

export const SITUACAO_DA_SOLICITACAO: Record<string, string> = {
  EM_ANALISE: 'Em análise',
  RETIRADA: 'Retirada',
  CONTESTADA: 'Contestada',
  RECUSADA: 'Recusada',
  APROVADA: 'Aprovada',
  EM_EXECUCAO: 'Em execução',
  ENCERRADA: 'Encerrada',
  CANCELADA: 'Cancelada',
}

export const DECISAO_DA_SOLICITACAO: Record<string, string> = {
  APROVAR: 'Aprovada',
  CONTESTAR: 'Contestada',
  RECUSAR: 'Recusada',
}

// O que cada registro do histórico de uma solicitação quer dizer.
const ACAO_NA_SOLICITACAO: Record<string, string> = {
  SOLICITACAO_ENVIADA: 'Enviada',
  APROVADOR_INDICADO: 'Aprovador indicado',
  SOLICITACAO_RETIRADA: 'Retirada',
  SOLICITACAO_REENVIADA: 'Reenviada',
  SOLICITACAO_REABERTA: 'Reaberta',
  SOLICITACAO_EDITADA: 'Editada',
  SOLICITACAO_CANCELADA: 'Cancelada',
  SOLICITACAO_APROVADA: 'Aprovada',
  SOLICITACAO_CONTESTADA: 'Contestada',
  SOLICITACAO_RECUSADA: 'Recusada',
  SOLICITACAO_EM_EXECUCAO: 'Em execução',
  SOLICITACAO_ENCERRADA: 'Encerrada',
}

export function rotuloDaAcaoNaSolicitacao(acao: string): string {
  return ACAO_NA_SOLICITACAO[acao] ?? acao
}
