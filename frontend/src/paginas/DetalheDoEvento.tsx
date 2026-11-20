import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import { aprovacoes, type DetalheDaSolicitacao } from '../api/aprovacoes'
import {
  eventos,
  type DetalheDoEvento,
  type Pessoa,
  type RegistroDoHistorico,
  type Resposta,
  type SaidaDoEvento,
} from '../api/eventos'
import { Alerta, Campo, Pagina } from '../componentes'
import { dataCurta, dataEHora, reais } from '../formatos'
import {
  SITUACAO_DA_SAIDA,
  SITUACAO_DA_SOLICITACAO,
  SITUACAO_DO_EVENTO,
  errosPorCampo,
  mensagemDoErro,
  rotuloDaAcaoNoEvento,
} from '../mensagens'
import { OrcamentoDoEvento } from './OrcamentoDoEvento'

function nomes(pessoas: Pessoa[]): string {
  return pessoas.length ? pessoas.map((p) => p.nome).join(', ') : 'ninguém'
}

/** As decisões e os motivos vêm da rota do motor; o site não repete a regra (spec técnica do M8, CA-12). */
function Solicitacao({ titulo, id }: { titulo: string; id: string }) {
  const [detalhe, definirDetalhe] = useState<DetalheDaSolicitacao | null>(null)

  useEffect(() => {
    aprovacoes
      .detalhe(id)
      .then(definirDetalhe)
      .catch(() => undefined)
  }, [id])

  return (
    <section aria-label={titulo}>
      <h2>{titulo}</h2>
      {detalhe && (
        <>
          <p>
            {SITUACAO_DA_SOLICITACAO[detalhe.situacao] ?? detalhe.situacao} ·{' '}
            <Link to={`/solicitacoes/${id}`}>Ver a solicitação</Link>
          </p>
          <ul className="lista">
            {detalhe.versoes
              .filter((versao) => versao.decisao)
              .map((versao) => (
                <li key={versao.numero}>
                  Versão {versao.numero}: {versao.decisao?.tipo.toLowerCase()} por {versao.decisao?.aprovador.nome} —{' '}
                  {versao.decisao?.motivo_texto}
                  {versao.decisao?.mensagem ? `. ${versao.decisao.mensagem}` : ''}
                </li>
              ))}
          </ul>
        </>
      )}
    </section>
  )
}

function Saida({ eventoId }: { eventoId: string }) {
  const [saidas, definirSaidas] = useState<SaidaDoEvento[]>([])

  useEffect(() => {
    eventos
      .saidas(eventoId)
      .then((pagina) => definirSaidas(pagina.itens))
      .catch(() => undefined)
  }, [eventoId])

  return (
    <ul className="lista">
      {saidas.map((saida) => (
        <li key={saida.id}>
          Saída {SITUACAO_DA_SAIDA[saida.situacao] ?? saida.situacao}: aprovado {reais(saida.valor_aprovado)}, enviado{' '}
          {reais(saida.total_enviado)} · <Link to={`/saidas/${saida.id}`}>Ver a saída</Link>
        </li>
      ))}
    </ul>
  )
}

function FormularioComTexto({
  titulo,
  rotulo,
  campo,
  aoEnviar,
  extra,
}: {
  titulo: string
  rotulo: string
  campo: string
  aoEnviar: (texto: string, data: string) => Promise<void>
  extra?: { rotulo: string }
}) {
  const [texto, definirTexto] = useState('')
  const [data, definirData] = useState('')
  const [erro, definirErro] = useState<unknown>(null)
  const campos = errosPorCampo(erro)

  async function enviar(formulario: FormEvent) {
    formulario.preventDefault()
    definirErro(null)
    try {
      await aoEnviar(texto, data)
    } catch (e) {
      definirErro(e)
    }
  }

  return (
    <form aria-label={titulo} onSubmit={(formulario) => void enviar(formulario)}>
      <h3>{titulo}</h3>
      {extra && <Campo rotulo={extra.rotulo} type="date" value={data} aoMudar={definirData} />}
      <Campo rotulo={rotulo} value={texto} erros={campos[campo]} aoMudar={definirTexto} />
      <Alerta>{erro && !Object.keys(campos).length ? mensagemDoErro(erro) : null}</Alerta>
      <button type="submit">{titulo}</button>
    </form>
  )
}

/** CA-12: dados, proponente, solicitações com decisões e motivos, orçamento, presenças e histórico. As ações
 * são só as que vierem em `acoes`; a API confere de novo cada uma. */
