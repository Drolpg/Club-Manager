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
  CATEGORIA_JA_EXISTE: 'Já existe uma categoria com este nome e natureza.',
  CHAVE_PIX_PADRAO_NAO_CONFIGURADA: 'Configure uma chave Pix padrão antes de gerar cobranças.',
  SO_O_DEVEDOR: 'Só o devedor da cobrança pode executar esta ação.',
  DEVEDOR_NAO_VALIDA: 'O devedor não pode validar nem rejeitar o próprio pagamento.',
  DEVEDOR_NAO_DECIDE: 'O devedor não pode decidir a própria cobrança.',
  REGISTRADOR_NAO_VALIDA: 'Quem registrou a entrada não pode validá-la.',
  VALOR_INVALIDO: 'O valor precisa ser maior que zero.',
  VENCIMENTO_NO_PASSADO: 'A data de vencimento não pode estar no passado.',
  PARCELAS_INVALIDAS: 'Informe ao menos uma parcela válida.',
  DEVEDOR_INATIVO: 'O diretor devedor está inativo.',
  RECEBEDOR_INVALIDO: 'Escolha um recebedor ativo que não seja o próprio devedor.',
  CATEGORIA_INATIVA: 'Esta categoria está inativa.',
  CHAVE_PIX_INATIVA: 'Esta chave Pix está inativa.',
  SUSPENSAO_JA_ENCERRADA: 'Esta suspensão já foi encerrada.',
  NAO_ACEITA_PAGAMENTO: 'Esta cobrança não aceita pagamento nesta situação.',
  NAO_ESTA_EM_VALIDACAO: 'Este item não está aguardando validação.',
  NAO_ACEITA_QUESTIONAMENTO: 'Esta cobrança não aceita questionamento agora.',
  QUESTIONAMENTO_JA_ABERTO: 'Já existe um questionamento aberto para esta cobrança.',
  SEM_QUESTIONAMENTO_ABERTO: 'Não há questionamento aberto nesta cobrança.',
  NAO_PODE_ISENTAR: 'Não é possível isentar esta cobrança agora.',
  NAO_PODE_CANCELAR: 'Não é possível cancelar esta cobrança agora.',
  SEM_CONVOCACAO_ABERTA: 'Não há convocação aberta para esta cobrança.',
  NAO_ESTA_ATRASADA: 'Esta ação só vale para cobranças atrasadas.',
  NAO_ESTA_PAGA: 'O recibo só fica disponível após a validação do pagamento.',
  COBRANCA_JA_GERADA: 'A cobrança desta competência já foi gerada.',
  ITENS_INVALIDOS: 'Informe itens válidos com descrição e valor maior que zero.',
  COTACAO_INVALIDA: 'Anexe uma cotação em PDF ou imagem válida.',
  APROVADOR_INVALIDO: 'Escolha outro diretor ativo com cargo como aprovador indicado.',
  SO_O_SOLICITANTE: 'Só quem solicitou o gasto pode executar esta ação.',
  SOLICITANTE_NAO_LIQUIDA: 'Quem pediu o gasto não pode conferir nem liquidar a própria saída.',
  SAIDA_JA_POSSUI_ENVIO: 'O recurso desta saída já foi enviado.',
  ENVIO_NAO_EXIGE_COMPLEMENTO: 'O envio inicial cobre até o valor aprovado.',
  COMPLEMENTO_NAO_APROVADO: 'Não há complemento aprovado aguardando envio.',
  COMPROVANTE_OBRIGATORIO: 'Anexe o comprovante da operação.',
  EVIDENCIA_OBRIGATORIA: 'Anexe o comprovante ou descreva a justificativa.',
  VALOR_ACIMA_DO_APROVADO: 'O valor informado ultrapassa o valor aprovado.',
  NAO_ESTA_EM_CONFERENCIA: 'A saída precisa estar em conferência para esta ação.',
  DEVOLUCAO_ACIMA_DO_ENVIADO: 'A devolução não pode ultrapassar o total enviado.',
  COMPLEMENTO_JA_EM_ANDAMENTO: 'Já existe um pedido de complemento em andamento nesta saída.',
  NAO_HA_EXCESSO_PARA_COMPLEMENTO: 'Só é possível pedir complemento quando o gasto supera o enviado.',
  DEVOLUCAO_PENDENTE: 'Aguarde a validação da devolução pendente antes de liquidar.',
  DIFERENCA_NAO_ACERTADA: 'Informe justificativa ou resolva a diferença antes de liquidar.',
  JUSTIFICATIVA_OBRIGATORIA: 'Informe a justificativa para concluir esta ação.',
  NAO_PODE_ESTORNAR: 'Este registro não pode ser estornado nesta situação.',
  COMUNICADO_NAO_PUBLICADO: 'O comunicado não está publicado.',
  COMUNICADO_JA_PUBLICADO: 'O comunicado já está publicado.',
  COMUNICADO_JA_DESPUBLICADO: 'O comunicado já está despublicado.',
  JA_ESTA_FIXADO: 'O comunicado já está fixado.',
  NAO_ESTA_FIXADO: 'O comunicado não está fixado.',
  SEM_REACAO: 'Você não tem uma reação neste comunicado.',
  COMENTARIO_JA_OCULTO: 'O comentário já está oculto.',
  COMENTARIO_NAO_ESTA_OCULTO: 'O comentário não está oculto.',
  DOCUMENTO_ARQUIVADO: 'O documento está arquivado.',
  DOCUMENTO_JA_ARQUIVADO: 'O documento já está arquivado.',
  DOCUMENTO_NAO_ESTA_ARQUIVADO: 'O documento não está arquivado.',
  DATA_FUTURA: 'A data da reunião não pode estar no futuro.',
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

