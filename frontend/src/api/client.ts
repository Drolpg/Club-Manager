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

export async function apiGet<T>(path: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, { headers: { Accept: 'application/json' } })
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'Não foi possível falar com a API.')
  }

  const body = await readJson(response)
  if (response.ok) return body as T

  if (isErrorEnvelope(body)) {
    throw new ApiError(response.status, body.error.code, body.error.message, body.error.details)
  }
  throw new ApiError(response.status, 'UNEXPECTED_RESPONSE', 'A API devolveu uma resposta inesperada.')
}
