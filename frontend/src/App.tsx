import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router'
import { CadastroPorConvite, Entrar, RecuperarSenha, RedefinirSenha, VerificarEmail } from './paginas/Acesso'
import { Moldura } from './Moldura'
import { Convites, Usuarios } from './paginas/Admin'
import { DetalheDeSolicitacao, FilaDePendencias, ListaDeSolicitacoes } from './paginas/Aprovacoes'
import { MotivosDeDecisao } from './paginas/Motivos'
import { Inicio } from './paginas/Inicio'
import { CargosESetores, Permissoes, UsuarioDetalhe } from './paginas/Permissoes'
import { Calendario } from './paginas/Calendario'
import { CategoriasDeEvento } from './paginas/CategoriasDeEvento'
import { Cobrancas } from './paginas/Cobrancas'
import { ConfiguracaoFinanceira } from './paginas/ConfiguracaoFinanceira'
import { DetalheDaCobranca } from './paginas/DetalheDaCobranca'
import { DetalheDaSaida } from './paginas/DetalheDaSaida'
import { CategoriasDeDocumento } from './paginas/CategoriasDeDocumento'
import { DetalheDoComunicado } from './paginas/DetalheDoComunicado'
import { DetalheDoDocumento } from './paginas/DetalheDoDocumento'
import { DetalheDoEvento } from './paginas/DetalheDoEvento'
import { Despublicados } from './paginas/Despublicados'
import { Entradas } from './paginas/Entradas'
import { Documentos } from './paginas/Documentos'
import { Feed } from './paginas/Feed'
import { FormularioDeComunicado } from './paginas/FormularioDeComunicado'
import { FormularioDeEvento } from './paginas/FormularioDeEvento'
import { HistoricoDeEventos } from './paginas/HistoricoDeEventos'
import { MinhasCobrancas } from './paginas/MinhasCobrancas'
import { NovaSolicitacaoDeGasto } from './paginas/NovaSolicitacaoDeGasto'
import { Perfil } from './paginas/Perfil'
import { Preferencias } from './paginas/Preferencias'
import { RecorrenciasESuspensoes } from './paginas/RecorrenciasESuspensoes'
import { Saidas } from './paginas/Saidas'
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

// Solicitações são lidas pelo admin e por quem tem cargo (regra 18). A API confere de novo a cada chamada.
function ProtegidaDeGestao({ children }: { children: ReactNode }) {
  const { usuario } = useSessao()
  if (usuario === undefined) return <p className="pagina">Carregando…</p>
  if (usuario === null) return <Navigate to="/entrar" replace />
  if (!usuario.admin && !usuario.tem_cargo) return <Navigate to="/" replace />
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
        <Route element={<Moldura />}>
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
          <Route
            path="/solicitacoes"
            element={
              <ProtegidaDeGestao>
                <ListaDeSolicitacoes />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/solicitacoes/:id"
            element={
              <ProtegidaDeGestao>
                <DetalheDeSolicitacao />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/fila"
            element={
              <ProtegidaDeGestao>
                <FilaDePendencias />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/admin/motivos"
            element={
              <Protegida soAdmin>
                <MotivosDeDecisao />
              </Protegida>
            }
          />
          <Route
            path="/perfil"
            element={
              <Protegida>
                <Perfil />
              </Protegida>
            }
          />
          <Route
            path="/admin/usuarios/:id/perfil"
            element={
              <Protegida soAdmin>
                <Perfil />
              </Protegida>
            }
          />
          <Route
            path="/preferencias"
            element={
              <Protegida>
                <Preferencias />
              </Protegida>
            }
          />
          <Route
            path="/minhas-cobrancas"
            element={
              <Protegida>
                <MinhasCobrancas />
              </Protegida>
            }
          />
          <Route
            path="/cobrancas"
            element={
              <ProtegidaDeGestao>
                <Cobrancas />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/cobrancas/:id"
            element={
              <Protegida>
                <DetalheDaCobranca />
              </Protegida>
            }
          />
          <Route
            path="/recorrencias"
            element={
              <ProtegidaDeGestao>
                <RecorrenciasESuspensoes />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/entradas"
            element={
              <ProtegidaDeGestao>
                <Entradas />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/gastos/novo"
            element={
              <ProtegidaDeGestao>
                <NovaSolicitacaoDeGasto />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/saidas"
            element={
              <ProtegidaDeGestao>
                <Saidas />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/saidas/:id"
            element={
              <ProtegidaDeGestao>
                <DetalheDaSaida />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/configuracao/financeiro"
            element={
              <Protegida soAdmin>
                <ConfiguracaoFinanceira />
              </Protegida>
            }
          />
          <Route
            path="/eventos"
            element={
              <ProtegidaDeGestao>
                <Calendario />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/eventos/historico"
            element={
              <ProtegidaDeGestao>
                <HistoricoDeEventos />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/eventos/novo"
            element={
              <ProtegidaDeGestao>
                <FormularioDeEvento />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/eventos/:id"
            element={
              <ProtegidaDeGestao>
                <DetalheDoEvento />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/eventos/:id/editar"
            element={
              <ProtegidaDeGestao>
                <FormularioDeEvento />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/feed"
            element={
              <ProtegidaDeGestao>
                <Feed />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/feed/novo"
            element={
              <ProtegidaDeGestao>
                <FormularioDeComunicado />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/feed/despublicados"
            element={
              <ProtegidaDeGestao>
                <Despublicados />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/feed/:id"
            element={
              <ProtegidaDeGestao>
                <DetalheDoComunicado />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/feed/:id/editar"
            element={
              <ProtegidaDeGestao>
                <FormularioDeComunicado />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/documentos"
            element={
              <ProtegidaDeGestao>
                <Documentos />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/documentos/:id"
            element={
              <ProtegidaDeGestao>
                <DetalheDoDocumento />
              </ProtegidaDeGestao>
            }
          />
          <Route
            path="/admin/categorias-de-documento"
            element={
              <Protegida soAdmin>
                <CategoriasDeDocumento />
              </Protegida>
            }
          />
          <Route
            path="/admin/categorias-de-evento"
            element={
              <Protegida soAdmin>
                <CategoriasDeEvento />
              </Protegida>
            }
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ProvedorDeSessao>
  )
}

export default App
