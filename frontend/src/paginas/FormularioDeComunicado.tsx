import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router'
import { comunicacao, type Documento, type DocumentoDoComunicado } from '../api/comunicacao'
import { Alerta, AreaDeTexto, Campo, Pagina, Selecao } from '../componentes'
import { TIPO_DE_COMUNICADO, errosPorCampo, mensagemDoErro } from '../mensagens'

interface Opcao {
  id: string
  titulo: string
  arquivado: boolean
}

/** Publicação (`/feed/novo`) e edição (`/feed/:id/editar`). Os documentos são os vigentes da aba, mais os que
 * o comunicado já indexa (um arquivado continua ligado, e some se for desmarcado). */
export function FormularioDeComunicado() {
  const { id } = useParams()
  const editando = id !== undefined
  const navegar = useNavigate()
  const [tipo, definirTipo] = useState('COMUNICADO')
  const [titulo, definirTitulo] = useState('')
  const [texto, definirTexto] = useState('')
  const [escolhidos, definirEscolhidos] = useState<string[]>([])
  const [ligados, definirLigados] = useState<DocumentoDoComunicado[]>([])
  const [vigentes, definirVigentes] = useState<Documento[]>([])
  const [temMaisDocumentos, definirTemMaisDocumentos] = useState(false)
  const [carregado, definirCarregado] = useState(!editando)
  const [erro, definirErro] = useState<unknown>(null)
  const [enviando, definirEnviando] = useState(false)
  const campos = errosPorCampo(erro)

  useEffect(() => {
    comunicacao
      .documentos()
      .then((pagina) => {
        definirVigentes(pagina.itens)
        definirTemMaisDocumentos(pagina.tem_mais)
      })
      .catch((e: unknown) => definirErro(e))
  }, [])

  useEffect(() => {
    if (!id) return
    comunicacao
      .detalhe(id)
      .then((comunicado) => {
        definirTipo(comunicado.tipo)
        definirTitulo(comunicado.titulo)
        definirTexto(comunicado.texto)
        definirLigados(comunicado.documentos)
        definirEscolhidos(comunicado.documentos.map((documento) => documento.id))
        definirCarregado(true)
      })
      .catch((e: unknown) => definirErro(e))
  }, [id])

  async function maisDocumentos() {
    const ultimo = vigentes.at(-1)
    if (!ultimo) return
    try {
      const pagina = await comunicacao.documentos({ antes: ultimo.id })
      definirVigentes([...vigentes, ...pagina.itens])
      definirTemMaisDocumentos(pagina.tem_mais)
    } catch (e) {
      definirErro(e)
    }
  }

  const opcoes: Opcao[] = [
    ...ligados
      .filter((ligado) => !vigentes.some((documento) => documento.id === ligado.id))
      .map((ligado) => ({
        id: ligado.id,
        titulo: ligado.titulo,
        arquivado: ligado.situacao === 'ARQUIVADO',
      })),
    ...vigentes.map((documento) => ({ id: documento.id, titulo: documento.titulo, arquivado: false })),
  ]

  function alternar(documentoId: string, marcado: boolean) {
    definirEscolhidos(
      marcado ? [...escolhidos, documentoId] : escolhidos.filter((outro) => outro !== documentoId),
    )
  }

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    definirErro(null)
    definirEnviando(true)
    try {
      const dados = { titulo, texto, documentos_ids: escolhidos }
      const salvo = editando
        ? await comunicacao.editar(id, dados)
        : await comunicacao.publicar({ tipo, ...dados })
      void navegar(`/feed/${salvo.id}`)
    } catch (e) {
      definirErro(e)
    } finally {
      definirEnviando(false)
    }
  }

  const nome = editando ? 'Editar comunicado' : 'Publicar comunicado'
  if (!carregado) {
    const conteudo = erro ? <Alerta>{mensagemDoErro(erro)}</Alerta> : <p>Carregando…</p>
    return <Pagina titulo={nome}>{conteudo}</Pagina>
  }

  return (
    <Pagina titulo={nome}>
      <form aria-label={nome} onSubmit={(evento) => void enviar(evento)}>
        {!editando && (
          <Selecao rotulo="Tipo" value={tipo} aoMudar={definirTipo}>
            {Object.entries(TIPO_DE_COMUNICADO).map(([valor, rotulo]) => (
              <option key={valor} value={valor}>
                {rotulo}
              </option>
            ))}
          </Selecao>
        )}
        {campos.tipo?.map((mensagem) => (
          <p key={mensagem} className="erro-de-campo">
            {mensagem}
          </p>
        ))}
        <Campo rotulo="Título" value={titulo} erros={campos.titulo} aoMudar={definirTitulo} />
        <AreaDeTexto rotulo="Texto" value={texto} erros={campos.texto} aoMudar={definirTexto} />
        <fieldset>
          <legend>Documentos da aba</legend>
          {opcoes.length === 0 && <p className="ajuda">Nenhum documento vigente na aba.</p>}
          {opcoes.map((opcao) => (
            <label key={opcao.id} className="opcao">
              <input
                type="checkbox"
                checked={escolhidos.includes(opcao.id)}
                onChange={(evento) => alternar(opcao.id, evento.target.checked)}
              />
              {opcao.arquivado ? `${opcao.titulo} (arquivado)` : opcao.titulo}
            </label>
          ))}
          {temMaisDocumentos && (
            <button type="button" onClick={() => void maisDocumentos()}>
              Mais documentos
            </button>
          )}
          {campos.documentos_ids?.map((mensagem) => (
            <p key={mensagem} className="erro-de-campo">
              {mensagem}
            </p>
          ))}
        </fieldset>
        <Alerta>{erro && !Object.keys(campos).length ? mensagemDoErro(erro) : null}</Alerta>
        <button type="submit" disabled={enviando}>
          {editando ? 'Salvar edição' : 'Publicar'}
        </button>
      </form>
    </Pagina>
  )
}
