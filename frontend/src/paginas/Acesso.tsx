import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { acesso } from '../api/acesso'
import { ApiError } from '../api/client'
import { Alerta, AvisoDePrivacidade, BotaoGoogle, Campo, Pagina } from '../componentes'
import { errosPorCampo, mensagemDoErro } from '../mensagens'
import { useSessao } from '../sessao'

export function Entrar() {
  const { definirUsuario, googleClientId } = useSessao()
  const navegar = useNavigate()
  const [identificador, definirIdentificador] = useState('')
  const [senha, definirSenha] = useState('')
  const [erro, definirErro] = useState<unknown>(null)
  const [reenviado, definirReenviado] = useState(false)

  async function concluir(pedido: Promise<{ usuario: Parameters<typeof definirUsuario>[0] }>) {
    definirErro(null)
    definirReenviado(false)
    try {
      definirUsuario((await pedido).usuario)
      navegar('/')
    } catch (falha) {
      definirErro(falha)
    }
  }

  function enviar(evento: FormEvent) {
    evento.preventDefault()
    void concluir(acesso.entrar(identificador, senha))
  }

  async function reenviar() {
    await acesso.reenviarVerificacao(identificador).catch(() => undefined)
    definirErro(null)
    definirReenviado(true)
  }

  const faltaVerificar = erro instanceof ApiError && erro.code === 'EMAIL_NAO_VERIFICADO'

  return (
    <Pagina titulo="Entrar">
      <form onSubmit={enviar}>
        <Campo
          rotulo="Nome de usuário ou e-mail"
          value={identificador}
          aoMudar={definirIdentificador}
          autoComplete="username"
          required
        />
        <Campo
          rotulo="Senha"
          type="password"
          value={senha}
          aoMudar={definirSenha}
          autoComplete="current-password"
          required
        />
        <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
        {faltaVerificar && (
          <button type="button" onClick={() => void reenviar()}>
            Reenviar o link de verificação
          </button>
        )}
        {reenviado && <p>Se a conta aguarda verificação, enviamos outro link para o e-mail dela.</p>}
        <button type="submit">Entrar</button>
      </form>
      <BotaoGoogle clientId={googleClientId} aoReceber={(credencial) => void concluir(acesso.entrarComGoogle(credencial))} />
      <p>
        <Link to="/recuperar-senha">Esqueci a senha</Link>
      </p>
    </Pagina>
  )
}

