import { useCallback, useEffect, useId, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import {
  PERM_ENTRADAS_REGISTRAR,
  TIPO_DECISAO_FINANCEIRO,
  financeiro,
  urlComprovanteEntrada,
  type AcaoEntrada,
  type Categoria,
  type Entrada,
  type FiltrosEntradas,
  type ResumoEntradas,
} from '../api/financeiro'
import { Alerta, Campo, Pagina, Selecao } from '../componentes'
import { dataCurta, reais } from '../formatos'
import { SITUACAO_DA_ENTRADA, errosPorCampo, mensagemDoErro } from '../mensagens'
import { useMotivosPorTipo, usePodeFinanceiro } from '../useFinanceiro'
import { AreaDeTexto, SeletorDeMotivo } from './apoioFinanceiro'
import { BlocoEstorno } from './apoioSaidas'

const TIPO_DECISAO_ENTRADA: Record<AcaoEntrada, string> = {
  validar: TIPO_DECISAO_FINANCEIRO.entrada_validar,
  rejeitar: TIPO_DECISAO_FINANCEIRO.entrada_rejeitar,
  estornar: TIPO_DECISAO_FINANCEIRO.estornar,
}

const ROTULO_DECISAO_ENTRADA: Record<AcaoEntrada, string> = {
  validar: 'Validar entrada',
  rejeitar: 'Rejeitar entrada',
  estornar: 'Estornar entrada',
}

function FormularioDecisaoEntrada({
  entradaId,
  acao,
  aoConcluir,
  aoFechar,
}: {
  entradaId: string
  acao: AcaoEntrada
  aoConcluir: () => void
  aoFechar: () => void
}) {
  const motivos = useMotivosPorTipo(TIPO_DECISAO_ENTRADA[acao])
  const [motivoId, definirMotivoId] = useState('')
  const [texto, definirTexto] = useState('')
  const [erro, definirErro] = useState<unknown>(null)
  const campos = errosPorCampo(erro)

  async function confirmar(evento: FormEvent) {
    evento.preventDefault()
    definirErro(null)
    try {
      if (acao === 'validar') {
        await financeiro.validarEntrada(entradaId, { motivo_id: motivoId, texto })
      } else if (acao === 'rejeitar') {
        await financeiro.rejeitarEntrada(entradaId, { motivo_id: motivoId, texto })
      } else {
        await financeiro.estornarEntrada(entradaId, { motivo_id: motivoId, justificativa: texto })
      }
      aoConcluir()
    } catch (falha) {
      definirErro(falha)
    }
  }

  return (
    <form aria-label={ROTULO_DECISAO_ENTRADA[acao]} onSubmit={(e) => void confirmar(e)}>
      <SeletorDeMotivo
        motivos={motivos}
        valor={motivoId}
        aoMudar={definirMotivoId}
        erros={campos.motivo_id}
      />
      <AreaDeTexto
        rotulo={acao === 'estornar' ? 'Justificativa' : 'Texto (opcional)'}
        valor={texto}
        aoMudar={definirTexto}
        erros={acao === 'estornar' ? campos.justificativa : campos.texto}
      />
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      <button type="submit">Confirmar</button>
      <button type="button" onClick={aoFechar}>
        Fechar
      </button>
    </form>
  )
}

/** Entradas sem devedor e devoluções de saída: registro, validação, rejeição e resumo consolidado. */
export function Entradas() {
  const podeRegistrar = usePodeFinanceiro(PERM_ENTRADAS_REGISTRAR)
  const fileId = useId()

  const [filtros, definirFiltros] = useState<FiltrosEntradas>({})
  const [categorias, definirCategorias] = useState<Categoria[]>([])
  const [itens, definirItens] = useState<Entrada[]>([])
  const [temMais, definirTemMais] = useState(false)
  const [resumo, definirResumo] = useState<ResumoEntradas | null>(null)
  const [decidindo, definirDecidindo] = useState<{ id: string; acao: AcaoEntrada } | null>(null)
  const [erro, definirErro] = useState<unknown>(null)
  const [recarga, definirRecarga] = useState(0)

  const [categoriaId, definirCategoriaId] = useState('')
  const [valor, definirValor] = useState('')
  const [data, definirData] = useState('')
  const [origem, definirOrigem] = useState('')
  const [evidencia, definirEvidencia] = useState('')
  const [comprovante, definirComprovante] = useState<File | null>(null)

  const carregarResumo = useCallback(() => {
    const { categoria_id, de, ate } = filtros
    financeiro
      .resumoEntradas({ categoria_id, de, ate })
      .then(definirResumo)
      .catch(definirErro)
  }, [filtros])

  useEffect(() => {
    financeiro.categorias({ natureza: 'ENTRADA' }).then(definirCategorias).catch(definirErro)
  }, [])

  useEffect(() => {
    let vivo = true
    carregarResumo()
    financeiro
      .entradas(filtros)
      .then((pagina) => {
        if (!vivo) return
        definirItens(pagina.itens)
        definirTemMais(pagina.tem_mais)
      })
      .catch((falha) => vivo && definirErro(falha))
    return () => {
      vivo = false
    }
  }, [filtros, recarga, carregarResumo])

  async function registrar(evento: FormEvent) {
    evento.preventDefault()
    definirErro(null)
    try {
      await financeiro.registrarEntrada({
        categoria_id: categoriaId,
        valor,
        data,
        origem,
        evidencia_texto: evidencia,
        comprovante,
      })
      definirValor('')
      definirOrigem('')
      definirEvidencia('')
      definirComprovante(null)
      definirRecarga((r) => r + 1)
    } catch (falha) {
      definirErro(falha)
    }
  }

  async function carregarMais() {
    const ultimo = itens[itens.length - 1]
    if (!ultimo) return
    try {
      const pagina = await financeiro.entradas({ ...filtros, antes: ultimo.id })
      definirItens((atuais) => [...atuais, ...pagina.itens])
      definirTemMais(pagina.tem_mais)
    } catch (falha) {
      definirErro(falha)
    }
  }

  const campos = errosPorCampo(erro)
  return (
    <Pagina titulo="Entradas sem devedor">
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {resumo && (
        <p>
          Total validado: {reais(resumo.total)} ({resumo.quantidade})
        </p>
      )}

      <form aria-label="Filtrar entradas" onSubmit={(e) => e.preventDefault()}>
        <Selecao
          rotulo="Situação"
          value={filtros.situacao ?? ''}
          aoMudar={(situacao) => definirFiltros({ ...filtros, situacao: situacao || undefined })}
        >
          <option value="">Todas</option>
          {Object.entries(SITUACAO_DA_ENTRADA).map(([codigo, rotulo]) => (
            <option key={codigo} value={codigo}>
              {rotulo}
            </option>
          ))}
        </Selecao>
        <Selecao
          rotulo="Categoria"
          value={filtros.categoria_id ?? ''}
          aoMudar={(categoria_id) =>
            definirFiltros({ ...filtros, categoria_id: categoria_id || undefined })
          }
        >
          <option value="">Todas</option>
          {categorias.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nome}
            </option>
          ))}
        </Selecao>
      </form>

      <ul>
        {itens.map((item) => (
          <li key={item.id}>
            <div>
              <strong>{item.origem}</strong> — {item.categoria_nome} — {reais(item.valor)} em{' '}
              {dataCurta(item.data)} ({SITUACAO_DA_ENTRADA[item.situacao] ?? item.situacao})
            </div>
            {item.evidencia_texto && <p>{item.evidencia_texto}</p>}
            {item.comprovante_disponivel && (
              <p>
                <a
                  href={urlComprovanteEntrada(item.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Abrir comprovante
                </a>
              </p>
            )}
            {item.acoes.includes('validar') && (
              <button
                type="button"
                onClick={() => definirDecidindo({ id: item.id, acao: 'validar' })}
              >
                Validar
              </button>
            )}{' '}
            {item.acoes.includes('rejeitar') && (
              <button
                type="button"
                onClick={() => definirDecidindo({ id: item.id, acao: 'rejeitar' })}
              >
                Rejeitar
              </button>
            )}{' '}
            {item.acoes.includes('estornar') && (
              <button
                type="button"
                onClick={() => definirDecidindo({ id: item.id, acao: 'estornar' })}
              >
                Estornar
              </button>
            )}
            {item.saida_id && (
              <p>
                Devolução vinculada à <Link to={`/saidas/${item.saida_id}`}>saída</Link>
              </p>
            )}
            {item.estorno && <BlocoEstorno estorno={item.estorno} />}
            {decidindo?.id === item.id && (
              <FormularioDecisaoEntrada
                key={`${item.id}-${decidindo.acao}`}
                entradaId={item.id}
                acao={decidindo.acao}
                aoFechar={() => definirDecidindo(null)}
                aoConcluir={() => {
                  definirDecidindo(null)
                  definirRecarga((r) => r + 1)
                }}
              />
            )}
          </li>
        ))}
      </ul>

      {temMais && (
        <button type="button" onClick={() => void carregarMais()}>
          Carregar mais
        </button>
      )}

      {podeRegistrar && (
        <form aria-label="Registrar entrada" onSubmit={(e) => void registrar(e)}>
          <h3>Registrar entrada</h3>
          <Selecao rotulo="Categoria" value={categoriaId} aoMudar={definirCategoriaId}>
            <option value="">Escolha a categoria</option>
            {categorias.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome}
              </option>
            ))}
          </Selecao>
          <Campo rotulo="Valor (R$)" inputMode="decimal" value={valor} aoMudar={definirValor} erros={campos.valor} />
          <Campo rotulo="Data" type="date" value={data} aoMudar={definirData} erros={campos.data} />
          <Campo rotulo="Origem" value={origem} aoMudar={definirOrigem} erros={campos.origem} />
          <Campo
            rotulo="Evidência em texto"
            value={evidencia}
            aoMudar={definirEvidencia}
            erros={campos.evidencia_texto}
          />
          <div className="campo">
            <label htmlFor={fileId}>Comprovante (opcional)</label>
            <input
              id={fileId}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.webp"
              onChange={(e) => definirComprovante(e.target.files?.[0] ?? null)}
            />
          </div>
          <button type="submit">Registrar entrada</button>
        </form>
      )}
    </Pagina>
  )
}
