import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { acesso, type Usuario } from './api/acesso'

interface Sessao {
  /** `undefined` enquanto a sessão ainda está sendo consultada. */
  usuario: Usuario | null | undefined
  googleClientId: string | null
  definirUsuario: (usuario: Usuario | null) => void
  sair: () => Promise<void>
  /** Sobe a cada `recarregar`. Quem depende de dados do usuário (como as permissões) refaz a consulta. */
  versao: number
  /** Consulta a sessão de novo (`tem_cargo`, `admin`…). Se falhar, mantém o que já se sabe. */
  recarregar: () => Promise<void>
}

const Contexto = createContext<Sessao | null>(null)

export function ProvedorDeSessao({ children }: { children: ReactNode }) {
  const [usuario, definirUsuario] = useState<Usuario | null | undefined>(undefined)
  const [googleClientId, definirGoogleClientId] = useState<string | null>(null)
  const [versao, definirVersao] = useState(0)

  useEffect(() => {
    let ativo = true
    // Consultar a sessão também faz a API entregar o cookie CSRF usado nas escritas.
    acesso
      .sessao()
      .then((sessao) => ativo && definirUsuario(sessao.usuario))
      .catch(() => ativo && definirUsuario(null))
    acesso
      .configuracao()
      .then((configuracao) => ativo && definirGoogleClientId(configuracao.google_client_id))
      .catch(() => undefined)
    return () => {
      ativo = false
    }
  }, [])

  const sair = useCallback(async () => {
    await acesso.sair().catch(() => undefined)
    definirUsuario(null)
  }, [])

  const recarregar = useCallback(async () => {
    try {
      const sessao = await acesso.sessao()
      // Sessão que acabou no meio do caminho: quem decide é o `Protegida`, que manda para a tela de entrar.
      definirUsuario(sessao.usuario)
      definirVersao((atual) => atual + 1)
    } catch {
      // Sem resposta, vale o que já está na tela; a próxima ação tenta de novo.
    }
  }, [])

  const valor = useMemo(
    () => ({ usuario, googleClientId, definirUsuario, sair, versao, recarregar }),
    [usuario, googleClientId, sair, versao, recarregar],
  )
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

// oxlint-disable-next-line react/only-export-components
export function useSessao(): Sessao {
  const sessao = useContext(Contexto)
  if (!sessao) throw new Error('useSessao precisa estar dentro de ProvedorDeSessao')
  return sessao
}
