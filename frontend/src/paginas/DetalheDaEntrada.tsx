import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { financeiro, urlComprovanteEntrada, type Entrada, type HistoricoFinanceiro } from '../api/financeiro'
import { Alerta, Pagina } from '../componentes'
import { dataCurta, dataEHora, reais } from '../formatos'
import { SITUACAO_DA_ENTRADA, mensagemDoErro, rotuloDaAcaoFinanceira } from '../mensagens'
import { BlocoEstorno } from './apoioSaidas'

/**
 * O detalhe de uma entrada, só de leitura (D9): os dados, o comprovante para quem pode vê-lo e o histórico. É
 * o destino da lista de lançamentos; validar, rejeitar e estornar continuam na tela de entradas. A regra de
 * quem vê o comprovante é da API: o link só aparece quando ela diz que o comprovante está disponível.
 */
export function DetalheDaEntrada() {
  const { id = '' } = useParams()
  const [entrada, definirEntrada] = useState<Entrada | null>(null)
  const [historico, definirHistorico] = useState<HistoricoFinanceiro[]>([])
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    let vivo = true
    Promise.all([financeiro.entrada(id), financeiro.historicoEntrada(id)])
      .then(([dados, registros]) => {
        if (!vivo) return
        definirEntrada(dados)
        definirHistorico(registros)
      })
      .catch((falha) => vivo && definirErro(falha))
    return () => {
      vivo = false
    }
  }, [id])

  if (erro) {
    return (
      <Pagina titulo="Entrada">
        <Alerta>{mensagemDoErro(erro)}</Alerta>
      </Pagina>
    )
  }
  if (!entrada) return <p className="pagina">Carregando…</p>

  return (
    <Pagina titulo={entrada.tipo === 'DEVOLUCAO' ? 'Entrada: devolução' : 'Entrada'}>
      <dl>
        <dt>Origem</dt>
        <dd>{entrada.origem}</dd>
        <dt>Categoria</dt>
        <dd>{entrada.categoria_nome}</dd>
        <dt>Valor</dt>
        <dd>{reais(entrada.valor)}</dd>
        <dt>Data</dt>
        <dd>{dataCurta(entrada.data)}</dd>
        <dt>Situação</dt>
        <dd>{SITUACAO_DA_ENTRADA[entrada.situacao] ?? entrada.situacao}</dd>
        <dt>Evidência</dt>
        <dd>{entrada.evidencia_texto || '—'}</dd>
        <dt>Registrada por</dt>
        <dd>
          {entrada.registrada_por.nome} ({dataEHora.format(new Date(entrada.registrada_em))})
        </dd>
        {entrada.decidido_por && entrada.decidido_em && (
          <>
            <dt>Decidida por</dt>
            <dd>
              {entrada.decidido_por.nome} ({dataEHora.format(new Date(entrada.decidido_em))}) —{' '}
              {entrada.motivo_texto}
            </dd>
          </>
        )}
      </dl>
      {entrada.saida_id && (
        <p>
          <Link to={`/saidas/${entrada.saida_id}`}>Ver a saída de origem</Link>
        </p>
      )}
      {entrada.comprovante_disponivel && (
        <p>
          <a href={urlComprovanteEntrada(entrada.id)}>Comprovante: {entrada.comprovante_nome}</a>
        </p>
      )}
      {entrada.estorno && <BlocoEstorno estorno={entrada.estorno} />}

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
