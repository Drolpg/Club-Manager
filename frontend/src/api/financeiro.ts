import { apiGet, apiPost, apiPostForm } from './client'

export interface PessoaFinanceira {
  id: string
  nome: string
}

export type NaturezaCategoria = 'ENTRADA' | 'SAIDA'
export type TipoChavePix = 'EMAIL' | 'TELEFONE' | 'CNPJ' | 'CPF' | 'ALEATORIA'
export type SituacaoCobranca =
  | 'ABERTA'
  | 'EM_VALIDACAO'
  | 'ATRASADA'
  | 'PAGA'
  | 'ISENTA'
  | 'CANCELADA'
  | 'PERDOADA'
  | 'RENEGOCIADA'
export type AcaoCobranca =
  | 'registrar_pagamento'
  | 'validar_pagamento'
  | 'rejeitar_pagamento'
  | 'questionar'
  | 'decidir_questionamento'
  | 'isentar'
  | 'cancelar'
  | 'justificar_divida'
  | 'perdoar'
  | 'renegociar'
  | 'manter_divida'
export type FormaPagamento = 'COMPROVANTE' | 'EM_MAO'
export type SituacaoPagamento = 'EM_VALIDACAO' | 'VALIDADO' | 'REJEITADO'
export type Periodicidade = 'MENSAL' | 'SEMANAL' | 'ANUAL'
export type SituacaoSuspensao = 'VIGENTE' | 'ENCERRADA'
export type SituacaoEntrada = 'EM_VALIDACAO' | 'VALIDADA' | 'REJEITADA'
export type AcaoEntrada = 'validar' | 'rejeitar'
export type DecisaoQuestionamento = 'ISENTAR' | 'CANCELAR' | 'MANTER'

export interface Categoria {
  id: string
  nome: string
  natureza: NaturezaCategoria
  ativa: boolean
  criada_em: string
}

export interface ChavePix {
  id: string
  tipo: TipoChavePix
  chave: string
  nome_recebedor: string
  cidade: string
  padrao: boolean
  ativa: boolean
  criada_em: string
}

export interface CobrancaItem {
  id: string
  devedor: PessoaFinanceira
  categoria_id: string
  categoria_nome: string
  descricao: string
  valor: string
  vencimento: string
  situacao: SituacaoCobranca
  tem_questionamento_aberto: boolean
  tem_convocacao_aberta: boolean
  recorrencia_id: string | null
  competencia: string
  cobranca_origem_id: string | null
  criada_em: string
}

export interface Pagamento {
  id: string
  forma: FormaPagamento
  data_pagamento: string
  recebedor: PessoaFinanceira | null
  comprovante_disponivel: boolean
  comprovante_nome: string
  situacao: SituacaoPagamento
  decidido_por: PessoaFinanceira | null
  motivo_texto: string
  decisao_texto: string
  registrado_em: string
  decidido_em: string | null
}

export interface Questionamento {
  id: string
  texto: string
  situacao: string
  decisao: DecisaoQuestionamento | null
  decidido_por: PessoaFinanceira | null
  motivo_texto: string
  decisao_texto: string
  aberto_em: string
  decidido_em: string | null
}

export interface Convocacao {
  convocado_em: string
  justificativa_do_devedor: string
  justificada_em: string | null
  decisao: string | null
  decidido_por: PessoaFinanceira | null
  motivo_texto: string
  decisao_texto: string
  decidido_em: string | null
}

export interface Renegociacao {
  id: string
  valor_acordado: string
  quantidade_parcelas: number
  decidido_por: PessoaFinanceira
  motivo_texto: string
  decisao_texto: string
  criada_em: string
}

export interface CobrancaDetalhe extends CobrancaItem {
  limite_de_inadimplencia: number
  chave_pix_id: string
  pix_chave: string
  pix_nome_recebedor: string
  pix_cidade: string
  pix_copia_e_cola: string
  qrcode_svg: string
  pausada_por_questionamento_em: string | null
  dias_pausados_inadimplencia: number
  isencao: { por: PessoaFinanceira; justificativa: string } | null
  cancelamento: { por: PessoaFinanceira; motivo_texto: string; texto: string } | null
  perdao: { por: PessoaFinanceira; motivo_texto: string; texto: string } | null
  paga_em: string | null
  encerrada_em: string | null
  atualizada_em: string
  pagamentos: Pagamento[]
  questionamentos: Questionamento[]
  convocacao: Convocacao | null
  renegociacao: Renegociacao | null
  parcelas: CobrancaItem[]
  acoes: AcaoCobranca[]
}

