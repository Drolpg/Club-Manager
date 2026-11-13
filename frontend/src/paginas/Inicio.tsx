import { Link } from 'react-router'
import { type DetalheDoUsuario } from '../api/permissoes'
import { Alerta, Pagina } from '../componentes'
import { mensagemDoErro } from '../mensagens'
import { useSessao } from '../sessao'
import { CONVITES_GERENCIAR, temPermissao, useMinhas } from '../useMinhas'

/** O cargo, os setores e as permissões de quem está logado (CA-26). A API só devolve os dele. */
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

// Página inicial provisória. O dashboard básico de verdade entra no M10.
export function Inicio() {
  const { usuario, sair } = useSessao()
  const { detalhe, erro } = useMinhas(!!usuario?.tem_cargo)
  if (!usuario) return null

  return (
    <Pagina titulo="Club Manager">
      <p>Olá, {usuario.nome}.</p>
      {!usuario.tem_cargo && !usuario.admin && (
        <p>Seu cadastro está concluído e aguarda a classificação pelo administrador do clube.</p>
      )}
      {usuario.tem_cargo && erro ? <Alerta>{mensagemDoErro(erro)}</Alerta> : null}
      {usuario.tem_cargo && detalhe && <MinhasPermissoes detalhe={detalhe} />}
      {!usuario.admin && temPermissao(detalhe, CONVITES_GERENCIAR) && (
        <nav aria-label="Convites">
          <Link to="/admin/convites">Convites</Link>
        </nav>
      )}
      {usuario.admin && (
        <nav aria-label="Administração">
          <Link to="/admin/convites">Convites</Link>
          <Link to="/admin/usuarios">Usuários</Link>
          <Link to="/admin/cargos">Cargos</Link>
          <Link to="/admin/setores">Setores</Link>
          <Link to="/admin/permissoes">Permissões</Link>
        </nav>
      )}
      <button type="button" onClick={() => void sair()}>
        Sair
      </button>
    </Pagina>
  )
}
