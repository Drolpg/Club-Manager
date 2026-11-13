import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import { acesso, type RegistroDoHistorico, type Usuario } from '../api/acesso'
import {
  ACESSO_TOTAL,
  permissoes,
  type Concessao,
  type DetalheDoUsuario,
  type Item,
  type PermissaoDoCatalogo,
  type TipoDeAlvo,
  type TipoDeItem,
} from '../api/permissoes'
import { Alerta, Campo, Pagina, Selecao } from '../componentes'
import { dataEHora } from '../formatos'
import {
  ROTULO_DO_ALVO,
  SITUACAO_DO_USUARIO,
  descreverOrigem,
  mensagemDoErro,
  rotuloDaAcao,
} from '../mensagens'
import { useLista } from '../useLista'

const TEXTO_DO_ITEM: Record<TipoDeItem, { titulo: string; novo: string }> = {
  cargos: { titulo: 'Cargos', novo: 'Novo cargo' },
  setores: { titulo: 'Setores', novo: 'Novo setor' },
}

/** Cargos e setores têm as mesmas ações; `tipo` vem da rota. */
export function CargosESetores({ tipo }: { tipo: TipoDeItem }) {
  const carregar = useCallback(() => permissoes.itens(tipo), [tipo])
  const { itens, erro, definirErro, recarregar } = useLista<Item>(carregar)
  const [nome, definirNome] = useState('')
  const [editando, definirEditando] = useState<{ id: string; nome: string } | null>(null)
  const texto = TEXTO_DO_ITEM[tipo]

  async function executar(acao: () => Promise<unknown>, depois?: () => void) {
    definirErro(null)
    try {
      await acao()
      depois?.()
      recarregar()
    } catch (falha) {
      definirErro(falha)
    }
  }

  function criar(evento: FormEvent) {
    evento.preventDefault()
    void executar(() => permissoes.criar(tipo, nome), () => definirNome(''))
  }

  return (
    <Pagina titulo={texto.titulo}>
      <Link to="/">Voltar</Link>
      <form onSubmit={criar}>
        <Campo rotulo={texto.novo} value={nome} aoMudar={definirNome} maxLength={60} />
        <button type="submit">Criar</button>
      </form>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      <table>
        <thead>
          <tr>
            <th>Nome</th>
            <th>Situação</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {itens.map((item) => (
            <tr key={item.id}>
              <td>
                {editando?.id === item.id ? (
                  <Campo
                    rotulo="Novo nome"
                    value={editando.nome}
                    aoMudar={(valor) => definirEditando({ id: item.id, nome: valor })}
                    maxLength={60}
                  />
                ) : (
                  item.nome
                )}
              </td>
              <td>{item.ativo ? 'Ativo' : 'Inativo'}</td>
              <td>
                {editando?.id === item.id ? (
                  <>
                    <button
                      type="button"
                      onClick={() =>
                        void executar(
                          () => permissoes.renomear(tipo, item.id, editando.nome),
                          () => definirEditando(null),
                        )
                      }
                    >
                      Salvar
                    </button>
                    <button type="button" onClick={() => definirEditando(null)}>
                      Cancelar
                    </button>
                  </>
                ) : (
                  <button type="button" onClick={() => definirEditando({ id: item.id, nome: item.nome })}>
                    Renomear
                  </button>
                )}
                {item.ativo ? (
                  <button type="button" onClick={() => void executar(() => permissoes.desativar(tipo, item.id))}>
                    Desativar
                  </button>
                ) : (
                  <button type="button" onClick={() => void executar(() => permissoes.reativar(tipo, item.id))}>
                    Reativar
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Pagina>
  )
}

interface DadosDePermissoes {
  catalogo: PermissaoDoCatalogo[]
  concessoes: Concessao[]
  cargos: Item[]
  setores: Item[]
  usuarios: Usuario[]
}

function carregarDadosDePermissoes(): Promise<DadosDePermissoes> {
  return Promise.all([
    permissoes.catalogo(),
    permissoes.concessoes(),
    permissoes.itens('cargos'),
    permissoes.itens('setores'),
    acesso.usuarios(),
  ]).then(([catalogo, concessoes, cargos, setores, usuarios]) => ({ catalogo, concessoes, cargos, setores, usuarios }))
}

export function Permissoes() {
  const [dados, definirDados] = useState<DadosDePermissoes | null>(null)
  const [erro, definirErro] = useState<unknown>(null)
  const [aviso, definirAviso] = useState<string | null>(null)
  const [permissao, definirPermissao] = useState('')
  const [tipo, definirTipo] = useState<TipoDeAlvo>('CARGO')
  const [alvoId, definirAlvoId] = useState('')

  const recarregar = useCallback(() => {
    carregarDadosDePermissoes().then(definirDados).catch(definirErro)
  }, [])
  useEffect(recarregar, [recarregar])

  const opcoes: { id: string; nome: string }[] =
    dados === null
      ? []
      : tipo === 'CARGO'
        ? dados.cargos.filter((c) => c.ativo)
        : tipo === 'SETOR'
          ? dados.setores.filter((s) => s.ativo)
          : dados.usuarios.filter((u) => u.situacao === 'ATIVO')

  async function conceder(evento: FormEvent) {
    evento.preventDefault()
    definirErro(null)
    definirAviso(null)
    try {
      const concessao = await permissoes.conceder(permissao, tipo, alvoId)
      // A API responde igual para criar e para repetir; o site sabe que já existia pela lista que tem.
      if (dados?.concessoes.some((c) => c.id === concessao.id)) definirAviso('Esta concessão já existia.')
      recarregar()
    } catch (falha) {
      definirErro(falha)
    }
  }

  async function revogar(concessao: Concessao) {
    definirErro(null)
    definirAviso(null)
    try {
      await permissoes.revogar(concessao.id)
      recarregar()
    } catch (falha) {
      definirErro(falha)
    }
  }

  return (
    <Pagina titulo="Permissões">
      <Link to="/">Voltar</Link>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {aviso && <p role="status">{aviso}</p>}

      {dados && (
        <>
        <section aria-labelledby="catalogo">
          <h2 id="catalogo">Catálogo</h2>
          <ul>
            {dados.catalogo.map((p) => (
              <li key={p.codigo}>
                <strong>{p.nome}</strong>: {p.descricao}
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="conceder">
          <h2 id="conceder">Conceder uma permissão</h2>
          <form onSubmit={(evento) => void conceder(evento)}>
            <Selecao rotulo="Permissão" value={permissao} aoMudar={definirPermissao} required>
              <option value="">Escolha…</option>
              {dados.catalogo.map((p) => (
                <option key={p.codigo} value={p.codigo}>
                  {p.nome}
                </option>
              ))}
            </Selecao>
            <Selecao
              rotulo="Conceder a"
              value={tipo}
              aoMudar={(valor) => {
                definirTipo(valor as TipoDeAlvo)
                definirAlvoId('')
              }}
            >
              <option value="CARGO">Um cargo</option>
              <option value="SETOR">Um setor</option>
              <option value="USUARIO">Uma pessoa</option>
            </Selecao>
            <Selecao rotulo={ROTULO_DO_ALVO[tipo]} value={alvoId} aoMudar={definirAlvoId} required>
              <option value="">Escolha…</option>
              {opcoes.map((opcao) => (
                <option key={opcao.id} value={opcao.id}>
                  {opcao.nome}
                </option>
              ))}
            </Selecao>
            <button type="submit">Conceder</button>
          </form>
        </section>

        <section aria-labelledby="ativas">
          <h2 id="ativas">Concessões ativas</h2>
          <table>
            <thead>
              <tr>
                <th>Permissão</th>
                <th>Concedida a</th>
                <th>Desde</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {dados.concessoes.map((concessao) => (
                <tr key={concessao.id}>
                  <td>{dados.catalogo.find((p) => p.codigo === concessao.permissao)?.nome ?? concessao.permissao}</td>
                  <td>
                    {ROTULO_DO_ALVO[concessao.alvo_tipo]}: {concessao.alvo.nome}
                  </td>
                  <td>{dataEHora.format(new Date(concessao.concedida_em))}</td>
                  <td>
                    <button type="button" onClick={() => void revogar(concessao)}>
                      Revogar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        </>
      )}
    </Pagina>
  )
}

interface DadosDoUsuario {
  detalhe: DetalheDoUsuario
  cargos: Item[]
  setores: Item[]
  usuario: Usuario | null
  acessoTotal: Concessao | null
  historico: RegistroDoHistorico[]
}

function carregarDadosDoUsuario(id: string): Promise<DadosDoUsuario> {
  return Promise.all([
    permissoes.detalheDoUsuario(id),
    permissoes.itens('cargos'),
    permissoes.itens('setores'),
    acesso.usuarios(),
    permissoes.concessoes(),
    acesso.historicoDeUsuario(id),
  ]).then(([detalhe, cargos, setores, usuarios, concessoes, historico]) => ({
    detalhe,
    cargos,
    setores,
    usuario: usuarios.find((u) => u.id === id) ?? null,
    acessoTotal:
      concessoes.find((c) => c.permissao === ACESSO_TOTAL && c.alvo_tipo === 'USUARIO' && c.alvo.id === id) ?? null,
    historico,
  }))
}

export function UsuarioDetalhe() {
  const { id = '' } = useParams()
  const [dados, definirDados] = useState<DadosDoUsuario | null>(null)
  const [erro, definirErro] = useState<unknown>(null)
  const [cargoId, definirCargoId] = useState('')
  const [setorIds, definirSetorIds] = useState<string[]>([])

  const recarregar = useCallback(() => {
    carregarDadosDoUsuario(id)
      .then((carregados) => {
        definirDados(carregados)
        definirCargoId(carregados.detalhe.cargo?.id ?? '')
        definirSetorIds(carregados.detalhe.setores.map((s) => s.id))
      })
      .catch(definirErro)
  }, [id])
  useEffect(recarregar, [recarregar])

  async function executar(acao: () => Promise<unknown>) {
    definirErro(null)
    try {
      await acao()
      recarregar()
    } catch (falha) {
      definirErro(falha)
    }
  }

  function classificar(evento: FormEvent) {
    evento.preventDefault()
    // Sem cargo não há setores: a API recusa setores sem cargo, então o site nem os envia.
    void executar(() => permissoes.classificar(id, cargoId || null, cargoId ? setorIds : []))
  }

  function alternarSetor(setorId: string, marcado: boolean) {
    definirSetorIds((atuais) => (marcado ? [...atuais, setorId] : atuais.filter((s) => s !== setorId)))
  }

  const ativo = dados?.usuario?.situacao === 'ATIVO'

  return (
    <Pagina titulo={dados?.usuario?.nome ?? 'Usuário'}>
      <Link to="/admin/usuarios">Voltar</Link>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      {dados && (
        <>
          <p>
            {dados.usuario ? SITUACAO_DO_USUARIO[dados.usuario.situacao] : ''}
            {dados.usuario?.admin ? ' · Admin' : ''}
          </p>

          <section aria-labelledby="classificacao">
            <h2 id="classificacao">Classificação</h2>
            {ativo ? (
              <form onSubmit={classificar}>
                <Selecao rotulo="Cargo" value={cargoId} aoMudar={definirCargoId}>
                  <option value="">Sem cargo</option>
                  {dados.cargos
                    .filter((c) => c.ativo || c.id === dados.detalhe.cargo?.id)
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nome}
                      </option>
                    ))}
                </Selecao>
                <fieldset disabled={!cargoId}>
                  <legend>Setores</legend>
                  {dados.setores
                    .filter((s) => s.ativo)
                    .map((s) => (
                      <label key={s.id}>
                        <input
                          type="checkbox"
                          checked={cargoId !== '' && setorIds.includes(s.id)}
                          onChange={(evento) => alternarSetor(s.id, evento.target.checked)}
                        />{' '}
                        {s.nome}
                      </label>
                    ))}
                </fieldset>
                <button type="submit">Salvar classificação</button>
              </form>
            ) : (
              <p>Só usuário ativo pode ser classificado.</p>
            )}
          </section>

          <section aria-labelledby="permissoes-do-usuario">
            <h2 id="permissoes-do-usuario">Permissões</h2>
            {dados.detalhe.permissoes.length === 0 ? (
              <p>Nenhuma permissão.</p>
            ) : (
              <ul>
                {dados.detalhe.permissoes.map((p) => (
                  <li key={p.codigo}>
                    <strong>{p.nome}</strong>: {p.origens.map(descreverOrigem).join('; ')}
                  </li>
                ))}
              </ul>
            )}
            <p>Acesso total: {dados.acessoTotal ? 'concedido' : 'não concedido'}.</p>
            {dados.acessoTotal ? (
              <button
                type="button"
                onClick={() => void executar(() => permissoes.revogar(dados.acessoTotal?.id ?? ''))}
              >
                Revogar acesso total
              </button>
            ) : (
              <button type="button" onClick={() => void executar(() => permissoes.conceder(ACESSO_TOTAL, 'USUARIO', id))}>
                Conceder acesso total
              </button>
            )}
          </section>

          <section aria-labelledby="historico">
            <h2 id="historico">Histórico</h2>
            <table>
              <thead>
                <tr>
                  <th>Ação</th>
                  <th>Quem</th>
                  <th>Quando</th>
                </tr>
              </thead>
              <tbody>
                {dados.historico.map((registro) => (
                  <tr key={`${registro.criado_em}-${registro.acao}`}>
                    <td>{rotuloDaAcao(registro.acao)}</td>
                    <td>{registro.ator?.nome ?? 'Sistema'}</td>
                    <td>{dataEHora.format(new Date(registro.criado_em))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </Pagina>
  )
}
