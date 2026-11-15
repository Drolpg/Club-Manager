import { useEffect, useId, useState, type FormEvent, type ReactNode } from 'react'
import {
  TIPO_DE_DECISAO,
  aprovacoes,
  type Acao,
  type DetalheDaSolicitacao,
  type Motivo,
} from '../api/aprovacoes'
import { Alerta, Campo, Selecao } from '../componentes'
import { financeiro, isConteudoGasto, type ConteudoGasto, type ReferenciasGastos } from '../api/financeiro'
import { errosPorCampo, mensagemDoErro } from '../mensagens'
import { ListaDeItensEditavel, type ItemEditavel } from './apoioSaidas'

const ROTULO: Record<Acao, string> = {
  retirar: 'Retirar',
  reenviar: 'Reenviar',
  reabrir: 'Reabrir',
  editar: 'Editar',
  cancelar: 'Cancelar',
  aprovar: 'Aprovar',
  contestar: 'Contestar',
  recusar: 'Recusar',
}

function AreaDeTexto({
  rotulo,
  valor,
  aoMudar,
  erros,
  linhas = 3,
}: {
  rotulo: string
  valor: string
  aoMudar: (valor: string) => void
  erros?: string[]
  linhas?: number
}) {
  const id = useId()
  return (
    <div className="campo">
      <label htmlFor={id}>{rotulo}</label>
      <textarea
        id={id}
        rows={linhas}
        maxLength={1000}
        value={valor}
        onChange={(evento) => aoMudar(evento.target.value)}
        aria-invalid={!!erros?.length}
      />
      {erros?.map((erro) => (
        <p key={erro} className="erro-de-campo">
          {erro}
        </p>
      ))}
    </div>
  )
}

/** Os motivos ativos do tipo de decisão, para o seletor. */
function useMotivos(acao: Acao): Motivo[] {
  const [motivos, definirMotivos] = useState<Motivo[]>([])
  useEffect(() => {
    if (acao !== 'aprovar' && acao !== 'contestar' && acao !== 'recusar') return
    let vivo = true
    aprovacoes
      .motivos(TIPO_DE_DECISAO[acao])
      .then((lista) => vivo && definirMotivos(lista))
      .catch(() => undefined)
    return () => {
      vivo = false
    }
  }, [acao])
  return motivos
}

class ConteudoInvalido extends Error {}

function lerConteudo(texto: string): unknown {
  try {
    return JSON.parse(texto)
  } catch {
    throw new ConteudoInvalido('O conteúdo precisa ser um JSON válido.')
  }
}

/**
 * O formulário de um comando: pede o que a rota pede. Reenviar e editar mostram o conteúdo da versão
 * atual em JSON, porque o site do motor não conhece o formato de nenhum tipo; o M7 e o M8 trocam isso
 * pelo formulário próprio dos tipos deles.
 */
