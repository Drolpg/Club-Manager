import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import {
  financeiro,
  type Categoria,
  type ChavePix,
  type NaturezaCategoria,
  type TipoChavePix,
} from '../api/financeiro'
import { Alerta, Campo, Pagina, Selecao } from '../componentes'
import { TIPO_DE_CHAVE_PIX, errosPorCampo, mensagemDoErro } from '../mensagens'

function LinhaCategoria({
  categoria,
  executar,
}: {
  categoria: Categoria
  executar: (acao: () => Promise<unknown>) => Promise<boolean>
}) {
  const [editando, definirEditando] = useState(false)
  const [nome, definirNome] = useState(categoria.nome)

  async function salvar(evento: FormEvent) {
    evento.preventDefault()
    if (await executar(() => financeiro.renomearCategoria(categoria.id, nome))) definirEditando(false)
  }

  return (
    <li>
      {editando ? (
        <form onSubmit={(e) => void salvar(e)}>
          <Campo
            rotulo="Novo nome da categoria"
            value={nome}
            aoMudar={definirNome}
            maxLength={80}
          />
          <button type="submit">Salvar nome</button>
          <button type="button" onClick={() => definirEditando(false)}>
            Desistir
          </button>
        </form>
      ) : (
        <>
          <span>
            {categoria.nome} ({categoria.natureza === 'ENTRADA' ? 'Entrada' : 'Saída'})
          </span>{' '}
          {!categoria.ativa && <span className="selo">Inativa</span>}{' '}
          <button
            type="button"
            onClick={() => {
              definirNome(categoria.nome)
              definirEditando(true)
            }}
          >
            Renomear
          </button>{' '}
          {categoria.ativa ? (
            <button
              type="button"
              onClick={() => void executar(() => financeiro.desativarCategoria(categoria.id))}
            >
              Desativar
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void executar(() => financeiro.reativarCategoria(categoria.id))}
            >
              Reativar
            </button>
          )}
        </>
      )}
    </li>
  )
}

function LinhaChavePix({
  chave,
  executar,
}: {
  chave: ChavePix
  executar: (acao: () => Promise<unknown>) => Promise<boolean>
}) {
  const [editando, definirEditando] = useState(false)
  const [tipo, definirTipo] = useState<TipoChavePix>(chave.tipo)
  const [valor, definirValor] = useState(chave.chave)
  const [recebedor, definirRecebedor] = useState(chave.nome_recebedor)
  const [cidade, definirCidade] = useState(chave.cidade)

  async function salvar(evento: FormEvent) {
    evento.preventDefault()
    const ok = await executar(() =>
      financeiro.editarChavePix(chave.id, { tipo, chave: valor, nome_recebedor: recebedor, cidade }),
    )
    if (ok) definirEditando(false)
  }

  return (
    <li>
      {editando ? (
        <form onSubmit={(e) => void salvar(e)}>
          <Selecao rotulo="Tipo da chave" value={tipo} aoMudar={(v) => definirTipo(v as TipoChavePix)}>
            {Object.entries(TIPO_DE_CHAVE_PIX).map(([codigo, rotulo]) => (
              <option key={codigo} value={codigo}>
                {rotulo}
              </option>
            ))}
          </Selecao>
          <Campo rotulo="Chave" value={valor} aoMudar={definirValor} maxLength={140} />
          <Campo rotulo="Nome do recebedor" value={recebedor} aoMudar={definirRecebedor} maxLength={100} />
          <Campo rotulo="Cidade" value={cidade} aoMudar={definirCidade} maxLength={60} />
          <button type="submit">Salvar chave</button>
          <button type="button" onClick={() => definirEditando(false)}>
            Desistir
          </button>
        </form>
      ) : (
        <>
          <span>
            {TIPO_DE_CHAVE_PIX[chave.tipo] ?? chave.tipo}: {chave.chave} — {chave.nome_recebedor} (
            {chave.cidade})
          </span>{' '}
          {chave.padrao && <span className="selo">Padrão</span>}{' '}
          {!chave.ativa && <span className="selo">Inativa</span>}{' '}
          <button type="button" onClick={() => definirEditando(true)}>
            Editar
          </button>{' '}
          {!chave.padrao && chave.ativa && (
            <button
              type="button"
              onClick={() => void executar(() => financeiro.marcarChavePixPadrao(chave.id))}
            >
              Marcar padrão
            </button>
          )}{' '}
          {chave.ativa ? (
            <button
              type="button"
              onClick={() => void executar(() => financeiro.desativarChavePix(chave.id))}
            >
              Desativar
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void executar(() => financeiro.reativarChavePix(chave.id))}
            >
              Reativar
            </button>
          )}
        </>
      )}
    </li>
  )
}

