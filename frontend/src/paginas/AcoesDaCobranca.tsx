import { useId, useState, type FormEvent } from 'react'
import {
  TIPO_DECISAO_FINANCEIRO,
  financeiro,
  type AcaoCobranca,
  type CobrancaDetalhe,
  type DecisaoQuestionamento,
  type FormaPagamento,
} from '../api/financeiro'
import { Alerta, Campo, Selecao } from '../componentes'
import { errosPorCampo, mensagemDoErro } from '../mensagens'
import { useMotivosPorTipo } from '../useFinanceiro'
import { AreaDeTexto, SeletorDeMotivo } from './apoioFinanceiro'

const ROTULO_ACAO: Record<AcaoCobranca, string> = {
  registrar_pagamento: 'Registrar pagamento',
  validar_pagamento: 'Validar pagamento',
  rejeitar_pagamento: 'Rejeitar pagamento',
  questionar: 'Questionar',
  decidir_questionamento: 'Decidir questionamento',
  isentar: 'Isentar',
  cancelar: 'Cancelar',
  justificar_divida: 'Justificar dívida',
  perdoar: 'Perdoar',
  renegociar: 'Renegociar',
  manter_divida: 'Manter dívida',
}

interface ParcelaForm {
  id: number
  valor: string
  vencimento: string
}

