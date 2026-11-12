import { useEffect, useState } from 'react'
import { apiGet } from './api/client'

type Situacao = 'verificando' | 'no-ar' | 'indisponivel'

const TEXTO: Record<Situacao, string> = {
  verificando: 'Verificando a API…',
  'no-ar': 'API no ar',
  indisponivel: 'API indisponível',
}

// Esqueleto do M1: prova que o site fala com a API. As telas entram a partir do M2.
// O sistema nasce sem marca de clube (BRD-01); a identidade visual é configurada no M11.
function App() {
  const [situacao, setSituacao] = useState<Situacao>('verificando')

  useEffect(() => {
    let ativo = true
    apiGet<{ status: string }>('/health/')
      .then((saude) => {
        if (ativo) setSituacao(saude.status === 'ok' ? 'no-ar' : 'indisponivel')
      })
      .catch(() => {
        if (ativo) setSituacao('indisponivel')
      })
    return () => {
      ativo = false
    }
  }, [])

  return (
    <main className="pagina">
      <h1>Club Manager</h1>
      <p role="status" data-situacao={situacao}>
        {TEXTO[situacao]}
      </p>
    </main>
  )
}

export default App
