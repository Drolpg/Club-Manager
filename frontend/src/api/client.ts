// Cliente da API única (RNF-01). Nenhuma regra de negócio mora aqui: o site só chama e mostra.

const BASE_URL = '/api/v1'

interface ErrorEnvelope {
  error: { code: string; message: string; details: unknown }
}

/** Erro devolvido pela API. O `code` é estável e pode ser usado para decidir o que mostrar. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown

  constructor(status: number, code: string, message: string, details: unknown = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

function isErrorEnvelope(body: unknown): body is ErrorEnvelope {
  if (typeof body !== 'object' || body === null || !('error' in body)) return false
  const error = (body as { error: unknown }).error
  return typeof error === 'object' && error !== null && 'code' in error && 'message' in error
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    return null
  }
}

// A API exige o token CSRF em toda escrita (ADR-008). Ele vem num cookie que o site pode ler.
function csrfToken(): string {
  const achado = document.cookie.split('; ').find((parte) => parte.startsWith('csrftoken='))
  return achado ? decodeURIComponent(achado.slice('csrftoken='.length)) : ''
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (method !== 'GET') {
    headers['X-CSRFToken'] = csrfToken()
    headers['Content-Type'] = 'application/json'
  }

  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      credentials: 'same-origin',
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'Não foi possível falar com a API.')
  }

  const data = response.status === 204 ? null : await readJson(response)
  if (response.ok) return data as T

  if (isErrorEnvelope(data)) {
    throw new ApiError(response.status, data.error.code, data.error.message, data.error.details)
  }
  throw new ApiError(response.status, 'UNEXPECTED_RESPONSE', 'A API devolveu uma resposta inesperada.')
}

export const apiGet = <T>(path: string) => request<T>('GET', path)
export const apiPost = <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {})
export const apiDelete = <T>(path: string) => request<T>('DELETE', path)
