import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  pedidosDeRelatorio,
  type FormaDosParametros,
  type NovoPedido,
  type PedidoDeRelatorio,
  type TipoDeRelatorio,
} from '../api/relatorios'
import { Alerta, Campo, Pagina, Selecao } from '../componentes'
import { dataCurta, dataEHora } from '../formatos'
import { SITUACAO_DO_PEDIDO_DE_RELATORIO, errosPorCampo, mensagemDoErro } from '../mensagens'

/** Enquanto há pedido na fila ou gerando, a lista é consultada de novo neste intervalo. */
export const INTERVALO_DOS_PEDIDOS_MS = 3000

interface Rascunho {
  mes: string
  de: string
  ate: string
  soPendentes: boolean
}

const VAZIO: Rascunho = { mes: '', de: '', ate: '', soPendentes: false }

/** Os parâmetros que a API espera, pela forma do tipo; quem valida é a API (CA-03). */
function parametrosDe(forma: FormaDosParametros, rascunho: Rascunho): Record<string, unknown> {
  if (forma === 'NENHUM') return {}
  if (forma === 'MESES') return { de: rascunho.de, ate: rascunho.ate }
  const periodo: Record<string, unknown> = rascunho.mes
    ? { mes: rascunho.mes }
    : { de: rascunho.de, ate: rascunho.ate }
  return forma === 'PERIODO_E_PENDENTES' ? { ...periodo, so_pendentes: rascunho.soPendentes } : periodo
}

/** Os parâmetros do pedido em texto: o período, e "só pendentes" quando marcado. */
function textoDosParametros(parametros: Record<string, unknown>): string {
  const { de, ate, so_pendentes: soPendentes } = parametros as {
    de?: string
    ate?: string
    so_pendentes?: boolean
  }
  const periodo = de && ate ? `${dataCurta(de)} a ${dataCurta(ate)}` : '—'
  return soPendentes ? `${periodo}, só pendentes` : periodo
}

/** Para pedir de novo: o pedido guarda as datas; o fluxo de caixa pede meses (AAAA-MM). */
function parametrosParaRepetir(pedido: PedidoDeRelatorio, tipo?: TipoDeRelatorio): Record<string, unknown> {
  if (tipo?.parametros !== 'MESES') return pedido.parametros
  const { de, ate } = pedido.parametros as { de: string; ate: string }
  return { de: de.slice(0, 7), ate: ate.slice(0, 7) }
}

const emAndamento = (pedido: PedidoDeRelatorio) =>
  pedido.situacao === 'NA_FILA' || pedido.situacao === 'GERANDO'

/**
 * Relatórios (RF-105 a RF-111, RF-144): pedir um relatório em PDF ou CSV e acompanhar os próprios pedidos. A
 * API diz quais tipos o usuário pode gerar e confere tudo de novo; o site só mostra e pede.
 */
