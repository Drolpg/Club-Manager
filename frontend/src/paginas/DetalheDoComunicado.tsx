import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import {
  comunicacao,
  TIPOS_DE_REACAO,
  type Comentario,
  type Comunicado,
  type Pessoa,
  type TipoDeReacao,
} from '../api/comunicacao'
import { Alerta, AreaDeTexto, Campo, Pagina } from '../componentes'
import { dataEHora } from '../formatos'
import { ROTULO_DA_REACAO, TIPO_DE_COMUNICADO, errosPorCampo, mensagemDoErro } from '../mensagens'
import { useSessao } from '../sessao'
import { DocumentosLigados, Reacoes, TextoLivre } from './apoioFeed'

function QuemReagiu({ comunicado }: { comunicado: Comunicado }) {
  const quem = comunicado.reacoes.quem
  const tipos = TIPOS_DE_REACAO.filter((tipo: TipoDeReacao) => (quem?.[tipo] ?? []).length > 0)
  if (tipos.length === 0) return null
  return (
    <section aria-label="Quem reagiu">
      {tipos.map((tipo) => (
        <p key={tipo}>
          {ROTULO_DA_REACAO[tipo]}: {(quem?.[tipo] ?? []).map((pessoa: Pessoa) => pessoa.nome).join(', ')}
        </p>
      ))}
    </section>
  )
}

function ItemDoComentario({
  comentario,
  aoMudar,
}: {
  comentario: Comentario
  aoMudar: (novo: Comentario) => void
}) {
  const { usuario } = useSessao()
  const [editando, definirEditando] = useState(false)
  const [texto, definirTexto] = useState(comentario.texto)
  const [motivo, definirMotivo] = useState('')
  const [erro, definirErro] = useState<unknown>(null)
  const campos = errosPorCampo(erro)
  const oculto = comentario.situacao === 'OCULTO'
  const meu = usuario?.id === comentario.autor.id
  const pode = (acao: string) => comentario.acoes.includes(acao as never)

  async function executar(acao: () => Promise<Comentario>) {
    definirErro(null)
    try {
      aoMudar(await acao())
      definirEditando(false)
      definirMotivo('')
    } catch (e) {
      definirErro(e)
    }
  }

  function salvar(formulario: FormEvent) {
    formulario.preventDefault()
    void executar(() => comunicacao.editarComentario(comentario.id, texto))
  }

  function ocultar(formulario: FormEvent) {
    formulario.preventDefault()
    void executar(() => comunicacao.ocultarComentario(comentario.id, meu ? '' : motivo))
  }

  return (
    <li
      aria-label={`Comentário de ${comentario.autor.nome}`}
      className={oculto ? 'comentario comentario-oculto' : 'comentario'}
    >
      <p className="ajuda">
        {comentario.autor.nome} · {dataEHora.format(new Date(comentario.criado_em))}
        {comentario.editado ? ' · editado' : ''}
        {oculto && (
          <>
            {' · '}
            <span className="selo">Oculto</span>
          </>
        )}
      </p>
      {editando ? (
        <form aria-label="Edição do comentário" onSubmit={salvar}>
          <AreaDeTexto rotulo="Editar comentário" value={texto} erros={campos.texto} aoMudar={definirTexto} />
          <button type="submit">Salvar</button>
          <button type="button" onClick={() => definirEditando(false)}>
            Cancelar
          </button>
        </form>
      ) : (
        <TextoLivre texto={comentario.texto} />
      )}
      {oculto && comentario.oculto?.motivo && <p className="ajuda">Motivo: {comentario.oculto.motivo}</p>}
      {pode('editar_comentario') && !editando && (
        <button type="button" onClick={() => definirEditando(true)}>
          Editar
        </button>
      )}
      {pode('ocultar_comentario') &&
        (meu ? (
          <button
            type="button"
            onClick={() => void executar(() => comunicacao.ocultarComentario(comentario.id, ''))}
          >
            Ocultar
          </button>
        ) : (
          <form aria-label="Ocultar comentário" onSubmit={ocultar}>
            <Campo
              rotulo="Motivo da ocultação"
              value={motivo}
              erros={campos.motivo}
              aoMudar={definirMotivo}
            />
            <button type="submit">Ocultar</button>
          </form>
        ))}
      {pode('reexibir_comentario') && (
        <button
          type="button"
          onClick={() => void executar(() => comunicacao.reexibirComentario(comentario.id))}
        >
          Reexibir
        </button>
      )}
      <Alerta>{erro && !Object.keys(campos).length ? mensagemDoErro(erro) : null}</Alerta>
    </li>
  )
}

