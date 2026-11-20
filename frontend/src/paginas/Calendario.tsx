import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { eventos, type EventoNoCalendario } from '../api/eventos'
import { Alerta, Pagina } from '../componentes'
import { mensagemDoErro } from '../mensagens'

const MESES = [
  'janeiro',
  'fevereiro',
  'março',
  'abril',
  'maio',
  'junho',
  'julho',
  'agosto',
  'setembro',
  'outubro',
  'novembro',
  'dezembro',
]
const DIAS_DA_SEMANA = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']

interface Mes {
  ano: number
  mes: number // 0 a 11
}

function chave({ ano, mes }: Mes): string {
  return `${ano}-${String(mes + 1).padStart(2, '0')}`
}

function deslocar({ ano, mes }: Mes, quanto: number): Mes {
  const data = new Date(ano, mes + quanto, 1)
  return { ano: data.getFullYear(), mes: data.getMonth() }
}

/** A data e a hora vêm da API no fuso do clube ("2026-12-12T19:30:00-03:00"): o site só recorta o texto. */
function diaDe(inicio: string): number {
  return Number(inicio.slice(8, 10))
}

function horaDe(inicio: string): string {
  return inicio.slice(11, 16)
}

/** CA-11: a grade do mês com os eventos publicados e realizados; clicar no card abre o detalhe. */
export function Calendario() {
  const [mes, definirMes] = useState<Mes>(() => {
    const hoje = new Date()
    return { ano: hoje.getFullYear(), mes: hoje.getMonth() }
  })
  const [itens, definirItens] = useState<EventoNoCalendario[] | null>(null)
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    let vivo = true
    eventos
      .calendario(chave(mes))
      .then((dados) => vivo && definirItens(dados))
      .catch((e: unknown) => vivo && definirErro(e))
    return () => {
      vivo = false
    }
  }, [mes])

  function mudarMes(quanto: number) {
    definirItens(null)
    definirMes(deslocar(mes, quanto))
  }

  const diasNoMes = new Date(mes.ano, mes.mes + 1, 0).getDate()
  const primeiroDiaDaSemana = new Date(mes.ano, mes.mes, 1).getDay()
  const vazios = Array.from({ length: primeiroDiaDaSemana }, (_, i) => `vazio-${i}`)
  const dias = Array.from({ length: diasNoMes }, (_, i) => i + 1)

  return (
    <Pagina titulo="Calendário de eventos">
      <div className="navegacao-do-mes">
        <button type="button" onClick={() => mudarMes(-1)}>
          Mês anterior
        </button>
        <h2>
          {MESES[mes.mes]} de {mes.ano}
        </h2>
        <button type="button" onClick={() => mudarMes(1)}>
          Próximo mês
        </button>
      </div>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {itens === null && !erro && <p>Carregando…</p>}
      {itens?.length === 0 && <p>Nenhum evento neste mês.</p>}
      {/* A grade aparece sempre, também vazia ou carregando: o tamanho e os botões não mudam de lugar. */}
      <div className="calendario" role="grid" aria-label={`${MESES[mes.mes]} de ${mes.ano}`}>
          {DIAS_DA_SEMANA.map((dia) => (
            <div key={dia} className="calendario-cabecalho" role="columnheader">
              {dia}
            </div>
          ))}
          {vazios.map((id) => (
            <div key={id} className="calendario-dia vazio" />
          ))}
          {dias.map((dia) => (
            <div key={dia} className="calendario-dia" role="gridcell">
              <span className="calendario-numero">{dia}</span>
              {(itens ?? [])
                .filter((item) => diaDe(item.inicio) === dia)
                .map((item) => (
                  <Link key={item.id} to={`/eventos/${item.id}`} className="cartao-de-evento">
                    <strong>{item.titulo}</strong>
                    <span>
                      {horaDe(item.inicio)} · {item.local}
                    </span>
                    <span>{item.categoria_nome}</span>
                    {item.situacao === 'REALIZADO' && <span className="selo">Realizado</span>}
                  </Link>
                ))}
            </div>
          ))}
      </div>
    </Pagina>
  )
}
