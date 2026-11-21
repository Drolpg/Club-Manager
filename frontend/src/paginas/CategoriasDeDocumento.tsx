import { useEffect, useState, type FormEvent } from 'react'
import { ApiError } from '../api/client'
import { comunicacao, type CategoriaDeDocumento } from '../api/comunicacao'
import { Alerta, Campo, Pagina } from '../componentes'
import { mensagemDoErro } from '../mensagens'

// O texto geral do código `CATEGORIA_JA_EXISTE` fala de natureza (financeiro); aqui vale o da API.
function mensagem(erro: unknown): string {
  return erro instanceof ApiError && erro.code === 'CATEGORIA_JA_EXISTE' ? erro.message : mensagemDoErro(erro)
}

function Linha({
  categoria,
  aoMudar,
  aoErrar,
}: {
  categoria: CategoriaDeDocumento
  aoMudar: (nova: CategoriaDeDocumento) => void
  aoErrar: (erro: unknown) => void
}) {
  const [nome, definirNome] = useState(categoria.nome)

  async function executar(acao: () => Promise<CategoriaDeDocumento>) {
    aoErrar(null)
    try {
      aoMudar(await acao())
    } catch (e) {
      aoErrar(e)
    }
  }

  return (
    <li aria-label={categoria.nome}>
      <Campo rotulo={`Nome de ${categoria.nome}`} value={nome} aoMudar={definirNome} />
      {!categoria.ativa && <span className="selo">Inativa</span>}
      <button
        type="button"
        onClick={() => void executar(() => comunicacao.editarCategoria(categoria.id, nome))}
      >
        Renomear
      </button>
      {categoria.ativa ? (
        <button
          type="button"
          onClick={() => void executar(() => comunicacao.desativarCategoria(categoria.id))}
        >
          Desativar
        </button>
      ) : (
        <button
          type="button"
          onClick={() => void executar(() => comunicacao.reativarCategoria(categoria.id))}
        >
          Reativar
        </button>
      )}
    </li>
  )
}

/** CA-28: só o admin mantém as categorias de documento; usada, é desativada, nunca apagada (RN-018). */
export function CategoriasDeDocumento() {
  const [categorias, definirCategorias] = useState<CategoriaDeDocumento[]>([])
  const [nova, definirNova] = useState('')
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    comunicacao
      .categorias(true)
      .then(definirCategorias)
      .catch((e: unknown) => definirErro(e))
  }, [])

  function substituir(atualizada: CategoriaDeDocumento) {
    definirCategorias(categorias.map((c) => (c.id === atualizada.id ? atualizada : c)))
  }

  async function criar(formulario: FormEvent) {
    formulario.preventDefault()
    definirErro(null)
    try {
      const criada = await comunicacao.criarCategoria(nova)
      definirCategorias([...categorias, criada])
      definirNova('')
    } catch (e) {
      definirErro(e)
    }
  }

  return (
    <Pagina titulo="Categorias de documento">
      <form aria-label="Nova categoria de documento" onSubmit={(formulario) => void criar(formulario)}>
        <Campo rotulo="Nova categoria" value={nova} aoMudar={definirNova} />
        <button type="submit">Criar categoria</button>
      </form>
      <Alerta>{erro ? mensagem(erro) : null}</Alerta>
      <ul className="lista">
        {categorias.map((categoria) => (
          <Linha key={categoria.id} categoria={categoria} aoMudar={substituir} aoErrar={definirErro} />
        ))}
      </ul>
    </Pagina>
  )
}
