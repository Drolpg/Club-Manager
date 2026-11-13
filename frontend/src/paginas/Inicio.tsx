import { Link } from 'react-router'
import { Pagina } from '../componentes'
import { useSessao } from '../sessao'

// Página inicial provisória do M2. O dashboard básico de verdade entra no M10; a classificação, no M3.
export function Inicio() {
  const { usuario, sair } = useSessao()
  if (!usuario) return null

  return (
    <Pagina titulo="Club Manager">
      <p>Olá, {usuario.nome}.</p>
      {!usuario.tem_cargo && !usuario.admin && (
        <p>Seu cadastro está concluído e aguarda a classificação pelo administrador do clube.</p>
      )}
      {usuario.admin && (
        <nav aria-label="Administração">
          <Link to="/admin/convites">Convites</Link>
          <Link to="/admin/usuarios">Usuários</Link>
        </nav>
      )}
      <button type="button" onClick={() => void sair()}>
        Sair
      </button>
    </Pagina>
  )
}
