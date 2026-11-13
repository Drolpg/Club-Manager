import { useCallback, useEffect, useState } from 'react'
import { notificacoes, type Notificacao } from './api/notificacoes'

/**
 * A lista da caixa: a primeira página ao abrir, "carregar mais" pelo ID da última recebida, abrir uma
 * notificação e marcar todas como lidas. `aoMudar` avisa o sino de que a quantidade de não lidas mudou.
 */
export function useCaixa(aoMudar: () => void) {
  const [itens, definirItens] = useState<Notificacao[]>([])
  const [temMais, definirTemMais] = useState(false)
  const [carregando, definirCarregando] = useState(true)
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    let ativo = true
    notificacoes
      .caixa()
      .then((pagina) => {
        if (!ativo) return
        definirItens(pagina.itens)
        definirTemMais(pagina.tem_mais)
      })
      .catch((falha) => ativo && definirErro(falha))
      .finally(() => ativo && definirCarregando(false))
    return () => {
      ativo = false
    }
  }, [])

  const carregarMais = useCallback(async () => {
    const ultima = itens.at(-1)
    if (!ultima) return
    definirErro(null)
    try {
      const pagina = await notificacoes.caixa(ultima.id)
      definirItens((atuais) => [...atuais, ...pagina.itens])
      definirTemMais(pagina.tem_mais)
    } catch (falha) {
      definirErro(falha)
    }
  }, [itens])

  /** Marca como lida. Devolve se deu certo; se falhar, o erro fica na caixa e nada mais acontece. */
  const ler = useCallback(
    async (item: Notificacao): Promise<boolean> => {
      definirErro(null)
      try {
        const lida = await notificacoes.ler(item.id)
        definirItens((atuais) => atuais.map((i) => (i.id === lida.id ? lida : i)))
        aoMudar()
        return true
      } catch (falha) {
        definirErro(falha)
        return false
      }
    },
    [aoMudar],
  )

  const lerTodas = useCallback(async () => {
    definirErro(null)
    try {
      await notificacoes.lerTodas()
      const agora = new Date().toISOString()
      definirItens((atuais) => atuais.map((i) => ({ ...i, lida_em: i.lida_em ?? agora })))
      aoMudar()
    } catch (falha) {
      definirErro(falha)
    }
  }, [aoMudar])

  return { itens, temMais, carregando, erro, carregarMais, ler, lerTodas }
}
