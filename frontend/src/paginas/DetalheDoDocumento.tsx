import { useEffect, useId, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import { comunicacao, enderecoDoArquivo, type DetalheDoDocumento } from '../api/comunicacao'
import { Alerta, Campo, Pagina } from '../componentes'
import { dataCurta, dataEHora } from '../formatos'
import {
  SITUACAO_DA_VERSAO,
  SITUACAO_DO_DOCUMENTO,
  TIPO_DE_DOCUMENTO,
  errosPorCampo,
  mensagemDoErro,
} from '../mensagens'
import { TextoLivre } from './apoioFeed'

function NovaVersao({ id, aoConcluir }: { id: string; aoConcluir: (novo: DetalheDoDocumento) => void }) {
  const arquivoId = useId()
  const [motivo, definirMotivo] = useState('')
  const [arquivo, definirArquivo] = useState<File | null>(null)
  const [erro, definirErro] = useState<unknown>(null)
  const campos = errosPorCampo(erro)

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    definirErro(null)
    try {
      aoConcluir(await comunicacao.novaVersao(id, { motivo, arquivo }))
      definirMotivo('')
      definirArquivo(null)
    } catch (e) {
      definirErro(e)
    }
  }

  return (
    <form aria-label="Nova versão" onSubmit={(evento) => void enviar(evento)}>
      <h2>Nova versão</h2>
      <Campo rotulo="Motivo" value={motivo} erros={campos.motivo} aoMudar={definirMotivo} />
      <div className="campo">
        <label htmlFor={arquivoId}>Arquivo</label>
        <input
          id={arquivoId}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.webp"
          onChange={(evento) => definirArquivo(evento.target.files?.[0] ?? null)}
          aria-invalid={!!campos.arquivo?.length}
        />
        {campos.arquivo?.map((mensagem) => (
          <p key={mensagem} className="erro-de-campo">
            {mensagem}
          </p>
        ))}
      </div>
      <Alerta>{erro && !Object.keys(campos).length ? mensagemDoErro(erro) : null}</Alerta>
      <button type="submit">Enviar nova versão</button>
    </form>
  )
}

/** CA-24 a CA-26: dados, versões (baixar cada uma), comunicados que o indexam e as ações de `acoes`. */
export function DetalheDoDocumento() {
  const { id = '' } = useParams()
  const [documento, definirDocumento] = useState<DetalheDoDocumento | null>(null)
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    let vivo = true
    comunicacao
      .detalheDoDocumento(id)
      .then((dados) => vivo && definirDocumento(dados))
      .catch((e: unknown) => vivo && definirErro(e))
    return () => {
      vivo = false
    }
  }, [id])

  if (!documento) {
    const conteudo = erro ? <Alerta>{mensagemDoErro(erro)}</Alerta> : <p>Carregando…</p>
    return <Pagina titulo="Documento">{conteudo}</Pagina>
  }

  const pode = (acao: string) => documento.acoes.includes(acao as never)
  const origem = documento.categoria
    ? documento.categoria.nome
    : `reunião de ${dataCurta(documento.data_da_reuniao)}`

  async function executar(acao: () => Promise<DetalheDoDocumento>) {
    definirErro(null)
    try {
      definirDocumento(await acao())
    } catch (e) {
      definirErro(e)
    }
  }

  return (
    <Pagina titulo={documento.titulo}>
      <p className="ajuda">
        {TIPO_DE_DOCUMENTO[documento.tipo] ?? documento.tipo} · {origem} · enviado por{' '}
        {documento.enviado_por.nome} · {SITUACAO_DO_DOCUMENTO[documento.situacao]}
      </p>
      {documento.descricao && <TextoLivre texto={documento.descricao} />}
      <a href={enderecoDoArquivo(documento.id)}>Baixar a versão vigente</a>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {pode('arquivar') && (
        <button type="button" onClick={() => void executar(() => comunicacao.arquivar(id))}>
          Arquivar
        </button>
      )}
      {pode('desarquivar') && (
        <button type="button" onClick={() => void executar(() => comunicacao.desarquivar(id))}>
          Desarquivar
        </button>
      )}

      <section aria-label="Versões">
        <h2>Versões</h2>
        <ul className="lista">
          {documento.versoes.map((versao) => (
            <li key={versao.numero}>
              Versão {versao.numero} · {SITUACAO_DA_VERSAO[versao.situacao]} · {versao.nome} ·{' '}
              {versao.enviada_por.nome} · {dataEHora.format(new Date(versao.enviada_em))}
              {versao.motivo ? ` — ${versao.motivo}` : ''}{' '}
              <a href={enderecoDoArquivo(documento.id, versao.numero)}>Baixar</a>
            </li>
          ))}
        </ul>
      </section>

      {documento.comunicados.length > 0 && (
        <section aria-label="Comunicados que indexam">
          <h2>Comunicados que indexam</h2>
          <ul className="lista">
            {documento.comunicados.map((comunicado) => (
              <li key={comunicado.id}>
                <Link to={`/feed/${comunicado.id}`}>{comunicado.titulo}</Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {pode('nova_versao') && <NovaVersao id={id} aoConcluir={definirDocumento} />}
    </Pagina>
  )
}