function FormularioDaAcao({
  acao,
  detalhe,
  aoConcluir,
  aoFechar,
}: {
  acao: Acao
  detalhe: DetalheDaSolicitacao
  aoConcluir: () => void
  aoFechar: () => void
}) {
  const motivos = useMotivos(acao)
  const atual = detalhe.versoes.find((v) => v.numero === detalhe.numero_da_versao_atual)
  const ehGasto = detalhe.tipo === 'financeiro.gasto' && isConteudoGasto(atual?.conteudo)
  const gastoInicial: ConteudoGasto | null = ehGasto ? (atual?.conteudo as ConteudoGasto) : null

  const [motivoId, definirMotivoId] = useState('')
  const [texto, definirTexto] = useState('')
  const [mensagem, definirMensagem] = useState('')
  const [teto, definirTeto] = useState('')
  const [justificativa, definirJustificativa] = useState('')
  const [motivo, definirMotivo] = useState('')
  const [conteudo, definirConteudo] = useState(() => JSON.stringify(atual?.conteudo ?? {}, null, 2))
  const [refsGasto, definirRefsGasto] = useState<ReferenciasGastos | null>(null)
  const [gastoDesc, definirGastoDesc] = useState(() => gastoInicial?.descricao ?? '')
  const [gastoCat, definirGastoCat] = useState(() => gastoInicial?.categoria_id ?? '')
  const [gastoSetor, definirGastoSetor] = useState(() => gastoInicial?.setor_id ?? '')
  const [gastoItens, definirGastoItens] = useState<ItemEditavel[]>(() =>
    gastoInicial?.itens.map((it, idx) => ({ chave: idx + 1, descricao: it.descricao, valor: it.valor })) ?? [
      { chave: 1, descricao: '', valor: '' },
    ],
  )
  const [gastoCotacaoId] = useState<string | null>(() => gastoInicial?.cotacao_id ?? null)
  const [erro, definirErro] = useState<unknown>(null)
  const [enviando, definirEnviando] = useState(false)
  const campos = errosPorCampo(erro)

  useEffect(() => {
    if (!ehGasto || (acao !== 'reenviar' && acao !== 'editar')) return
    let vivo = true
    financeiro
      .referenciasGastos()
      .then((dados) => vivo && definirRefsGasto(dados))
      .catch(() => undefined)
    return () => {
      vivo = false
    }
  }, [ehGasto, acao])

  function conteudoEstruturado(): Record<string, unknown> {
    return {
      descricao: gastoDesc,
      categoria_id: gastoCat,
      setor_id: gastoSetor,
      itens: gastoItens.map((it) => ({ descricao: it.descricao, valor: it.valor })),
      cotacao_id: gastoCotacaoId,
    }
  }

  function corpo(): Record<string, unknown> {
    switch (acao) {
      case 'aprovar':
      case 'recusar':
        return { motivo_id: motivoId, texto }
      case 'contestar':
        return { motivo_id: motivoId, texto, mensagem, teto_sugerido: teto.trim() || null }
      case 'reabrir':
        return { justificativa }
      case 'cancelar':
        return { motivo }
      case 'reenviar':
        return { conteudo: ehGasto ? conteudoEstruturado() : lerConteudo(conteudo) }
      case 'editar':
        return { conteudo: ehGasto ? conteudoEstruturado() : lerConteudo(conteudo), justificativa }
      default:
        return {}
    }
  }

  async function confirmar(evento: FormEvent) {
    evento.preventDefault()
    definirErro(null)
    definirEnviando(true)
    try {
      await aprovacoes.executar(detalhe.id, acao, corpo())
      aoConcluir()
    } catch (falha) {
      definirErro(falha)
    } finally {
      definirEnviando(false)
    }
  }

  const decisao = acao === 'aprovar' || acao === 'contestar' || acao === 'recusar'
  let camposDaAcao: ReactNode = null
  if (decisao) {
    camposDaAcao = (
      <>
        <Selecao rotulo="Motivo" value={motivoId} aoMudar={definirMotivoId}>
          <option value="">Escolha um motivo</option>
          {motivos.map((m) => (
            <option key={m.id} value={m.id}>
              {m.texto}
            </option>
          ))}
        </Selecao>
        {campos.motivo_id?.map((e) => (
          <p key={e} className="erro-de-campo">
            {e}
          </p>
        ))}
        {acao === 'contestar' && (
          <AreaDeTexto
            rotulo="Mensagem ao solicitante"
            valor={mensagem}
            aoMudar={definirMensagem}
            erros={campos.mensagem}
          />
        )}
        {acao === 'contestar' && detalhe.tem_valor && (
          <Campo
            rotulo="Teto sugerido (opcional)"
            inputMode="decimal"
            placeholder="0.00"
            value={teto}
            aoMudar={definirTeto}
            erros={campos.teto_sugerido}
          />
        )}
        <AreaDeTexto rotulo="Texto (opcional)" valor={texto} aoMudar={definirTexto} erros={campos.texto} />
      </>
    )
  } else if (acao === 'reabrir') {
    camposDaAcao = (
      <AreaDeTexto
        rotulo="Justificativa"
        valor={justificativa}
        aoMudar={definirJustificativa}
        erros={campos.justificativa}
      />
    )
  } else if (acao === 'cancelar') {
    camposDaAcao = (
      <AreaDeTexto
        rotulo="Motivo do cancelamento"
        valor={motivo}
        aoMudar={definirMotivo}
        erros={campos.motivo}
      />
    )
  } else if (acao === 'reenviar' || acao === 'editar') {
    camposDaAcao = (
      <>
        {ehGasto ? (
          <>
            <Campo rotulo="Descrição geral" value={gastoDesc} aoMudar={definirGastoDesc} erros={campos.descricao} />
            <Selecao rotulo="Categoria de saída" value={gastoCat} aoMudar={definirGastoCat}>
              <option value="">Escolha a categoria</option>
              {(refsGasto?.categorias_saida ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </Selecao>
            <Selecao rotulo="Setor" value={gastoSetor} aoMudar={definirGastoSetor}>
              <option value="">Escolha o setor</option>
              {(refsGasto?.setores ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.nome}
                </option>
              ))}
            </Selecao>
            <ListaDeItensEditavel itens={gastoItens} aoMudar={definirGastoItens} erros={campos.itens} />
          </>
        ) : (
          <div className="campo">
            <label htmlFor={`conteudo-${detalhe.id}`}>Conteúdo (JSON)</label>
            <textarea
              id={`conteudo-${detalhe.id}`}
              rows={8}
              value={conteudo}
              onChange={(evento) => definirConteudo(evento.target.value)}
            />
          </div>
        )}
        {acao === 'editar' && (
          <AreaDeTexto
            rotulo="Justificativa (opcional)"
            valor={justificativa}
            aoMudar={definirJustificativa}
            erros={campos.justificativa}
          />
        )}
      </>
    )
  } else {
    camposDaAcao = <p>A solicitação sai da fila e volta à análise quando você a reenviar.</p>
  }

  return (
    <form aria-label={ROTULO[acao]} onSubmit={(evento) => void confirmar(evento)}>
      <h3>{ROTULO[acao]}</h3>
      {camposDaAcao}
      <Alerta>{erro instanceof ConteudoInvalido ? erro.message : erro ? mensagemDoErro(erro) : null}</Alerta>
      <button type="submit" disabled={enviando}>
        Confirmar
      </button>
      <button type="button" onClick={aoFechar}>
        Fechar
      </button>
    </form>
  )
}

/** Os botões do que quem está logado pode fazer agora (o campo `acoes` da API) e o formulário de cada. */
export function AcoesDaSolicitacao({
  detalhe,
  aoMudar,
}: {
  detalhe: DetalheDaSolicitacao
  aoMudar: () => void
}) {
  const [aberta, definirAberta] = useState<Acao | null>(null)
  if (detalhe.acoes.length === 0) return null

  return (
    <section aria-label="Ações">
      <h2>Ações</h2>
      {detalhe.acoes.map((acao) => (
        <button key={acao} type="button" onClick={() => definirAberta(acao)}>
          {ROTULO[acao]}
        </button>
      ))}
      {aberta && (
        <FormularioDaAcao
          key={aberta}
          acao={aberta}
          detalhe={detalhe}
          aoFechar={() => definirAberta(null)}
          aoConcluir={() => {
            definirAberta(null)
            aoMudar()
          }}
        />
      )}
    </section>
  )
}
