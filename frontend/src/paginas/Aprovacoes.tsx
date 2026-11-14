import { Fragment, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import {
  aprovacoes,
  type DetalheDaSolicitacao,
  type ItemDaLista,
  type RegistroDoHistorico,
  type TipoDeSolicitacao,
  type Versao,
} from '../api/aprovacoes'
import { Alerta, Pagina, Selecao } from '../componentes'
import { dataEHora, reais } from '../formatos'
import {
  DECISAO_DA_SOLICITACAO,
  SITUACAO_DA_SOLICITACAO,
  mensagemDoErro,
  rotuloDaAcaoNaSolicitacao,
} from '../mensagens'

function quando(texto: string): string {
  return dataEHora.format(new Date(texto))
}

function LinkDaSolicitacao({ item }: { item: ItemDaLista }) {
  return <Link to={`/solicitacoes/${item.id}`}>{item.resumo}</Link>
}

interface Filtros {
  tipo: string
  situacao: string
  minhas: boolean
}

/** Todas as solicitações, da mais recente para a mais antiga, com filtros (CA-27). */
export function ListaDeSolicitacoes() {
  const [filtros, definirFiltros] = useState<Filtros>({ tipo: '', situacao: '', minhas: false })
  const [tipos, definirTipos] = useState<TipoDeSolicitacao[]>([])
  const [itens, definirItens] = useState<ItemDaLista[]>([])
  const [temMais, definirTemMais] = useState(false)
  const [carregada, definirCarregada] = useState(false)
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    aprovacoes
      .tipos()
      .then(definirTipos)
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    let vivo = true
    aprovacoes
      .lista(filtros)
      .then((pagina) => {
        if (!vivo) return
        definirItens(pagina.itens)
        definirTemMais(pagina.tem_mais)
        definirErro(null)
        definirCarregada(true)
      })
      .catch((falha) => vivo && definirErro(falha))
    return () => {
      vivo = false
    }
  }, [filtros])

  async function carregarMais() {
    const ultima = itens.at(-1)
    if (!ultima) return
    try {
      const pagina = await aprovacoes.lista({ ...filtros, antes: ultima.id })
      definirItens((atuais) => [...atuais, ...pagina.itens])
      definirTemMais(pagina.tem_mais)
    } catch (falha) {
      definirErro(falha)
    }
  }

  return (
    <Pagina titulo="Solicitações">
      <form aria-label="Filtros" onSubmit={(evento) => evento.preventDefault()}>
        <Selecao rotulo="Tipo" value={filtros.tipo} aoMudar={(tipo) => definirFiltros({ ...filtros, tipo })}>
          <option value="">Todos</option>
          {tipos.map((tipo) => (
            <option key={tipo.codigo} value={tipo.codigo}>
              {tipo.nome}
            </option>
          ))}
        </Selecao>
        <Selecao
          rotulo="Situação"
          value={filtros.situacao}
          aoMudar={(situacao) => definirFiltros({ ...filtros, situacao })}
        >
          <option value="">Todas</option>
          {Object.entries(SITUACAO_DA_SOLICITACAO).map(([codigo, nome]) => (
            <option key={codigo} value={codigo}>
              {nome}
            </option>
          ))}
        </Selecao>
        <label>
          <input
            type="checkbox"
            checked={filtros.minhas}
            onChange={(evento) => definirFiltros({ ...filtros, minhas: evento.target.checked })}
          />
          Só as minhas
        </label>
      </form>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {carregada && itens.length === 0 && <p>Nenhuma solicitação encontrada.</p>}
      {itens.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Solicitação</th>
              <th>Tipo</th>
              <th>Situação</th>
              <th>Valor</th>
              <th>Solicitante</th>
              <th>Atualizada em</th>
            </tr>
          </thead>
          <tbody>
            {itens.map((item) => (
              <tr key={item.id}>
                <td>
                  <LinkDaSolicitacao item={item} />
                </td>
                <td>{item.tipo_nome}</td>
                <td>{SITUACAO_DA_SOLICITACAO[item.situacao] ?? item.situacao}</td>
                <td>{reais(item.valor)}</td>
                <td>{item.solicitante.nome}</td>
                <td>{quando(item.atualizada_em)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {temMais && (
        <button type="button" onClick={() => void carregarMais()}>
          Carregar mais
        </button>
      )}
    </Pagina>
  )
}

/** O que quem está logado pode decidir, da que espera há mais tempo (CA-26). */
export function FilaDePendencias() {
  const [itens, definirItens] = useState<ItemDaLista[] | null>(null)
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    aprovacoes.fila().then(definirItens).catch(definirErro)
  }, [])

  return (
    <Pagina titulo="Fila de pendências">
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {itens?.length === 0 && <p>Nada para decidir agora.</p>}
      {itens && itens.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Solicitação</th>
              <th>Tipo</th>
              <th>Solicitante</th>
              <th>Valor</th>
              <th>Aguardando desde</th>
            </tr>
          </thead>
          <tbody>
            {itens.map((item) => (
              <tr key={item.id}>
                <td>
                  <LinkDaSolicitacao item={item} />
                </td>
                <td>{item.tipo_nome}</td>
                <td>{item.solicitante.nome}</td>
                <td>{reais(item.valor)}</td>
                <td>{quando(item.aguardando_desde)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Pagina>
  )
}

/**
 * O conteúdo de uma versão, de forma genérica: chave e valor, listas e objetos aninhados. Sempre como texto,
 * nunca como HTML. O M7 e o M8 acrescentam a apresentação própria dos tipos deles.
 */
function Conteudo({ valor }: { valor: unknown }) {
  if (valor === null || valor === undefined || valor === '') return <>—</>
  if (Array.isArray(valor)) {
    return (
      <ol>
        {valor.map((parte, posicao) => (
          // A lista vem pronta da API e não muda de ordem: a posição identifica cada parte.
          // oxlint-disable-next-line react/no-array-index-key
          <li key={posicao}>
            <Conteudo valor={parte} />
          </li>
        ))}
      </ol>
    )
  }
  if (typeof valor === 'object') {
    return (
      <dl>
        {Object.entries(valor).map(([chave, parte]) => (
          <Fragment key={chave}>
            <dt>{chave}</dt>
            <dd>
              <Conteudo valor={parte} />
            </dd>
          </Fragment>
        ))}
      </dl>
    )
  }
  return <>{String(valor)}</>
}

function DecisaoDaVersao({ versao }: { versao: Versao }) {
  const decisao = versao.decisao
  if (!decisao) return <p>Sem decisão ainda.</p>
  const tipo = DECISAO_DA_SOLICITACAO[decisao.tipo] ?? decisao.tipo
  return (
    <div role="group" aria-label="Decisão">
      <p>
        {tipo} por {decisao.aprovador.nome} em {quando(decisao.criada_em)}
        {decisao.aprovacao_propria && ' (aprovação própria)'}
      </p>
      <p>Motivo: {decisao.motivo_texto}</p>
      {decisao.texto && <p>{decisao.texto}</p>}
      {decisao.mensagem && <p>Mensagem: {decisao.mensagem}</p>}
      {decisao.teto_sugerido !== null && <p>Teto sugerido: {reais(decisao.teto_sugerido)}</p>}
    </div>
  )
}

function VersaoDaSolicitacao({ versao, temValor }: { versao: Versao; temValor: boolean }) {
  return (
    <section aria-label={`Versão ${versao.numero}`}>
      <h3>
        Versão {versao.numero}: {versao.resumo}
      </h3>
      <dl>
        {temValor && (
          <>
            <dt>Valor</dt>
            <dd>{reais(versao.valor)}</dd>
          </>
        )}
        <dt>Autor</dt>
        <dd>{versao.autor.nome}</dd>
        <dt>Criada em</dt>
        <dd>{quando(versao.criada_em)}</dd>
        {versao.justificativa && (
          <>
            <dt>Justificativa</dt>
            <dd>{versao.justificativa}</dd>
          </>
        )}
      </dl>
      <h4>Conteúdo</h4>
      <Conteudo valor={versao.conteudo} />
      <DecisaoDaVersao versao={versao} />
    </section>
  )
}

function Historico({ registros }: { registros: RegistroDoHistorico[] }) {
  return (
    <section aria-label="Histórico">
      <h2>Histórico</h2>
      <ul>
        {registros.map((registro) => (
          <li key={`${registro.acao}-${registro.criado_em}`}>
            {rotuloDaAcaoNaSolicitacao(registro.acao)} — {registro.ator?.nome ?? 'Sistema'}
            {registro.justificativa && `: ${registro.justificativa}`} ({quando(registro.criado_em)})
          </li>
        ))}
      </ul>
    </section>
  )
}

/** Todas as versões, as decisões, a indicação e o histórico de uma solicitação (CA-28). */
export function DetalheDeSolicitacao() {
  const { id = '' } = useParams()
  const [detalhe, definirDetalhe] = useState<DetalheDaSolicitacao | null>(null)
  const [historico, definirHistorico] = useState<RegistroDoHistorico[]>([])
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    let vivo = true
    Promise.all([aprovacoes.detalhe(id), aprovacoes.historico(id)])
      .then(([encontrado, registros]) => {
        if (!vivo) return
        definirDetalhe(encontrado)
        definirHistorico(registros)
      })
      .catch((falha) => vivo && definirErro(falha))
    return () => {
      vivo = false
    }
  }, [id])

  if (!detalhe) {
    return (
      <Pagina titulo="Solicitação">
        <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
        {!erro && <p>Carregando…</p>}
      </Pagina>
    )
  }

  const atual = detalhe.versoes.find((v) => v.numero === detalhe.numero_da_versao_atual)
  return (
    <Pagina titulo={atual?.resumo ?? 'Solicitação'}>
      <Link to="/solicitacoes">Voltar às solicitações</Link>
      <p>{detalhe.tipo_nome}</p>
      <p>
        Situação: <strong>{SITUACAO_DA_SOLICITACAO[detalhe.situacao] ?? detalhe.situacao}</strong>
      </p>
      <p>Solicitante: {detalhe.solicitante.nome}</p>
      {detalhe.aprovador_indicado && <p>Aprovador indicado: {detalhe.aprovador_indicado.nome}</p>}
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      <h2>Versões</h2>
      {[...detalhe.versoes].reverse().map((versao) => (
        <VersaoDaSolicitacao key={versao.numero} versao={versao} temValor={detalhe.tem_valor} />
      ))}
      <Historico registros={historico} />
    </Pagina>
  )
}