export function DetalheDoEvento() {
  const { id = '' } = useParams()
  const [evento, definirEvento] = useState<DetalheDoEvento | null>(null)
  const [registros, definirRegistros] = useState<RegistroDoHistorico[]>([])
  const [erro, definirErro] = useState<unknown>(null)
  const [versao, definirVersao] = useState(0)

  useEffect(() => {
    let vivo = true
    eventos
      .detalhe(id)
      .then((dados) => vivo && definirEvento(dados))
      .catch((e: unknown) => vivo && definirErro(e))
    eventos
      .registros(id)
      .then((dados) => vivo && definirRegistros(dados))
      .catch(() => undefined)
    return () => {
      vivo = false
    }
  }, [id, versao])

  if (!evento) return <Pagina titulo="Evento">{erro ? <Alerta>{mensagemDoErro(erro)}</Alerta> : <p>Carregando…</p>}</Pagina>

  const pode = (acao: string) => evento.acoes.includes(acao as never)
  const atualizar = (novo: DetalheDoEvento) => {
    definirEvento(novo)
    definirVersao(versao + 1)
  }

  async function responder(resposta: Resposta) {
    try {
      const presencas = await eventos.responder(id, resposta)
      if (evento) definirEvento({ ...evento, presencas })
    } catch (e) {
      definirErro(e)
    }
  }

  return (
    <Pagina titulo={evento.titulo}>
      <p>
        {SITUACAO_DO_EVENTO[evento.situacao] ?? evento.situacao} · {dataCurta(evento.inicio.slice(0, 10))} às{' '}
        {evento.inicio.slice(11, 16)} · {evento.local} · {evento.categoria_nome}
        {evento.envolve_custo ? ' · envolve custo' : ''}
      </p>
      {evento.descricao && <p>{evento.descricao}</p>}
      <p>Proposto por {evento.proponente.nome}</p>
      {evento.realizacao && (
        <p>
          Realizado em {dataCurta(evento.realizacao.data)} por {evento.realizacao.por?.nome ?? 'o sistema'}
          {evento.realizacao.motivo ? ` — ${evento.realizacao.motivo}` : ''}
        </p>
      )}
      {evento.cancelamento && (
        <p>
          Cancelado {evento.cancelamento.pelo_sistema ? 'pelo sistema' : `por ${evento.cancelamento.por?.nome ?? ''}`}:{' '}
          {evento.cancelamento.motivo}
        </p>
      )}
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {pode('editar') && <Link to={`/eventos/${evento.id}/editar`}>Editar evento</Link>}

      <Solicitacao titulo="Solicitação do evento" id={evento.solicitacao_do_evento.id} />
      {evento.orcamento && (
        <>
          <Solicitacao titulo="Orçamento" id={evento.orcamento.solicitacao_id} />
          <Saida eventoId={evento.id} />
        </>
      )}
      {pode('vincular_orcamento') && <OrcamentoDoEvento evento={evento} aoConcluir={atualizar} />}

      <section aria-label="Presenças">
        <h2>Presenças</h2>
        <p>Vão: {nomes(evento.presencas.vou)}</p>
        <p>Não vão: {nomes(evento.presencas.nao_vou)}</p>
        <p>Não responderam: {nomes(evento.presencas.sem_resposta)}</p>
        {pode('responder_presenca') && (
          <p>
            <button type="button" aria-pressed={evento.presencas.minha === 'VOU'} onClick={() => void responder('VOU')}>
              Vou
            </button>{' '}
            <button
              type="button"
              aria-pressed={evento.presencas.minha === 'NAO_VOU'}
              onClick={() => void responder('NAO_VOU')}
            >
              Não vou
            </button>
          </p>
        )}
      </section>

      {pode('reabrir') && (
        <FormularioComTexto
          titulo="Reabrir evento"
          rotulo="Justificativa"
          campo="justificativa"
          aoEnviar={async (texto) => atualizar(await eventos.reabrir(id, texto))}
        />
      )}
      {pode('confirmar_realizacao') && (
        <FormularioComTexto
          titulo="Confirmar realização"
          rotulo="Motivo da data diferente"
          campo="motivo"
          extra={{ rotulo: 'Data em que aconteceu' }}
          aoEnviar={async (texto, data) => atualizar(await eventos.realizar(id, data || null, texto))}
        />
      )}
      {pode('cancelar') && (
        <FormularioComTexto
          titulo="Cancelar evento"
          rotulo="Motivo do cancelamento"
          campo="motivo"
          aoEnviar={async (texto) => atualizar(await eventos.cancelar(id, texto))}
        />
      )}

      <section aria-label="Histórico">
        <h2>Histórico</h2>
        <ul className="lista">
          {registros.map((registro, indice) => (
            <li key={`${registro.criado_em}-${indice}`}>
              {dataEHora.format(new Date(registro.criado_em))} · {rotuloDaAcaoNoEvento(registro.acao)} ·{' '}
              {registro.ator?.nome ?? 'o sistema'}
              {registro.justificativa ? ` — ${registro.justificativa}` : ''}
            </li>
          ))}
        </ul>
      </section>
    </Pagina>
  )
}
