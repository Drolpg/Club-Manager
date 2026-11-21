import { useState } from 'react'
import { Link } from 'react-router'
import {
  comunicacao,
  enderecoDoArquivo,
  type Comunicado,
  TIPOS_DE_REACAO,
  type DocumentoDoComunicado,
  type TipoDeReacao,
} from '../api/comunicacao'
import { Alerta } from '../componentes'
import { ROTULO_DA_REACAO, mensagemDoErro } from '../mensagens'

/** Texto de comunicado ou comentário: sempre como texto do React, com as quebras de linha (R9, CA-31). */
export function TextoLivre({ texto }: { texto: string }) {
  return <p className="texto-livre">{texto}</p>
}

export function DocumentosLigados({ documentos }: { documentos: DocumentoDoComunicado[] }) {
  if (documentos.length === 0) return null
  return (
    <ul className="lista" aria-label="Documentos">
      {documentos.map((documento) => (
        <li key={documento.id}>
          <a href={enderecoDoArquivo(documento.id)}>{documento.titulo}</a>{' '}
          {documento.situacao === 'ARQUIVADO' && <span className="selo">Arquivado</span>}
        </li>
      ))}
    </ul>
  )
}

/**
 * A contagem por tipo e, para quem pode (`acoes` traz `reagir`), os botões. Escolher de novo o tipo marcado
 * retira a reação: a API decide, e o site mostra o resultado.
 */
export function Reacoes({
  comunicado,
  aoMudar,
}: {
  comunicado: Comunicado
  aoMudar: (novo: Comunicado) => void
}) {
  const [erro, definirErro] = useState<unknown>(null)
  const { contagem, minha } = comunicado.reacoes
  const podeReagir = comunicado.acoes.includes('reagir')

  async function reagir(tipo: TipoDeReacao) {
    definirErro(null)
    try {
      const reacoes = await comunicacao.reagir(comunicado.id, tipo)
      aoMudar({ ...comunicado, reacoes })
    } catch (e) {
      definirErro(e)
    }
  }

  return (
    <div className="reacoes">
      {TIPOS_DE_REACAO.map((tipo) =>
        podeReagir ? (
          <button
            key={tipo}
            type="button"
            className={minha === tipo ? 'marcado' : undefined}
            aria-pressed={minha === tipo}
            onClick={() => void reagir(tipo)}
          >
            {ROTULO_DA_REACAO[tipo]} <span className="contagem">{contagem[tipo]}</span>
          </button>
        ) : (
          <span key={tipo} className="contagem-de-reacao">
            {ROTULO_DA_REACAO[tipo]} {contagem[tipo]}
          </span>
        ),
      )}
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
    </div>
  )
}

export function Rodape({ comunicado }: { comunicado: Comunicado }) {
  const total = comunicado.total_de_comentarios
  return (
    <Link to={`/feed/${comunicado.id}`}>
      {total === 1 ? '1 comentário' : `${total} comentários`}
    </Link>
  )
}
