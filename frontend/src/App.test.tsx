import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

function respostaJson(corpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('mostra o nome do sistema, sem marca de clube', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))

    render(<App />)

    expect(screen.getByRole('heading', { name: 'Club Manager' })).toBeInTheDocument()
  })

  it('avisa que está verificando enquanto a API não responde', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))

    render(<App />)

    expect(screen.getByRole('status')).toHaveTextContent('Verificando a API')
  })

  it('mostra que a API está no ar quando a saúde responde ok', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respostaJson({ status: 'ok', database: 'ok' })))

    render(<App />)

    expect(await screen.findByText('API no ar')).toBeInTheDocument()
  })

  it('mostra que a API está indisponível quando a saúde responde 503', async () => {
    const corpo = { status: 'unavailable', database: 'unavailable' }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respostaJson(corpo, 503)))

    render(<App />)

    expect(await screen.findByText('API indisponível')).toBeInTheDocument()
  })

  it('mostra que a API está indisponível quando a rede falha', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    render(<App />)

    expect(await screen.findByText('API indisponível')).toBeInTheDocument()
  })
})
