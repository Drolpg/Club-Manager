import { vi } from 'vitest'

type Resposta = unknown | [number, unknown] | (() => unknown | [number, unknown])

export interface Chamada {
  metodo: string
  caminho: string
  corpo: unknown
  cabecalhos: Record<string, string>
}

function resolver(resposta: Resposta): [number, unknown] {
  const valor = typeof resposta === 'function' ? (resposta as () => unknown)() : resposta
  if (Array.isArray(valor) && valor.length === 2 && typeof valor[0] === 'number') {
    return valor as [number, unknown]
  }
  return [200, valor]
}

export function erro(status: number, code: string, message = 'mensagem da API', details: unknown = null) {
  return [status, { error: { code, message, details } }] as [number, unknown]
}

/**
 * Simula a API: cada chave é "MÉTODO /caminho" (sem o prefixo /api/v1). Devolve a lista das chamadas feitas,
 * para o teste conferir o que o site enviou.
 */
export function simularApi(rotas: Record<string, Resposta>): Chamada[] {
  const chamadas: Chamada[] = []
  const fetchFalso = vi.fn(async (url: string, init: RequestInit = {}) => {
    const metodo = (init.method ?? 'GET').toUpperCase()
    const caminho = url.replace('/api/v1', '')
    chamadas.push({
      metodo,
      caminho,
      corpo: init.body ? JSON.parse(init.body as string) : undefined,
      cabecalhos: (init.headers ?? {}) as Record<string, string>,
    })
    const chave = `${metodo} ${caminho}`
    if (!(chave in rotas)) {
      return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: `sem simulação: ${chave}` } }), {
        status: 404,
      })
    }
    const [status, corpo] = resolver(rotas[chave])
    return new Response(status === 204 ? null : JSON.stringify(corpo), { status })
  })
  vi.stubGlobal('fetch', fetchFalso)
  return chamadas
}

export const DIRETOR = {
  id: 'u-1',
  nome: 'Bia Diretora',
  nome_de_usuario: 'bia',
  email: 'bia@exemplo.com',
  admin: false,
  situacao: 'ATIVO',
  tem_cargo: false,
}

export const ADMIN = { ...DIRETOR, id: 'u-0', nome: 'Ana Admin', nome_de_usuario: 'ana.admin', admin: true }

export const SEM_GOOGLE = { 'GET /acesso/configuracao/': { google_client_id: null } }
