import { useEffect, useState } from 'react'
import { aprovacoes, type Motivo } from './api/aprovacoes'
import { useSessao } from './sessao'
import { temPermissao, useMinhasDaMoldura } from './useMinhas'

export function usePodeFinanceiro(permissao: string): boolean {
  const { usuario } = useSessao()
  const { detalhe } = useMinhasDaMoldura()
  return !!usuario?.admin || temPermissao(detalhe, permissao)
}

export function useMotivosPorTipo(tipoDeDecisao: string | null): Motivo[] {
  const [motivos, definirMotivos] = useState<Motivo[]>([])
  useEffect(() => {
    if (!tipoDeDecisao) return
    let vivo = true
    aprovacoes
      .motivos(tipoDeDecisao)
      .then((lista) => vivo && definirMotivos(lista))
      .catch(() => undefined)
    return () => {
      vivo = false
    }
  }, [tipoDeDecisao])
  return tipoDeDecisao ? motivos : []
}
