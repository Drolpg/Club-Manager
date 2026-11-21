"""Validações puras dos textos e das datas (spec técnica do M9, "Funções puras").

Cada função devolve os erros por campo, vazio quando está tudo certo; o serviço os transforma em
`VALIDATION_ERROR`. O texto é guardado como veio: aqui só se confere se está preenchido e se cabe no limite.
"""

from datetime import date

from comunicacao.domain.valores import TipoDeComunicado, TipoDeReacao

LIMITE_DO_TITULO = 120
LIMITE_DO_TEXTO = 5000
LIMITE_DO_COMENTARIO = 2000
LIMITE_DA_DESCRICAO = 1000
LIMITE_DO_MOTIVO = 500

TIPOS_DE_REACAO: tuple[str, ...] = tuple(tipo.value for tipo in TipoDeReacao)

Erros = dict[str, list[str]]


def _obrigatorio(erros: Erros, campo: str, valor: str, limite: int, nome: str) -> None:
    if not valor.strip():
        erros[campo] = [f"Informe {nome}."]
    elif len(valor) > limite:
        erros[campo] = [f"Use no máximo {limite} caracteres."]


def validar_comunicado(tipo: str, titulo: str, texto: str) -> Erros:
    erros: Erros = {}
    if tipo not in {t.value for t in TipoDeComunicado}:
        erros["tipo"] = ["Escolha comunicado ou pauta."]
    _obrigatorio(erros, "titulo", titulo, LIMITE_DO_TITULO, "o título")
    _obrigatorio(erros, "texto", texto, LIMITE_DO_TEXTO, "o texto")
    return erros


def validar_comentario(texto: str) -> Erros:
    erros: Erros = {}
    _obrigatorio(erros, "texto", texto, LIMITE_DO_COMENTARIO, "o comentário")
    return erros


def validar_motivo(motivo: str) -> Erros:
    erros: Erros = {}
    _obrigatorio(erros, "motivo", motivo, LIMITE_DO_MOTIVO, "o motivo")
    return erros


def validar_documento(titulo: str, descricao: str) -> Erros:
    erros: Erros = {}
    _obrigatorio(erros, "titulo", titulo, LIMITE_DO_TITULO, "o título")
    if len(descricao) > LIMITE_DA_DESCRICAO:
        erros["descricao"] = [f"Use no máximo {LIMITE_DA_DESCRICAO} caracteres."]
    return erros


def validar_ata(titulo: str, descricao: str, data_da_reuniao: date | None) -> Erros:
    erros = validar_documento(titulo, descricao)
    if data_da_reuniao is None:
        erros["data_da_reuniao"] = ["Informe a data da reunião."]
    return erros


def reuniao_no_futuro(data_da_reuniao: date, hoje: date) -> bool:
    return data_da_reuniao > hoje