export const SITUACAO_DA_COBRANCA: Record<string, string> = {
  ABERTA: 'Aberta',
  EM_VALIDACAO: 'Em validação',
  ATRASADA: 'Atrasada',
  PAGA: 'Paga',
  ISENTA: 'Isenta',
  CANCELADA: 'Cancelada',
  PERDOADA: 'Perdoada',
  RENEGOCIADA: 'Renegociada',
  ESTORNADA: 'Estornada',
}

export const SITUACAO_DA_ENTRADA: Record<string, string> = {
  EM_VALIDACAO: 'Em validação',
  VALIDADA: 'Validada',
  REJEITADA: 'Rejeitada',
  ESTORNADA: 'Estornada',
}

export const SITUACAO_DA_SAIDA: Record<string, string> = {
  AGUARDANDO_ENVIO: 'Aguardando envio',
  RECURSO_ENVIADO: 'Recurso enviado',
  EM_CONFERENCIA: 'Em conferência',
  LIQUIDADA: 'Liquidada',
  CANCELADA: 'Cancelada',
  ESTORNADA: 'Estornada',
}

export const SITUACAO_DA_PRESTACAO: Record<string, string> = {
  VIGENTE: 'Vigente',
  DEVOLVIDA: 'Devolvida',
}

export const SITUACAO_DO_COMPLEMENTO: Record<string, string> = {
  EM_ANDAMENTO: 'Em andamento',
  APROVADO: 'Aprovado',
  RECUSADO: 'Recusado',
  CANCELADO: 'Cancelado',
}

export const ALVO_DO_ESTORNO: Record<string, string> = {
  SAIDA: 'Saída',
  ENTRADA: 'Entrada',
  COBRANCA: 'Cobrança',
}

export const SITUACAO_DO_PAGAMENTO: Record<string, string> = {
  EM_VALIDACAO: 'Em validação',
  VALIDADO: 'Validado',
  REJEITADO: 'Rejeitado',
}

export const TIPO_DE_CHAVE_PIX: Record<string, string> = {
  EMAIL: 'E-mail',
  TELEFONE: 'Telefone',
  CNPJ: 'CNPJ',
  CPF: 'CPF',
  ALEATORIA: 'Chave aleatória',
}

export const PERIODICIDADE_FINANCEIRA: Record<string, string> = {
  MENSAL: 'Mensal',
  SEMANAL: 'Semanal',
  ANUAL: 'Anual',
}

export const SITUACAO_DA_SUSPENSAO: Record<string, string> = {
  VIGENTE: 'Vigente',
  ENCERRADA: 'Encerrada',
}