export interface PaginaCobrancas {
  itens: CobrancaItem[]
  tem_mais: boolean
}

export interface Recorrencia {
  id: string
  devedor: PessoaFinanceira
  categoria_id: string
  categoria_nome: string
  descricao: string
  valor: string
  periodicidade: Periodicidade
  dia_vencimento: number
  mes_vencimento: number | null
  antecedencia_dias: number
  limite_de_inadimplencia: number
  chave_pix_id: string
  ativa: boolean
  a_partir_de: string
  criada_em: string
}

export interface Suspensao {
  id: string
  diretor: PessoaFinanceira
  recorrencia_id: string | null
  inicio: string
  fim: string | null
  justificativa: string
  situacao: SituacaoSuspensao
  criada_em: string
  encerrada_em: string | null
}

export interface Entrada {
  id: string
  tipo: 'SEM_DEVEDOR' | 'DEVOLUCAO_SAIDA'
  categoria_id: string
  categoria_nome: string
  valor: string
  data: string
  origem: string
  evidencia_texto: string
  comprovante_disponivel: boolean
  comprovante_nome: string
  registrada_por: PessoaFinanceira
  situacao: SituacaoEntrada
  decidido_por: PessoaFinanceira | null
  motivo_texto: string
  decisao_texto: string
  registrada_em: string
  decidido_em: string | null
  acoes: AcaoEntrada[]
}

export interface PaginaEntradas {
  itens: Entrada[]
  tem_mais: boolean
}

export interface ResumoEntradas {
  quantidade: number
  total: string
}

export interface HistoricoFinanceiro {
  acao: string
  ator: PessoaFinanceira | null
  justificativa: string
  dados: Record<string, unknown>
  criado_em: string
}

export interface FiltrosMinhasCobrancas {
  situacao?: string
  antes?: string
}

export interface FiltrosCobrancas {
  situacao?: string
  categoria_id?: string
  devedor_id?: string
  de?: string
  ate?: string
  inadimplentes?: boolean
  antes?: string
}

export interface FiltrosEntradas {
  situacao?: string
  categoria_id?: string
  de?: string
  ate?: string
  antes?: string
}

export const PERM_COBRANCAS_CRIAR = 'financeiro.cobrancas.criar'
export const PERM_COBRANCAS_SUSPENDER = 'financeiro.cobrancas.suspender'
export const PERM_ENTRADAS_REGISTRAR = 'financeiro.entradas.registrar'

export const TIPO_DECISAO_FINANCEIRO: Record<string, string> = {
  validar_pagamento: 'financeiro.pagamento_validar',
  rejeitar_pagamento: 'financeiro.pagamento_rejeitar',
  cancelar: 'financeiro.cobranca_cancelar',
  decidir_questionamento: 'financeiro.questionamento_decidir',
  perdoar: 'financeiro.divida_decidir',
  renegociar: 'financeiro.divida_decidir',
  manter_divida: 'financeiro.divida_decidir',
  entrada_validar: 'financeiro.entrada_validar',
  entrada_rejeitar: 'financeiro.entrada_rejeitar',
}

export const POR_PAGINA = 20
const base = '/financeiro'

export function urlComprovanteCobranca(cobrancaId: string, pagamentoId: string): string {
  return `/api/v1${base}/cobrancas/${cobrancaId}/pagamentos/${pagamentoId}/comprovante/`
}

export function urlReciboCobranca(cobrancaId: string): string {
  return `/api/v1${base}/cobrancas/${cobrancaId}/recibo/`
}

export function urlComprovanteEntrada(entradaId: string): string {
  return `/api/v1${base}/entradas/${entradaId}/comprovante/`
}

