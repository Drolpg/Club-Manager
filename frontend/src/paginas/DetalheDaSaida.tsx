import { useEffect, useId, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import { aprovacoes } from '../api/aprovacoes'
import {
  TIPO_DECISAO_FINANCEIRO,
  financeiro,
  urlComprovanteEntrada,
  urlComprovanteEnvioSaida,
  urlComprovantePrestacaoSaida,
  urlCotacao,
  type AcaoSaida,
  type HistoricoFinanceiro,
  type SaidaDetalhe,
} from '../api/financeiro'
import { Alerta, Campo, Pagina, Selecao } from '../componentes'
import { dataCurta, dataEHora, reais } from '../formatos'
import {
  SITUACAO_DA_ENTRADA,
  SITUACAO_DA_PRESTACAO,
  SITUACAO_DA_SAIDA,
  SITUACAO_DO_COMPLEMENTO,
  errosPorCampo,
  mensagemDoErro,
  rotuloDaAcaoFinanceira,
} from '../mensagens'
import { useSessao } from '../sessao'
import { useMotivosPorTipo } from '../useFinanceiro'
import { AreaDeTexto, SeletorDeMotivo } from './apoioFinanceiro'
import { BlocoEstorno, ListaDeItensEditavel, type ItemEditavel } from './apoioSaidas'

const ROTULO_ACAO_SAIDA: Record<AcaoSaida, string> = {
  enviar_recurso: 'Enviar recurso',
  prestar_contas: 'Prestar contas',
  devolver_prestacao: 'Devolver prestação',
  devolver_sobra: 'Devolver sobra',
  pedir_complemento: 'Pedir complemento',
  liquidar: 'Liquidar',
  estornar: 'Estornar',
}

function FormularioAcaoSaida({
  acao,
  detalhe,
  aoConcluir,
  aoFechar,
}: {
  acao: AcaoSaida
  detalhe: SaidaDetalhe
  aoConcluir: () => void
  aoFechar: () => void
}) {
  const motivos = useMotivosPorTipo(TIPO_DECISAO_FINANCEIRO[acao] ?? null)
  const fileId = useId()
  const complementoAprovado = detalhe.complementos.find((c) => c.situacao === 'APROVADO' && !c.envio_id)

  const [valor, definirValor] = useState('')
  const [descricao, definirDescricao] = useState('')
  const [data, definirData] = useState('')
  const [complementoId, definirComplementoId] = useState(complementoAprovado?.id ?? '')
  const [comprovante, definirComprovante] = useState<File | null>(null)
  const [motivoId, definirMotivoId] = useState('')
  const [texto, definirTexto] = useState('')
  const [itens, definirItens] = useState<ItemEditavel[]>([{ chave: 1, descricao: '', valor: '' }])
  const [enviando, definirEnviando] = useState(false)
  const [erro, definirErro] = useState<unknown>(null)
  const campos = errosPorCampo(erro)

  async function confirmar(evento: FormEvent) {
    evento.preventDefault()
    if (acao === 'enviar_recurso' && !comprovante) {
      definirErro(new Error('Anexe o comprovante do envio.'))
      return
    }
    definirErro(null)
    definirEnviando(true)
    try {
      switch (acao) {
        case 'enviar_recurso':
          await financeiro.enviarRecursoSaida(detalhe.id, {
            valor,
            complemento_id: complementoId || null,
            comprovante: comprovante as File,
          })
          break
        case 'prestar_contas':
          await financeiro.prestarContas(detalhe.id, { valor, descricao, comprovante })
          break
        case 'devolver_prestacao':
          await financeiro.devolverPrestacao(detalhe.id, { motivo_id: motivoId, texto })
          break
        case 'devolver_sobra':
          await financeiro.devolverSobra(detalhe.id, {
            valor,
            data: data || undefined,
            evidencia_texto: descricao,
            comprovante,
          })
          break
        case 'pedir_complemento':
          await financeiro.pedirComplemento(detalhe.id, {
            itens: itens.map((it) => ({ descricao: it.descricao, valor: it.valor })),
            descricao,
          })
          break
        case 'liquidar':
          await financeiro.liquidarSaida(detalhe.id, texto)
          break
        case 'estornar':
          await financeiro.estornarSaida(detalhe.id, { motivo_id: motivoId, justificativa: texto })
          break
      }
      aoConcluir()
    } catch (falha) {
      definirErro(falha)
    } finally {
      definirEnviando(false)
    }
  }

  return (
    <form aria-label={ROTULO_ACAO_SAIDA[acao]} onSubmit={(e) => void confirmar(e)}>
      <h3>{ROTULO_ACAO_SAIDA[acao]}</h3>

      {acao === 'enviar_recurso' && (
        <>
          <Campo
            rotulo="Valor enviado (R$)"
            inputMode="decimal"
            placeholder="0.00"
            value={valor}
            aoMudar={definirValor}
            erros={campos.valor}
          />
          {complementoAprovado && (
            <Selecao rotulo="Complemento" value={complementoId} aoMudar={definirComplementoId}>
              <option value={complementoAprovado.id}>
                Complemento aprovado ({reais(complementoAprovado.valor)})
              </option>
            </Selecao>
          )}
          <div className="campo">
            <label htmlFor={fileId}>Comprovante do envio (obrigatório)</label>
            <input
              id={fileId}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp"
              onChange={(e) => definirComprovante(e.target.files?.[0] ?? null)}
            />
          </div>
        </>
      )}

      {acao === 'prestar_contas' && (
        <>
          <Campo
            rotulo="Total gasto (R$)"
            inputMode="decimal"
            placeholder="0.00"
            value={valor}
            aoMudar={definirValor}
            erros={campos.valor}
          />
          <AreaDeTexto
            rotulo="Descrição / justificativa"
            valor={descricao}
            aoMudar={definirDescricao}
            erros={campos.descricao}
          />
          <div className="campo">
            <label htmlFor={fileId}>Comprovante (opcional)</label>
            <input
              id={fileId}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp"
              onChange={(e) => definirComprovante(e.target.files?.[0] ?? null)}
            />
          </div>
        </>
      )}

      {(acao === 'devolver_prestacao' || acao === 'estornar') && (
        <>
          <SeletorDeMotivo
            motivos={motivos}
            valor={motivoId}
            aoMudar={definirMotivoId}
            erros={campos.motivo_id}
          />
          <AreaDeTexto
            rotulo={acao === 'estornar' ? 'Justificativa' : 'Texto (opcional)'}
            valor={texto}
            aoMudar={definirTexto}
            erros={acao === 'estornar' ? campos.justificativa : campos.texto}
          />
        </>
      )}

      {acao === 'devolver_sobra' && (
        <>
          <Campo
            rotulo="Valor devolvido (R$)"
            inputMode="decimal"
            placeholder="0.00"
            value={valor}
            aoMudar={definirValor}
            erros={campos.valor}
          />
          <Campo rotulo="Data (opcional)" type="date" value={data} aoMudar={definirData} erros={campos.data} />
          <AreaDeTexto
            rotulo="Evidência em texto"
            valor={descricao}
            aoMudar={definirDescricao}
            erros={campos.evidencia_texto}
          />
          <div className="campo">
            <label htmlFor={fileId}>Comprovante (opcional)</label>
            <input
              id={fileId}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp"
              onChange={(e) => definirComprovante(e.target.files?.[0] ?? null)}
            />
          </div>
        </>
      )}

      {acao === 'pedir_complemento' && (
        <>
          <AreaDeTexto
            rotulo="Descrição do complemento (opcional)"
            valor={descricao}
            aoMudar={definirDescricao}
            erros={campos.descricao}
          />
          <ListaDeItensEditavel itens={itens} aoMudar={definirItens} erros={campos.itens} />
        </>
      )}

      {acao === 'liquidar' && (
        <AreaDeTexto
          rotulo="Justificativa (obrigatória se houver excesso sem reembolso)"
          valor={texto}
          aoMudar={definirTexto}
          erros={campos.justificativa}
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

/** Detalhe operacional completo de uma saída financeira e todas as ações permitidas (CA-06 a CA-33). */
export function DetalheDaSaida() {
  const { id = '' } = useParams()
  const { usuario } = useSessao()
  const [detalhe, definirDetalhe] = useState<SaidaDetalhe | null>(null)
  const [historico, definirHistorico] = useState<HistoricoFinanceiro[]>([])
  const [acaoAberta, definirAcaoAberta] = useState<AcaoSaida | null>(null)
  const [cancelandoPreEnvio, definirCancelandoPreEnvio] = useState(false)
  const [motivoCancelamento, definirMotivoCancelamento] = useState('')
  const [erro, definirErro] = useState<unknown>(null)
  const [recarga, definirRecarga] = useState(0)

  useEffect(() => {
    let vivo = true
    Promise.all([financeiro.detalheSaida(id), financeiro.historicoSaida(id)])
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

  async function cancelarPreEnvio(evento: FormEvent) {
    evento.preventDefault()
    if (!detalhe) return
    definirErro(null)
    try {
      await aprovacoes.executar(detalhe.solicitacao_id, 'cancelar', { motivo: motivoCancelamento })
      definirCancelandoPreEnvio(false)
      definirMotivoCancelamento('')
      definirRecarga((r) => r + 1)
    } catch (falha) {
      definirErro(falha)
    }
  }

  if (!detalhe) {
    return (
      <Pagina titulo="Saída">
        <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
        {!erro && <p>Carregando…</p>}
      </Pagina>
    )
  }

  const podeCancelarPreEnvio =
    detalhe.situacao === 'AGUARDANDO_ENVIO' &&
    detalhe.envios.length === 0 &&
    usuario?.id === detalhe.solicitante.id

  return (
    <Pagina titulo={detalhe.descricao}>
      <Link to="/saidas">Voltar às saídas</Link>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>

      <dl>
        <dt>Situação</dt>
        <dd>
          {SITUACAO_DA_SAIDA[detalhe.situacao] ?? detalhe.situacao}
          {detalhe.em_atraso && ' (Em atraso)'}
        </dd>
        <dt>Solicitante</dt>
        <dd>{detalhe.solicitante.nome}</dd>
        <dt>Categoria</dt>
        <dd>{detalhe.categoria_nome}</dd>
        <dt>Setor</dt>
        <dd>{detalhe.setor_nome}</dd>
        <dt>Valor aprovado total</dt>
        <dd>{reais(detalhe.valor_aprovado_total)}</dd>
        <dt>Total enviado</dt>
        <dd>{reais(detalhe.total_enviado)}</dd>
        <dt>Total gasto informado</dt>
        <dd>{reais(detalhe.total_gasto)}</dd>
        <dt>Devoluções validadas</dt>
        <dd>{reais(detalhe.total_devolvido_validado)}</dd>
        <dt>Valor não reembolsado</dt>
        <dd>{reais(detalhe.valor_nao_reembolsado)}</dd>
        <dt>Solicitação</dt>
        <dd>
          <Link to={`/solicitacoes/${detalhe.solicitacao_id}`}>Ver solicitação no motor</Link>
        </dd>
        {detalhe.cotacao?.disponivel && (
          <>
            <dt>Cotação</dt>
            <dd>
              <a href={urlCotacao(detalhe.cotacao.id)} target="_blank" rel="noopener noreferrer">
                Abrir cotação ({detalhe.cotacao.nome})
              </a>
            </dd>
          </>
        )}
      </dl>

      {(detalhe.acoes.length > 0 || podeCancelarPreEnvio) && (
        <section aria-label="Ações da saída">
          <h2>Ações</h2>
          {detalhe.acoes.map((acao) => (
            <button key={acao} type="button" onClick={() => definirAcaoAberta(acao)}>
              {ROTULO_ACAO_SAIDA[acao]}
            </button>
          ))}{' '}
          {podeCancelarPreEnvio && (
            <button type="button" onClick={() => definirCancelandoPreEnvio(true)}>
              Cancelar solicitação
            </button>
          )}
          {acaoAberta && (
            <FormularioAcaoSaida
              key={acaoAberta}
              acao={acaoAberta}
              detalhe={detalhe}
              aoFechar={() => definirAcaoAberta(null)}
              aoConcluir={() => {
                definirAcaoAberta(null)
                definirRecarga((r) => r + 1)
              }}
            />
          )}
          {cancelandoPreEnvio && (
            <form aria-label="Cancelar solicitação" onSubmit={(e) => void cancelarPreEnvio(e)}>
              <h3>Cancelar solicitação</h3>
              <AreaDeTexto
                rotulo="Motivo do cancelamento"
                valor={motivoCancelamento}
                aoMudar={definirMotivoCancelamento}
              />
              <button type="submit">Confirmar</button>
              <button type="button" onClick={() => definirCancelandoPreEnvio(false)}>
                Fechar
              </button>
            </form>
          )}
        </section>
      )}

      {detalhe.estorno && <BlocoEstorno estorno={detalhe.estorno} />}

      <section aria-label="Envios realizados">
        <h2>Envios realizados</h2>
        {detalhe.envios.length === 0 ? (
          <p>Nenhum envio registrado.</p>
        ) : (
          <ul>
            {detalhe.envios.map((e) => (
              <li key={e.id}>
                {reais(e.valor)} por {e.enviado_por.nome} em {dataEHora.format(new Date(e.enviado_em))}
                {e.comprovante_disponivel && (
                  <>
                    {' '}
                    <a
                      href={urlComprovanteEnvioSaida(detalhe.id, e.id)}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Comprovante do envio ({e.comprovante_nome})
                    </a>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-label="Prestações de contas">
        <h2>Prestações de contas</h2>
        {detalhe.prestacoes.length === 0 ? (
          <p>Nenhuma prestação registrada.</p>
        ) : (
          <ul>
            {detalhe.prestacoes.map((p) => (
              <li key={p.id}>
                {reais(p.valor)} — {SITUACAO_DA_PRESTACAO[p.situacao] ?? p.situacao} — {p.descricao}
                {p.comprovante_disponivel && (
                  <>
                    {' '}
                    <a
                      href={urlComprovantePrestacaoSaida(detalhe.id, p.id)}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Comprovante da prestação ({p.comprovante_nome})
                    </a>
                  </>
                )}
                {p.motivo_devolucao_texto && (
                  <p>
                    Devolvida: {p.motivo_devolucao_texto} {p.texto_devolucao}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {detalhe.devolucoes.length > 0 && (
        <section aria-label="Devoluções vinculadas">
          <h2>Devoluções vinculadas</h2>
          <ul>
            {detalhe.devolucoes.map((d) => (
              <li key={d.id}>
                {reais(d.valor)} em {dataCurta(d.data)} — {SITUACAO_DA_ENTRADA[d.situacao] ?? d.situacao}
                {d.comprovante_disponivel && (
                  <>
                    {' '}
                    <a href={urlComprovanteEntrada(d.id)} target="_blank" rel="noopener noreferrer">
                      Abrir comprovante
                    </a>
                  </>
                )}{' '}
                {d.situacao === 'EM_VALIDACAO' && <Link to="/entradas">Validar nas entradas</Link>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {detalhe.complementos.length > 0 && (
        <section aria-label="Complementos">
          <h2>Complementos solicitados</h2>
          <ul>
            {detalhe.complementos.map((c) => (
              <li key={c.id}>
                {reais(c.valor)} — {SITUACAO_DO_COMPLEMENTO[c.situacao] ?? c.situacao} (
                <Link to={`/solicitacoes/${c.solicitacao_id}`}>Ver solicitação</Link>)
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-label="Histórico">
        <h2>Histórico</h2>
        <ul>
          {historico.map((h) => (
            <li key={`${h.acao}-${h.criado_em}`}>
              {rotuloDaAcaoFinanceira(h.acao)} — {h.ator?.nome ?? 'Sistema'}{' '}
              {h.justificativa ? `: ${h.justificativa} ` : ''}(
              {dataEHora.format(new Date(h.criado_em))})
            </li>
          ))}
        </ul>
      </section>
    </Pagina>
  )
}
