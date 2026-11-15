import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { acesso, type Usuario } from '../api/acesso'
import {
  PERM_COBRANCAS_CRIAR,
  financeiro,
  type Categoria,
  type ChavePix,
  type CobrancaItem,
  type FiltrosCobrancas,
} from '../api/financeiro'
import { Alerta, Campo, Pagina, Selecao } from '../componentes'
import { dataCurta, reais } from '../formatos'
import { SITUACAO_DA_COBRANCA, errosPorCampo, mensagemDoErro } from '../mensagens'
import { useSessao } from '../sessao'
import { usePodeFinanceiro } from '../useFinanceiro'

function FormularioAvulso({
  categorias,
  chaves,
  usuarios,
  ehAdmin,
  aoCriar,
}: {
  categorias: Categoria[]
  chaves: ChavePix[]
  usuarios: Usuario[]
  ehAdmin: boolean
  aoCriar: () => void
}) {
  const [devedorId, definirDevedorId] = useState('')
  const [categoriaId, definirCategoriaId] = useState('')
  const [descricao, definirDescricao] = useState('')
  const [valor, definirValor] = useState('')
  const [vencimento, definirVencimento] = useState('')
  const [limite, definirLimite] = useState('30')
  const [chavePixId, definirChavePixId] = useState('')
  const [erro, definirErro] = useState<unknown>(null)
  const campos = errosPorCampo(erro)

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    definirErro(null)
    try {
      await financeiro.criarCobranca({
        devedor_id: devedorId,
        categoria_id: categoriaId,
        descricao,
        valor,
        vencimento,
        limite_de_inadimplencia: Number(limite) || 30,
        ...(chavePixId ? { chave_pix_id: chavePixId } : {}),
      })
      definirDescricao('')
      definirValor('')
      aoCriar()
    } catch (falha) {
      definirErro(falha)
    }
  }

  return (
    <form aria-label="Nova cobrança avulsa" onSubmit={(e) => void enviar(e)}>
      <h3>Nova cobrança avulsa</h3>
      {ehAdmin ? (
        <Selecao rotulo="Devedor" value={devedorId} aoMudar={definirDevedorId}>
          <option value="">Escolha o diretor</option>
          {usuarios
            .filter((u) => u.situacao === 'ATIVO')
            .map((u) => (
              <option key={u.id} value={u.id}>
                {u.nome}
              </option>
            ))}
        </Selecao>
      ) : (
        <Campo rotulo="Devedor" value={devedorId} aoMudar={definirDevedorId} erros={campos.devedor_id} />
      )}
      <Selecao rotulo="Categoria" value={categoriaId} aoMudar={definirCategoriaId}>
        <option value="">Escolha a categoria</option>
        {categorias.map((c) => (
          <option key={c.id} value={c.id}>
            {c.nome}
          </option>
        ))}
      </Selecao>
      <Campo rotulo="Descrição" value={descricao} aoMudar={definirDescricao} erros={campos.descricao} />
      <Campo
        rotulo="Valor (R$)"
        inputMode="decimal"
        placeholder="0.00"
        value={valor}
        aoMudar={definirValor}
        erros={campos.valor}
      />
      <Campo rotulo="Vencimento" type="date" value={vencimento} aoMudar={definirVencimento} erros={campos.vencimento} />
      <Campo rotulo="Limite de inadimplência (dias)" type="number" value={limite} aoMudar={definirLimite} />
      <Selecao rotulo="Chave Pix (opcional)" value={chavePixId} aoMudar={definirChavePixId}>
        <option value="">Chave padrão do clube</option>
        {chaves.map((c) => (
          <option key={c.id} value={c.id}>
            {c.chave}
          </option>
        ))}
      </Selecao>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      <button type="submit">Criar cobrança</button>
    </form>
  )
}

function FormularioLote({
  categorias,
  aoCriar,
}: {
  categorias: Categoria[]
  aoCriar: () => void
}) {
  const [todos, definirTodos] = useState(false)
  const [idsTexto, definirIdsTexto] = useState('')
  const [categoriaId, definirCategoriaId] = useState('')
  const [descricao, definirDescricao] = useState('')
  const [valor, definirValor] = useState('')
  const [vencimento, definirVencimento] = useState('')
  const [erro, definirErro] = useState<unknown>(null)
  const campos = errosPorCampo(erro)

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    definirErro(null)
    try {
      const devedorIds = todos
        ? []
        : idsTexto
            .split(',')
            .map((s) => s.trim())
            .filter(Boolean)
      await financeiro.criarCobrancasEmLote({
        devedor_ids: devedorIds,
        todos_ativos_com_cargo: todos,
        categoria_id: categoriaId,
        descricao,
        valor,
        vencimento,
        limite_de_inadimplencia: 30,
      })
      definirDescricao('')
      definirValor('')
      aoCriar()
    } catch (falha) {
      definirErro(falha)
    }
  }

  return (
    <form aria-label="Cobrança em lote" onSubmit={(e) => void enviar(e)}>
      <h3>Cobrança em lote</h3>
      <label className="opcao">
        <input type="checkbox" checked={todos} onChange={(e) => definirTodos(e.target.checked)} />
        Todos os diretores ativos com cargo
      </label>
      {!todos && (
        <Campo
          rotulo="IDs dos devedores (separados por vírgula)"
          value={idsTexto}
          aoMudar={definirIdsTexto}
          erros={campos.devedor_ids}
        />
      )}
      <Selecao rotulo="Categoria" value={categoriaId} aoMudar={definirCategoriaId}>
        <option value="">Escolha a categoria</option>
        {categorias.map((c) => (
          <option key={c.id} value={c.id}>
            {c.nome}
          </option>
        ))}
      </Selecao>
      <Campo rotulo="Descrição" value={descricao} aoMudar={definirDescricao} erros={campos.descricao} />
      <Campo rotulo="Valor (R$)" inputMode="decimal" value={valor} aoMudar={definirValor} erros={campos.valor} />
      <Campo rotulo="Vencimento" type="date" value={vencimento} aoMudar={definirVencimento} erros={campos.vencimento} />
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      <button type="submit">Criar em lote</button>
    </form>
  )
}