function query(params: Record<string, string | boolean | number | undefined>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === '' || v === false) continue
    sp.set(k, v === true ? '1' : String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

export const financeiro = {
  categorias: (opcoes: { natureza?: NaturezaCategoria; todas?: boolean } = {}) =>
    apiGet<Categoria[]>(`${base}/categorias/${query(opcoes)}`),
  criarCategoria: (nome: string, natureza: NaturezaCategoria) =>
    apiPost<Categoria>(`${base}/categorias/`, { nome, natureza }),
  renomearCategoria: (id: string, nome: string) =>
    apiPost<Categoria>(`${base}/categorias/${id}/renomear/`, { nome }),
  desativarCategoria: (id: string) => apiPost<Categoria>(`${base}/categorias/${id}/desativar/`),
  reativarCategoria: (id: string) => apiPost<Categoria>(`${base}/categorias/${id}/reativar/`),

  chavesPix: (opcoes: { todas?: boolean } = {}) =>
    apiGet<ChavePix[]>(`${base}/chaves-pix/${query(opcoes)}`),
  criarChavePix: (dados: {
    tipo: TipoChavePix
    chave: string
    nome_recebedor: string
    cidade: string
    padrao: boolean
  }) => apiPost<ChavePix>(`${base}/chaves-pix/`, dados),
  editarChavePix: (
    id: string,
    dados: { tipo: TipoChavePix; chave: string; nome_recebedor: string; cidade: string },
  ) => apiPost<ChavePix>(`${base}/chaves-pix/${id}/editar/`, dados),
  marcarChavePixPadrao: (id: string) => apiPost<ChavePix>(`${base}/chaves-pix/${id}/marcar-padrao/`),
  desativarChavePix: (id: string) => apiPost<ChavePix>(`${base}/chaves-pix/${id}/desativar/`),
  reativarChavePix: (id: string) => apiPost<ChavePix>(`${base}/chaves-pix/${id}/reativar/`),

  minhasCobrancas: (filtros: FiltrosMinhasCobrancas = {}) =>
    apiGet<PaginaCobrancas>(
      `${base}/minhas-cobrancas/${query({ ...filtros, limite: POR_PAGINA })}`,
    ),
  cobrancas: (filtros: FiltrosCobrancas = {}) =>
    apiGet<PaginaCobrancas>(`${base}/cobrancas/${query({ ...filtros, limite: POR_PAGINA })}`),
  criarCobranca: (dados: {
    devedor_id: string
    categoria_id: string
    descricao: string
    valor: string
    vencimento: string
    limite_de_inadimplencia: number
    chave_pix_id?: string | null
  }) => apiPost<CobrancaDetalhe>(`${base}/cobrancas/`, dados),
  criarCobrancasEmLote: (dados: {
    devedor_ids: string[]
    todos_ativos_com_cargo: boolean
    categoria_id: string
    descricao: string
    valor: string
    vencimento: string
    limite_de_inadimplencia: number
    chave_pix_id?: string | null
  }) => apiPost<CobrancaItem[]>(`${base}/cobrancas/lote/`, dados),
  detalheCobranca: (id: string) => apiGet<CobrancaDetalhe>(`${base}/cobrancas/${id}/`),
  historicoCobranca: (id: string) =>
    apiGet<HistoricoFinanceiro[]>(`${base}/cobrancas/${id}/historico/`),

  registrarPagamentoEmMao: (id: string, dados: { data_pagamento: string; recebedor_id: string }) =>
    apiPost<CobrancaDetalhe>(`${base}/cobrancas/${id}/pagamentos/`, { forma: 'EM_MAO', ...dados }),
  registrarPagamentoComComprovante: (id: string, dados: { data_pagamento: string; comprovante: File }) => {
    const fd = new FormData()
    fd.set('forma', 'COMPROVANTE')
    fd.set('data_pagamento', dados.data_pagamento)
    fd.set('comprovante', dados.comprovante)
    return apiPostForm<CobrancaDetalhe>(`${base}/cobrancas/${id}/pagamentos/`, fd)
  },
  validarPagamento: (id: string, corpo: { motivo_id: string; texto: string }) =>
    apiPost<CobrancaDetalhe>(`${base}/cobrancas/${id}/validar-pagamento/`, corpo),
  rejeitarPagamento: (id: string, corpo: { motivo_id: string; texto: string }) =>
    apiPost<CobrancaDetalhe>(`${base}/cobrancas/${id}/rejeitar-pagamento/`, corpo),
  questionar: (id: string, texto: string) =>
    apiPost<CobrancaDetalhe>(`${base}/cobrancas/${id}/questionar/`, { texto }),
  decidirQuestionamento: (
    id: string,
    corpo: { decisao: DecisaoQuestionamento; motivo_id: string; texto: string },
  ) => apiPost<CobrancaDetalhe>(`${base}/cobrancas/${id}/questionamento/decidir/`, corpo),
  isentar: (id: string, justificativa: string) =>
    apiPost<CobrancaDetalhe>(`${base}/cobrancas/${id}/isentar/`, { justificativa }),
  cancelarCobranca: (id: string, corpo: { motivo_id: string; texto: string }) =>
    apiPost<CobrancaDetalhe>(`${base}/cobrancas/${id}/cancelar/`, corpo),
  justificarDivida: (id: string, texto: string) =>
    apiPost<CobrancaDetalhe>(`${base}/cobrancas/${id}/justificar-divida/`, { texto }),
  perdoarDivida: (id: string, corpo: { motivo_id: string; texto: string }) =>
    apiPost<CobrancaDetalhe>(`${base}/cobrancas/${id}/perdoar/`, corpo),
  manterDivida: (id: string, corpo: { motivo_id: string; texto: string }) =>
    apiPost<CobrancaDetalhe>(`${base}/cobrancas/${id}/manter-divida/`, corpo),
  renegociarDivida: (
    id: string,
    corpo: { motivo_id: string; texto: string; parcelas: Array<{ valor: string; vencimento: string }> },
  ) => apiPost<CobrancaDetalhe>(`${base}/cobrancas/${id}/renegociar/`, corpo),

  recorrencias: (opcoes: { devedor_id?: string; todas?: boolean } = {}) =>
    apiGet<Recorrencia[]>(`${base}/recorrencias/${query(opcoes)}`),
  criarRecorrencia: (dados: {
    devedor_id: string
    categoria_id: string
    descricao: string
    valor: string
    periodicidade: Periodicidade
    dia_vencimento: number
    mes_vencimento: number | null
    antecedencia_dias: number
    limite_de_inadimplencia: number
    chave_pix_id?: string | null
    a_partir_de?: string | null
  }) => apiPost<Recorrencia>(`${base}/recorrencias/`, dados),
  editarRecorrencia: (
    id: string,
    dados: {
      categoria_id: string
      descricao: string
      valor: string
      dia_vencimento: number
      mes_vencimento: number | null
      antecedencia_dias: number
      limite_de_inadimplencia: number
      chave_pix_id?: string | null
    },
  ) => apiPost<Recorrencia>(`${base}/recorrencias/${id}/editar/`, dados),
  desativarRecorrencia: (id: string) => apiPost<Recorrencia>(`${base}/recorrencias/${id}/desativar/`),

  suspensoes: (opcoes: { diretor_id?: string; todas?: boolean } = {}) =>
    apiGet<Suspensao[]>(`${base}/suspensoes/${query(opcoes)}`),
  criarSuspensao: (dados: {
    diretor_id: string
    recorrencia_id: string | null
    inicio: string
    fim: string | null
    justificativa: string
  }) => apiPost<Suspensao>(`${base}/suspensoes/`, dados),
  encerrarSuspensao: (id: string) => apiPost<Suspensao>(`${base}/suspensoes/${id}/encerrar/`),

  entradas: (filtros: FiltrosEntradas = {}) =>
    apiGet<PaginaEntradas>(`${base}/entradas/${query({ ...filtros, limite: POR_PAGINA })}`),
  resumoEntradas: (filtros: Omit<FiltrosEntradas, 'situacao' | 'antes'> = {}) =>
    apiGet<ResumoEntradas>(`${base}/entradas/resumo/${query(filtros)}`),
  registrarEntrada: (dados: {
    categoria_id: string
    valor: string
    data: string
    origem: string
    evidencia_texto: string
    comprovante: File | null
  }) => {
    if (dados.comprovante) {
      const fd = new FormData()
      fd.set('categoria_id', dados.categoria_id)
      fd.set('valor', dados.valor)
      fd.set('data', dados.data)
      fd.set('origem', dados.origem)
      fd.set('evidencia_texto', dados.evidencia_texto)
      fd.set('comprovante', dados.comprovante)
      return apiPostForm<Entrada>(`${base}/entradas/`, fd)
    }
    return apiPost<Entrada>(`${base}/entradas/`, {
      categoria_id: dados.categoria_id,
      valor: dados.valor,
      data: dados.data,
      origem: dados.origem,
      evidencia_texto: dados.evidencia_texto,
    })
  },
  validarEntrada: (id: string, corpo: { motivo_id: string; texto: string }) =>
    apiPost<Entrada>(`${base}/entradas/${id}/validar/`, corpo),
  rejeitarEntrada: (id: string, corpo: { motivo_id: string; texto: string }) =>
    apiPost<Entrada>(`${base}/entradas/${id}/rejeitar/`, corpo),
}