/** Cadastro administrativo de categorias financeiras e chaves Pix com aviso de LGPD para CPF. */
export function ConfiguracaoFinanceira() {
  const [categorias, definirCategorias] = useState<Categoria[]>([])
  const [chaves, definirChaves] = useState<ChavePix[]>([])
  const [erro, definirErro] = useState<unknown>(null)

  const [nomeCat, definirNomeCat] = useState('')
  const [naturezaCat, definirNaturezaCat] = useState<NaturezaCategoria>('ENTRADA')

  const [tipoPix, definirTipoPix] = useState<TipoChavePix>('EMAIL')
  const [valorPix, definirValorPix] = useState('')
  const [recebedorPix, definirRecebedorPix] = useState('')
  const [cidadePix, definirCidadePix] = useState('')
  const [padraoPix, definirPadraoPix] = useState(false)

  const recarregar = useCallback(() => {
    Promise.all([financeiro.categorias({ todas: true }), financeiro.chavesPix({ todas: true })])
      .then(([cats, pix]) => {
        definirCategorias(cats)
        definirChaves(pix)
      })
      .catch(definirErro)
  }, [])

  useEffect(recarregar, [recarregar])

  async function executar(acao: () => Promise<unknown>): Promise<boolean> {
    definirErro(null)
    try {
      await acao()
      recarregar()
      return true
    } catch (falha) {
      definirErro(falha)
      return false
    }
  }

  async function criarCategoria(evento: FormEvent) {
    evento.preventDefault()
    if (await executar(() => financeiro.criarCategoria(nomeCat, naturezaCat))) definirNomeCat('')
  }

  async function criarChavePix(evento: FormEvent) {
    evento.preventDefault()
    const ok = await executar(() =>
      financeiro.criarChavePix({
        tipo: tipoPix,
        chave: valorPix,
        nome_recebedor: recebedorPix,
        cidade: cidadePix,
        padrao: padraoPix,
      }),
    )
    if (ok) {
      definirValorPix('')
      definirPadraoPix(false)
    }
  }

  const campos = errosPorCampo(erro)
  return (
    <Pagina titulo="Configuração financeira">
      <Link to="/">Voltar</Link>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>

      <section aria-label="Categorias financeiras">
        <h2>Categorias financeiras</h2>
        <form aria-label="Nova categoria" onSubmit={(e) => void criarCategoria(e)}>
          <Campo rotulo="Nome" value={nomeCat} aoMudar={definirNomeCat} erros={campos.nome} maxLength={80} />
          <Selecao
            rotulo="Natureza"
            value={naturezaCat}
            aoMudar={(v) => definirNaturezaCat(v as NaturezaCategoria)}
          >
            <option value="ENTRADA">Entrada</option>
            <option value="SAIDA">Saída</option>
          </Selecao>
          <button type="submit">Criar categoria</button>
        </form>
        <ul>
          {categorias.map((c) => (
            <LinhaCategoria key={c.id} categoria={c} executar={executar} />
          ))}
        </ul>
      </section>

      <section aria-label="Chaves Pix">
        <h2>Chaves Pix</h2>
        <form aria-label="Nova chave Pix" onSubmit={(e) => void criarChavePix(e)}>
          <Selecao
            rotulo="Tipo da chave"
            value={tipoPix}
            aoMudar={(v) => definirTipoPix(v as TipoChavePix)}
          >
            {Object.entries(TIPO_DE_CHAVE_PIX).map(([codigo, rotulo]) => (
              <option key={codigo} value={codigo}>
                {rotulo}
              </option>
            ))}
          </Selecao>
          {tipoPix === 'CPF' && (
            <p className="aviso">
              Atenção (LGPD): o CPF cadastrado como chave Pix é um dado pessoal do titular exibido nas
              cobranças para pagamento. Prefira CNPJ do clube, e-mail institucional ou chave aleatória.
            </p>
          )}
          <Campo rotulo="Chave" value={valorPix} aoMudar={definirValorPix} erros={campos.chave} maxLength={140} />
          <Campo
            rotulo="Nome do recebedor"
            value={recebedorPix}
            aoMudar={definirRecebedorPix}
            erros={campos.nome_recebedor}
            maxLength={100}
          />
          <Campo rotulo="Cidade" value={cidadePix} aoMudar={definirCidadePix} erros={campos.cidade} maxLength={60} />
          <label className="opcao">
            <input
              type="checkbox"
              checked={padraoPix}
              onChange={(e) => definirPadraoPix(e.target.checked)}
            />
            Definir como chave padrão
          </label>
          <button type="submit">Cadastrar chave Pix</button>
        </form>
        <ul>
          {chaves.map((ch) => (
            <LinhaChavePix key={ch.id} chave={ch} executar={executar} />
          ))}
        </ul>
      </section>
    </Pagina>
  )
}
