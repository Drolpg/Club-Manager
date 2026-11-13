import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router'
import { CadastroPorConvite, Entrar, RecuperarSenha, RedefinirSenha, VerificarEmail } from './paginas/Acesso'
import { Convites, Usuarios } from './paginas/Admin'
import { Inicio } from './paginas/Inicio'
import { CargosESetores, Permissoes, UsuarioDetalhe } from './paginas/Permissoes'
import { ProvedorDeSessao, useSessao } from './sessao'
import { CONVITES_GERENCIAR, temPermissao, useMinhas } from './useMinhas'

// O site só decide o que mostrar. Quem pode o quê é sempre conferido pela API (RNF-01).
function Protegida({ soAdmin = false, children }: { soAdmin?: boolean; children: ReactNode }) {
  const { usuario } = useSessao()
  if (usuario === undefined) return <p className="pagina">Carregando…</p>
  if (usuario === null) return <Navigate to="/entrar" replace />
  if (soAdmin && !usuario.admin) return <Navigate to="/" replace />
  return children
}

// Convites são do admin e de quem tem a permissão `convites.gerenciar`. A API confere de novo em cada chamada.
function ProtegidaDeConvites({ children }: { children: ReactNode }) {
  const { usuario } = useSessao()
  const { detalhe, carregando } = useMinhas(!!usuario && !usuario.admin)
  if (usuario === undefined || carregando) return <p className="pagina">Carregando…</p>
  if (usuario === null) return <Navigate to="/entrar" replace />
  if (!usuario.admin && !temPermissao(detalhe, CONVITES_GERENCIAR)) return <Navigate to="/" replace />
  return children
}

function App() {
  return (
    <ProvedorDeSessao>
      <Routes>
        <Route path="/entrar" element={<Entrar />} />
        <Route path="/convite/:token" element={<CadastroPorConvite />} />
        <Route path="/verificar/:token" element={<VerificarEmail />} />
        <Route path="/recuperar-senha" element={<RecuperarSenha />} />
        <Route path="/redefinir-senha/:token" element={<RedefinirSenha />} />
        <Route
          path="/"
          element={
            <Protegida>
              <Inicio />
            </Protegida>
          }
        />
        <Route
          path="/admin/convites"
          element={
            <ProtegidaDeConvites>
              <Convites />
            </ProtegidaDeConvites>
          }
        />
        <Route
          path="/admin/usuarios"
          element={
            <Protegida soAdmin>
              <Usuarios />
            </Protegida>
          }
        />
        <Route
          path="/admin/usuarios/:id"
          element={
            <Protegida soAdmin>
              <UsuarioDetalhe />
            </Protegida>
          }
        />
        <Route
          path="/admin/cargos"
          element={
            <Protegida soAdmin>
              <CargosESetores tipo="cargos" />
            </Protegida>
          }
        />
        <Route
          path="/admin/setores"
          element={
            <Protegida soAdmin>
              <CargosESetores tipo="setores" />
            </Protegida>
          }
        />
        <Route
          path="/admin/permissoes"
          element={
            <Protegida soAdmin>
              <Permissoes />
            </Protegida>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ProvedorDeSessao>
  )
}

export default App