function Comentarios({ comunicado }: { comunicado: Comunicado }) {
  const [itens, definirItens] = useState<Comentario[]>([])
  const [temMais, definirTemMais] = useState(false)
  const [texto, definirTexto] = useState('')
  const [erro, definirErro] = useState<unknown>(null)
  const campos = errosPorCampo(erro)

  useEffect(() => {
    let vivo = true
    comunicacao
      .comentarios(comunicado.id)
      .then((pagina) => {
        if (!vivo) return
        definirItens(pagina.itens)
        definirTemMais(pagina.tem_mais)
      })
      .catch((e: unknown) => vivo && definirErro(e))
    return () => {
      vivo = false
    }
  }, [comunicado.id])

  async function carregarMais() {
    const ultimo = itens.at(-1)
    if (!ultimo) return
    try {
      const pagina = await comunicacao.comentarios(comunicado.id, ultimo.id)
      definirItens([...itens, ...pagina.itens])
      definirTemMais(pagina.tem_mais)
    } catch (e) {
      definirErro(e)
    }
  }

  async function comentar(formulario: FormEvent) {
    formulario.preventDefault()
    definirErro(null)
    try {
      const novo = await comunicacao.comentar(comunicado.id, texto)
      definirItens([...itens, novo])
      definirTexto('')
    } catch (e) {
      definirErro(e)
    }
  }

  function substituir(novo: Comentario) {
    definirItens(itens.map((item) => (item.id === novo.id ? novo : item)))
  }

  return (
    <section aria-label="Comentários">
      <h2>Comentários</h2>
      {itens.length === 0 && <p className="ajuda">Nenhum comentário ainda.</p>}
      <ul className="lista">
        {itens.map((item) => (
          <ItemDoComentario key={item.id} comentario={item} aoMudar={substituir} />
        ))}
      </ul>
      {temMais && (
        <button type="button" onClick={() => void carregarMais()}>
          Carregar mais comentários
        </button>
      )}
      {comunicado.acoes.includes('comentar') && (
        <form aria-label="Novo comentário" onSubmit={(formulario) => void comentar(formulario)}>
          <AreaDeTexto rotulo="Seu comentário" value={texto} erros={campos.texto} aoMudar={definirTexto} />
          <button type="submit">Comentar</button>
        </form>
      )}
      <Alerta>{erro && !Object.keys(campos).length ? mensagemDoErro(erro) : null}</Alerta>
    </section>
  )
}

/** CA-01 a CA-20: o comunicado, as reações com quem reagiu, os comentários e as ações de `acoes`. */
export function DetalheDoComunicado() {
  const { id = '' } = useParams()
  const [comunicado, definirComunicado] = useState<Comunicado | null>(null)
  const [motivo, definirMotivo] = useState('')
  const [erro, definirErro] = useState<unknown>(null)
  const campos = errosPorCampo(erro)

  useEffect(() => {
    let vivo = true
    comunicacao
      .detalhe(id)
      .then((dados) => vivo && definirComunicado(dados))
      .catch((e: unknown) => vivo && definirErro(e))
    return () => {
      vivo = false
    }
  }, [id])

  if (!comunicado) {
    const conteudo = erro ? <Alerta>{mensagemDoErro(erro)}</Alerta> : <p>Carregando…</p>
    return <Pagina titulo="Comunicado">{conteudo}</Pagina>
  }

  const pode = (acao: string) => comunicado.acoes.includes(acao as never)

  async function executar(acao: () => Promise<Comunicado>) {
    definirErro(null)
    try {
      definirComunicado(await acao())
      definirMotivo('')
    } catch (e) {
      definirErro(e)
    }
  }

  function despublicar(formulario: FormEvent) {
    formulario.preventDefault()
    void executar(() => comunicacao.despublicar(id, motivo))
  }

  return (
    <Pagina titulo={comunicado.titulo}>
      <p className="ajuda">
        {TIPO_DE_COMUNICADO[comunicado.tipo] ?? comunicado.tipo} · {comunicado.autor.nome} ·{' '}
        {dataEHora.format(new Date(comunicado.publicado_em))}
        {comunicado.editado ? ' · editado' : ''}
        {comunicado.fixado ? ' · fixado' : ''}
      </p>
      {comunicado.despublicado && (
        <p className="alerta">
          Despublicado por {comunicado.despublicado.por?.nome ?? 'alguém'}: {comunicado.despublicado.motivo}
        </p>
      )}
      <TextoLivre texto={comunicado.texto} />
      <DocumentosLigados documentos={comunicado.documentos} />
      <Reacoes comunicado={comunicado} aoMudar={definirComunicado} />
      <QuemReagiu comunicado={comunicado} />
      <Alerta>{erro && !Object.keys(campos).length ? mensagemDoErro(erro) : null}</Alerta>
      {pode('editar_comunicado') && <Link to={`/feed/${comunicado.id}/editar`}>Editar comunicado</Link>}
      {pode('fixar') && (
        <button type="button" onClick={() => void executar(() => comunicacao.fixar(id))}>
          Fixar
        </button>
      )}
      {pode('desafixar') && (
        <button type="button" onClick={() => void executar(() => comunicacao.desafixar(id))}>
          Desafixar
        </button>
      )}
      {pode('republicar') && (
        <button type="button" onClick={() => void executar(() => comunicacao.republicar(id))}>
          Republicar
        </button>
      )}
      {pode('despublicar') && (
        <form aria-label="Despublicar comunicado" onSubmit={despublicar}>
          <Campo rotulo="Motivo" value={motivo} erros={campos.motivo} aoMudar={definirMotivo} />
          <button type="submit">Despublicar</button>
        </form>
      )}
      <Comentarios comunicado={comunicado} />
    </Pagina>
  )
}
