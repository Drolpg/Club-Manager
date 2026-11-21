import { useEffect, useId, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import {
  comunicacao,
  enderecoDoArquivo,
  type CategoriaDeDocumento,
  type Documento,
  type FiltrosDeDocumentos,
} from '../api/comunicacao'
import { Alerta, AreaDeTexto, Campo, Pagina, Selecao } from '../componentes'
import { dataCurta } from '../formatos'
import { SITUACAO_DO_DOCUMENTO, TIPO_DE_DOCUMENTO, errosPorCampo, mensagemDoErro } from '../mensagens'
import { useSessao } from '../sessao'
import {
  COMUNICACAO_ENVIAR_DOCUMENTOS,
  COMUNICACAO_REGISTRAR_ATAS,
  temPermissao,
  useMinhasDaMoldura,
} from '../useMinhas'
import { TextoLivre } from './apoioFeed'

const TIPOS_DE_ARQUIVO = '.pdf,.png,.jpg,.jpeg,.webp'

/** O documento fica visível a todos os diretores com cargo (Q3): o aviso vem antes do campo de arquivo. */
function AvisoDeDadoPessoal() {
  return (
    <p className="aviso-de-dado-pessoal">
      Este documento ficará visível a todos os diretores. Não envie dado pessoal desnecessário.
    </p>
  )
}

function CampoDeArquivo({
  erros,
  aoEscolher,
}: {
  erros?: string[]
  aoEscolher: (arquivo: File | null) => void
}) {
  const id = useId()
  return (
    <div className="campo">
      <label htmlFor={id}>Arquivo</label>
      <input
        id={id}
        type="file"
        accept={TIPOS_DE_ARQUIVO}
        onChange={(evento) => aoEscolher(evento.target.files?.[0] ?? null)}
        aria-invalid={!!erros?.length}
      />
      {erros?.map((mensagem) => (
        <p key={mensagem} className="erro-de-campo">
          {mensagem}
        </p>
      ))}
    </div>
  )
}

function FormularioDeEnvio({ categorias }: { categorias: CategoriaDeDocumento[] }) {
  const navegar = useNavigate()
  const [titulo, definirTitulo] = useState('')
  const [descricao, definirDescricao] = useState('')
  const [categoriaId, definirCategoriaId] = useState('')
  const [arquivo, definirArquivo] = useState<File | null>(null)
  const [erro, definirErro] = useState<unknown>(null)
  const [enviando, definirEnviando] = useState(false)
  const campos = errosPorCampo(erro)

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    definirErro(null)
    definirEnviando(true)
    try {
      const criado = await comunicacao.enviarDocumento({
        titulo,
        descricao,
        categoria_id: categoriaId,
        arquivo,
      })
      void navegar(`/documentos/${criado.id}`)
    } catch (e) {
      definirErro(e)
    } finally {
      definirEnviando(false)
    }
  }

  return (
    <form aria-label="Enviar documento" onSubmit={(evento) => void enviar(evento)}>
      <h2>Enviar documento</h2>
      <Campo rotulo="Título" value={titulo} erros={campos.titulo} aoMudar={definirTitulo} />
      <AreaDeTexto rotulo="Descrição" value={descricao} erros={campos.descricao} aoMudar={definirDescricao} />
      <Selecao rotulo="Categoria" value={categoriaId} aoMudar={definirCategoriaId}>
        <option value="">Escolha</option>
        {categorias.map((categoria) => (
          <option key={categoria.id} value={categoria.id}>
            {categoria.nome}
          </option>
        ))}
      </Selecao>
      {campos.categoria_id?.map((mensagem) => (
        <p key={mensagem} className="erro-de-campo">
          {mensagem}
        </p>
      ))}
      <AvisoDeDadoPessoal />
      <CampoDeArquivo erros={campos.arquivo} aoEscolher={definirArquivo} />
      <Alerta>{erro && !Object.keys(campos).length ? mensagemDoErro(erro) : null}</Alerta>
      <button type="submit" disabled={enviando}>
        Enviar documento
      </button>
    </form>
  )
}

function FormularioDeAta() {
  const navegar = useNavigate()
  const [titulo, definirTitulo] = useState('')
  const [descricao, definirDescricao] = useState('')
  const [data, definirData] = useState('')
  const [arquivo, definirArquivo] = useState<File | null>(null)
  const [erro, definirErro] = useState<unknown>(null)
  const [enviando, definirEnviando] = useState(false)
  const campos = errosPorCampo(erro)

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    definirErro(null)
    definirEnviando(true)
    try {
      const criada = await comunicacao.registrarAta({ titulo, descricao, data_da_reuniao: data, arquivo })
      void navegar(`/documentos/${criada.id}`)
    } catch (e) {
      definirErro(e)
    } finally {
      definirEnviando(false)
    }
  }

  return (
    <form aria-label="Registrar ata" onSubmit={(evento) => void enviar(evento)}>
      <h2>Registrar ata</h2>
      <Campo rotulo="Título" value={titulo} erros={campos.titulo} aoMudar={definirTitulo} />
      <AreaDeTexto rotulo="Descrição" value={descricao} erros={campos.descricao} aoMudar={definirDescricao} />
      <Campo
        rotulo="Data da reunião"
        type="date"
        value={data}
        erros={campos.data_da_reuniao}
        aoMudar={definirData}
      />
      <AvisoDeDadoPessoal />
      <CampoDeArquivo erros={campos.arquivo} aoEscolher={definirArquivo} />
      <Alerta>{erro && !Object.keys(campos).length ? mensagemDoErro(erro) : null}</Alerta>
      <button type="submit" disabled={enviando}>
        Registrar ata
      </button>
    </form>
  )
}

