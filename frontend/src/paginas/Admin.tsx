import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { acesso, type AcaoDeUsuario, type Convite, type ConviteGerado, type Usuario } from '../api/acesso'
import { Alerta, Pagina } from '../componentes'
import { SITUACAO_DO_CONVITE, SITUACAO_DO_USUARIO, mensagemDoErro } from '../mensagens'
import { useSessao } from '../sessao'

const dataEHora = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

function useLista<T>(carregar: () => Promise<T[]>) {
  const [itens, definirItens] = useState<T[]>([])
  const [erro, definirErro] = useState<unknown>(null)
  const recarregar = useCallback(() => {
    carregar().then(definirItens).catch(definirErro)
  }, [carregar])
  useEffect(recarregar, [recarregar])
  return { itens, erro, definirErro, recarregar }
}

export function Convites() {
  const { itens, erro, definirErro, recarregar } = useLista<Convite>(acesso.convites)
  const [link, definirLink] = useState<string | null>(null)

  async function executar(acao: () => Promise<Convite | ConviteGerado>) {
    definirErro(null)
    try {
      const resultado = await acao()
      // Só gerar e regenerar devolvem o link.
      definirLink('link' in resultado ? resultado.link : null)
      recarregar()
    } catch (falha) {
      definirErro(falha)
    }
  }

  return (
    <Pagina titulo="Convites">
      <Link to="/">Voltar</Link>
      <button type="button" onClick={() => void executar(acesso.gerarConvite)}>
        Gerar convite
      </button>
      {link && (
        <section className="aviso">
          <p>Copie o link e envie ao convidado. Ele só aparece agora, vale 24 horas e serve para um cadastro.</p>
          <input readOnly value={link} aria-label="Link do convite" onFocus={(evento) => evento.target.select()} />
        </section>
      )}
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      <table>
        <thead>
          <tr>
            <th>Situação</th>
            <th>Gerado por</th>
            <th>Gerado em</th>
            <th>Expira em</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {itens.map((convite) => (
            <tr key={convite.id}>
              <td>{SITUACAO_DO_CONVITE[convite.situacao]}</td>
              <td>{convite.gerado_por.nome}</td>
              <td>{dataEHora.format(new Date(convite.gerado_em))}</td>
              <td>{dataEHora.format(new Date(convite.expira_em))}</td>
              <td>
                {convite.situacao === 'ATIVO' && (
                  <button type="button" onClick={() => void executar(() => acesso.revogarConvite(convite.id))}>
                    Revogar
                  </button>
                )}
                {(convite.situacao === 'ATIVO' || convite.situacao === 'EXPIRADO') && (
                  <button type="button" onClick={() => void executar(() => acesso.regenerarConvite(convite.id))}>
                    Regenerar
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

const ROTULO_DA_ACAO: Record<AcaoDeUsuario, string> = {
  desativar: 'Desativar',
  reativar: 'Reativar',
  'tornar-admin': 'Tornar admin',
  'remover-admin': 'Tirar o papel de admin',
}

function acoesPara(usuario: Usuario): AcaoDeUsuario[] {
  if (usuario.situacao === 'INATIVO') return ['reativar']
  if (usuario.situacao !== 'ATIVO') return []
  return ['desativar', usuario.admin ? 'remover-admin' : 'tornar-admin']
}

export function Usuarios() {
  const { usuario: eu } = useSessao()
  const { itens, erro, definirErro, recarregar } = useLista<Usuario>(acesso.usuarios)

  async function executar(usuario: Usuario, acao: AcaoDeUsuario) {
    definirErro(null)
    try {
      await acesso.acaoDeUsuario(usuario.id, acao)
      recarregar()
    } catch (falha) {
      definirErro(falha)
    }
  }

  return (
    <Pagina titulo="Usuários">
      <Link to="/">Voltar</Link>
      <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
      <table>
        <thead>
          <tr>
            <th>Nome</th>
            <th>Nome de usuário</th>
            <th>Situação</th>
            <th>Papel</th>
            <th>Cargo</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {itens.map((usuario) => (
            <tr key={usuario.id}>
              <td>{usuario.nome}</td>
              <td>{usuario.nome_de_usuario}</td>
              <td>{SITUACAO_DO_USUARIO[usuario.situacao]}</td>
              <td>{usuario.admin ? 'Admin' : 'Diretor'}</td>
              <td>{usuario.tem_cargo ? 'Com cargo' : 'Sem cargo'}</td>
              <td>
                {/* Ninguém desativa a si mesmo nem tira o próprio papel; a API recusa de qualquer jeito. */}
                {usuario.id !== eu?.id &&
                  acoesPara(usuario).map((acao) => (
                    <button key={acao} type="button" onClick={() => void executar(usuario, acao)}>
                      {ROTULO_DA_ACAO[acao]}
                    </button>
                  ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Pagina>
  )
}
