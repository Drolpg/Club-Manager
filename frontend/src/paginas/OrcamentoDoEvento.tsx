import { useEffect, useState, type FormEvent } from 'react'
import { eventos, type DetalheDoEvento } from '../api/eventos'
import { financeiro, type ReferenciasGastos } from '../api/financeiro'
import { Alerta, Campo, Selecao } from '../componentes'
import { errosPorCampo, mensagemDoErro } from '../mensagens'
import { ListaDeItensEditavel, type ItemEditavel } from './apoioSaidas'

/** RF-086: quem aprova eventos abre o orçamento, uma solicitação de gasto ligada ao evento. Sugere a descrição
 * "Orçamento: <título>" e a categoria de saída "Eventos". */
export function OrcamentoDoEvento({
  evento,
  aoConcluir,
}: {
  evento: DetalheDoEvento
  aoConcluir: (novo: DetalheDoEvento) => void
}) {
  const [referencias, definirReferencias] = useState<ReferenciasGastos | null>(null)
  const [descricao, definirDescricao] = useState(`Orçamento: ${evento.titulo}`)
  const [categoria, definirCategoria] = useState('')
  const [setor, definirSetor] = useState('')
  const [itens, definirItens] = useState<ItemEditavel[]>([{ chave: 1, descricao: '', valor: '' }])
  const [erro, definirErro] = useState<unknown>(null)
  const campos = errosPorCampo(erro)

  useEffect(() => {
    financeiro
      .referenciasGastos()
      .then((dados) => {
        definirReferencias(dados)
        const deEventos = dados.categorias_saida.find((c) => c.nome === 'Eventos') ?? dados.categorias_saida[0]
        if (deEventos) definirCategoria(deEventos.id)
      })
      .catch((e: unknown) => definirErro(e))
  }, [])

  async function enviar(formulario: FormEvent) {
    formulario.preventDefault()
    definirErro(null)
    try {
      const novo = await eventos.abrirOrcamento(evento.id, {
        descricao,
        categoria_id: categoria,
        setor_id: setor,
        itens: itens.map((item) => ({ descricao: item.descricao, valor: item.valor })),
      })
      aoConcluir(novo)
    } catch (e) {
      definirErro(e)
    }
  }

  return (
    <form aria-label="Abrir orçamento" onSubmit={(formulario) => void enviar(formulario)}>
      <h3>Abrir orçamento</h3>
      <Campo rotulo="Descrição do orçamento" value={descricao} erros={campos.descricao} aoMudar={definirDescricao} />
      <Selecao rotulo="Categoria de saída" value={categoria} aoMudar={definirCategoria}>
        {referencias?.categorias_saida.map((c) => (
          <option key={c.id} value={c.id}>
            {c.nome}
          </option>
        ))}
      </Selecao>
      <Selecao rotulo="Setor" value={setor} aoMudar={definirSetor}>
        <option value="">Escolha</option>
        {referencias?.setores.map((s) => (
          <option key={s.id} value={s.id}>
            {s.nome}
          </option>
        ))}
      </Selecao>
      <ListaDeItensEditavel itens={itens} aoMudar={definirItens} erros={campos.itens} />
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      <button type="submit">Abrir orçamento</button>
    </form>
  )
}
