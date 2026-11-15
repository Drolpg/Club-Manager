import { useEffect, useId, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { PERM_GASTOS_APROVAR, financeiro, type ReferenciasGastos } from '../api/financeiro'
import { Alerta, Campo, Pagina, Selecao } from '../componentes'
import { errosPorCampo, mensagemDoErro } from '../mensagens'
import { useSessao } from '../sessao'
import { usePodeFinanceiro } from '../useFinanceiro'
import { ListaDeItensEditavel, type ItemEditavel } from './apoioSaidas'

/** Formulário estruturado para abrir solicitação de gasto no motor de aprovações (CA-01, CA-02, CA-04). */
export function NovaSolicitacaoDeGasto() {
  const navigate = useNavigate()
  const { usuario } = useSessao()
  const podeAprovar = usePodeFinanceiro(PERM_GASTOS_APROVAR)
  const fileId = useId()

  const [refs, definirRefs] = useState<ReferenciasGastos | null>(null)
  const [descricao, definirDescricao] = useState('')
  const [categoriaId, definirCategoriaId] = useState('')
  const [setorId, definirSetorId] = useState('')
  const [itens, definirItens] = useState<ItemEditavel[]>([{ chave: 1, descricao: '', valor: '' }])
  const [arquivoCotacao, definirArquivoCotacao] = useState<File | null>(null)
  const [aprovadorId, definirAprovadorId] = useState('')
  const [enviando, definirEnviando] = useState(false)
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    let vivo = true
    financeiro
      .referenciasGastos()
      .then((dados) => vivo && definirRefs(dados))
      .catch((falha) => vivo && definirErro(falha))
    return () => {
      vivo = false
    }
  }, [])

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    definirErro(null)
    definirEnviando(true)
    try {
      let cotacaoId: string | null = null
      if (arquivoCotacao) {
        const cotacao = await financeiro.enviarCotacao(arquivoCotacao)
        cotacaoId = cotacao.id
      }
      const payload = {
        descricao,
        categoria_id: categoriaId,
        setor_id: setorId,
        itens: itens.map((it) => ({ descricao: it.descricao, valor: it.valor })),
        cotacao_id: cotacaoId,
        ...(aprovadorId ? { aprovador_indicado_id: aprovadorId } : {}),
      }
      const criada = await financeiro.abrirGasto(payload)
      void navigate(`/solicitacoes/${criada.id}`)
    } catch (falha) {
      definirErro(falha)
    } finally {
      definirEnviando(false)
    }
  }

  const campos = errosPorCampo(erro)
  const aprovadoresElegiveis = (refs?.aprovadores_gastos ?? []).filter((a) => a.id !== usuario?.id)
  const mostrarAprovador = podeAprovar || !!usuario?.admin

  return (
    <Pagina titulo="Pedir gasto">
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      <form aria-label="Nova solicitação de gasto" onSubmit={(e) => void enviar(e)}>
        <Campo rotulo="Descrição geral" value={descricao} aoMudar={definirDescricao} erros={campos.descricao} />
        <Selecao rotulo="Categoria de saída" value={categoriaId} aoMudar={definirCategoriaId}>
          <option value="">Escolha a categoria</option>
          {(refs?.categorias_saida ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.nome}
            </option>
          ))}
        </Selecao>
        {campos.categoria_id?.map((msg) => (
          <p key={msg} className="erro-de-campo">
            {msg}
          </p>
        ))}

        <Selecao rotulo="Setor" value={setorId} aoMudar={definirSetorId}>
          <option value="">Escolha o setor</option>
          {(refs?.setores ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.nome}
            </option>
          ))}
        </Selecao>
        {campos.setor_id?.map((msg) => (
          <p key={msg} className="erro-de-campo">
            {msg}
          </p>
        ))}

        <ListaDeItensEditavel itens={itens} aoMudar={definirItens} erros={campos.itens} />

        <div className="campo">
          <label htmlFor={fileId}>Cotação (PDF ou imagem, opcional)</label>
          <input
            id={fileId}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.webp"
            onChange={(e) => definirArquivoCotacao(e.target.files?.[0] ?? null)}
          />
          {campos.cotacao_id?.map((msg) => (
            <p key={msg} className="erro-de-campo">
              {msg}
            </p>
          ))}
        </div>

        {mostrarAprovador && (
          <Selecao rotulo="Aprovador indicado (opcional)" value={aprovadorId} aoMudar={definirAprovadorId}>
            <option value="">Qualquer aprovador</option>
            {aprovadoresElegiveis.map((a) => (
              <option key={a.id} value={a.id}>
                {a.nome}
              </option>
            ))}
          </Selecao>
        )}

        <button type="submit" disabled={enviando}>
          Enviar solicitação
        </button>
      </form>
    </Pagina>
  )
}
