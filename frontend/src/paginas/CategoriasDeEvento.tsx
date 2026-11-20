import { useEffect, useState, type FormEvent } from 'react'
import { eventos, type CategoriaDeEvento } from '../api/eventos'
import { Alerta, Campo, Pagina } from '../componentes'
import { mensagemDoErro } from '../mensagens'

function Linha({
  categoria,
  aoMudar,
  aoErrar,
}: {
  categoria: CategoriaDeEvento
  aoMudar: (nova: CategoriaDeEvento) => void
  aoErrar: (erro: unknown) => void
}) {
  const [nome, definirNome] = useState(categoria.nome)

  async function executar(acao: () => Promise<CategoriaDeEvento>) {
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
      <button type="button" onClick={() => void executar(() => eventos.editarCategoria(categoria.id, nome))}>
        Renomear
      </button>
      {categoria.ativa ? (
        <button type="button" onClick={() => void executar(() => eventos.desativarCategoria(categoria.id))}>
          Desativar
        </button>
      ) : (
        <button type="button" onClick={() => void executar(() => eventos.reativarCategoria(categoria.id))}>
          Reativar
        </button>
      )}
    </li>
  )
}

/** CA-01: só o admin mantém as categorias de evento; usada, é desativada, nunca apagada (RN-018). */
export function CategoriasDeEvento() {
  const [categorias, definirCategorias] = useState<CategoriaDeEvento[]>([])
  const [nova, definirNova] = useState('')
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    eventos
      .categorias(true)
      .then(definirCategorias)
      .catch((e: unknown) => definirErro(e))
  }, [])

  function substituir(atualizada: CategoriaDeEvento) {
    definirCategorias(categorias.map((c) => (c.id === atualizada.id ? atualizada : c)))
  }

  async function criar(formulario: FormEvent) {
    formulario.preventDefault()
    definirErro(null)
    try {
      const criada = await eventos.criarCategoria(nova)
      definirCategorias([...categorias, criada])
      definirNova('')
    } catch (e) {
      definirErro(e)
    }
  }

  return (
    <Pagina titulo="Categorias de evento">
      <form aria-label="Nova categoria de evento" onSubmit={(formulario) => void criar(formulario)}>
        <Campo rotulo="Nova categoria" value={nova} aoMudar={definirNova} />
        <button type="submit">Criar categoria</button>
      </form>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      <ul className="lista">
        {categorias.map((categoria) => (
          <Linha key={categoria.id} categoria={categoria} aoMudar={substituir} aoErrar={definirErro} />
        ))}
      </ul>
    </Pagina>
  )
}
