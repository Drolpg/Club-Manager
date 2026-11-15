import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { financeiro, type CobrancaItem, type FiltrosMinhasCobrancas } from '../api/financeiro'
import { Alerta, Pagina, Selecao } from '../componentes'
import { dataCurta, reais } from '../formatos'
import { SITUACAO_DA_COBRANCA, mensagemDoErro } from '../mensagens'

/** Lista as cobranças do usuário autenticado, inclusive diretores sem cargo. */
export function MinhasCobrancas() {
  const [situacao, definirSituacao] = useState('')
  const [itens, definirItens] = useState<CobrancaItem[]>([])
  const [temMais, definirTemMais] = useState(false)
  const [carregada, definirCarregada] = useState(false)
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    let vivo = true
    const filtros: FiltrosMinhasCobrancas = situacao ? { situacao } : {}
    financeiro
      .minhasCobrancas(filtros)
      .then((pagina) => {
        if (!vivo) return
        definirItens(pagina.itens)
        definirTemMais(pagina.tem_mais)
        definirErro(null)
        definirCarregada(true)
      })
      .catch((falha) => vivo && definirErro(falha))
    return () => {
      vivo = false
    }
  }, [situacao])

  async function carregarMais() {
    const ultimo = itens[itens.length - 1]
    if (!ultimo) return
    try {
      const pagina = await financeiro.minhasCobrancas({
        ...(situacao ? { situacao } : {}),
        antes: ultimo.id,
      })
      definirItens((atuais) => [...atuais, ...pagina.itens])
      definirTemMais(pagina.tem_mais)
    } catch (falha) {
      definirErro(falha)
    }
  }

  return (
    <Pagina titulo="Minhas cobranças">
      <form aria-label="Filtrar minhas cobranças" onSubmit={(e) => e.preventDefault()}>
        <Selecao rotulo="Situação" value={situacao} aoMudar={definirSituacao}>
          <option value="">Todas</option>
          {Object.entries(SITUACAO_DA_COBRANCA).map(([codigo, rotulo]) => (
            <option key={codigo} value={codigo}>
              {rotulo}
            </option>
          ))}
        </Selecao>
      </form>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {carregada && itens.length === 0 && <p>Nenhuma cobrança encontrada.</p>}
      {itens.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Descrição</th>
              <th>Categoria</th>
              <th>Valor</th>
              <th>Vencimento</th>
              <th>Situação</th>
            </tr>
          </thead>
          <tbody>
            {itens.map((item) => (
              <tr key={item.id}>
                <td>
                  <Link to={`/cobrancas/${item.id}`}>{item.descricao}</Link>
                </td>
                <td>{item.categoria_nome}</td>
                <td>{reais(item.valor)}</td>
                <td>{dataCurta(item.vencimento)}</td>
                <td>{SITUACAO_DA_COBRANCA[item.situacao] ?? item.situacao}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {temMais && (
        <button type="button" onClick={() => void carregarMais()}>
          Carregar mais
        </button>
      )}
    </Pagina>
  )
}
