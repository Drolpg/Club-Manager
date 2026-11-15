import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  PERM_COBRANCAS_CRIAR,
  PERM_COBRANCAS_SUSPENDER,
  financeiro,
  type Categoria,
  type Periodicidade,
  type Recorrencia,
  type Suspensao,
} from '../api/financeiro'
import { Alerta, Campo, Pagina, Selecao } from '../componentes'
import { dataCurta, reais } from '../formatos'
import {
  PERIODICIDADE_FINANCEIRA,
  SITUACAO_DA_SUSPENSAO,
  errosPorCampo,
  mensagemDoErro,
} from '../mensagens'
import { usePodeFinanceiro } from '../useFinanceiro'

function LinhaRecorrencia({
  recorrencia,
  categorias,
  podeEditar,
  executar,
}: {
  recorrencia: Recorrencia
  categorias: Categoria[]
  podeEditar: boolean
  executar: (acao: () => Promise<unknown>) => Promise<boolean>
}) {
  const [editando, definirEditando] = useState(false)
  const [categoriaId, definirCategoriaId] = useState(recorrencia.categoria_id)
  const [descricao, definirDescricao] = useState(recorrencia.descricao)
  const [valor, definirValor] = useState(recorrencia.valor)
  const [dia, definirDia] = useState(String(recorrencia.dia_vencimento))

  async function salvar(evento: FormEvent) {
    evento.preventDefault()
    const ok = await executar(() =>
      financeiro.editarRecorrencia(recorrencia.id, {
        categoria_id: categoriaId,
        descricao,
        valor,
        dia_vencimento: Number(dia),
        mes_vencimento: recorrencia.mes_vencimento,
        antecedencia_dias: recorrencia.antecedencia_dias,
        limite_de_inadimplencia: recorrencia.limite_de_inadimplencia,
        chave_pix_id: recorrencia.chave_pix_id,
      }),
    )
    if (ok) definirEditando(false)
  }

  if (editando) {
    return (
      <li>
        <form onSubmit={(e) => void salvar(e)}>
          <Selecao rotulo="Categoria" value={categoriaId} aoMudar={definirCategoriaId}>
            {categorias.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome}
              </option>
            ))}
          </Selecao>
          <Campo rotulo="Descrição" value={descricao} aoMudar={definirDescricao} />
          <Campo rotulo="Valor (R$)" value={valor} aoMudar={definirValor} />
          <Campo rotulo="Dia do vencimento" type="number" value={dia} aoMudar={definirDia} />
          <button type="submit">Salvar</button>
          <button type="button" onClick={() => definirEditando(false)}>
            Desistir
          </button>
        </form>
      </li>
    )
  }

  return (
    <li>
      <span>
        {recorrencia.descricao} — {recorrencia.devedor.nome} — {reais(recorrencia.valor)} (
        {PERIODICIDADE_FINANCEIRA[recorrencia.periodicidade] ?? recorrencia.periodicidade}, dia{' '}
        {recorrencia.dia_vencimento})
      </span>{' '}
      {!recorrencia.ativa && <span className="selo">Inativa</span>}{' '}
      {podeEditar && recorrencia.ativa && (
        <>
          <button type="button" onClick={() => definirEditando(true)}>
            Editar
          </button>{' '}
          <button
            type="button"
            onClick={() => void executar(() => financeiro.desativarRecorrencia(recorrencia.id))}
          >
            Desativar
          </button>
        </>
      )}
    </li>
  )
}

