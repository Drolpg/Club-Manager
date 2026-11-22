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
  | 'ESTORNADA'
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
  | 'estornar'
export type FormaPagamento = 'COMPROVANTE' | 'EM_MAO'
export type SituacaoPagamento = 'EM_VALIDACAO' | 'VALIDADO' | 'REJEITADO'
export type Periodicidade = 'MENSAL' | 'SEMANAL' | 'ANUAL'
export type SituacaoSuspensao = 'VIGENTE' | 'ENCERRADA'
export type SituacaoEntrada = 'EM_VALIDACAO' | 'VALIDADA' | 'REJEITADA' | 'ESTORNADA'
export type AcaoEntrada = 'validar' | 'rejeitar' | 'estornar'
export type DecisaoQuestionamento = 'ISENTAR' | 'CANCELAR' | 'MANTER'
export type SituacaoSaida =
  | 'AGUARDANDO_ENVIO'
  | 'RECURSO_ENVIADO'
  | 'EM_CONFERENCIA'
  | 'LIQUIDADA'
  | 'CANCELADA'
  | 'ESTORNADA'
export type AcaoSaida =
  | 'enviar_recurso'
  | 'prestar_contas'
  | 'devolver_prestacao'
  | 'devolver_sobra'
  | 'pedir_complemento'
  | 'liquidar'
  | 'estornar'
export type AlvoEstorno = 'SAIDA' | 'ENTRADA' | 'COBRANCA'

export interface EstornoResumo {
  id: string
  valor: string
  motivo_texto: string
  justificativa: string
  registrado_por: PessoaFinanceira
  registrado_em: string
}

export interface EstornoItem extends EstornoResumo {
  alvo_tipo: AlvoEstorno
  alvo_id: string
  motivo_id: string
}

export interface PaginaEstornos {
  itens: EstornoItem[]
  tem_mais: boolean
}

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
  estorno?: EstornoResumo | null
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
  tipo: 'SEM_DEVEDOR' | 'DEVOLUCAO'
  categoria_id: string
  categoria_nome: string
  saida_id?: string | null
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
  estorno?: EstornoResumo | null
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

export type TipoDeLancamento = 'COBRANCA' | 'ENTRADA' | 'SAIDA' | 'ESTORNO'
export type EstadoDoLancamento =
  | 'EM_ABERTO'
  | 'EM_VALIDACAO'
  | 'REALIZADO'
  | 'ENCERRADO_SEM_VALOR'
  | 'ESTORNADO'

/** Um item da lista de lançamentos (RF-104). Valores em texto; o estorno vem com sinal negativo. */
export interface Lancamento {
  tipo: TipoDeLancamento
  subtipo: string | null
  id: string
  data_referencia: string
  descricao: string
  categoria: ReferenciaItem
  contraparte: string
  valor: string
  valor_realizado: string | null
  estado: EstadoDoLancamento
  situacao: string
  realizado_em: string | null
  original: { tipo: TipoDeLancamento; id: string } | null
}