export function Relatorios() {
  const [tipos, definirTipos] = useState<TipoDeRelatorio[]>([])
  const [codigo, definirCodigo] = useState('')
  const [formato, definirFormato] = useState('')
  const [rascunho, definirRascunho] = useState<Rascunho>(VAZIO)
  const [erro, definirErro] = useState<unknown>(null)
  const [aviso, definirAviso] = useState('')
  const [pedidos, definirPedidos] = useState<PedidoDeRelatorio[]>([])
  const [temMais, definirTemMais] = useState(false)

  const tipo = tipos.find((t) => t.codigo === codigo)

  useEffect(() => {
    pedidosDeRelatorio
      .tipos()
      .then((lista) => {
        definirTipos(lista)
        definirCodigo(lista[0]?.codigo ?? '')
        definirFormato(lista[0]?.formatos[0] ?? '')
      })
      .catch(definirErro)
  }, [])

  const atualizar = useCallback(() => {
    pedidosDeRelatorio
      .listar()
      .then((pagina) => {
        definirPedidos(pagina.itens)
        definirTemMais(pagina.tem_mais)
      })
      .catch(definirErro)
  }, [])

  useEffect(atualizar, [atualizar])

  const andando = pedidos.some(emAndamento)
  useEffect(() => {
    if (!andando) return undefined
    const intervalo = setInterval(atualizar, INTERVALO_DOS_PEDIDOS_MS)
    return () => clearInterval(intervalo)
  }, [andando, atualizar])

  function escolherTipo(novo: string) {
    definirCodigo(novo)
    definirFormato(tipos.find((t) => t.codigo === novo)?.formatos[0] ?? '')
    definirRascunho(VAZIO)
  }

  function enviar(novo: NovoPedido) {
    definirAviso('')
    pedidosDeRelatorio
      .pedir(novo)
      .then(() => {
        definirErro(null)
        definirAviso('Pedido na fila. Você recebe um aviso quando o arquivo ficar pronto.')
        atualizar()
      })
      .catch(definirErro)
  }

  function pedir(evento: FormEvent) {
    evento.preventDefault()
    if (!tipo) return
    enviar({ tipo: tipo.codigo, formato, parametros: parametrosDe(tipo.parametros, rascunho) })
  }

  function carregarMais() {
    const ultimo = pedidos[pedidos.length - 1]
    pedidosDeRelatorio
      .listar(ultimo.id)
      .then((pagina) => {
        definirPedidos((atuais) => [...atuais, ...pagina.itens])
        definirTemMais(pagina.tem_mais)
      })
      .catch(definirErro)
  }

  const campos = errosPorCampo(erro)
  const mudar = (campo: keyof Rascunho) => (valor: string) =>
    definirRascunho((atual) => ({ ...atual, [campo]: valor }))

  return (
    <Pagina titulo="Relatórios">
      <form onSubmit={pedir} aria-label="Pedir relatório">
        <Selecao rotulo="Relatório" value={codigo} aoMudar={escolherTipo}>
          {tipos.map((t) => (
            <option key={t.codigo} value={t.codigo}>
              {t.nome}
            </option>
          ))}
        </Selecao>
        <Selecao rotulo="Formato" value={formato} aoMudar={definirFormato}>
          {(tipo?.formatos ?? []).map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </Selecao>
        {(tipo?.parametros === 'PERIODO' || tipo?.parametros === 'PERIODO_E_PENDENTES') && (
          <fieldset>
            <legend>Período: um mês, ou de e até</legend>
            <Campo rotulo="Mês" type="month" value={rascunho.mes} aoMudar={mudar('mes')} erros={campos.mes} />
            <Campo rotulo="De" type="date" value={rascunho.de} aoMudar={mudar('de')} erros={campos.de} />
            <Campo rotulo="Até" type="date" value={rascunho.ate} aoMudar={mudar('ate')} erros={campos.ate} />
            {tipo.parametros === 'PERIODO_E_PENDENTES' && (
              <label>
                <input
                  type="checkbox"
                  checked={rascunho.soPendentes}
                  onChange={(e) => definirRascunho((atual) => ({ ...atual, soPendentes: e.target.checked }))}
                />
                Só pendentes
              </label>
            )}
          </fieldset>
        )}
        {tipo?.parametros === 'MESES' && (
          <fieldset>
            <legend>Meses</legend>
            <Campo rotulo="Do mês" type="month" value={rascunho.de} aoMudar={mudar('de')} erros={campos.de} />
            <Campo
              rotulo="Até o mês"
              type="month"
              value={rascunho.ate}
              aoMudar={mudar('ate')}
              erros={campos.ate}
            />
          </fieldset>
        )}
        <p>O arquivo fica disponível por 7 dias depois de pronto.</p>
        <button type="submit" disabled={!tipo}>
          Pedir
        </button>
      </form>

      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {aviso && <p role="status">{aviso}</p>}

      <h2>Meus relatórios</h2>
      {!pedidos.length && <p>Você ainda não pediu nenhum relatório.</p>}
      {pedidos.length > 0 && (
        <table aria-label="Meus relatórios">
          <thead>
            <tr>
              <th>Relatório</th>
              <th>Formato</th>
              <th>Parâmetros</th>
              <th>Pedido em</th>
              <th>Situação</th>
              <th>Disponível até</th>
              <th>Ação</th>
            </tr>
          </thead>
          <tbody>
            {pedidos.map((p) => (
              <tr key={p.id}>
                <td>{p.tipo_nome}</td>
                <td>{p.formato}</td>
                <td>{textoDosParametros(p.parametros)}</td>
                <td>{dataEHora.format(new Date(p.pedido_em))}</td>
                <td>{SITUACAO_DO_PEDIDO_DE_RELATORIO[p.situacao] ?? p.situacao}</td>
                <td>{p.disponivel && p.expira_em ? dataEHora.format(new Date(p.expira_em)) : '—'}</td>
                <td>
                  {p.disponivel && <a href={pedidosDeRelatorio.arquivo(p.id)}>Baixar</a>}
                  {(p.situacao === 'EXPIRADO' || p.situacao === 'FALHOU') && (
                    <button
                      type="button"
                      onClick={() =>
                        enviar({
                          tipo: p.tipo,
                          formato: p.formato,
                          parametros: parametrosParaRepetir(p, tipos.find((t) => t.codigo === p.tipo)),
                        })
                      }
                    >
                      Pedir de novo
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {temMais && (
        <button type="button" onClick={carregarMais}>
          Carregar mais
        </button>
      )}
    </Pagina>
  )
}
