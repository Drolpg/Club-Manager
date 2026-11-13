# Ligar o login com o Google

Guia. O login com o Google é opcional: sem o ID de cliente, o botão não aparece e o sistema funciona só com senha.

> Este passo a passo descreve o Google Cloud Console como o agente o conhece; ele não foi executado nesta máquina,
> porque exige a conta Google do dono. Se uma tela estiver diferente, procure pelos mesmos nomes de opção.

## 1. Criar o ID de cliente

1. Abra <https://console.cloud.google.com/> e crie um projeto (por exemplo, "Club Manager"). Não tem custo.
2. Em "APIs e serviços" → "Tela de permissão OAuth", configure o aplicativo como "Externo", com o nome do clube e o
   seu e-mail de contato. Não é preciso pedir nenhum escopo além dos básicos (e-mail e perfil).
3. Em "APIs e serviços" → "Credenciais" → "Criar credenciais" → "ID do cliente OAuth".
4. Tipo de aplicativo: "Aplicativo da Web".
5. Em "Origens JavaScript autorizadas", adicione o endereço do site:
   - desenvolvimento: `http://localhost:8080` e, se usar o Vite, `http://localhost:5173`;
   - produção: o endereço público, com `https://`.
6. Não é preciso URI de redirecionamento: o sistema usa o botão do Google, sem redirecionar.
7. Copie o "ID do cliente" (termina em `.apps.googleusercontent.com`). O "segredo do cliente" não é usado.

## 2. Configurar o sistema

No `.env`, na raiz:

```text
GOOGLE_CLIENT_ID=<o ID copiado>
```

Recrie os contêineres para a variável valer:

```text
docker compose up -d
```

Como verificar: `GET http://localhost:8080/api/v1/acesso/configuracao/` devolve o ID, e a tela "Entrar" mostra o
botão do Google. O roteiro de teste está em [api/manual-testing.md](../api/manual-testing.md).

## O que o Google faz e o que não faz

O Google só confirma quem é a pessoa e qual é o e-mail dela. Ele não cria conta: quem não foi convidado não entra, e
cargo, setores e permissões são sempre os do sistema (ADR-008).