/** Gestão de recorrências financeiras e suspensões temporárias de cobrança. */
export function RecorrenciasESuspensoes() {
  const podeCriar = usePodeFinanceiro(PERM_COBRANCAS_CRIAR)
  const podeSuspender = usePodeFinanceiro(PERM_COBRANCAS_SUSPENDER)

  const [categorias, definirCategorias] = useState<Categoria[]>([])
  const [recorrencias, definirRecorrencias] = useState<Recorrencia[]>([])
  const [suspensoes, definirSuspensoes] = useState<Suspensao[]>([])
  const [todasRec, definirTodasRec] = useState(false)
  const [todasSus, definirTodasSus] = useState(false)
  const [erro, definirErro] = useState<unknown>(null)

  const [devedorId, definirDevedorId] = useState('')
  const [categoriaId, definirCategoriaId] = useState('')
  const [descricao, definirDescricao] = useState('')
  const [valor, definirValor] = useState('')
  const [periodicidade, definirPeriodicidade] = useState<Periodicidade>('MENSAL')
  const [dia, definirDia] = useState('10')
  const [mes, definirMes] = useState('')
  const [antecedencia, definirAntecedencia] = useState('5')

  const [diretorSusId, definirDiretorSusId] = useState('')
  const [recSusId, definirRecSusId] = useState('')
  const [inicioSus, definirInicioSus] = useState('')
  const [fimSus, definirFimSus] = useState('')
  const [justificativaSus, definirJustificativaSus] = useState('')

  const recarregar = useCallback(() => {
    Promise.all([
      financeiro.categorias({ natureza: 'ENTRADA' }),
      financeiro.recorrencias({ todas: todasRec }),
      financeiro.suspensoes({ todas: todasSus }),
    ])
      .then(([cats, recs, suss]) => {
        definirCategorias(cats)
        definirRecorrencias(recs)
        definirSuspensoes(suss)
        definirErro(null)
      })
      .catch(definirErro)
  }, [todasRec, todasSus])

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

  async function criarRecorrencia(evento: FormEvent) {
    evento.preventDefault()
    const ok = await executar(() =>
      financeiro.criarRecorrencia({
        devedor_id: devedorId,
        categoria_id: categoriaId,
        descricao,
        valor,
        periodicidade,
        dia_vencimento: Number(dia),
        mes_vencimento: periodicidade === 'ANUAL' && mes ? Number(mes) : null,
        antecedencia_dias: Number(antecedencia),
        limite_de_inadimplencia: 30,
      }),
    )
    if (ok) {
      definirDescricao('')
      definirValor('')
    }
  }

  async function criarSuspensao(evento: FormEvent) {
    evento.preventDefault()
    const ok = await executar(() =>
      financeiro.criarSuspensao({
        diretor_id: diretorSusId,
        recorrencia_id: recSusId || null,
        inicio: inicioSus,
        fim: fimSus || null,
        justificativa: justificativaSus,
      }),
    )
    if (ok) {
      definirJustificativaSus('')
    }
  }

  const campos = errosPorCampo(erro)
  return (
    <Pagina titulo="Recorrências e suspensões">
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>

      <section aria-label="Recorrências">
        <h2>Recorrências</h2>
        <label className="opcao">
          <input type="checkbox" checked={todasRec} onChange={(e) => definirTodasRec(e.target.checked)} />
          Incluir inativas
        </label>
        <ul>
          {recorrencias.map((r) => (
            <LinhaRecorrencia
              key={r.id}
              recorrencia={r}
              categorias={categorias}
              podeEditar={podeCriar}
              executar={executar}
            />
          ))}
        </ul>

        {podeCriar && (
          <form aria-label="Nova recorrência" onSubmit={(e) => void criarRecorrencia(e)}>
            <h3>Nova recorrência</h3>
            <Campo rotulo="ID do devedor" value={devedorId} aoMudar={definirDevedorId} erros={campos.devedor_id} />
            <Selecao rotulo="Categoria" value={categoriaId} aoMudar={definirCategoriaId}>
              <option value="">Escolha a categoria</option>
              {categorias.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </Selecao>
            <Campo rotulo="Descrição" value={descricao} aoMudar={definirDescricao} />
            <Campo rotulo="Valor (R$)" inputMode="decimal" value={valor} aoMudar={definirValor} />
            <Selecao
              rotulo="Periodicidade"
              value={periodicidade}
              aoMudar={(v) => definirPeriodicidade(v as Periodicidade)}
            >
              {Object.entries(PERIODICIDADE_FINANCEIRA).map(([codigo, rotulo]) => (
                <option key={codigo} value={codigo}>
                  {rotulo}
                </option>
              ))}
            </Selecao>
            <Campo rotulo="Dia do vencimento" type="number" value={dia} aoMudar={definirDia} />
            {periodicidade === 'ANUAL' && (
              <Campo rotulo="Mês do vencimento" type="number" value={mes} aoMudar={definirMes} />
            )}
            <Campo rotulo="Antecedência (dias)" type="number" value={antecedencia} aoMudar={definirAntecedencia} />
            <button type="submit">Criar recorrência</button>
          </form>
        )}
      </section>

      <section aria-label="Suspensões">
        <h2>Suspensões</h2>
        <label className="opcao">
          <input type="checkbox" checked={todasSus} onChange={(e) => definirTodasSus(e.target.checked)} />
          Incluir encerradas
        </label>
        <ul>
          {suspensoes.map((s) => (
            <li key={s.id}>
              <span>
                {s.diretor.nome} — {dataCurta(s.inicio)} a {dataCurta(s.fim)} — {s.justificativa} (
                {SITUACAO_DA_SUSPENSAO[s.situacao] ?? s.situacao})
              </span>{' '}
              {podeSuspender && s.situacao === 'VIGENTE' && (
                <button
                  type="button"
                  onClick={() => void executar(() => financeiro.encerrarSuspensao(s.id))}
                >
                  Encerrar
                </button>
              )}
            </li>
          ))}
        </ul>

        {podeSuspender && (
          <form aria-label="Nova suspensão" onSubmit={(e) => void criarSuspensao(e)}>
            <h3>Nova suspensão</h3>
            <Campo rotulo="ID do diretor" value={diretorSusId} aoMudar={definirDiretorSusId} />
            <Selecao rotulo="Recorrência (opcional)" value={recSusId} aoMudar={definirRecSusId}>
              <option value="">Todas as recorrências do diretor</option>
              {recorrencias.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.descricao} ({r.devedor.nome})
                </option>
              ))}
            </Selecao>
            <Campo rotulo="Início" type="date" value={inicioSus} aoMudar={definirInicioSus} />
            <Campo rotulo="Fim (opcional)" type="date" value={fimSus} aoMudar={definirFimSus} />
            <Campo rotulo="Justificativa" value={justificativaSus} aoMudar={definirJustificativaSus} />
            <button type="submit">Suspender</button>
          </form>
        )}
      </section>
    </Pagina>
  )
}
