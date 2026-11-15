import { urlCotacao, type ConteudoGasto, type EstornoResumo, type VisaoDoCaixa } from '../api/financeiro'
import { Campo } from '../componentes'
import { dataEHora, reais, somarCentavos } from '../formatos'

export interface ItemEditavel {
  chave: number
  descricao: string
  valor: string
}

/** Cartões consolidados do caixa: entradas validadas, saídas liquidadas e comprometido. */
export function CartoesDoCaixa({ caixa }: { caixa: VisaoDoCaixa }) {
  return (
    <section aria-label="Visão do caixa">
      <h2>Visão do caixa</h2>
      <dl>
        <dt>Entradas validadas</dt>
        <dd>{reais(caixa.total_entradas_validadas)}</dd>
        <dt>Saídas liquidadas</dt>
        <dd>{reais(caixa.total_saidas_liquidadas)}</dd>
        <dt>Comprometido</dt>
        <dd>{reais(caixa.total_comprometido)}</dd>
      </dl>
    </section>
  )
}

/** Bloco padronizado de resumo de estorno ligado a saída, entrada ou cobrança. */
export function BlocoEstorno({ estorno }: { estorno: EstornoResumo }) {
  return (
    <section aria-label="Estorno">
      <h2>Estorno</h2>
      <dl>
        <dt>Valor estornado</dt>
        <dd>{reais(estorno.valor)}</dd>
        <dt>Motivo</dt>
        <dd>{estorno.motivo_texto}</dd>
        <dt>Justificativa</dt>
        <dd>{estorno.justificativa}</dd>
        <dt>Registrado por</dt>
        <dd>
          {estorno.registrado_por.nome} em {dataEHora.format(new Date(estorno.registrado_em))}
        </dd>
      </dl>
    </section>
  )
}

/** Exibição estruturada do conteúdo de uma versão de `financeiro.gasto` (sempre como texto). */
export function DetalhesConteudoGasto({ conteudo }: { conteudo: ConteudoGasto }) {
  const total = somarCentavos(conteudo.itens.map((i) => i.valor))
  return (
    <div>
      <dl>
        <dt>Descrição</dt>
        <dd>{conteudo.descricao}</dd>
        <dt>Categoria</dt>
        <dd>{conteudo.categoria_nome || conteudo.categoria_id}</dd>
        <dt>Setor</dt>
        <dd>{conteudo.setor_nome || conteudo.setor_id}</dd>
        {conteudo.cotacao_id && (
          <>
            <dt>Cotação</dt>
            <dd>
              <a href={urlCotacao(conteudo.cotacao_id)} target="_blank" rel="noopener noreferrer">
                Abrir cotação{conteudo.cotacao_nome ? ` (${conteudo.cotacao_nome})` : ''}
              </a>
            </dd>
          </>
        )}
      </dl>
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Valor</th>
          </tr>
        </thead>
        <tbody>
          {conteudo.itens.map((item, idx) => (
            // Lista imutável vinda da versão persistida.
            // oxlint-disable-next-line react/no-array-index-key
            <tr key={`${item.descricao}-${idx}`}>
              <td>{item.descricao}</td>
              <td>{reais(item.valor)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th>Total</th>
            <td>{reais(total)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

/** Lista dinâmica de itens com adição/remoção e cálculo exato em tempo real. */
export function ListaDeItensEditavel({
  itens,
  aoMudar,
  erros,
}: {
  itens: ItemEditavel[]
  aoMudar: (novos: ItemEditavel[]) => void
  erros?: string[]
}) {
  const proximo = (itens.reduce((m, i) => Math.max(m, i.chave), 0) || 0) + 1
  const total = somarCentavos(itens.map((i) => i.valor))

  return (
    <fieldset>
      <legend>Itens do gasto</legend>
      {erros?.map((erro) => (
        <p key={erro} className="erro-de-campo">
          {erro}
        </p>
      ))}
      {itens.map((item, idx) => (
        <div key={item.chave}>
          <Campo
            rotulo={`Descrição do item ${idx + 1}`}
            value={item.descricao}
            aoMudar={(descricao) =>
              aoMudar(itens.map((it) => (it.chave === item.chave ? { ...it, descricao } : it)))
            }
          />
          <Campo
            rotulo={`Valor do item ${idx + 1} (R$)`}
            inputMode="decimal"
            placeholder="0.00"
            value={item.valor}
            aoMudar={(valor) =>
              aoMudar(itens.map((it) => (it.chave === item.chave ? { ...it, valor } : it)))
            }
          />
          {itens.length > 1 && (
            <button
              type="button"
              onClick={() => aoMudar(itens.filter((it) => it.chave !== item.chave))}
            >
              Remover item {idx + 1}
            </button>
          )}
        </div>
      ))}
      <button
        type="button"
        onClick={() => aoMudar([...itens, { chave: proximo, descricao: '', valor: '' }])}
      >
        Adicionar item
      </button>
      <p>Total calculado: {reais(total)}</p>
    </fieldset>
  )
}
