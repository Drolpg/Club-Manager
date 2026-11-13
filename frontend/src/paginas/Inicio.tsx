import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { permissoes, type DetalheDoUsuario } from '../api/permissoes'
import { Alerta, Pagina } from '../componentes'
import { mensagemDoErro } from '../mensagens'
import { useSessao } from '../sessao'

/** O cargo, os setores e as permissões de quem está logado (CA-26). A API só devolve os dele. */
function MinhasPermissoes() {
  const [detalhe, definirDetalhe] = useState<DetalheDoUsuario | null>(null)
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    let ativo = true
    permissoes
      .minhas()
      .then((resposta) => ativo && definirDetalhe(resposta))
      .catch((falha) => ativo && definirErro(falha))
    return () => {
      ativo = false
    }
  }, [])

  if (erro) return <Alerta>{mensagemDoErro(erro)}</Alerta>
  if (!detalhe) return null
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
  if (!usuario) return null

  return (
    <Pagina titulo="Club Manager">
      <p>Olá, {usuario.nome}.</p>
      {!usuario.tem_cargo && !usuario.admin && (
        <p>Seu cadastro está concluído e aguarda a classificação pelo administrador do clube.</p>
      )}
      {usuario.tem_cargo && <MinhasPermissoes />}
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
