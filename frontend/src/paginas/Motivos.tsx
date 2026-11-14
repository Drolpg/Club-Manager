import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { aprovacoes, type Motivo, type TipoDeDecisao } from '../api/aprovacoes'
import { Alerta, Campo, Pagina, Selecao } from '../componentes'
import { errosPorCampo, mensagemDoErro } from '../mensagens'

type Executar = (acao: () => Promise<unknown>) => Promise<boolean>

function LinhaDoMotivo({ motivo, executar }: { motivo: Motivo; executar: Executar }) {
  const [editando, definirEditando] = useState(false)
  const [texto, definirTexto] = useState(motivo.texto)

  async function salvar(evento: FormEvent) {
    evento.preventDefault()
    if (await executar(() => aprovacoes.editarMotivo(motivo.id, texto))) definirEditando(false)
  }

  if (editando) {
    return (
      <li>
        <form aria-label={`Editar ${motivo.texto}`} onSubmit={(evento) => void salvar(evento)}>
          <Campo rotulo="Texto do motivo" value={texto} aoMudar={definirTexto} maxLength={200} />
          <button type="submit">Salvar</button>
          <button type="button" onClick={() => definirEditando(false)}>
            Desistir
          </button>
        </form>
      </li>
    )
  }
  return (
    <li>
      <span>{motivo.texto}</span> {!motivo.ativo && <span className="selo">Inativo</span>}{' '}
      <button
        type="button"
        onClick={() => {
          definirTexto(motivo.texto)
          definirEditando(true)
        }}
      >
        Editar
      </button>{' '}
      {motivo.ativo ? (
        <button type="button" onClick={() => void executar(() => aprovacoes.desativarMotivo(motivo.id))}>
          Desativar
        </button>
      ) : (
        <button type="button" onClick={() => void executar(() => aprovacoes.reativarMotivo(motivo.id))}>
          Reativar
        </button>
      )}
    </li>
  )
}

/**
 * Os motivos de decisão, por tipo de decisão (CA-29 a CA-31). Só o admin chega aqui; a API confere de novo.
 * Um motivo desativado some das opções, mas continua nas decisões antigas, que guardam o texto delas.
 */
export function MotivosDeDecisao() {
  const [tipos, definirTipos] = useState<TipoDeDecisao[]>([])
  const [motivos, definirMotivos] = useState<Motivo[]>([])
  const [tipoNovo, definirTipoNovo] = useState('')
  const [textoNovo, definirTextoNovo] = useState('')
  const [erro, definirErro] = useState<unknown>(null)

  const recarregar = useCallback(() => {
    aprovacoes.todosOsMotivos().then(definirMotivos).catch(definirErro)
  }, [])

  useEffect(() => {
    aprovacoes.tiposDeDecisao().then(definirTipos).catch(definirErro)
    recarregar()
  }, [recarregar])

  async function executar(acao: () => Promise<unknown>): Promise<boolean> {
    definirErro(null)
    try {
      await acao()
      recarregar()
      return true
    } catch (falha) {
      definirErro(falha)
      return false
    }
  }

  async function criar(evento: FormEvent) {
    evento.preventDefault()
    if (await executar(() => aprovacoes.criarMotivo(tipoNovo, textoNovo))) definirTextoNovo('')
  }

  const campos = errosPorCampo(erro)
  return (
    <Pagina titulo="Motivos de decisão">
      <form aria-label="Cadastrar motivo" onSubmit={(evento) => void criar(evento)}>
        <Selecao rotulo="Tipo de decisão" value={tipoNovo} aoMudar={definirTipoNovo}>
          <option value="">Escolha o tipo</option>
          {tipos.map((tipo) => (
            <option key={tipo.codigo} value={tipo.codigo}>
              {tipo.nome}
            </option>
          ))}
        </Selecao>
        <Campo
          rotulo="Novo motivo"
          value={textoNovo}
          aoMudar={definirTextoNovo}
          maxLength={200}
          erros={campos.texto ?? campos.tipo_de_decisao}
        />
        <button type="submit">Criar</button>
      </form>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {tipos.map((tipo) => {
        const doTipo = motivos.filter((m) => m.tipo_de_decisao === tipo.codigo)
        return (
          <section key={tipo.codigo} aria-label={tipo.nome}>
            <h2>{tipo.nome}</h2>
            {doTipo.length === 0 ? (
              <p>Nenhum motivo cadastrado.</p>
            ) : (
              <ul>
                {doTipo.map((motivo) => (
                  <LinhaDoMotivo key={`${motivo.id}-${motivo.texto}`} motivo={motivo} executar={executar} />
                ))}
              </ul>
            )}
          </section>
        )
      })}
    </Pagina>
  )
}
