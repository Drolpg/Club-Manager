import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { comunicacao, type Comunicado } from '../api/comunicacao'
import { Alerta, Pagina } from '../componentes'
import { dataEHora } from '../formatos'
import { TIPO_DE_COMUNICADO, mensagemDoErro } from '../mensagens'
import { DocumentosLigados, TextoLivre } from './apoioFeed'

/** Os despublicados que o ator pode ver, com o motivo, e a ação de republicar (só o que `acoes` autoriza). */
export function Despublicados() {
  const [itens, definirItens] = useState<Comunicado[]>([])
  const [temMais, definirTemMais] = useState(false)
  const [carregado, definirCarregado] = useState(false)
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    let vivo = true
    comunicacao
      .despublicados()
      .then((pagina) => {
        if (!vivo) return
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
      const pagina = await comunicacao.despublicados(ultimo.id)
      definirItens([...itens, ...pagina.itens])
      definirTemMais(pagina.tem_mais)
    } catch (e) {
      definirErro(e)
    }
  }

  async function republicar(id: string) {
    definirErro(null)
    try {
      await comunicacao.republicar(id)
      definirItens(itens.filter((item) => item.id !== id))
    } catch (e) {
      definirErro(e)
    }
  }

  return (
    <Pagina titulo="Comunicados despublicados">
      <Link to="/feed">Voltar ao feed</Link>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {carregado && itens.length === 0 && <p>Nenhum comunicado despublicado.</p>}
      {itens.map((comunicado) => (
        <article key={comunicado.id} aria-label={comunicado.titulo} className="item-do-feed">
          <h2>
            <Link to={`/feed/${comunicado.id}`}>{comunicado.titulo}</Link>
          </h2>
          <p className="ajuda">
            {TIPO_DE_COMUNICADO[comunicado.tipo] ?? comunicado.tipo} · {comunicado.autor.nome}
          </p>
          <TextoLivre texto={comunicado.texto} />
          <DocumentosLigados documentos={comunicado.documentos} />
          {comunicado.despublicado && (
            <p>
              Despublicado por {comunicado.despublicado.por?.nome ?? 'alguém'}
              {comunicado.despublicado.em
                ? ` em ${dataEHora.format(new Date(comunicado.despublicado.em))}`
                : ''}
              :{' '}
              {comunicado.despublicado.motivo}
            </p>
          )}
          {comunicado.acoes.includes('republicar') && (
            <button type="button" onClick={() => void republicar(comunicado.id)}>
              Republicar
            </button>
          )}
        </article>
      ))}
      {temMais && (
        <button type="button" onClick={() => void carregarMais()}>
          Carregar mais
        </button>
      )}
    </Pagina>
  )
}
