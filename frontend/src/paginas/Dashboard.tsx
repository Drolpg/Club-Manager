import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { type DetalheDoUsuario } from '../api/permissoes'
import {
  dashboard,
  type Dashboard as DadosDoDashboard,
  type DashboardCompleto,
  type MinhasCobrancasDoPainel,
} from '../api/relatorios'
import { Alerta, Pagina } from '../componentes'
import { dataCurta, dataEHora, reais } from '../formatos'
import { mensagemDoErro } from '../mensagens'
import { useSessao } from '../sessao'
import { useMinhasDaMoldura } from '../useMinhas'

/** O cargo, os setores e as permissões de quem está logado (CA-26 do M3). A API só devolve os dele. */
function MinhasPermissoes({ detalhe }: { detalhe: DetalheDoUsuario }) {
  return (
    <section aria-label="Meu acesso">
      <p>Cargo: {detalhe.cargo?.nome}</p>
      <p>Setores: {detalhe.setores.length ? detalhe.setores.map((s) => s.nome).join(', ') : 'nenhum'}</p>
      <h2>Minhas permissões</h2>
      {detalhe.permissoes.length ? (
        <ul>
          {detalhe.permissoes.map((p) => (
            <li key={p.codigo}>{p.nome}</li>
          ))}
        </ul>
      ) : (
        <p>Nenhuma permissão concedida ainda.</p>
      )}
    </section>
  )
}

/** "2026-11" em "11/2026". */
function rotuloDoMes(mes: string): string {
  const [ano, numero] = mes.split('-')
  return `${numero}/${ano}`
}

/** Os meses de `de` até `ate` (AAAA-MM), do mais novo para o mais antigo. Só conta inteiros, sem datas. */
function mesesEntre(de: string, ate: string): string[] {
  const [anoDe, mesDe] = de.split('-').map(Number)
  let [ano, mes] = ate.split('-').map(Number)
  const meses: string[] = []
  while (ano > anoDe || (ano === anoDe && mes >= mesDe)) {
    meses.push(`${ano}-${String(mes).padStart(2, '0')}`)
    mes -= 1
    if (mes === 0) {
      mes = 12
      ano -= 1
    }
  }
  return meses
}

/** O primeiro e o último dia do mês (AAAA-MM), para filtrar a lista de lançamentos. */
function limitesDoMes(mes: string): { de: string; ate: string } {
  const [ano, numero] = mes.split('-').map(Number)
  const ultimo = new Date(Date.UTC(ano, numero, 0)).getUTCDate()
  return { de: `${mes}-01`, ate: `${mes}-${String(ultimo).padStart(2, '0')}` }
}

function contagem(quantidade: number, singular: string, plural: string): string {
  return `${quantidade} ${quantidade === 1 ? singular : plural}`
}

function MinhasCobrancas({ minhas }: { minhas: MinhasCobrancasDoPainel }) {
  return (
    <section aria-label="Minhas cobranças">
      <h2>Minhas cobranças</h2>
      <p>
        {minhas.em_aberto.quantidade} em aberto ({reais(minhas.em_aberto.total)}),{' '}
        {minhas.atrasadas.quantidade} atrasada{minhas.atrasadas.quantidade === 1 ? '' : 's'} (
        {reais(minhas.atrasadas.total)}) e {minhas.em_validacao.quantidade} em validação.
      </p>
      {minhas.proxima && (
        <p>
          Próxima: {minhas.proxima.descricao}, {reais(minhas.proxima.valor)}, vence em{' '}
          {dataCurta(minhas.proxima.vencimento)}.
        </p>
      )}
      <Link to="/minhas-cobrancas">Ver minhas cobranças</Link>
    </section>
  )
}

interface PropsDoPainel {
  painel: DashboardCompleto
  aoMudarMes: (mes: string) => void
}

