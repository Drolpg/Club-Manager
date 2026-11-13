import { useEffect, useState } from 'react'
import { permissoes, type DetalheDoUsuario } from './api/permissoes'

/** Permissão de gerenciar convites, a mesma do catálogo da API. */
export const CONVITES_GERENCIAR = 'convites.gerenciar'

export function temPermissao(detalhe: DetalheDoUsuario | null, codigo: string): boolean {
  return detalhe?.permissoes.some((p) => p.codigo === codigo) ?? false
}

/**
 * Cargo, setores e permissões de quem está logado, de `GET permissoes/minhas/`. Com `ativo` falso não consulta.
 * `carregando` é verdadeiro até a resposta chegar (ou falhar).
 */
export function useMinhas(ativo: boolean) {
  const [detalhe, definirDetalhe] = useState<DetalheDoUsuario | null>(null)
  const [erro, definirErro] = useState<unknown>(null)
  const [concluido, definirConcluido] = useState(false)

  useEffect(() => {
    if (!ativo) return
    let vivo = true
    permissoes
      .minhas()
      .then((resposta) => vivo && definirDetalhe(resposta))
      .catch((falha) => vivo && definirErro(falha))
      .finally(() => vivo && definirConcluido(true))
    return () => {
      vivo = false
    }
  }, [ativo])

  return { detalhe, erro, carregando: ativo && !concluido }
}
