import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router'
import { eventos, type Referencias } from '../api/eventos'
import { Alerta, Campo, Pagina, Selecao } from '../componentes'
import { errosPorCampo, mensagemDoErro } from '../mensagens'

interface Dados {
  titulo: string
  descricao: string
  inicio: string
  local: string
  categoria_id: string
  envolve_custo: boolean
}

const VAZIO: Dados = { titulo: '', descricao: '', inicio: '', local: '', categoria_id: '', envolve_custo: false }

/** Proposta (`/eventos/novo`) e edição (`/eventos/:id/editar`). A data e a hora vão sem fuso: a API as lê no
 * fuso do clube. Na edição, o valor vem da API já no fuso do clube, e o site só recorta o texto. */
export function FormularioDeEvento() {
  const { id } = useParams()
  const editando = id !== undefined
  const navegar = useNavigate()
  const [dados, definirDados] = useState<Dados>(VAZIO)
  const [carregado, definirCarregado] = useState(!editando)
  const [referencias, definirReferencias] = useState<Referencias | null>(null)
  const [aprovadorIndicado, definirAprovadorIndicado] = useState('')
  const [justificativa, definirJustificativa] = useState('')
  const [erro, definirErro] = useState<unknown>(null)
  const [enviando, definirEnviando] = useState(false)
  const campos = errosPorCampo(erro)

  useEffect(() => {
    eventos
      .referencias()
      .then(definirReferencias)
      .catch((e: unknown) => definirErro(e))
  }, [])

  useEffect(() => {
    if (!id) return
    eventos
      .detalhe(id)
      .then((evento) => {
        definirDados({
          titulo: evento.titulo,
          descricao: evento.descricao,
          inicio: evento.inicio.slice(0, 16),
          local: evento.local,
          categoria_id: evento.categoria_id,
          envolve_custo: evento.envolve_custo,
        })
        definirCarregado(true)
      })
      .catch((e: unknown) => definirErro(e))
  }, [id])

  function mudar<K extends keyof Dados>(campo: K, valor: Dados[K]) {
    definirDados({ ...dados, [campo]: valor })
  }

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    definirErro(null)
    definirEnviando(true)
    try {
      const salvo = editando
        ? await eventos.editar(id, { ...dados, justificativa })
        : await eventos.propor({
            ...dados,
            ...(referencias?.precisa_indicar_aprovador ? { aprovador_indicado_id: aprovadorIndicado || null } : {}),
          })
      void navegar(`/eventos/${salvo.id}`)
    } catch (e) {
      definirErro(e)
    } finally {
      definirEnviando(false)
    }
  }

  if (!carregado) return <Pagina titulo="Editar evento">{erro ? <Alerta>{mensagemDoErro(erro)}</Alerta> : <p>Carregando…</p>}</Pagina>

  return (
    <Pagina titulo={editando ? 'Editar evento' : 'Propor evento'}>
      <form aria-label={editando ? 'Editar evento' : 'Propor evento'} onSubmit={(evento) => void enviar(evento)}>
        <Campo rotulo="Título" value={dados.titulo} erros={campos.titulo} aoMudar={(v) => mudar('titulo', v)} />
        <Campo
          rotulo="Descrição"
          value={dados.descricao}
          erros={campos.descricao}
          aoMudar={(v) => mudar('descricao', v)}
        />
        <Campo
          rotulo="Data e hora"
          type="datetime-local"
          value={dados.inicio}
          erros={campos.inicio}
          aoMudar={(v) => mudar('inicio', v)}
        />
        <Campo rotulo="Local" value={dados.local} erros={campos.local} aoMudar={(v) => mudar('local', v)} />
        <Selecao rotulo="Categoria" value={dados.categoria_id} aoMudar={(v) => mudar('categoria_id', v)}>
          <option value="">Escolha</option>
          {referencias?.categorias.map((categoria) => (
            <option key={categoria.id} value={categoria.id}>
              {categoria.nome}
            </option>
          ))}
        </Selecao>
        {campos.categoria_id?.map((mensagem) => (
          <p key={mensagem} className="erro-de-campo">
            {mensagem}
          </p>
        ))}
        <div className="campo">
          <label>
            <input
              type="checkbox"
              checked={dados.envolve_custo}
              onChange={(evento) => mudar('envolve_custo', evento.target.checked)}
            />
            Envolve custo
          </label>
        </div>
        {!editando && referencias?.precisa_indicar_aprovador && (
          <Selecao rotulo="Aprovador indicado" value={aprovadorIndicado} aoMudar={definirAprovadorIndicado}>
            <option value="">Escolha quem vai decidir</option>
            {referencias.aprovadores_eventos.map((pessoa) => (
              <option key={pessoa.id} value={pessoa.id}>
                {pessoa.nome}
              </option>
            ))}
          </Selecao>
        )}
        {editando && (
          <Campo
            rotulo="Justificativa (obrigatória se recusado)"
            value={justificativa}
            erros={campos.justificativa}
            aoMudar={definirJustificativa}
          />
        )}
        <Alerta>{erro && !Object.keys(campos).length ? mensagemDoErro(erro) : null}</Alerta>
        <button type="submit" disabled={enviando}>
          {editando ? 'Salvar edição' : 'Propor evento'}
        </button>
      </form>
    </Pagina>
  )
}
