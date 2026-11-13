from django.contrib.auth.hashers import Argon2PasswordHasher


class FastArgon2PasswordHasher(Argon2PasswordHasher):
    """O mesmo Argon2 da produção, com custo mínimo, para os testes não gastarem segundos em cada senha."""

    time_cost = 1
    memory_cost = 8
    parallelism = 1