function ItemDoDocumento({ documento }: { documento: Documento }) {
  const origem = documento.categoria
    ? documento.categoria.nome
    : `reunião de ${dataCurta(documento.data_da_reuniao)}`
  return (
    <article aria-label={documento.titulo} className="item-do-feed">
      <h2>
        <Link to={`/documentos/${documento.id}`}>{documento.titulo}</Link>
      </h2>
      <p className="ajuda">
        {TIPO_DE_DOCUMENTO[documento.tipo] ?? documento.tipo} · {origem} · versão {documento.versao_atual} ·
        enviado por {documento.enviado_por.nome} · {SITUACAO_DO_DOCUMENTO[documento.situacao]}
      </p>
      {documento.descricao && <TextoLivre texto={documento.descricao} />}
      <a href={enderecoDoArquivo(documento.id)}>Baixar</a>
    </article>
  )
}

/** CA-23: a aba de documentos, com filtros por categoria, tipo, título e arquivados. */
export function Documentos() {
  const { usuario } = useSessao()
  const { detalhe } = useMinhasDaMoldura()
  const [filtros, definirFiltros] = useState<FiltrosDeDocumentos>({})
  const [itens, definirItens] = useState<Documento[]>([])
  const [temMais, definirTemMais] = useState(false)
  const [carregado, definirCarregado] = useState(false)
  const [categorias, definirCategorias] = useState<CategoriaDeDocumento[]>([])
  const [erro, definirErro] = useState<unknown>(null)
  const admin = !!usuario?.admin
  const podeEnviar = admin || temPermissao(detalhe, COMUNICACAO_ENVIAR_DOCUMENTOS)
  const podeRegistrarAta = admin || temPermissao(detalhe, COMUNICACAO_REGISTRAR_ATAS)

  useEffect(() => {
    comunicacao
      .categorias()
      .then(definirCategorias)
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    let vivo = true
    comunicacao
      .documentos(filtros)
      .then((pagina) => {
        if (!vivo) return
        definirItens(pagina.itens)
        definirTemMais(pagina.tem_mais)
        definirCarregado(true)
      })
      .catch((e: unknown) => vivo && definirErro(e))
    return () => {
      vivo = false
    }
  }, [filtros])

  async function carregarMais() {
    const ultimo = itens.at(-1)
    if (!ultimo) return
    try {
      const pagina = await comunicacao.documentos({ ...filtros, antes: ultimo.id })
      definirItens([...itens, ...pagina.itens])
      definirTemMais(pagina.tem_mais)
    } catch (e) {
      definirErro(e)
    }
  }

  return (
    <Pagina titulo="Documentos">
      <form aria-label="Filtros" onSubmit={(evento) => evento.preventDefault()}>
        <Selecao
          rotulo="Categoria"
          value={filtros.categoria_id ?? ''}
          aoMudar={(categoria_id) => definirFiltros({ ...filtros, categoria_id })}
        >
          <option value="">Todas</option>
          {categorias.map((categoria) => (
            <option key={categoria.id} value={categoria.id}>
              {categoria.nome}
            </option>
          ))}
        </Selecao>
        <Selecao
          rotulo="Tipo"
          value={filtros.tipo ?? ''}
          aoMudar={(tipo) => definirFiltros({ ...filtros, tipo })}
        >
          <option value="">Todos</option>
          {Object.entries(TIPO_DE_DOCUMENTO).map(([valor, rotulo]) => (
            <option key={valor} value={valor}>
              {rotulo}
            </option>
          ))}
        </Selecao>
        <Campo
          rotulo="Título"
          value={filtros.titulo ?? ''}
          aoMudar={(titulo) => definirFiltros({ ...filtros, titulo })}
        />
        <label className="opcao">
          <input
            type="checkbox"
            checked={!!filtros.arquivados}
            onChange={(evento) => definirFiltros({ ...filtros, arquivados: evento.target.checked })}
          />
          Arquivados
        </label>
      </form>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {carregado && itens.length === 0 && <p>Nenhum documento encontrado.</p>}
      {itens.map((documento) => (
        <ItemDoDocumento key={documento.id} documento={documento} />
      ))}
      {temMais && (
        <button type="button" onClick={() => void carregarMais()}>
          Carregar mais
        </button>
      )}
      {podeEnviar && <FormularioDeEnvio categorias={categorias} />}
      {podeRegistrarAta && <FormularioDeAta />}
    </Pagina>
  )
}
