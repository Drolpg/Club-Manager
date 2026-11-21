import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { comunicacao, type Comunicado } from '../api/comunicacao'
import { Alerta, Pagina } from '../componentes'
import { dataEHora } from '../formatos'
import { TIPO_DE_COMUNICADO, mensagemDoErro } from '../mensagens'
import { useSessao } from '../sessao'
import { COMUNICACAO_GERENCIAR, COMUNICACAO_PUBLICAR, temPermissao, useMinhasDaMoldura } from '../useMinhas'
import { DocumentosLigados, Reacoes, Rodape, TextoLivre } from './apoioFeed'

export function ItemDoFeed({ inicial }: { inicial: Comunicado }) {
  const [comunicado, definirComunicado] = useState(inicial)
  return (
    <article aria-label={comunicado.titulo} className="item-do-feed">
      <h2>
        <Link to={`/feed/${comunicado.id}`}>{comunicado.titulo}</Link>
      </h2>
      <p className="ajuda">
        {TIPO_DE_COMUNICADO[comunicado.tipo] ?? comunicado.tipo} · {comunicado.autor.nome} ·{' '}
        {dataEHora.format(new Date(comunicado.publicado_em))}
        {comunicado.editado ? ' · editado' : ''}
      </p>
      <TextoLivre texto={comunicado.texto} />
      <DocumentosLigados documentos={comunicado.documentos} />
      <Reacoes comunicado={comunicado} aoMudar={definirComunicado} />
      <Rodape comunicado={comunicado} />
    </article>
  )
}

/** CA-01 e CA-02: os fixados no topo (só na primeira página) e os demais, do mais novo ao mais antigo. */
export function Feed() {
  const { usuario } = useSessao()
  const { detalhe } = useMinhasDaMoldura()
  const [fixados, definirFixados] = useState<Comunicado[]>([])
  const [itens, definirItens] = useState<Comunicado[]>([])
  const [temMais, definirTemMais] = useState(false)
  const [carregado, definirCarregado] = useState(false)
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    let vivo = true
    comunicacao
      .feed()
      .then((pagina) => {
        if (!vivo) return
        definirFixados(pagina.fixados)
        definirItens(pagina.itens)
        definirTemMais(pagina.tem_mais)
        definirCarregado(true)
      })
      .catch((e: unknown) => vivo && definirErro(e))
    return () => {
      vivo = false
    }
  }, [])

  async function carregarMais() {
    const ultimo = itens.at(-1)
    if (!ultimo) return
    try {
      const pagina = await comunicacao.feed(ultimo.id)
      definirItens([...itens, ...pagina.itens])
      definirTemMais(pagina.tem_mais)
    } catch (e) {
      definirErro(e)
    }
  }

  // Quem publica ou gerencia pode ter comunicado despublicado a ver; a API devolve só os que o ator vê.
  const veDespublicados =
    !!usuario?.admin ||
    temPermissao(detalhe, COMUNICACAO_PUBLICAR) ||
    temPermissao(detalhe, COMUNICACAO_GERENCIAR)

  return (
    <Pagina titulo="Feed">
      {veDespublicados && <Link to="/feed/despublicados">Despublicados</Link>}
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {fixados.length > 0 && (
        <section aria-label="Fixados">
          <h2>Fixados</h2>
          {fixados.map((comunicado) => (
            <ItemDoFeed key={comunicado.id} inicial={comunicado} />
          ))}
        </section>
      )}
      {itens.map((comunicado) => (
        <ItemDoFeed key={comunicado.id} inicial={comunicado} />
      ))}
      {carregado && fixados.length + itens.length === 0 && <p>Nenhum comunicado publicado ainda.</p>}
      {temMais && (
        <button type="button" onClick={() => void carregarMais()}>
          Carregar mais
        </button>
      )}
    </Pagina>
  )
}
