import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { eventos, type CategoriaDeEvento, type EventoDaLista, type FiltrosDoHistorico } from '../api/eventos'
import { Alerta, Campo, Pagina, Selecao } from '../componentes'
import { dataCurta } from '../formatos'
import { SITUACAO_DO_EVENTO, mensagemDoErro } from '../mensagens'

/** CA-26: todos os eventos, em qualquer situação, com filtros por situação, categoria e período. */
export function HistoricoDeEventos() {
  const [filtros, definirFiltros] = useState<FiltrosDoHistorico>({})
  const [itens, definirItens] = useState<EventoDaLista[]>([])
  const [temMais, definirTemMais] = useState(false)
  const [categorias, definirCategorias] = useState<CategoriaDeEvento[]>([])
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    eventos
      .categorias()
      .then(definirCategorias)
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    let vivo = true
    eventos
      .historico(filtros)
      .then((pagina) => {
        if (!vivo) return
        definirItens(pagina.itens)
        definirTemMais(pagina.tem_mais)
      })
      .catch((e: unknown) => vivo && definirErro(e))
    return () => {
      vivo = false
    }
  }, [filtros])

  async function carregarMais() {
    const ultimo = itens.at(-1)
    if (!ultimo) return
    try {
      const pagina = await eventos.historico({ ...filtros, antes: ultimo.id })
      definirItens([...itens, ...pagina.itens])
      definirTemMais(pagina.tem_mais)
    } catch (e) {
      definirErro(e)
    }
  }

  return (
    <Pagina titulo="Histórico de eventos">
      <form aria-label="Filtros" onSubmit={(evento) => evento.preventDefault()}>
        <Selecao
          rotulo="Situação"
          value={filtros.situacao ?? ''}
          aoMudar={(situacao) => definirFiltros({ ...filtros, situacao })}
        >
          <option value="">Todas</option>
          {Object.entries(SITUACAO_DO_EVENTO).map(([valor, rotulo]) => (
            <option key={valor} value={valor}>
              {rotulo}
            </option>
          ))}
        </Selecao>
        <Selecao
          rotulo="Categoria"
          value={filtros.categoria_id ?? ''}
          aoMudar={(categoria_id) => definirFiltros({ ...filtros, categoria_id })}
        >
          <option value="">Todas</option>
          {categorias.map((categoria) => (
            <option key={categoria.id} value={categoria.id}>
              {categoria.nome}
            </option>
          ))}
        </Selecao>
        <Campo rotulo="De" type="date" value={filtros.de ?? ''} aoMudar={(de) => definirFiltros({ ...filtros, de })} />
        <Campo
          rotulo="Até"
          type="date"
          value={filtros.ate ?? ''}
          aoMudar={(ate) => definirFiltros({ ...filtros, ate })}
        />
      </form>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {itens.length === 0 && <p>Nenhum evento encontrado.</p>}
      <ul className="lista">
        {itens.map((item) => (
          <li key={item.id}>
            <Link to={`/eventos/${item.id}`}>{item.titulo}</Link> — {dataCurta(item.inicio.slice(0, 10))}{' '}
            {item.inicio.slice(11, 16)}, {item.local} · {item.categoria_nome} ·{' '}
            {SITUACAO_DO_EVENTO[item.situacao] ?? item.situacao}
          </li>
        ))}
      </ul>
      {temMais && (
        <button type="button" onClick={() => void carregarMais()}>
          Carregar mais
        </button>
      )}
    </Pagina>
  )
}
