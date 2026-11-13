import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { ADMIN, DIRETOR, SEM_GOOGLE, erro, simularApi } from './test/api'

function abrir(caminho: string) {
  return render(
    <MemoryRouter initialEntries={[caminho]}>
      <App />
    </MemoryRouter>,
  )
}

const SEM_SESSAO = { 'GET /acesso/sessao/': { usuario: null }, ...SEM_GOOGLE }
const COMO_DIRETOR = { 'GET /acesso/sessao/': { usuario: DIRETOR }, ...SEM_GOOGLE }
const COMO_ADMIN = { 'GET /acesso/sessao/': { usuario: ADMIN }, ...SEM_GOOGLE }

afterEach(() => {
  vi.unstubAllGlobals()
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
})

describe('entrar e sair', () => {
  it('leva quem não está logado para a tela de entrar', async () => {
    simularApi(SEM_SESSAO)

    abrir('/')

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument()
  })

  it('entra com identificador e senha, enviando o token CSRF', async () => {
    document.cookie = 'csrftoken=token-do-cookie'
    const chamadas = simularApi({ ...SEM_SESSAO, 'POST /acesso/sessao/': { usuario: DIRETOR } })
    abrir('/entrar')

    await userEvent.type(await screen.findByLabelText('Nome de usuário ou e-mail'), 'bia')
    await userEvent.type(screen.getByLabelText('Senha'), 'uma-senha-comprida')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByText(/aguarda a classificação/i)).toBeInTheDocument()
    const login = chamadas.find((c) => c.metodo === 'POST')!
    expect(login.corpo).toEqual({ identificador: 'bia', senha: 'uma-senha-comprida' })
    expect(login.cabecalhos['X-CSRFToken']).toBe('token-do-cookie')
  })

  it.each([
    ['CREDENCIAIS_INVALIDAS', 401, 'Usuário ou senha inválidos.'],
    ['MUITAS_TENTATIVAS', 429, 'Muitas tentativas. Espere alguns minutos e tente de novo.'],
  ])('mostra a mensagem do erro %s', async (codigo, status, mensagem) => {
    simularApi({ ...SEM_SESSAO, 'POST /acesso/sessao/': erro(status, codigo) })
    abrir('/entrar')

    await userEvent.type(await screen.findByLabelText('Nome de usuário ou e-mail'), 'bia')
    await userEvent.type(screen.getByLabelText('Senha'), 'errada')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(mensagem)
  })

  it('oferece o reenvio do link quando o e-mail ainda não foi verificado', async () => {
    const chamadas = simularApi({
      ...SEM_SESSAO,
      'POST /acesso/sessao/': erro(403, 'EMAIL_NAO_VERIFICADO'),
      'POST /acesso/verificacoes/reenviar/': [204, null],
    })
    abrir('/entrar')
    await userEvent.type(await screen.findByLabelText('Nome de usuário ou e-mail'), 'caio')
    await userEvent.type(screen.getByLabelText('Senha'), 'uma-senha-comprida')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    await userEvent.click(await screen.findByRole('button', { name: 'Reenviar o link de verificação' }))

    expect(await screen.findByText(/enviamos outro link/i)).toBeInTheDocument()
    expect(chamadas.at(-1)).toMatchObject({ caminho: '/acesso/verificacoes/reenviar/', corpo: { identificador: 'caio' } })
  })

  it('sai e volta para a tela de entrar', async () => {
    const chamadas = simularApi({ ...COMO_DIRETOR, 'DELETE /acesso/sessao/': [204, null] })
    abrir('/')

    await userEvent.click(await screen.findByRole('button', { name: 'Sair' }))

    expect(await screen.findByRole('heading', { name: 'Entrar' })).toBeInTheDocument()
    expect(chamadas.some((c) => c.metodo === 'DELETE' && c.caminho === '/acesso/sessao/')).toBe(true)
  })
})