function nomeNaCredencial(credencial: string): string {
  // Só para preencher o campo: a API é quem valida a credencial e decide o e-mail.
  try {
    const dados = JSON.parse(atob(credencial.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return typeof dados.name === 'string' ? dados.name : ''
  } catch {
    return ''
  }
}

export function CadastroPorConvite() {
  const { token = '' } = useParams()
  const { definirUsuario, googleClientId } = useSessao()
  const navegar = useNavigate()
  const [situacao, definirSituacao] = useState<'consultando' | 'valido' | 'invalido' | 'enviado'>('consultando')
  const [credencial, definirCredencial] = useState<string | null>(null)
  const [dados, definirDados] = useState({ nome: '', nome_de_usuario: '', telefone: '', email: '', senha: '' })
  const [erro, definirErro] = useState<unknown>(null)

  useEffect(() => {
    let ativo = true
    acesso
      .consultarConvite(token)
      .then(() => ativo && definirSituacao('valido'))
      .catch(() => ativo && definirSituacao('invalido'))
    return () => {
      ativo = false
    }
  }, [token])

  const mudar = (campo: keyof typeof dados) => (valor: string) => definirDados((atual) => ({ ...atual, [campo]: valor }))

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    definirErro(null)
    try {
      if (credencial) {
        const { email: _email, ...semEmail } = dados
        const sessao = await acesso.cadastrarComGoogle({ token, credencial, ...semEmail })
        definirUsuario(sessao.usuario)
        navegar('/')
      } else {
        await acesso.cadastrar({ token, ...dados })
        definirSituacao('enviado')
      }
    } catch (falha) {
      definirErro(falha)
    }
  }

  if (situacao === 'consultando') return <Pagina titulo="Cadastro">Conferindo o convite…</Pagina>
  if (situacao === 'invalido') {
    return (
      <Pagina titulo="Cadastro">
        <Alerta>Convite inválido ou expirado.</Alerta>
        <p>Peça outro convite ao administrador do clube.</p>
      </Pagina>
    )
  }
  if (situacao === 'enviado') {
    return (
      <Pagina titulo="Verifique seu e-mail">
        <p>Enviamos um link para {dados.email}. Abra-o em até 24 horas para concluir o cadastro.</p>
        <p>
          Não chegou? Tente <Link to="/entrar">entrar</Link>: a tela oferece o reenvio.
        </p>
      </Pagina>
    )
  }

  const campos = errosPorCampo(erro)
  return (
    <Pagina titulo="Cadastro">
      <AvisoDePrivacidade />
      {!credencial && (
        <BotaoGoogle
          clientId={googleClientId}
          aoReceber={(recebida) => {
            definirCredencial(recebida)
            definirDados((atual) => ({ ...atual, nome: atual.nome || nomeNaCredencial(recebida) }))
          }}
        />
      )}
      {credencial && <p>Conta Google confirmada. Complete os dados abaixo.</p>}
      <form onSubmit={(evento) => void enviar(evento)}>
        <Campo rotulo="Nome" value={dados.nome} aoMudar={mudar('nome')} erros={campos.nome} required />
        <Campo
          rotulo="Nome de usuário"
          value={dados.nome_de_usuario}
          aoMudar={mudar('nome_de_usuario')}
          erros={campos.nome_de_usuario}
          autoComplete="username"
          required
        />
        <Campo rotulo="Telefone" value={dados.telefone} aoMudar={mudar('telefone')} erros={campos.telefone} required />
        {!credencial && (
          <Campo rotulo="E-mail" type="email" value={dados.email} aoMudar={mudar('email')} erros={campos.email} required />
        )}
        <Campo
          rotulo="Senha"
          type="password"
          value={dados.senha}
          aoMudar={mudar('senha')}
          erros={campos.senha}
          autoComplete="new-password"
          required
        />
        <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
        <button type="submit">Cadastrar</button>
      </form>
    </Pagina>
  )
}

export function VerificarEmail() {
  const { token = '' } = useParams()
  const [resultado, definirResultado] = useState<'verificando' | 'ok' | unknown>('verificando')

  useEffect(() => {
    let ativo = true
    acesso
      .verificar(token)
      .then(() => ativo && definirResultado('ok'))
      .catch((falha: unknown) => ativo && definirResultado(falha))
    return () => {
      ativo = false
    }
  }, [token])

  if (resultado === 'verificando') return <Pagina titulo="Verificação">Verificando…</Pagina>
  if (resultado === 'ok') {
    return (
      <Pagina titulo="Verificação">
        <p>E-mail verificado. Seu cadastro está concluído.</p>
        <Link to="/entrar">Entrar</Link>
      </Pagina>
    )
  }
  return (
    <Pagina titulo="Verificação">
      <Alerta>{mensagemDoErro(resultado)}</Alerta>
      <p>
        Tente <Link to="/entrar">entrar</Link>: a tela oferece o reenvio do link.
      </p>
    </Pagina>
  )
}

export function RecuperarSenha() {
  const [email, definirEmail] = useState('')
  const [enviado, definirEnviado] = useState(false)

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    // A resposta é sempre a mesma, exista a conta ou não.
    await acesso.recuperarSenha(email).catch(() => undefined)
    definirEnviado(true)
  }

  return (
    <Pagina titulo="Recuperar a senha">
      {enviado ? (
        <p>Se houver uma conta com esse e-mail, enviamos as instruções para redefinir a senha.</p>
      ) : (
        <form onSubmit={(evento) => void enviar(evento)}>
          <Campo rotulo="E-mail" type="email" value={email} aoMudar={definirEmail} required />
          <button type="submit">Enviar instruções</button>
        </form>
      )}
      <p>
        <Link to="/entrar">Voltar</Link>
      </p>
    </Pagina>
  )
}

export function RedefinirSenha() {
  const { token = '' } = useParams()
  const [senha, definirSenha] = useState('')
  const [erro, definirErro] = useState<unknown>(null)
  const [trocada, definirTrocada] = useState(false)

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    definirErro(null)
    try {
      await acesso.redefinirSenha(token, senha)
      definirTrocada(true)
    } catch (falha) {
      definirErro(falha)
    }
  }

  if (trocada) {
    return (
      <Pagina titulo="Nova senha">
        <p>Senha trocada. As sessões abertas foram encerradas.</p>
        <Link to="/entrar">Entrar</Link>
      </Pagina>
    )
  }
  return (
    <Pagina titulo="Nova senha">
      <form onSubmit={(evento) => void enviar(evento)}>
        <Campo
          rotulo="Nova senha"
          type="password"
          value={senha}
          aoMudar={definirSenha}
          erros={errosPorCampo(erro).senha}
          autoComplete="new-password"
          required
        />
        <Alerta>{erro ? mensagemDoErro(erro) : null}</Alerta>
        <button type="submit">Trocar a senha</button>
      </form>
    </Pagina>
  )
}