export interface FiltrosLancamentos {
  de?: string
  ate?: string
  tipo?: TipoDeLancamento
  estado?: EstadoDoLancamento
  categoria_id?: string
  antes?: string
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

export interface VisaoDoCaixa {
  total_entradas_validadas: string
  total_saidas_liquidadas: string
  total_comprometido: string
}

export interface ReferenciaItem {
  id: string
  nome: string
}

export interface ReferenciasGastos {
  categorias_saida: ReferenciaItem[]
  categorias_entrada: ReferenciaItem[]
  setores: ReferenciaItem[]
  aprovadores_gastos: PessoaFinanceira[]
  diretores_ativos: PessoaFinanceira[]
}

export interface Cotacao {
  id: string
  nome: string
  mime: string
  tamanho: number
  criada_em: string
}

export interface ItemDeGasto {
  descricao: string
  valor: string
}

export interface ConteudoGasto {
  descricao: string
  categoria_id: string
  categoria_nome: string
  setor_id: string
  setor_nome: string
  itens: ItemDeGasto[]
  cotacao_id: string | null
  cotacao_nome: string
  saida_origem_id: string | null
  evento_id: string | null
}

export function isConteudoGasto(valor: unknown): valor is ConteudoGasto {
  if (typeof valor !== 'object' || valor === null) return false
  const reg = valor as Record<string, unknown>
  return typeof reg.descricao === 'string' && Array.isArray(reg.itens) && typeof reg.categoria_id === 'string'
}

export interface SolicitacaoGastoCriada {
  id: string
  tipo: string
  situacao: string
  solicitante_id: string
  aprovador_indicado_id: string | null
  versao_atual: number
  valor: string | null
  resumo: string
  conteudo: ConteudoGasto
}

export interface FiltrosSaidas {
  situacao?: string
  categoria_id?: string
  setor_id?: string
  solicitante_id?: string
  de?: string
  ate?: string
  pendentes_envio?: boolean
  pendentes_prestacao?: boolean
  atrasadas?: boolean
  antes?: string
}

export interface SaidaItem {
  id: string
  solicitacao_id: string
  versao_aprovada: number
  solicitante: PessoaFinanceira
  categoria_id: string
  categoria_nome: string
  setor_id: string
  setor_nome: string
  evento_id: string | null
  descricao: string
  valor_aprovado: string
  valor_aprovado_total: string
  total_enviado: string
  total_gasto: string | null
  total_devolvido_validado: string
  total_devolvido_pendente: string
  valor_nao_reembolsado: string
  situacao: SituacaoSaida
  em_atraso: boolean
  tem_complemento_aprovado_para_enviar: boolean
  tem_complemento_em_andamento: boolean
  primeiro_envio_em: string | null
  criada_em: string
  atualizada_em: string
}

export interface PaginaSaidas {
  itens: SaidaItem[]
  tem_mais: boolean
}

export interface CotacaoResumo {
  id: string
  nome: string
  disponivel: boolean
}

export interface EnvioSaida {
  id: string
  valor: string
  complemento_id: string | null
  enviado_por: PessoaFinanceira
  enviado_em: string
  comprovante_disponivel: boolean
  comprovante_nome: string
}

export interface PrestacaoSaida {
  id: string
  valor: string
  descricao: string
  registrada_por: PessoaFinanceira
  registrada_em: string
  situacao: 'VIGENTE' | 'DEVOLVIDA'
  comprovante_disponivel: boolean
  comprovante_nome: string
  devolvida_por: PessoaFinanceira | null
  motivo_devolucao_texto: string
  texto_devolucao: string
  devolvida_em: string | null
}

export interface DevolucaoSaida {
  id: string
  valor: string
  data: string
  origem: string
  evidencia_texto: string
  situacao: SituacaoEntrada
  registrada_por: PessoaFinanceira
  registrada_em: string
  decidido_por: PessoaFinanceira | null
  motivo_texto: string
  decisao_texto: string
  decidido_em: string | null
  comprovante_disponivel: boolean
  comprovante_nome: string
}

export interface ComplementoSaida {
  id: string
  solicitacao_id: string
  valor: string
  situacao: string
  aprovado_em: string | null
  decidido_em: string | null
  criado_em: string
  envio_id: string | null
}

export interface SaidaDetalhe extends SaidaItem {
  itens: ItemDeGasto[]
  liquidacao_justificativa: string
  liquidada_por: PessoaFinanceira | null
  liquidada_em: string | null
  cancelada_em: string | null
  cotacao: CotacaoResumo | null
  envios: EnvioSaida[]
  prestacoes: PrestacaoSaida[]
  devolucoes: DevolucaoSaida[]
  complementos: ComplementoSaida[]
  estorno: EstornoResumo | null
  acoes: AcaoSaida[]
}

export interface ComplementoCriado {
  id: string
  saida_id: string
  solicitacao_id: string
  valor: string
  situacao: string
}

export interface EstornoSaidaResposta extends EstornoItem {
  registro: SaidaDetalhe
}

export interface EstornoEntradaResposta extends EstornoItem {
  registro: Entrada
}

export interface EstornoCobrancaResposta extends EstornoItem {
  registro: CobrancaDetalhe
}

export const PERM_COBRANCAS_CRIAR = 'financeiro.cobrancas.criar'
export const PERM_COBRANCAS_SUSPENDER = 'financeiro.cobrancas.suspender'
export const PERM_ENTRADAS_REGISTRAR = 'financeiro.entradas.registrar'
export const PERM_GASTOS_APROVAR = 'gastos.aprovar'
export const PERM_SAIDAS_ENVIAR = 'saidas.enviar'
export const PERM_SAIDAS_LIQUIDAR = 'saidas.liquidar'
export const PERM_FINANCEIRO_ESTORNAR = 'financeiro.estornar'

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
  devolver_prestacao: 'financeiro.prestacao_devolver',
  estornar: 'financeiro.estornar',
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

export function urlCotacao(cotacaoId: string): string {
  return `/api/v1${base}/cotacoes/${cotacaoId}/`
}

export function urlComprovanteEnvioSaida(saidaId: string, envioId: string): string {
  return `/api/v1${base}/saidas/${saidaId}/envios/${envioId}/comprovante/`
}

export function urlComprovantePrestacaoSaida(saidaId: string, prestacaoId: string): string {
  return `/api/v1${base}/saidas/${saidaId}/prestacoes/${prestacaoId}/comprovante/`
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

  lancamentos: (filtros: FiltrosLancamentos = {}) =>
    apiGet<{ itens: Lancamento[]; tem_mais: boolean }>(`${base}/lancamentos/${query({ ...filtros })}`),
  entrada: (id: string) => apiGet<Entrada>(`${base}/entradas/${id}/`),
  historicoEntrada: (id: string) => apiGet<HistoricoFinanceiro[]>(`${base}/entradas/${id}/historico/`),
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

  caixa: () => apiGet<VisaoDoCaixa>(`${base}/caixa/`),
  referenciasGastos: () => apiGet<ReferenciasGastos>(`${base}/referencias-gastos/`),
  enviarCotacao: (arquivo: File) => {
    const fd = new FormData()
    fd.set('arquivo', arquivo)
    return apiPostForm<Cotacao>(`${base}/cotacoes/`, fd)
  },
  abrirGasto: (dados: {
    descricao: string
    categoria_id: string
    setor_id: string
    itens: ItemDeGasto[]
    cotacao_id?: string | null
    aprovador_indicado_id?: string | null
  }) => apiPost<SolicitacaoGastoCriada>(`${base}/gastos/`, dados),

  saidas: (filtros: FiltrosSaidas = {}) =>
    apiGet<PaginaSaidas>(`${base}/saidas/${query({ ...filtros, limite: POR_PAGINA })}`),
  detalheSaida: (id: string) => apiGet<SaidaDetalhe>(`${base}/saidas/${id}/`),
  historicoSaida: (id: string) => apiGet<HistoricoFinanceiro[]>(`${base}/saidas/${id}/historico/`),
  enviarRecursoSaida: (
    id: string,
    dados: { valor: string; enviado_em?: string; complemento_id?: string | null; comprovante: File },
  ) => {
    const fd = new FormData()
    fd.set('valor', dados.valor)
    if (dados.enviado_em) fd.set('enviado_em', dados.enviado_em)
    if (dados.complemento_id) fd.set('complemento_id', dados.complemento_id)
    fd.set('comprovante', dados.comprovante)
    return apiPostForm<SaidaDetalhe>(`${base}/saidas/${id}/envios/`, fd)
  },
  prestarContas: (id: string, dados: { valor: string; descricao: string; comprovante?: File | null }) => {
    if (dados.comprovante) {
      const fd = new FormData()
      fd.set('valor', dados.valor)
      fd.set('descricao', dados.descricao)
      fd.set('comprovante', dados.comprovante)
      return apiPostForm<SaidaDetalhe>(`${base}/saidas/${id}/prestacoes/`, fd)
    }
    return apiPost<SaidaDetalhe>(`${base}/saidas/${id}/prestacoes/`, {
      valor: dados.valor,
      descricao: dados.descricao,
    })
  },
  devolverPrestacao: (id: string, corpo: { motivo_id: string; texto: string }) =>
    apiPost<SaidaDetalhe>(`${base}/saidas/${id}/devolver-prestacao/`, corpo),
  devolverSobra: (
    id: string,
    dados: { valor: string; data?: string; evidencia_texto?: string; comprovante?: File | null },
  ) => {
    if (dados.comprovante) {
      const fd = new FormData()
      fd.set('valor', dados.valor)
      if (dados.data) fd.set('data', dados.data)
      if (dados.evidencia_texto) fd.set('evidencia_texto', dados.evidencia_texto)
      fd.set('comprovante', dados.comprovante)
      return apiPostForm<Entrada>(`${base}/saidas/${id}/devolucoes/`, fd)
    }
    return apiPost<Entrada>(`${base}/saidas/${id}/devolucoes/`, {
      valor: dados.valor,
      ...(dados.data ? { data: dados.data } : {}),
      ...(dados.evidencia_texto ? { evidencia_texto: dados.evidencia_texto } : {}),
    })
  },
  pedirComplemento: (
    id: string,
    dados: {
      itens: ItemDeGasto[]
      descricao?: string
      cotacao_id?: string | null
      aprovador_indicado_id?: string | null
    },
  ) => apiPost<ComplementoCriado>(`${base}/saidas/${id}/complementos/`, dados),
  liquidarSaida: (id: string, justificativa = '') =>
    apiPost<SaidaDetalhe>(`${base}/saidas/${id}/liquidar/`, { justificativa }),

  estornarSaida: (id: string, corpo: { motivo_id: string; justificativa: string }) =>
    apiPost<EstornoSaidaResposta>(`${base}/saidas/${id}/estornar/`, corpo),
  estornarEntrada: (id: string, corpo: { motivo_id: string; justificativa: string }) =>
    apiPost<EstornoEntradaResposta>(`${base}/entradas/${id}/estornar/`, corpo),
  estornarCobranca: (id: string, corpo: { motivo_id: string; justificativa: string }) =>
    apiPost<EstornoCobrancaResposta>(`${base}/cobrancas/${id}/estornar/`, corpo),
  estornos: (opcoes: { alvo_tipo?: string; antes?: string } = {}) =>
    apiGet<PaginaEstornos>(`${base}/estornos/${query({ ...opcoes, limite: POR_PAGINA })}`),
}
