import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiGet } from './client'

function respostaJson(corpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('apiGet', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('chama a API versionada e devolve o corpo', async () => {
    const fetchFalso = vi.fn().mockResolvedValue(respostaJson({ status: 'ok' }))
    vi.stubGlobal('fetch', fetchFalso)

    const corpo = await apiGet<{ status: string }>('/health/')

    expect(corpo).toEqual({ status: 'ok' })
    expect(fetchFalso).toHaveBeenCalledWith(
      '/api/v1/health/',
      expect.objectContaining({ headers: expect.objectContaining({ Accept: 'application/json' }) }),
    )
  })

  it('transforma o envelope de erro da API em ApiError, com o código estável', async () => {
    const envelope = {
      error: { code: 'NAO_ESTA_EM_ANALISE', message: 'A solicitação não está em análise.', details: null },
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respostaJson(envelope, 422)))

    const erro = await apiGet('/qualquer/').catch((e: unknown) => e)

    expect(erro).toBeInstanceOf(ApiError)
    expect(erro).toMatchObject({
      status: 422,
      code: 'NAO_ESTA_EM_ANALISE',
      message: 'A solicitação não está em análise.',
    })
  })

  it('usa um código genérico quando a resposta de erro não tem envelope', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>502</html>', { status: 502 })))

    const erro = await apiGet('/qualquer/').catch((e: unknown) => e)

    expect(erro).toMatchObject({ status: 502, code: 'UNEXPECTED_RESPONSE' })
  })

  it('usa o código NETWORK_ERROR quando a API não responde', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    const erro = await apiGet('/qualquer/').catch((e: unknown) => e)

    expect(erro).toMatchObject({ status: 0, code: 'NETWORK_ERROR' })
  })
})
