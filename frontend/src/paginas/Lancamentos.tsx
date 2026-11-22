import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'
import {
  financeiro,
  type Categoria,
  type EstadoDoLancamento,
  type FiltrosLancamentos,
  type Lancamento,
  type TipoDeLancamento,
} from '../api/financeiro'
import { Alerta, Campo, Pagina, Selecao } from '../componentes'
import { dataCurta, reais } from '../formatos'
import { ESTADO_DO_LANCAMENTO, TIPO_DE_LANCAMENTO, mensagemDoErro } from '../mensagens'

/** O valor com o sinal na frente do "R$": o estorno chega como "-100.00". */
function valorComSinal(valor: string): string {
  return valor.startsWith('-') ? `-${reais(valor.slice(1))}` : reais(valor)
}

const DETALHE: Record<TipoDeLancamento, string> = {
  COBRANCA: '/cobrancas',
  ENTRADA: '/entradas',
  SAIDA: '/saidas',
  ESTORNO: '',
}

/** Para onde o item leva: o detalhe que já existe; a devolução vai à saída, e o estorno ao original. */
function destino(item: Lancamento): string {
  if (item.tipo === 'ESTORNO' && item.original) return `${DETALHE[item.original.tipo]}/${item.original.id}`
  if (item.tipo === 'ENTRADA' && item.original?.tipo === 'SAIDA') return `/saidas/${item.original.id}`
  return `${DETALHE[item.tipo]}/${item.id}`
}

function filtrosDaUrl(parametros: URLSearchParams): FiltrosLancamentos {
  return { de: parametros.get('de') ?? undefined, ate: parametros.get('ate') ?? undefined }
}

/**
 * A lista de lançamentos da aba Financeiro (RF-104): cobranças, entradas, saídas e estornos, com filtros. A
 * API filtra, ordena e pagina; o site só mostra e leva ao detalhe que já existe.
 */
export function Lancamentos() {
  const [parametros] = useSearchParams()
  const [rascunho, definirRascunho] = useState<FiltrosLancamentos>(() => filtrosDaUrl(parametros))
  const [filtros, definirFiltros] = useState<FiltrosLancamentos>(() => filtrosDaUrl(parametros))
  const [categorias, definirCategorias] = useState<Categoria[]>([])
  const [itens, definirItens] = useState<Lancamento[]>([])
  const [temMais, definirTemMais] = useState(false)
  const [carregada, definirCarregada] = useState(false)
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    financeiro
      .categorias({ todas: true })
      .then(definirCategorias)
      .catch(() => definirCategorias([]))
  }, [])

  useEffect(() => {
    let vivo = true
    financeiro
      .lancamentos(filtros)
      .then((pagina) => {
        if (!vivo) return
        definirItens(pagina.itens)
        definirTemMais(pagina.tem_mais)
        definirErro(null)
      })
      .catch((falha) => vivo && definirErro(falha))
      .finally(() => vivo && definirCarregada(true))
    return () => {
      vivo = false
    }
  }, [filtros])

  function filtrar(evento: FormEvent) {
    evento.preventDefault()
    definirFiltros({ ...rascunho })
  }

  function carregarMais() {
    const ultimo = itens[itens.length - 1]
    financeiro
      .lancamentos({ ...filtros, antes: `${ultimo.tipo}:${ultimo.id}` })
      .then((pagina) => {
        definirItens((atuais) => [...atuais, ...pagina.itens])
        definirTemMais(pagina.tem_mais)
      })
      .catch(definirErro)
  }

  const mudar = (campo: keyof FiltrosLancamentos) => (valor: string) =>
    definirRascunho((atual) => ({ ...atual, [campo]: valor || undefined }))

  return (
    <Pagina titulo="Lançamentos">
      <form onSubmit={filtrar} aria-label="Filtros">
        <Campo rotulo="De" type="date" value={rascunho.de ?? ''} aoMudar={mudar('de')} />
        <Campo rotulo="Até" type="date" value={rascunho.ate ?? ''} aoMudar={mudar('ate')} />
        <Selecao rotulo="Tipo" value={rascunho.tipo ?? ''} aoMudar={mudar('tipo')}>
          <option value="">Todos</option>
          {(Object.keys(TIPO_DE_LANCAMENTO) as TipoDeLancamento[]).map((tipo) => (
            <option key={tipo} value={tipo}>
              {TIPO_DE_LANCAMENTO[tipo]}
            </option>
          ))}
        </Selecao>
        <Selecao rotulo="Estado" value={rascunho.estado ?? ''} aoMudar={mudar('estado')}>
          <option value="">Todos</option>
          {(Object.keys(ESTADO_DO_LANCAMENTO) as EstadoDoLancamento[]).map((estado) => (
            <option key={estado} value={estado}>
              {ESTADO_DO_LANCAMENTO[estado]}
            </option>
          ))}
        </Selecao>
        <Selecao rotulo="Categoria" value={rascunho.categoria_id ?? ''} aoMudar={mudar('categoria_id')}>
          <option value="">Todas</option>
          {categorias.map((c) => (
            <option key={c.id} value={c.id}>
              {c.ativa ? c.nome : `${c.nome} (desativada)`}
            </option>
          ))}
        </Selecao>
        <button type="submit">Filtrar</button>
      </form>

      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>

      {carregada && !itens.length && !erro && <p>Nenhum lançamento com esses filtros.</p>}
      {itens.length > 0 && (
        <table aria-label="Lançamentos">
          <thead>
            <tr>
              <th>Data</th>
              <th>Tipo</th>
              <th>Descrição</th>
              <th>Categoria</th>
              <th>Contraparte</th>
              <th>Valor</th>
              <th>Estado</th>
              <th>Realizado em</th>
            </tr>
          </thead>
          <tbody>
            {itens.map((item) => (
              <tr key={`${item.tipo}-${item.id}`}>
                <td>{dataCurta(item.data_referencia)}</td>
                <td>
                  {TIPO_DE_LANCAMENTO[item.tipo]}
                  {item.subtipo === 'DEVOLUCAO' && ' (devolução)'}
                </td>
                <td>
                  <Link to={destino(item)}>{item.descricao}</Link>
                </td>
                <td>{item.categoria.nome}</td>
                <td>{item.contraparte}</td>
                <td>
                  {valorComSinal(item.valor)}
                  {item.valor_realizado !== null && ` (realizado ${reais(item.valor_realizado)})`}
                </td>
                <td>{ESTADO_DO_LANCAMENTO[item.estado]}</td>
                <td>{dataCurta(item.realizado_em)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {temMais && (
        <button type="button" onClick={carregarMais}>
          Carregar mais
        </button>
      )}
    </Pagina>
  )
}
