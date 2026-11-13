import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { notificacoes, type Preferencias as DadosDePreferencias } from '../api/notificacoes'
import { Alerta, Pagina } from '../componentes'
import { mensagemDoErro } from '../mensagens'

/** Como o usuário quer ser alertado (RF-030). Nenhuma chave desliga o registro da notificação. */
export function Preferencias() {
  const [preferencias, definirPreferencias] = useState<DadosDePreferencias | null>(null)
  const [erro, definirErro] = useState<unknown>(null)
  const [salvo, definirSalvo] = useState(false)
  const [salvando, definirSalvando] = useState(false)

  useEffect(() => {
    let ativo = true
    notificacoes
      .preferencias()
      .then((resposta) => ativo && definirPreferencias(resposta))
      .catch((falha) => ativo && definirErro(falha))
    return () => {
      ativo = false
    }
  }, [])

  function alterar(campo: keyof DadosDePreferencias, valor: boolean) {
    if (!preferencias) return
    definirSalvo(false)
    definirPreferencias({ ...preferencias, [campo]: valor })
  }

  async function salvar(evento: FormEvent) {
    evento.preventDefault()
    if (!preferencias) return
    definirErro(null)
    definirSalvo(false)
    definirSalvando(true)
    try {
      definirPreferencias(await notificacoes.salvarPreferencias(preferencias))
      definirSalvo(true)
    } catch (falha) {
      definirErro(falha)
    } finally {
      definirSalvando(false)
    }
  }

  return (
    <Pagina titulo="Preferências de alerta">
      <Link to="/">Voltar</Link>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {!preferencias && !erro && <p>Carregando…</p>}
      {preferencias && (
        <form onSubmit={(evento) => void salvar(evento)}>
          <label className="opcao">
            <input
              type="checkbox"
              checked={preferencias.aviso_na_tela}
              onChange={(evento) => alterar('aviso_na_tela', evento.target.checked)}
            />
            Aviso na tela
          </label>
          <label className="opcao">
            <input
              type="checkbox"
              checked={preferencias.email_informativos}
              onChange={(evento) => alterar('email_informativos', evento.target.checked)}
            />
            E-mail dos avisos informativos
          </label>
          <p className="ajuda">
            As notificações que pedem uma ação sua sempre ficam na caixa e sempre chegam por e-mail. Nenhuma
            preferência desliga o registro, a caixa nem o indicador de não lidas.
          </p>
          <button type="submit" disabled={salvando}>
            Salvar
          </button>
          {salvo && <p role="status">Preferências salvas.</p>}
        </form>
      )}
    </Pagina>
  )
}