const ACAO_FINANCEIRA_AUDITADA: Record<string, string> = {
  COBRANCA_CRIADA: 'Cobrança criada',
  COBRANCA_AVULSA_CRIADA: 'Cobrança avulsa criada',
  COBRANCA_EM_LOTE_CRIADA: 'Cobrança em lote criada',
  PAGAMENTO_REGISTRADO: 'Pagamento registrado',
  PAGAMENTO_VALIDADO: 'Pagamento validado',
  PAGAMENTO_REJEITADO: 'Pagamento rejeitado',
  COBRANCA_ATRASADA: 'Cobrança atrasada',
  COBRANCA_ISENTA: 'Cobrança isenta',
  COBRANCA_CANCELADA: 'Cobrança cancelada',
  QUESTIONAMENTO_ABERTO: 'Questionamento aberto',
  QUESTIONAMENTO_DECIDIDO: 'Questionamento decidido',
  DEVEDOR_CONVOCADO: 'Devedor convocado',
  DIVIDA_JUSTIFICADA: 'Dívida justificada',
  COBRANCA_PERDOADA: 'Cobrança perdoada',
  COBRANCA_RENEGOCIADA: 'Cobrança renegociada',
  DIVIDA_MANTIDA: 'Dívida mantida',
  ENTRADA_REGISTRADA: 'Entrada registrada',
  ENTRADA_VALIDADA: 'Entrada validada',
  ENTRADA_REJEITADA: 'Entrada rejeitada',
  SAIDA_ABERTA: 'Saída aberta',
  SAIDA_CANCELADA: 'Saída cancelada',
  RECURSO_ENVIADO: 'Recurso enviado',
  PRESTACAO_REGISTRADA: 'Prestação de contas registrada',
  PRESTACAO_DEVOLVIDA: 'Prestação devolvida para correção',
  COMPLEMENTO_SOLICITADO: 'Complemento solicitado',
  COMPLEMENTO_APROVADO: 'Complemento aprovado',
  COMPLEMENTO_RECUSADO: 'Complemento recusado',
  COMPLEMENTO_CANCELADO: 'Complemento cancelado',
  SAIDA_LIQUIDADA: 'Saída liquidada',
  SAIDA_ESTORNADA: 'Saída estornada',
  ENTRADA_ESTORNADA: 'Entrada estornada',
  COBRANCA_ESTORNADA: 'Cobrança estornada',
  ESTORNO_REGISTRADO: 'Estorno registrado',
}

export function rotuloDaAcaoFinanceira(acao: string): string {
  return ACAO_FINANCEIRA_AUDITADA[acao] ?? acao
}

export const SITUACAO_DO_EVENTO: Record<string, string> = {
  EM_APROVACAO: 'Em aprovação',
  PUBLICADO: 'Publicado',
  RECUSADO: 'Recusado',
  REALIZADO: 'Realizado',
  CANCELADO: 'Cancelado',
}

const ACAO_NO_HISTORICO_DO_EVENTO: Record<string, string> = {
  EVENTO_PROPOSTO: 'Evento proposto',
  EVENTO_EDITADO: 'Evento editado',
  EVENTO_REABERTO: 'Evento reaberto',
  ORCAMENTO_VINCULADO: 'Orçamento aberto',
  ORCAMENTO_DESVINCULADO: 'Orçamento desligado do evento',
  EVENTO_PUBLICADO: 'Evento publicado',
  EVENTO_DESPUBLICADO: 'Evento saiu do calendário',
  EVENTO_RECUSADO: 'Evento recusado',
  PRESENCA_RESPONDIDA: 'Presença respondida',
  EVENTO_REALIZADO: 'Evento realizado',
  EVENTO_CANCELADO: 'Evento cancelado',
  AVISO_DE_REALIZACAO_ENVIADO: 'Lembrete de confirmação enviado',
}

export function rotuloDaAcaoNoEvento(acao: string): string {
  return ACAO_NO_HISTORICO_DO_EVENTO[acao] ?? acao
}

export const TIPO_DE_COMUNICADO: Record<string, string> = { COMUNICADO: 'Comunicado', PAUTA: 'Pauta' }

export const ROTULO_DA_REACAO: Record<string, string> = {
  CIENTE: 'Ciente',
  DE_ACORDO: 'De acordo',
  DUVIDA: 'Dúvida',
  COMEMORACAO: 'Comemoração',
}

export const TIPO_DE_DOCUMENTO: Record<string, string> = { DOCUMENTO: 'Documento', ATA: 'Ata' }

export const SITUACAO_DO_DOCUMENTO: Record<string, string> = { VIGENTE: 'Vigente', ARQUIVADO: 'Arquivado' }

export const SITUACAO_DA_VERSAO: Record<string, string> = { VIGENTE: 'Vigente', SUBSTITUIDA: 'Substituída' }