describe('página inicial', () => {
  it('CA-33: o diretor sem cargo vê que aguarda a classificação e nenhum atalho de gestão', async () => {
    simularApi(COMO_DIRETOR)

    abrir('/')

    expect(await screen.findByText(/aguarda a classificação/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Convites' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Usuários' })).not.toBeInTheDocument()
  })

  it('o admin vê os atalhos de convites e de usuários', async () => {
    simularApi(COMO_ADMIN)

    abrir('/')

    expect(await screen.findByRole('link', { name: 'Convites' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Usuários' })).toBeInTheDocument()
  })

  it('o diretor que abre uma tela de admin volta para a página inicial', async () => {
    simularApi(COMO_DIRETOR)

    abrir('/admin/convites')

    expect(await screen.findByText(/aguarda a classificação/i)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Convites' })).not.toBeInTheDocument()
  })
})

describe('cadastro pelo convite', () => {
  const CONVITE_OK = { ...SEM_SESSAO, 'POST /acesso/convites/consultar/': [204, null] as [number, unknown] }

  async function preencher() {
    await userEvent.type(await screen.findByLabelText('Nome'), 'Caio Convidado')
    await userEvent.type(screen.getByLabelText('Nome de usuário'), 'caio')
    await userEvent.type(screen.getByLabelText('Telefone'), '11977776666')
    await userEvent.type(screen.getByLabelText('E-mail'), 'caio@exemplo.com')
    await userEvent.type(screen.getByLabelText('Senha'), 'uma-senha-comprida')
  }

  it('convite inválido mostra o aviso e nenhum formulário', async () => {
    simularApi({ ...SEM_SESSAO, 'POST /acesso/convites/consultar/': erro(404, 'CONVITE_INVALIDO') })

    abrir('/convite/abc')

    expect(await screen.findByRole('alert')).toHaveTextContent('Convite inválido ou expirado.')
    expect(screen.queryByLabelText('Nome de usuário')).not.toBeInTheDocument()
  })

  it('CA-14: o formulário mostra o aviso de privacidade e não pede CPF', async () => {
    simularApi(CONVITE_OK)

    abrir('/convite/abc')

    expect(await screen.findByRole('heading', { name: 'Seus dados no Club Manager' })).toBeInTheDocument()
    expect(screen.getByText(/guardamos seu nome, nome de usuário, e-mail e telefone/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/cpf/i)).not.toBeInTheDocument()
  })

  it('envia o cadastro com o token do link e pede para verificar o e-mail', async () => {
    const chamadas = simularApi({
      ...CONVITE_OK,
      'POST /acesso/cadastros/': [201, { situacao: 'AGUARDANDO_VERIFICACAO' }],
    })
    abrir('/convite/token-do-link')
    await preencher()

    await userEvent.click(screen.getByRole('button', { name: 'Cadastrar' }))

    expect(await screen.findByText(/enviamos um link para caio@exemplo.com/i)).toBeInTheDocument()
    expect(chamadas.at(-1)!.corpo).toEqual({
      token: 'token-do-link',
      nome: 'Caio Convidado',
      nome_de_usuario: 'caio',
      telefone: '11977776666',
      email: 'caio@exemplo.com',
      senha: 'uma-senha-comprida',
    })
  })

  it('mostra o erro de nome de usuário em uso e mantém o formulário', async () => {
    simularApi({ ...CONVITE_OK, 'POST /acesso/cadastros/': erro(409, 'NOME_DE_USUARIO_EM_USO') })
    abrir('/convite/abc')
    await preencher()

    await userEvent.click(screen.getByRole('button', { name: 'Cadastrar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Este nome de usuário já está em uso.')
    expect(screen.getByLabelText('Nome de usuário')).toHaveValue('caio')
  })

  it('mostra o motivo de cada campo recusado', async () => {
    const detalhes = { senha: ['Esta senha é muito curta.'] }
    simularApi({
      ...CONVITE_OK,
      'POST /acesso/cadastros/': erro(400, 'VALIDATION_ERROR', 'inválido', detalhes),
    })
    abrir('/convite/abc')
    await preencher()

    await userEvent.click(screen.getByRole('button', { name: 'Cadastrar' }))

    expect(await screen.findByText('Esta senha é muito curta.')).toBeInTheDocument()
  })
})

describe('verificação e recuperação', () => {
  it('verifica o e-mail pelo link e convida a entrar', async () => {
    const chamadas = simularApi({ ...SEM_SESSAO, 'POST /acesso/verificacoes/': [204, null] })

    abrir('/verificar/token-de-verificacao')

    expect(await screen.findByText(/e-mail verificado/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Entrar' })).toBeInTheDocument()
    const verificacao = chamadas.find((c) => c.caminho === '/acesso/verificacoes/')!
    expect(verificacao.corpo).toEqual({ token: 'token-de-verificacao' })
  })

  it('avisa quando o link de verificação é inválido', async () => {
    simularApi({ ...SEM_SESSAO, 'POST /acesso/verificacoes/': erro(400, 'LINK_INVALIDO') })

    abrir('/verificar/vencido')

    expect(await screen.findByRole('alert')).toHaveTextContent('Este link é inválido ou venceu.')
  })

  it('o pedido de recuperação responde sempre a mesma coisa', async () => {
    const chamadas = simularApi({ ...SEM_SESSAO, 'POST /acesso/senhas/recuperar/': [204, null] })
    abrir('/recuperar-senha')

    await userEvent.type(await screen.findByLabelText('E-mail'), 'bia@exemplo.com')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar instruções' }))

    expect(await screen.findByText(/se houver uma conta com esse e-mail/i)).toBeInTheDocument()
    expect(chamadas.at(-1)!.corpo).toEqual({ email: 'bia@exemplo.com' })
  })

  it('redefine a senha com o token do link', async () => {
    const chamadas = simularApi({ ...SEM_SESSAO, 'POST /acesso/senhas/redefinir/': [204, null] })
    abrir('/redefinir-senha/id.token')

    await userEvent.type(await screen.findByLabelText('Nova senha'), 'outra-senha-comprida')
    await userEvent.click(screen.getByRole('button', { name: 'Trocar a senha' }))

    expect(await screen.findByText(/senha trocada/i)).toBeInTheDocument()
    expect(chamadas.at(-1)!.corpo).toEqual({ token: 'id.token', senha: 'outra-senha-comprida' })
  })
})

describe('administração', () => {
  const CONVITE = {
    id: 'c-1',
    situacao: 'ATIVO',
    gerado_por: { id: 'u-0', nome: 'Ana Admin' },
    gerado_em: '2026-11-12T10:00:00-03:00',
    expira_em: '2026-11-13T10:00:00-03:00',
    usado_em: null,
    revogado_em: null,
  }

  it('lista os convites com a situação e quem gerou', async () => {
    simularApi({ ...COMO_ADMIN, 'GET /acesso/convites/': [CONVITE, { ...CONVITE, id: 'c-2', situacao: 'EXPIRADO' }] })

    abrir('/admin/convites')

    await screen.findByText('Expirado')
    const linhas = screen.getAllByRole('row')
    expect(within(linhas[1]).getByText('Ativo')).toBeInTheDocument()
    expect(within(linhas[1]).getByText('Ana Admin')).toBeInTheDocument()
    expect(within(linhas[2]).getByText('Expirado')).toBeInTheDocument()
  })

  it('gera um convite e mostra o link, avisando que ele aparece uma vez só', async () => {
    simularApi({
      ...COMO_ADMIN,
      'GET /acesso/convites/': [],
      'POST /acesso/convites/': [201, { ...CONVITE, link: 'https://clube.exemplo/convite/segredo' }],
    })
    abrir('/admin/convites')

    await userEvent.click(await screen.findByRole('button', { name: 'Gerar convite' }))

    expect(await screen.findByDisplayValue('https://clube.exemplo/convite/segredo')).toBeInTheDocument()
    expect(screen.getByText(/só aparece agora/i)).toBeInTheDocument()
  })

  it('revoga um convite ativo', async () => {
    const chamadas = simularApi({
      ...COMO_ADMIN,
      'GET /acesso/convites/': [CONVITE],
      'POST /acesso/convites/c-1/revogar/': { ...CONVITE, situacao: 'REVOGADO' },
    })
    abrir('/admin/convites')

    await userEvent.click(await screen.findByRole('button', { name: 'Revogar' }))

    await waitFor(() => expect(chamadas.some((c) => c.caminho === '/acesso/convites/c-1/revogar/')).toBe(true))
  })

  it('lista os usuários e desativa um deles', async () => {
    const chamadas = simularApi({
      ...COMO_ADMIN,
      'GET /acesso/usuarios/': [ADMIN, DIRETOR],
      'POST /acesso/usuarios/u-1/desativar/': { ...DIRETOR, situacao: 'INATIVO' },
    })
    abrir('/admin/usuarios')
    const linha = (await screen.findByText('Bia Diretora')).closest('tr')!
    expect(within(linha).getByText('Ativo')).toBeInTheDocument()
    expect(within(linha).getByText('Sem cargo')).toBeInTheDocument()

    await userEvent.click(within(linha).getByRole('button', { name: 'Desativar' }))

    await waitFor(() => expect(chamadas.some((c) => c.caminho === '/acesso/usuarios/u-1/desativar/')).toBe(true))
  })

  it('mostra o motivo quando a ação é recusada', async () => {
    simularApi({
      ...COMO_ADMIN,
      'GET /acesso/usuarios/': [ADMIN, { ...DIRETOR, admin: true }],
      'POST /acesso/usuarios/u-1/remover-admin/': erro(422, 'NAO_PODE_ALTERAR_A_SI_MESMO'),
    })
    abrir('/admin/usuarios')
    const linha = (await screen.findByText('Bia Diretora')).closest('tr')!

    await userEvent.click(within(linha).getByRole('button', { name: 'Tirar o papel de admin' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Esta ação precisa ser feita por outro admin.')
  })

  it('não oferece desativar nem tirar o papel na linha do próprio admin', async () => {
    simularApi({ ...COMO_ADMIN, 'GET /acesso/usuarios/': [ADMIN, DIRETOR] })
    abrir('/admin/usuarios')

    const linha = (await screen.findByText('Ana Admin')).closest('tr')!

    expect(within(linha).queryByRole('button')).not.toBeInTheDocument()
  })
})

describe('Google', () => {
  it('não mostra o botão do Google quando o clube não configurou o ID de cliente', async () => {
    simularApi(SEM_SESSAO)

    abrir('/entrar')

    await screen.findByRole('heading', { name: 'Entrar' })
    expect(screen.queryByTestId('botao-google')).not.toBeInTheDocument()
  })

  it('entra com a credencial devolvida pelo Google', async () => {
    let aoReceber: (resposta: { credential: string }) => void = () => {}
    vi.stubGlobal('google', {
      accounts: {
        id: {
          initialize: (opcoes: { callback: typeof aoReceber }) => {
            aoReceber = opcoes.callback
          },
          renderButton: vi.fn(),
        },
      },
    })
    const chamadas = simularApi({
      'GET /acesso/sessao/': { usuario: null },
      'GET /acesso/configuracao/': { google_client_id: 'id-do-clube' },
      'POST /acesso/sessao/google/': { usuario: DIRETOR },
    })
    abrir('/entrar')
    await screen.findByTestId('botao-google')

    aoReceber({ credential: 'credencial-do-google' })

    expect(await screen.findByText(/aguarda a classificação/i)).toBeInTheDocument()
    // Depois do login a moldura monta o sino, que consulta o resumo: o POST não é mais a última chamada.
    expect(chamadas.find((c) => c.metodo === 'POST')).toMatchObject({
      caminho: '/acesso/sessao/google/',
      corpo: { credencial: 'credencial-do-google' },
    })
  })
})