/** Lista geral das cobranças do clube para gestão e criação (avulsa e em lote). */
export function Cobrancas() {
  const { usuario } = useSessao()
  const podeCriar = usePodeFinanceiro(PERM_COBRANCAS_CRIAR)
  const [filtros, definirFiltros] = useState<FiltrosCobrancas>({})
  const [categorias, definirCategorias] = useState<Categoria[]>([])
  const [chaves, definirChaves] = useState<ChavePix[]>([])
  const [usuarios, definirUsuarios] = useState<Usuario[]>([])
  const [itens, definirItens] = useState<CobrancaItem[]>([])
  const [temMais, definirTemMais] = useState(false)
  const [carregada, definirCarregada] = useState(false)
  const [recarga, definirRecarga] = useState(0)
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    financeiro.categorias({ natureza: 'ENTRADA' }).then(definirCategorias).catch(() => undefined)
    financeiro.chavesPix().then(definirChaves).catch(() => undefined)
    if (usuario?.admin) {
      acesso.usuarios().then(definirUsuarios).catch(() => undefined)
    }
  }, [usuario?.admin])

  useEffect(() => {
    let vivo = true
    financeiro
      .cobrancas(filtros)
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
  }, [filtros, recarga])

  async function carregarMais() {
    const ultimo = itens[itens.length - 1]
    if (!ultimo) return
    try {
      const pagina = await financeiro.cobrancas({ ...filtros, antes: ultimo.id })
      definirItens((atuais) => [...atuais, ...pagina.itens])
      definirTemMais(pagina.tem_mais)
    } catch (falha) {
      definirErro(falha)
    }
  }

  return (
    <Pagina titulo="Cobranças">
      <form aria-label="Filtrar cobranças" onSubmit={(e) => e.preventDefault()}>
        <Selecao
          rotulo="Situação"
          value={filtros.situacao ?? ''}
          aoMudar={(situacao) => definirFiltros({ ...filtros, situacao: situacao || undefined })}
        >
          <option value="">Todas</option>
          {Object.entries(SITUACAO_DA_COBRANCA).map(([codigo, rotulo]) => (
            <option key={codigo} value={codigo}>
              {rotulo}
            </option>
          ))}
        </Selecao>
        <Selecao
          rotulo="Categoria"
          value={filtros.categoria_id ?? ''}
          aoMudar={(categoria_id) =>
            definirFiltros({ ...filtros, categoria_id: categoria_id || undefined })
          }
        >
          <option value="">Todas</option>
          {categorias.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nome}
            </option>
          ))}
        </Selecao>
        <Campo
          rotulo="De"
          type="date"
          value={filtros.de ?? ''}
          aoMudar={(de) => definirFiltros({ ...filtros, de: de || undefined })}
        />
        <Campo
          rotulo="Até"
          type="date"
          value={filtros.ate ?? ''}
          aoMudar={(ate) => definirFiltros({ ...filtros, ate: ate || undefined })}
        />
        <label className="opcao">
          <input
            type="checkbox"
            checked={!!filtros.inadimplentes}
            onChange={(e) => definirFiltros({ ...filtros, inadimplentes: e.target.checked || undefined })}
          />
          Só inadimplentes
        </label>
      </form>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {carregada && itens.length === 0 && <p>Nenhuma cobrança encontrada.</p>}
      {itens.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Descrição</th>
              <th>Devedor</th>
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
                <td>{item.devedor.nome}</td>
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
      {podeCriar && (
        <section aria-label="Criar cobranças">
          <FormularioAvulso
            categorias={categorias}
            chaves={chaves}
            usuarios={usuarios}
            ehAdmin={!!usuario?.admin}
            aoCriar={() => definirRecarga((r) => r + 1)}
          />
          <FormularioLote categorias={categorias} aoCriar={() => definirRecarga((r) => r + 1)} />
        </section>
      )}
    </Pagina>
  )
}
