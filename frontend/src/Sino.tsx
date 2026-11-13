import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { notificacoes, type Notificacao, type Resumo } from './api/notificacoes'
import { Alerta } from './componentes'
import { mensagemDoErro } from './mensagens'
import { useSessao } from './sessao'
import { useCaixa } from './useCaixa'

/** O indicador se atualiza sozinho a cada minuto (decisão 2 da spec: sem tempo real). */
const INTERVALO_DA_CONSULTA_MS = 60_000
/** Quanto tempo o aviso flutuante fica na tela. */
const DURACAO_DO_AVISO_MS = 6_000

/** Só caminhos do próprio site: um caminho vindo da API nunca leva o usuário para outro endereço. */
function caminhoDoSite(caminho: string): boolean {
  return caminho === '/' || /^\/[^/\\]/.test(caminho)
}

function rotuloDoSino(naoLidas: number): string {
  return naoLidas > 0 ? `Notificações, ${naoLidas} não lidas` : 'Notificações'
}

function Caixa({ aoFechar, aoMudar }: { aoFechar: () => void; aoMudar: () => void }) {
  const navegar = useNavigate()
  const { recarregar } = useSessao()
  const { itens, temMais, carregando, erro, carregarMais, ler, lerTodas } = useCaixa(aoMudar)

  async function abrirItem(item: Notificacao) {
    if (!(await ler(item))) return
    // A notificação pode dizer que algo mudou para o usuário (cargo, papel, permissão): atualiza o que o site sabe.
    void recarregar()
    aoFechar()
    if (caminhoDoSite(item.caminho)) void navegar(item.caminho)
  }

  return (
    <section className="caixa" aria-label="Caixa de notificações">
      <header>
        <h2>Notificações</h2>
        <button type="button" onClick={() => void lerTodas()}>
          Marcar todas como lidas
        </button>
        <button type="button" onClick={aoFechar}>
          Fechar
        </button>
      </header>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {!carregando && !erro && itens.length === 0 && <p>Nenhuma notificação.</p>}
      <ul>
        {itens.map((item) => (
          <li key={item.id} data-lida={item.lida_em !== null}>
            <button type="button" onClick={() => void abrirItem(item)}>
              <strong>{item.titulo}</strong> <span>{item.texto}</span>
              {item.lida_em === null && <span className="selo">Nova</span>}
            </button>
          </li>
        ))}
      </ul>
      {temMais && (
        <button type="button" onClick={() => void carregarMais()}>
          Carregar mais
        </button>
      )}
    </section>
  )
}

/**
 * O sino das telas logadas: o indicador de não lidas, o aviso flutuante e a caixa (RF-031, RF-032).
 *
 * Consulta `resumo/` ao montar e a cada minuto, só com a aba visível. Uma falha de consulta não vira alerta:
 * o sino é discreto, e a consulta seguinte tenta de novo.
 */
export function Sino() {
  const [resumo, definirResumo] = useState<Resumo | null>(null)
  const [aberta, definirAberta] = useState(false)
  const [aviso, definirAviso] = useState<Notificacao | null>(null)
  const vivo = useRef(false)
  // `undefined` até a primeira consulta dar certo: ela só marca o ponto de partida, sem avisar.
  const ultimoVisto = useRef<string | null | undefined>(undefined)

  const avisarDaChegada = useCallback(async () => {
    try {
      const preferencias = await notificacoes.preferencias()
      if (!preferencias.aviso_na_tela) return
      const { itens } = await notificacoes.caixa(undefined, 1)
      if (vivo.current && itens[0]) definirAviso(itens[0])
    } catch {
      // Sem a preferência ou o conteúdo, não há o que mostrar. O indicador já se atualizou.
    }
  }, [])

  // Guarda o resultado e, se chegou algo novo desde a consulta anterior, tenta avisar.
  const aplicar = useCallback(
    (novo: Resumo) => {
      if (!vivo.current) return
      definirResumo(novo)
      const anterior = ultimoVisto.current
      ultimoVisto.current = novo.mais_recente_id
      if (anterior !== undefined && novo.mais_recente_id !== null && novo.mais_recente_id !== anterior) {
        void avisarDaChegada()
      }
    },
    [avisarDaChegada],
  )

  const consultar = useCallback(() => {
    notificacoes
      .resumo()
      .then(aplicar)
      .catch(() => undefined) // A próxima consulta tenta de novo.
  }, [aplicar])

  useEffect(() => {
    vivo.current = true
    const seVisivel = () => {
      if (document.visibilityState === 'visible') consultar()
    }
    consultar()
    const intervalo = setInterval(seVisivel, INTERVALO_DA_CONSULTA_MS)
    document.addEventListener('visibilitychange', seVisivel)
    return () => {
      vivo.current = false
      clearInterval(intervalo)
      document.removeEventListener('visibilitychange', seVisivel)
    }
  }, [consultar])

  useEffect(() => {
    if (!aviso) return
    const espera = setTimeout(() => definirAviso(null), DURACAO_DO_AVISO_MS)
    return () => clearTimeout(espera)
  }, [aviso])

  const naoLidas = resumo?.nao_lidas ?? 0
  return (
    <div className="sino">
      <button
        type="button"
        className="sino-botao"
        aria-label={rotuloDoSino(naoLidas)}
        aria-expanded={aberta}
        onClick={() => definirAberta((estavaAberta) => !estavaAberta)}
      >
        <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
          <path d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Zm7-6v-5a7 7 0 0 0-5.5-6.84V3.5a1.5 1.5 0 0 0-3 0v.66A7 7 0 0 0 5 11v5l-2 2v1h18v-1l-2-2Z" />
        </svg>
        {naoLidas > 0 && <span className="contador">{naoLidas > 99 ? '99+' : naoLidas}</span>}
      </button>
      {aviso && (
        <div role="status" className="aviso-flutuante">
          <strong>{aviso.titulo}</strong>
          <span>{aviso.texto}</span>
        </div>
      )}
      {aberta && <Caixa aoFechar={() => definirAberta(false)} aoMudar={() => consultar()} />}
    </div>
  )
}
