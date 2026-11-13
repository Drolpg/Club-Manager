import { useCallback, useEffect, useState } from 'react'

/** Carrega uma lista da API e permite recarregar depois de uma ação. */
export function useLista<T>(carregar: () => Promise<T[]>) {
  const [itens, definirItens] = useState<T[]>([])
  const [erro, definirErro] = useState<unknown>(null)
  const recarregar = useCallback(() => {
    carregar().then(definirItens).catch(definirErro)
  }, [carregar])
  useEffect(recarregar, [recarregar])
  return { itens, erro, definirErro, recarregar }
}