function FormularioAcao({
  acao,
  cobrancaId,
  aoConcluir,
  aoFechar,
}: {
  acao: AcaoCobranca
  cobrancaId: string
  aoConcluir: (atualizada: CobrancaDetalhe) => void
  aoFechar: () => void
}) {
  const motivos = useMotivosPorTipo(TIPO_DECISAO_FINANCEIRO[acao] ?? null)
  const fileId = useId()

  const [forma, definirForma] = useState<FormaPagamento>('COMPROVANTE')
  const [dataPagamento, definirDataPagamento] = useState('')
  const [recebedorId, definirRecebedorId] = useState('')
  const [comprovante, definirComprovante] = useState<File | null>(null)

  const [motivoId, definirMotivoId] = useState('')
  const [decisaoQuest, definirDecisaoQuest] = useState<DecisaoQuestionamento>('MANTER')
  const [texto, definirTexto] = useState('')
  const [parcelas, definirParcelas] = useState<ParcelaForm[]>([{ id: 1, valor: '', vencimento: '' }])
  const [proxId, definirProxId] = useState(2)

  const [enviando, definirEnviando] = useState(false)
  const [erro, definirErro] = useState<unknown>(null)
  const campos = errosPorCampo(erro)

  async function executarAcao(): Promise<CobrancaDetalhe> {
    switch (acao) {
      case 'registrar_pagamento':
        if (forma === 'EM_MAO') {
          return financeiro.registrarPagamentoEmMao(cobrancaId, {
            data_pagamento: dataPagamento,
            recebedor_id: recebedorId,
          })
        }
        return financeiro.registrarPagamentoComComprovante(cobrancaId, {
          data_pagamento: dataPagamento,
          comprovante: comprovante as File,
        })
      case 'validar_pagamento':
        return financeiro.validarPagamento(cobrancaId, { motivo_id: motivoId, texto })
      case 'rejeitar_pagamento':
        return financeiro.rejeitarPagamento(cobrancaId, { motivo_id: motivoId, texto })
      case 'questionar':
        return financeiro.questionar(cobrancaId, texto)
      case 'decidir_questionamento':
        return financeiro.decidirQuestionamento(cobrancaId, {
          decisao: decisaoQuest,
          motivo_id: motivoId,
          texto,
        })
      case 'isentar':
        return financeiro.isentar(cobrancaId, texto)
      case 'cancelar':
        return financeiro.cancelarCobranca(cobrancaId, { motivo_id: motivoId, texto })
      case 'justificar_divida':
        return financeiro.justificarDivida(cobrancaId, texto)
      case 'perdoar':
        return financeiro.perdoarDivida(cobrancaId, { motivo_id: motivoId, texto })
      case 'manter_divida':
        return financeiro.manterDivida(cobrancaId, { motivo_id: motivoId, texto })
      case 'renegociar':
        return financeiro.renegociarDivida(cobrancaId, {
          motivo_id: motivoId,
          texto,
          parcelas: parcelas.map(({ valor, vencimento }) => ({ valor, vencimento })),
        })
    }
  }

  async function confirmar(evento: FormEvent) {
    evento.preventDefault()
    if (acao === 'registrar_pagamento' && forma === 'COMPROVANTE' && !comprovante) {
      definirErro(new Error('Anexe o comprovante do pagamento.'))
      return
    }
    definirErro(null)
    definirEnviando(true)
    try {
      const atualizada = await executarAcao()
      aoConcluir(atualizada)
    } catch (falha) {
      definirErro(falha)
    } finally {
      definirEnviando(false)
    }
  }

  const precisaMotivo = acao in TIPO_DECISAO_FINANCEIRO
  return (
    <form aria-label={ROTULO_ACAO[acao]} onSubmit={(e) => void confirmar(e)}>
      <h3>{ROTULO_ACAO[acao]}</h3>
      {acao === 'registrar_pagamento' && (
        <>
          <Selecao
            rotulo="Forma"
            value={forma}
            aoMudar={(v) => definirForma(v as FormaPagamento)}
          >
            <option value="COMPROVANTE">Comprovante</option>
            <option value="EM_MAO">Em mão</option>
          </Selecao>
          <Campo
            rotulo="Data do pagamento"
            type="date"
            value={dataPagamento}
            aoMudar={definirDataPagamento}
            erros={campos.data_pagamento}
          />
          {forma === 'COMPROVANTE' ? (
            <div className="campo">
              <label htmlFor={fileId}>Comprovante (PDF ou imagem)</label>
              <input
                id={fileId}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.webp"
                onChange={(e) => definirComprovante(e.target.files?.[0] ?? null)}
              />
            </div>
          ) : (
            <Campo
              rotulo="ID do recebedor"
              value={recebedorId}
              aoMudar={definirRecebedorId}
              erros={campos.recebedor_id}
            />
          )}
        </>
      )}

      {acao === 'decidir_questionamento' && (
        <Selecao
          rotulo="Decisão"
          value={decisaoQuest}
          aoMudar={(v) => definirDecisaoQuest(v as DecisaoQuestionamento)}
        >
          <option value="MANTER">Manter cobrança</option>
          <option value="ISENTAR">Isentar cobrança</option>
          <option value="CANCELAR">Cancelar cobrança</option>
        </Selecao>
      )}

      {precisaMotivo && (
        <SeletorDeMotivo
          motivos={motivos}
          valor={motivoId}
          aoMudar={definirMotivoId}
          erros={campos.motivo_id}
        />
      )}

      {acao === 'renegociar' && (
        <div>
          <h4>Parcelas</h4>
          {parcelas.map((p, idx) => (
            <div key={p.id}>
              <Campo
                rotulo={`Valor da parcela ${idx + 1} (R$)`}
                inputMode="decimal"
                value={p.valor}
                aoMudar={(valor) =>
                  definirParcelas((atuais) =>
                    atuais.map((item) => (item.id === p.id ? { ...item, valor } : item)),
                  )
                }
              />
              <Campo
                rotulo={`Vencimento da parcela ${idx + 1}`}
                type="date"
                value={p.vencimento}
                aoMudar={(vencimento) =>
                  definirParcelas((atuais) =>
                    atuais.map((item) => (item.id === p.id ? { ...item, vencimento } : item)),
                  )
                }
              />
            </div>
          ))}
          <button
            type="button"
            onClick={() => {
              definirParcelas((atuais) => [...atuais, { id: proxId, valor: '', vencimento: '' }])
              definirProxId((n) => n + 1)
            }}
          >
            Adicionar parcela
          </button>
        </div>
      )}

      {acao !== 'registrar_pagamento' && (
        <AreaDeTexto
          rotulo={
            acao === 'questionar' || acao === 'isentar' || acao === 'justificar_divida'
              ? 'Justificativa'
              : 'Texto (opcional)'
          }
          valor={texto}
          aoMudar={definirTexto}
          erros={campos.texto ?? campos.justificativa}
        />
      )}

      <Alerta>
        {erro instanceof Error && !(erro instanceof Object && 'code' in erro)
          ? erro.message
          : erro
            ? mensagemDoErro(erro)
            : null}
      </Alerta>
      <button type="submit" disabled={enviando}>
        Confirmar
      </button>
      <button type="button" onClick={aoFechar}>
        Fechar
      </button>
    </form>
  )
}

/** Botões de ação dirigidos por `detalhe.acoes` e seus formulários específicos. */
export function AcoesDaCobranca({
  detalhe,
  aoAtualizar,
}: {
  detalhe: CobrancaDetalhe
  aoAtualizar: (atualizada: CobrancaDetalhe) => void
}) {
  const [aberta, definirAberta] = useState<AcaoCobranca | null>(null)
  if (detalhe.acoes.length === 0) return null

  return (
    <section aria-label="Ações da cobrança">
      <h2>Ações</h2>
      {detalhe.acoes.map((acao) => (
        <button key={acao} type="button" onClick={() => definirAberta(acao)}>
          {ROTULO_ACAO[acao]}
        </button>
      ))}
      {aberta && (
        <FormularioAcao
          key={aberta}
          acao={aberta}
          cobrancaId={detalhe.id}
          aoFechar={() => definirAberta(null)}
          aoConcluir={(atualizada) => {
            definirAberta(null)
            aoAtualizar(atualizada)
          }}
        />
      )}
    </section>
  )
}