function PainelCompleto({ painel, aoMudarMes }: PropsDoPainel) {
  const { do_mes: doMes, hoje } = painel
  const limites = limitesDoMes(painel.mes)
  const validacao = hoje.pendencias_de_validacao
  const aprovacao = hoje.pendencias_de_aprovacao
  const prestacoes = hoje.prestacoes_pendentes
  return (
    <>
      <label>
        Mês{' '}
        <select aria-label="Mês" value={painel.mes} onChange={(e) => aoMudarMes(e.target.value)}>
          {mesesEntre(painel.meses.de, painel.meses.ate).map((mes) => (
            <option key={mes} value={mes}>
              {rotuloDoMes(mes)}
            </option>
          ))}
        </select>
      </label>

      <section aria-label="Números do mês" className="painel-cartoes">
        <h2>{rotuloDoMes(painel.mes)}</h2>
        <dl>
          <dt>Entradas</dt>
          <dd>{reais(doMes.entradas)}</dd>
          <dt>Saídas</dt>
          <dd>{reais(doMes.saidas)}</dd>
          <dt>Resultado</dt>
          <dd>{reais(doMes.resultado)}</dd>
          <dt>Saldo acumulado</dt>
          <dd>{reais(doMes.saldo_acumulado)}</dd>
          <dt>A receber no mês</dt>
          <dd>
            {reais(doMes.a_receber.total)} ({contagem(doMes.a_receber.quantidade, 'cobrança', 'cobranças')})
          </dd>
        </dl>
        <Link to={`/lancamentos?de=${limites.de}&ate=${limites.ate}`}>Ver os lançamentos do mês</Link>
      </section>

      <section aria-label={`Hoje, ${dataCurta(hoje.data)}`} className="painel-cartoes">
        <h2>Hoje, {dataCurta(hoje.data)}</h2>
        <dl>
          <dt>Comprometido</dt>
          <dd>{reais(hoje.comprometido)}</dd>
          <dt>Saldo livre</dt>
          <dd>{reais(hoje.saldo_livre)}</dd>
          <dt>Pendências de validação</dt>
          <dd>
            {contagem(validacao.pagamentos.quantidade, 'pagamento', 'pagamentos')} (
            {reais(validacao.pagamentos.total)}) e{' '}
            {contagem(validacao.entradas.quantidade, 'entrada', 'entradas')} (
            {reais(validacao.entradas.total)})
          </dd>
          <dt>Pendências de aprovação</dt>
          <dd>
            <Link to="/fila">{aprovacao.minha_fila} na sua fila</Link>
            {aprovacao.por_tipo.length > 0 && (
              <ul>
                {aprovacao.por_tipo.map((t) => (
                  <li key={t.tipo}>
                    {t.nome}: {t.quantidade} em análise no clube
                  </li>
                ))}
              </ul>
            )}
          </dd>
          <dt>Prestações de contas</dt>
          <dd>
            <Link to="/saidas?fila=prestacao">{prestacoes.aguardando} aguardando prestação</Link>,{' '}
            {prestacoes.em_atraso} em atraso e {prestacoes.em_conferencia} em conferência
          </dd>
          <dt>Inadimplência</dt>
          <dd>
            <Link to="/cobrancas?inadimplentes=1">
              {contagem(hoje.inadimplencia.cobrancas, 'cobrança inadimplente', 'cobranças inadimplentes')}
            </Link>{' '}
            de {contagem(hoje.inadimplencia.devedores, 'devedor', 'devedores')},{' '}
            {reais(hoje.inadimplencia.total)}
          </dd>
        </dl>
      </section>

      <section aria-label="Próximos eventos">
        <h2>Próximos eventos</h2>
        {painel.proximos_eventos.length ? (
          <ul>
            {painel.proximos_eventos.map((e) => (
              <li key={e.id}>
                <Link to={`/eventos/${e.id}`}>{e.titulo}</Link> — {dataEHora.format(new Date(e.inicio))},{' '}
                {e.categoria_nome}
              </li>
            ))}
          </ul>
        ) : (
          <p>Nenhum evento publicado pela frente.</p>
        )}
      </section>

      <section aria-label="Últimos comunicados">
        <h2>Últimos comunicados</h2>
        {painel.ultimos_comunicados.length ? (
          <ul>
            {painel.ultimos_comunicados.map((c) => (
              <li key={c.id}>
                <Link to={`/feed/${c.id}`}>{c.titulo}</Link> — {dataEHora.format(new Date(c.publicado_em))}
                {c.fixado && <span className="marca"> fixado</span>}
              </li>
            ))}
          </ul>
        ) : (
          <p>Nenhum comunicado publicado.</p>
        )}
      </section>

      <MinhasCobrancas minhas={painel.minhas_cobrancas} />
    </>
  )
}

function usePainel(mes: string | undefined) {
  const [painel, definirPainel] = useState<DadosDoDashboard | null>(null)
  const [erro, definirErro] = useState<unknown>(null)
  useEffect(() => {
    let vivo = true
    dashboard(mes)
      .then((resposta) => {
        if (!vivo) return
        definirPainel(resposta)
        definirErro(null)
      })
      .catch((falha) => vivo && definirErro(falha))
    return () => {
      vivo = false
    }
  }, [mes])
  return { painel, erro }
}

/**
 * A página inicial: o dashboard (RF-102, RF-103). Os números chegam prontos da API, que escolhe o completo
 * ou o básico; o site só formata. O aviso de classificação e o bloco "Meu acesso" continuam como estavam
 * (D10), e um erro do painel aparece só no bloco dele.
 */
export function Dashboard() {
  const { usuario } = useSessao()
  const { detalhe, erro: erroMinhas } = useMinhasDaMoldura()
  const [mes, definirMes] = useState<string | undefined>(undefined)
  const { painel, erro } = usePainel(mes)
  if (!usuario) return null

  return (
    <Pagina titulo="Club Manager">
      {!usuario.tem_cargo && !usuario.admin && (
        <p>Seu cadastro está concluído e aguarda a classificação pelo administrador do clube.</p>
      )}
      {erro ? (
        <p className="erro-do-painel">Não foi possível carregar o painel: {mensagemDoErro(erro)}</p>
      ) : null}
      {painel?.tipo === 'COMPLETO' && <PainelCompleto painel={painel} aoMudarMes={definirMes} />}
      {painel?.tipo === 'BASICO' && (
        <>
          <MinhasCobrancas minhas={painel.minhas_cobrancas} />
          <p>
            Você tem{' '}
            {contagem(painel.notificacoes_nao_lidas, 'notificação não lida', 'notificações não lidas')}, no
            sino do cabeçalho.
          </p>
        </>
      )}
      {usuario.tem_cargo && erroMinhas ? <Alerta>{mensagemDoErro(erroMinhas)}</Alerta> : null}
      {usuario.tem_cargo && detalhe && <MinhasPermissoes detalhe={detalhe} />}
    </Pagina>
  )
}
