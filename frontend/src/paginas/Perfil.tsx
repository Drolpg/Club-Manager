import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import { acesso } from '../api/acesso'
import {
  relatorios,
  type CobrancaDoPerfil,
  type DadosDoPerfil,
  type EventoDoPerfil,
  type Perfil as PerfilCompleto,
} from '../api/relatorios'
import { Alerta, Campo, Pagina } from '../componentes'
import { dataCurta, dataEHora, reais } from '../formatos'
import {
  SITUACAO_DA_COBRANCA,
  SITUACAO_DO_EVENTO,
  SITUACAO_DO_PAGAMENTO,
  errosPorCampo,
  mensagemDoErro,
} from '../mensagens'

const FORMA_DO_PAGAMENTO: Record<string, string> = { COMPROVANTE: 'Comprovante', EM_MAO: 'Em mãos' }
const PAPEL_NO_EVENTO: Record<string, string> = {
  PROPONENTE: 'Propôs',
  PRESENCA: 'Respondeu à presença',
  PROPONENTE_E_PRESENCA: 'Propôs e respondeu à presença',
}
const RESPOSTA_DE_PRESENCA: Record<string, string> = { VOU: 'Vou', NAO_VOU: 'Não vou' }

function FormularioDoTelefone({
  telefone,
  aoSalvar,
}: {
  telefone: string
  aoSalvar: (novo: string) => void
}) {
  const [valor, definirValor] = useState(telefone)
  const [erro, definirErro] = useState<unknown>(null)
  const [salvo, definirSalvo] = useState(false)
  const campos = errosPorCampo(erro)

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    definirErro(null)
    definirSalvo(false)
    try {
      // Só o telefone vai na chamada: nome, nome de usuário e e-mail não mudam por aqui.
      const resposta = await acesso.alterarTelefone(valor)
      definirValor(resposta.telefone)
      aoSalvar(resposta.telefone)
      definirSalvo(true)
    } catch (e) {
      definirErro(e)
    }
  }

  return (
    <form aria-label="Telefone" onSubmit={(evento) => void enviar(evento)}>
      <Campo rotulo="Telefone" value={valor} erros={campos.telefone} aoMudar={definirValor} />
      <Alerta>{erro && !Object.keys(campos).length ? mensagemDoErro(erro) : null}</Alerta>
      {salvo && <p role="status">Telefone atualizado.</p>}
      <button type="submit">Salvar telefone</button>
    </form>
  )
}

function SecaoDeDados({
  dados,
  proprio,
  aoSalvarTelefone,
}: {
  dados: DadosDoPerfil
  proprio: boolean
  aoSalvarTelefone: (novo: string) => void
}) {
  return (
    <section aria-label="Dados">
      <h2>Dados</h2>
      <p>{dados.nome}</p>
      <p>
        {dados.nome_de_usuario} · {dados.email} · {dados.ativo ? 'Ativo' : 'Desativado'}
        {dados.admin ? ' · Admin' : ''}
      </p>
      <p>
        {dados.cargo ? `Cargo: ${dados.cargo}` : 'Sem cargo'}
        {dados.setores.length ? ` · Setores: ${dados.setores.join(', ')}` : ''}
      </p>
      <p>Cadastro em {dataEHora.format(new Date(dados.cadastrado_em))}</p>
      {proprio ? (
        <FormularioDoTelefone telefone={dados.telefone} aoSalvar={aoSalvarTelefone} />
      ) : (
        <p>Telefone: {dados.telefone}</p>
      )}
    </section>
  )
}

