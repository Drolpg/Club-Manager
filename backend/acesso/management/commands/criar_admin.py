import getpass
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from acesso.services import usuarios
from kernel.errors import BusinessError

_CAMPOS = {
    "nome": "nome",
    "nome_de_usuario": "nome de usuário",
    "email": "e-mail",
    "telefone": "telefone",
    "senha": "senha",
}


class Command(BaseCommand):
    help = (
        "Cria um admin, pedindo os dados na hora. É o único caminho para o primeiro admin, e o de "
        "recuperação se todos perderem o acesso. A senha nunca é aceita por argumento."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        nome = input("Nome: ")
        nome_de_usuario = input("Nome de usuário: ")
        email = input("E-mail: ")
        telefone = input("Telefone: ")
        senha = getpass.getpass("Senha: ")
        if senha != getpass.getpass("Senha (de novo): "):
            raise CommandError("As senhas não conferem. Nenhum usuário foi criado.")

        try:
            usuario = usuarios.criar_admin(
                nome=nome, nome_de_usuario=nome_de_usuario, email=email, telefone=telefone, senha=senha
            )
        except BusinessError as erro:
            raise CommandError(self._explicar(erro)) from erro

        self.stdout.write(self.style.SUCCESS(f"Admin {usuario.nome_de_usuario} criado."))

    @staticmethod
    def _explicar(erro: BusinessError) -> str:
        linhas = [f"{erro.message} Nenhum usuário foi criado."]
        if erro.code == "NOME_DE_USUARIO_EM_USO":
            linhas.append("Escolha outro nome de usuário.")
        if isinstance(erro.details, dict):
            for campo, mensagens in erro.details.items():
                linhas.append(f"- {_CAMPOS.get(campo, campo)}: {' '.join(mensagens)}")
        return "\n".join(linhas)
