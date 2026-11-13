import { useEffect, useId, useRef, type InputHTMLAttributes, type ReactNode } from 'react'

export function Pagina({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <main className="pagina">
      <h1>{titulo}</h1>
      {children}
    </main>
  )
}

export function Alerta({ children }: { children: ReactNode }) {
  if (!children) return null
  return (
    <p role="alert" className="alerta">
      {children}
    </p>
  )
}

interface CampoProps extends InputHTMLAttributes<HTMLInputElement> {
  rotulo: string
  erros?: string[]
  aoMudar: (valor: string) => void
}

export function Campo({ rotulo, erros, aoMudar, ...resto }: CampoProps) {
  const id = useId()
  return (
    <div className="campo">
      <label htmlFor={id}>{rotulo}</label>
      <input id={id} onChange={(evento) => aoMudar(evento.target.value)} aria-invalid={!!erros?.length} {...resto} />
      {erros?.map((erro) => (
        <p key={erro} className="erro-de-campo">
          {erro}
        </p>
      ))}
    </div>
  )
}

/** Texto aprovado em docs/security/lgpd.md. */
export function AvisoDePrivacidade() {
  return (
    <section className="aviso">
      <h2>Seus dados no Club Manager</h2>
      <p>
        Para você participar da gestão do clube, guardamos seu nome, nome de usuário, e-mail e telefone. Eles são
        usados para identificar você nas decisões e nos registros financeiros, para o login e para avisos do
        sistema.
      </p>
      <p>
        Os outros diretores veem seu nome nas decisões e nos registros. Seu perfil completo só é visto por você e
        pelo administrador.
      </p>
      <p>
        As ações feitas no sistema ficam registradas, porque a rastreabilidade é o propósito dele. Se você deixar a
        diretoria, sua conta é desativada e o histórico é mantido.
      </p>
      <p>Para ver, corrigir ou pedir a anonimização dos seus dados, fale com o administrador do clube.</p>
    </section>
  )
}

interface GoogleAccounts {
  accounts: {
    id: {
      initialize: (opcoes: { client_id: string; callback: (resposta: { credential: string }) => void }) => void
      renderButton: (elemento: HTMLElement, opcoes: Record<string, unknown>) => void
    }
  }
}

const SCRIPT_DO_GOOGLE = 'https://accounts.google.com/gsi/client'

function carregarGoogle(): Promise<GoogleAccounts> {
  const jaCarregado = (globalThis as { google?: GoogleAccounts }).google
  if (jaCarregado) return Promise.resolve(jaCarregado)
  return new Promise((resolver, rejeitar) => {
    const script = document.createElement('script')
    script.src = SCRIPT_DO_GOOGLE
    script.async = true
    script.onload = () => resolver((globalThis as { google?: GoogleAccounts }).google as GoogleAccounts)
    script.onerror = () => rejeitar(new Error('Não foi possível carregar o Google.'))
    document.head.appendChild(script)
  })
}

/** Botão "Entrar com o Google". Só aparece quando o clube configurou o ID de cliente. */
export function BotaoGoogle({
  clientId,
  aoReceber,
}: {
  clientId: string | null
  aoReceber: (credencial: string) => void
}) {
  const alvo = useRef<HTMLDivElement>(null)
  // Guarda sempre a função mais recente, sem recriar o botão do Google a cada renderização.
  const retorno = useRef(aoReceber)
  useEffect(() => {
    retorno.current = aoReceber
  })

  useEffect(() => {
    if (!clientId) return
    let ativo = true
    carregarGoogle()
      .then((google) => {
        if (!ativo || !alvo.current) return
        google.accounts.id.initialize({
          client_id: clientId,
          callback: (resposta) => retorno.current(resposta.credential),
        })
        google.accounts.id.renderButton(alvo.current, { theme: 'outline', size: 'large', locale: 'pt-BR' })
      })
      .catch(() => undefined)
    return () => {
      ativo = false
    }
  }, [clientId])

  if (!clientId) return null
  return <div ref={alvo} data-testid="botao-google" className="botao-google" />
}