function ItemDeCobranca({ cobranca }: { cobranca: CobrancaDoPerfil }) {
  return (
    <li>
      {cobranca.descricao} · {SITUACAO_DA_COBRANCA[cobranca.situacao] ?? cobranca.situacao} ·{' '}
      {reais(cobranca.valor)} · vence em {dataCurta(cobranca.vencimento)}{' '}
      <Link to={`/cobrancas/${cobranca.id}`}>Abrir cobrança</Link>
      {cobranca.pagamentos.length > 0 && (
        <ul>
          {cobranca.pagamentos.map((pagamento, indice) => (
            <li key={`${pagamento.data_pagamento}-${indice}`}>
              {FORMA_DO_PAGAMENTO[pagamento.forma] ?? pagamento.forma} ·{' '}
              {dataCurta(pagamento.data_pagamento)} ·{' '}
              {SITUACAO_DO_PAGAMENTO[pagamento.situacao] ?? pagamento.situacao}
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

function ItemDeEvento({ evento }: { evento: EventoDoPerfil }) {
  return (
    <li>
      <Link to={`/eventos/${evento.id}`}>{evento.titulo}</Link> ·{' '}
      {dataEHora.format(new Date(evento.inicio))} · {evento.local} ·{' '}
      {SITUACAO_DO_EVENTO[evento.situacao] ?? evento.situacao} ·{' '}
      {PAPEL_NO_EVENTO[evento.papel] ?? evento.papel}
      {evento.resposta ? ` (${RESPOSTA_DE_PRESENCA[evento.resposta] ?? evento.resposta})` : ''}
    </li>
  )
}

/** CA-01 a CA-07: o próprio perfil (`/perfil`) ou, só para o admin, o de outro (`.../:id/perfil`). */
export function Perfil() {
  const { id } = useParams()
  const proprio = id === undefined
  const [perfil, definirPerfil] = useState<PerfilCompleto | null>(null)
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    let vivo = true
    relatorios
      .perfil(id)
      .then((dados) => vivo && definirPerfil(dados))
      .catch((e: unknown) => vivo && definirErro(e))
    return () => {
      vivo = false
    }
  }, [id])

  async function maisCobrancas() {
    const ultima = perfil?.cobrancas.itens.at(-1)
    if (!perfil || !ultima) return
    try {
      const pagina = await relatorios.cobrancas(id, ultima.id)
      const itens = [...perfil.cobrancas.itens, ...pagina.itens]
      definirPerfil({ ...perfil, cobrancas: { itens, tem_mais: pagina.tem_mais } })
    } catch (e) {
      definirErro(e)
    }
  }

  async function maisEventos() {
    const ultimo = perfil?.eventos.itens.at(-1)
    if (!perfil || !ultimo) return
    try {
      const pagina = await relatorios.eventos(id, ultimo.id)
      const itens = [...perfil.eventos.itens, ...pagina.itens]
      definirPerfil({ ...perfil, eventos: { itens, tem_mais: pagina.tem_mais } })
    } catch (e) {
      definirErro(e)
    }
  }

  if (!perfil) {
    const conteudo = erro ? <Alerta>{mensagemDoErro(erro)}</Alerta> : <p>Carregando…</p>
    return <Pagina titulo={proprio ? 'Meu perfil' : 'Perfil do usuário'}>{conteudo}</Pagina>
  }

  // A caixa só vem no próprio perfil: se ela não veio, quem olha é o admin vendo outra pessoa.
  const naoLidas = perfil.notificacoes?.nao_lidas
  const mostrarNotificacoes = naoLidas !== undefined

  return (
    <Pagina titulo={proprio ? 'Meu perfil' : `Perfil de ${perfil.dados.nome}`}>
      {!mostrarNotificacoes && (
        <p className="ajuda">Esta consulta fica registrada no histórico de auditoria.</p>
      )}
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      <SecaoDeDados
        dados={perfil.dados}
        proprio={mostrarNotificacoes}
        aoSalvarTelefone={(telefone) => definirPerfil({ ...perfil, dados: { ...perfil.dados, telefone } })}
      />

      <section aria-label="Histórico de pagamentos">
        <h2>Histórico de pagamentos</h2>
        {perfil.cobrancas.itens.length === 0 && <p>Nenhuma cobrança.</p>}
        <ul className="lista">
          {perfil.cobrancas.itens.map((cobranca) => (
            <ItemDeCobranca key={cobranca.id} cobranca={cobranca} />
          ))}
        </ul>
        {perfil.cobrancas.tem_mais && (
          <button type="button" onClick={() => void maisCobrancas()}>
            Carregar mais cobranças
          </button>
        )}
      </section>

      <section aria-label="Eventos relacionados">
        <h2>Eventos relacionados</h2>
        {perfil.eventos.itens.length === 0 && <p>Nenhum evento.</p>}
        <ul className="lista">
          {perfil.eventos.itens.map((evento) => (
            <ItemDeEvento key={evento.id} evento={evento} />
          ))}
        </ul>
        {perfil.eventos.tem_mais && (
          <button type="button" onClick={() => void maisEventos()}>
            Carregar mais eventos
          </button>
        )}
      </section>

      {mostrarNotificacoes && (
        <section aria-label="Notificações">
          <h2>Notificações</h2>
          <p>{naoLidas === 1 ? '1 não lida' : `${naoLidas} não lidas`}. A caixa fica no sino do cabeçalho.</p>
          <Link to="/preferencias">Preferências de alerta</Link>
        </section>
      )}
    </Pagina>
  )
}
