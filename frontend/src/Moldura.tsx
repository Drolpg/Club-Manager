import { Link, Outlet } from 'react-router'
import { Sino } from './Sino'
import { useSessao } from './sessao'
import { CONVITES_GERENCIAR, ProvedorDeMinhas, temPermissao, useMinhas } from './useMinhas'

/**
 * A moldura comum das telas logadas: o nome de quem está logado, o menu, o sino e "Sair" (RF-031).
 *
 * O site só decide o que mostrar; quem pode o quê é sempre conferido pela API (RNF-01). Sem sessão, a moldura
 * não aparece: cada tela protegida cuida de esperar ou de mandar para a tela de entrar.
 */
export function Moldura() {
  const { usuario, sair, versao } = useSessao()
  // Só quem tem cargo pode ter permissão por cargo ou setor; a mesma resposta serve às telas dentro da moldura.
  const minhas = useMinhas(!!usuario?.tem_cargo, versao)
  if (!usuario) return <Outlet />

  return (
    <ProvedorDeMinhas value={minhas}>
      <header className="cabecalho">
        <span className="cabecalho-nome">Olá, {usuario.nome}</span>
        {!usuario.admin && temPermissao(minhas.detalhe, CONVITES_GERENCIAR) && (
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
        {(usuario.admin || usuario.tem_cargo) && (
          <nav aria-label="Aprovações">
            <Link to="/fila">Fila de pendências</Link>
            <Link to="/solicitacoes">Solicitações</Link>
            {usuario.admin && <Link to="/admin/motivos">Motivos de decisão</Link>}
          </nav>
        )}
        <Link to="/preferencias">Preferências</Link>
        <Sino />
        <button type="button" onClick={() => void sair()}>
          Sair
        </button>
      </header>
      <Outlet />
    </ProvedorDeMinhas>
  )
}
