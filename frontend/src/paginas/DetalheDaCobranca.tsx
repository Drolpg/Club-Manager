import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import {
  financeiro,
  urlComprovanteCobranca,
  urlReciboCobranca,
  type CobrancaDetalhe,
  type HistoricoFinanceiro,
} from '../api/financeiro'
import { Alerta, Pagina } from '../componentes'
import { dataCurta, dataEHora, reais } from '../formatos'
import {
  SITUACAO_DA_COBRANCA,
  SITUACAO_DO_PAGAMENTO,
  mensagemDoErro,
  rotuloDaAcaoFinanceira,
} from '../mensagens'
import { AcoesDaCobranca } from './AcoesDaCobranca'
import { QrCodePix } from './QrCodePix'

/** Detalhe da cobrança: Pix copia e cola, QR Code SVG seguro, comprovantes, recibo e ações. */
export function DetalheDaCobranca() {
  const { id = '' } = useParams()
  const [detalhe, definirDetalhe] = useState<CobrancaDetalhe | null>(null)
  const [historico, definirHistorico] = useState<HistoricoFinanceiro[]>([])
  const [copiado, definirCopiado] = useState(false)
  const [erro, definirErro] = useState<unknown>(null)
  const [recarga, definirRecarga] = useState(0)

  useEffect(() => {
    let vivo = true
    Promise.all([financeiro.detalheCobranca(id), financeiro.historicoCobranca(id)])
      .then(([enc, hist]) => {
        if (!vivo) return
        definirDetalhe(enc)
        definirHistorico(hist)
        definirErro(null)
      })
      .catch((falha) => vivo && definirErro(falha))
    return () => {
      vivo = false
    }
  }, [id, recarga])

  async function copiarPix(codigo: string) {
    await navigator.clipboard?.writeText(codigo)
    definirCopiado(true)
  }

  if (!detalhe) {
    return (
      <Pagina titulo="Cobrança">
        <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
        {!erro && <p>Carregando…</p>}
      </Pagina>
    )
  }

  return (
    <Pagina titulo={detalhe.descricao}>
      <Link to="/minhas-cobrancas">Voltar às minhas cobranças</Link>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>

      <dl>
        <dt>Situação</dt>
        <dd>{SITUACAO_DA_COBRANCA[detalhe.situacao] ?? detalhe.situacao}</dd>
        <dt>Devedor</dt>
        <dd>{detalhe.devedor.nome}</dd>
        <dt>Categoria</dt>
        <dd>{detalhe.categoria_nome}</dd>
        <dt>Valor</dt>
        <dd>{reais(detalhe.valor)}</dd>
        <dt>Vencimento</dt>
        <dd>{dataCurta(detalhe.vencimento)}</dd>
      </dl>

      {detalhe.situacao === 'PAGA' && (
        <p>
          <a href={urlReciboCobranca(detalhe.id)} target="_blank" rel="noopener noreferrer">
            Baixar recibo (PDF)
          </a>
        </p>
      )}

      <section aria-label="Pagamento via Pix">
        <h2>Pix</h2>
        <p>
          Chave {detalhe.pix_chave} — {detalhe.pix_nome_recebedor} ({detalhe.pix_cidade})
        </p>
        <QrCodePix svg={detalhe.qrcode_svg} />
        <div>
          <input
            readOnly
            aria-label="Pix copia e cola"
            value={detalhe.pix_copia_e_cola}
            onFocus={(e) => e.target.select()}
          />
          <button type="button" onClick={() => void copiarPix(detalhe.pix_copia_e_cola)}>
            Copiar código Pix
          </button>
          {copiado && <span role="status">Código Pix copiado.</span>}
        </div>
      </section>

      <AcoesDaCobranca
        detalhe={detalhe}
        aoAtualizar={(atualizada) => {
          definirDetalhe(atualizada)
          definirRecarga((r) => r + 1)
        }}
      />

      {detalhe.pagamentos.length > 0 && (
        <section aria-label="Pagamentos">
          <h2>Pagamentos</h2>
          <ul>
            {detalhe.pagamentos.map((p) => (
              <li key={p.id}>
                <span>
                  {p.forma === 'EM_MAO' ? 'Em mão' : 'Comprovante'} em {dataCurta(p.data_pagamento)} —{' '}
                  {SITUACAO_DO_PAGAMENTO[p.situacao] ?? p.situacao}
                </span>
                {p.recebedor && <span> (Recebedor: {p.recebedor.nome})</span>}
                {p.comprovante_disponivel && (
                  <>
                    {' '}
                    <a
                      href={urlComprovanteCobranca(detalhe.id, p.id)}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Abrir comprovante
                    </a>
                  </>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {detalhe.questionamentos.length > 0 && (
        <section aria-label="Questionamentos">
          <h2>Questionamentos</h2>
          <ul>
            {detalhe.questionamentos.map((q) => (
              <li key={q.id}>
                <p>{q.texto}</p>
                <p>
                  {q.situacao}
                  {q.motivo_texto ? ` — ${q.motivo_texto}` : ''}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {detalhe.convocacao && (
        <section aria-label="Convocação">
          <h2>Convocação de inadimplência</h2>
          <p>Convocado em {dataEHora.format(new Date(detalhe.convocacao.convocado_em))}</p>
          {detalhe.convocacao.justificativa_do_devedor && (
            <p>Justificativa: {detalhe.convocacao.justificativa_do_devedor}</p>
          )}
        </section>
      )}

      {detalhe.renegociacao && (
        <section aria-label="Renegociação">
          <h2>Renegociação</h2>
          <p>
            Valor acordado: {reais(detalhe.renegociacao.valor_acordado)} em{' '}
            {detalhe.renegociacao.quantidade_parcelas} parcela(s)
          </p>
        </section>
      )}

      <section aria-label="Histórico">
        <h2>Histórico</h2>
        <ul>
          {historico.map((h) => (
            <li key={`${h.acao}-${h.criado_em}`}>
              {rotuloDaAcaoFinanceira(h.acao)} — {h.ator?.nome ?? 'Sistema'} (
              {dataEHora.format(new Date(h.criado_em))})
            </li>
          ))}
        </ul>
      </section>
    </Pagina>
  )
}
