import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import {
  financeiro,
  type EstornoItem,
  type FiltrosSaidas,
  type ReferenciasGastos,
  type SaidaItem,
  type VisaoDoCaixa,
} from '../api/financeiro'
import { Alerta, Campo, Pagina, Selecao } from '../componentes'
import { dataEHora, reais } from '../formatos'
import { ALVO_DO_ESTORNO, SITUACAO_DA_SAIDA, mensagemDoErro } from '../mensagens'
import { CartoesDoCaixa } from './apoioSaidas'

type FilaRapida = 'todas' | 'envio' | 'prestacao' | 'atrasadas'

const FILAS: FilaRapida[] = ['todas', 'envio', 'prestacao', 'atrasadas']

function filaDaUrl(valor: string | null): FilaRapida {
  return FILAS.find((f) => f === valor) ?? 'todas'
}

/** Painel operacional de saídas financeiras, visão do caixa, filas e consulta de estornos (CA-30, CA-31). */
export function Saidas() {
  const [caixa, definirCaixa] = useState<VisaoDoCaixa | null>(null)
  const [refs, definirRefs] = useState<ReferenciasGastos | null>(null)
  const [filtros, definirFiltros] = useState<FiltrosSaidas>({})
  // O dashboard abre esta tela já na fila pedida (por exemplo, `?fila=prestacao`).
  const [parametros] = useSearchParams()
  const [fila, definirFila] = useState<FilaRapida>(() => filaDaUrl(parametros.get('fila')))
  const [itens, definirItens] = useState<SaidaItem[]>([])
  const [temMais, definirTemMais] = useState(false)

  const [alvoEstorno, definirAlvoEstorno] = useState('')
  const [estornos, definirEstornos] = useState<EstornoItem[]>([])
  const [temMaisEstornos, definirTemMaisEstornos] = useState(false)
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    Promise.all([financeiro.caixa(), financeiro.referenciasGastos()])
      .then(([cx, rf]) => {
        definirCaixa(cx)
        definirRefs(rf)
      })
      .catch(definirErro)
  }, [])

  useEffect(() => {
    let vivo = true
    const consulta: FiltrosSaidas = {
      ...filtros,
      pendentes_envio: fila === 'envio' ? true : undefined,
      pendentes_prestacao: fila === 'prestacao' ? true : undefined,
      atrasadas: fila === 'atrasadas' ? true : undefined,
    }
    financeiro
      .saidas(consulta)
      .then((pag) => {
        if (!vivo) return
        definirItens(pag.itens)
        definirTemMais(pag.tem_mais)
      })
      .catch((falha) => vivo && definirErro(falha))
    return () => {
      vivo = false
    }
  }, [filtros, fila])

  useEffect(() => {
    let vivo = true
    financeiro
      .estornos({ alvo_tipo: alvoEstorno || undefined })
      .then((pag) => {
        if (!vivo) return
        definirEstornos(pag.itens)
        definirTemMaisEstornos(pag.tem_mais)
      })
      .catch((falha) => vivo && definirErro(falha))
    return () => {
      vivo = false
    }
  }, [alvoEstorno])

  async function carregarMaisSaidas() {
    const ultimo = itens.at(-1)
    if (!ultimo) return
    try {
      const pag = await financeiro.saidas({
        ...filtros,
        pendentes_envio: fila === 'envio' ? true : undefined,
        pendentes_prestacao: fila === 'prestacao' ? true : undefined,
        atrasadas: fila === 'atrasadas' ? true : undefined,
        antes: ultimo.id,
      })
      definirItens((atuais) => [...atuais, ...pag.itens])
      definirTemMais(pag.tem_mais)
    } catch (falha) {
      definirErro(falha)
    }
  }

  async function carregarMaisEstornos() {
    const ultimo = estornos.at(-1)
    if (!ultimo) return
    try {
      const pag = await financeiro.estornos({
        alvo_tipo: alvoEstorno || undefined,
        antes: ultimo.id,
      })
      definirEstornos((atuais) => [...atuais, ...pag.itens])
      definirTemMaisEstornos(pag.tem_mais)
    } catch (falha) {
      definirErro(falha)
    }
  }

  return (
    <Pagina titulo="Saídas e gastos">
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {caixa && <CartoesDoCaixa caixa={caixa} />}

      <p>
        <Link to="/gastos/novo">Pedir gasto</Link>
      </p>

      <div role="group" aria-label="Filas operacionais">
        <button type="button" onClick={() => definirFila('todas')}>
          Todas
        </button>
        <button type="button" onClick={() => definirFila('envio')}>
          Aguardando envio
        </button>
        <button type="button" onClick={() => definirFila('prestacao')}>
          Prestações pendentes
        </button>
        <button type="button" onClick={() => definirFila('atrasadas')}>
          Em atraso
        </button>
      </div>

      <form aria-label="Filtrar saídas" onSubmit={(e) => e.preventDefault()}>
        <Selecao
          rotulo="Situação"
          value={filtros.situacao ?? ''}
          aoMudar={(situacao) => definirFiltros({ ...filtros, situacao: situacao || undefined })}
        >
          <option value="">Todas</option>
          {Object.entries(SITUACAO_DA_SAIDA).map(([codigo, rotulo]) => (
            <option key={codigo} value={codigo}>
              {rotulo}
            </option>
          ))}
        </Selecao>
        <Selecao
          rotulo="Categoria"
          value={filtros.categoria_id ?? ''}
          aoMudar={(categoria_id) => definirFiltros({ ...filtros, categoria_id: categoria_id || undefined })}
        >
          <option value="">Todas</option>
          {(refs?.categorias_saida ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.nome}
            </option>
          ))}
        </Selecao>
        <Selecao
          rotulo="Setor"
          value={filtros.setor_id ?? ''}
          aoMudar={(setor_id) => definirFiltros({ ...filtros, setor_id: setor_id || undefined })}
        >
          <option value="">Todos</option>
          {(refs?.setores ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.nome}
            </option>
          ))}
        </Selecao>
        <Selecao
          rotulo="Solicitante"
          value={filtros.solicitante_id ?? ''}
          aoMudar={(solicitante_id) =>
            definirFiltros({ ...filtros, solicitante_id: solicitante_id || undefined })
          }
        >
          <option value="">Todos</option>
          {(refs?.diretores_ativos ?? []).map((d) => (
            <option key={d.id} value={d.id}>
              {d.nome}
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
      </form>

      {itens.length === 0 ? (
        <p>Nenhuma saída encontrada.</p>
      ) : (
        <ul>
          {itens.map((item) => (
            <li key={item.id}>
              <Link to={`/saidas/${item.id}`}>{item.descricao}</Link> —{' '}
              {SITUACAO_DA_SAIDA[item.situacao] ?? item.situacao} — {item.solicitante.nome} —{' '}
              {item.categoria_nome} ({item.setor_nome}) — Aprovado: {reais(item.valor_aprovado_total)} | Enviado:{' '}
              {reais(item.total_enviado)}
              {item.em_atraso && <span> — Em atraso</span>}
            </li>
          ))}
        </ul>
      )}

      {temMais && (
        <button type="button" onClick={() => void carregarMaisSaidas()}>
          Carregar mais
        </button>
      )}

      <section aria-label="Estornos registrados">
        <h2>Estornos registrados</h2>
        <Selecao rotulo="Alvo do estorno" value={alvoEstorno} aoMudar={definirAlvoEstorno}>
          <option value="">Todos</option>
          {Object.entries(ALVO_DO_ESTORNO).map(([codigo, rotulo]) => (
            <option key={codigo} value={codigo}>
              {rotulo}
            </option>
          ))}
        </Selecao>
        {estornos.length === 0 ? (
          <p>Nenhum estorno registrado.</p>
        ) : (
          <ul>
            {estornos.map((est) => (
              <li key={est.id}>
                {ALVO_DO_ESTORNO[est.alvo_tipo] ?? est.alvo_tipo} — {reais(est.valor)} — {est.motivo_texto}:{' '}
                {est.justificativa} ({est.registrado_por.nome} em{' '}
                {dataEHora.format(new Date(est.registrado_em))})
              </li>
            ))}
          </ul>
        )}
        {temMaisEstornos && (
          <button type="button" onClick={() => void carregarMaisEstornos()}>
            Carregar mais estornos
          </button>
        )}
      </section>
    </Pagina>
  )
}
