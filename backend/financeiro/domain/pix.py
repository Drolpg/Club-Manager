"""Validação e normalização de chaves Pix e geração do payload EMV BR Code com CRC16-CCITT."""

import re
import unicodedata
import uuid
from decimal import Decimal
from enum import StrEnum

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_E164_RE = re.compile(r"^\+[1-9]\d{9,14}$")


class TipoChavePix(StrEnum):
    """Tipos oficiais de chave Pix aceitos pelo DICT do Banco Central."""

    EMAIL = "EMAIL"
    TELEFONE = "TELEFONE"
    CNPJ = "CNPJ"
    CPF = "CPF"
    ALEATORIA = "ALEATORIA"


def _validar_dv_cpf(digitos: str) -> bool:
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    nums = [int(c) for c in digitos]
    soma1 = sum(n * peso for n, peso in zip(nums[:9], range(10, 1, -1), strict=True))
    dv1 = (soma1 * 10) % 11 % 10
    soma2 = sum(n * peso for n, peso in zip(nums[:10], range(11, 1, -1), strict=True))
    dv2 = (soma2 * 10) % 11 % 10
    return nums[9] == dv1 and nums[10] == dv2


def _validar_dv_cnpj(digitos: str) -> bool:
    if len(digitos) != 14 or len(set(digitos)) == 1:
        return False
    nums = [int(c) for c in digitos]
    pesos1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    pesos2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    r1 = sum(n * p for n, p in zip(nums[:12], pesos1, strict=True)) % 11
    dv1 = 0 if r1 < 2 else 11 - r1
    r2 = sum(n * p for n, p in zip(nums[:13], pesos2, strict=True)) % 11
    dv2 = 0 if r2 < 2 else 11 - r2
    return nums[12] == dv1 and nums[13] == dv2


def _normalizar_telefone(chave: str) -> str:
    limpa = re.sub(r"[\s().-]", "", chave.strip())
    if limpa.startswith("+"):
        candidato = limpa
    else:
        apenas_digitos = re.sub(r"\D", "", limpa)
        if len(apenas_digitos) in (10, 11):
            candidato = f"+55{apenas_digitos}"
        elif len(apenas_digitos) in (12, 13) and apenas_digitos.startswith("55"):
            candidato = f"+{apenas_digitos}"
        else:
            raise ValueError("Telefone da chave Pix inválido. Informe DDD e número ou +55...")
    if not _E164_RE.fullmatch(candidato):
        raise ValueError("Telefone da chave Pix fora do padrão internacional E.164.")
    if candidato.startswith("+55") and len(candidato) not in (13, 14):
        raise ValueError("Telefone brasileiro da chave Pix precisa de DDD e 8 ou 9 dígitos.")
    return candidato


def normalizar_e_validar_chave(tipo: str, chave: str) -> str:
    """Valida e devolve a chave Pix no formato canônico esperado pelo BR Code."""
    try:
        tipo_enum = TipoChavePix(tipo)
    except ValueError:
        raise ValueError(f"Tipo de chave Pix inválido: {tipo!r}.") from None

    valor = chave.strip()
    if tipo_enum == TipoChavePix.EMAIL:
        normalizado = valor.lower()
        if not _EMAIL_RE.fullmatch(normalizado) or len(normalizado) > 77:
            raise ValueError("E-mail da chave Pix inválido.")
        return normalizado

    if tipo_enum == TipoChavePix.TELEFONE:
        return _normalizar_telefone(valor)

    if tipo_enum == TipoChavePix.CPF:
        digitos = re.sub(r"\D", "", valor)
        if not _validar_dv_cpf(digitos):
            raise ValueError("CPF da chave Pix inválido.")
        return digitos

    if tipo_enum == TipoChavePix.CNPJ:
        digitos = re.sub(r"\D", "", valor)
        if not _validar_dv_cnpj(digitos):
            raise ValueError("CNPJ da chave Pix inválido.")
        return digitos

    # ALEATORIA
    try:
        uid = uuid.UUID(valor)
    except ValueError:
        raise ValueError("Chave Pix aleatória precisa ser um UUID válido.") from None
    return str(uid).lower()


def _normalizar_texto_emv(texto: str, limite: int, *, padrao: str) -> str:
    decomposed = unicodedata.normalize("NFKD", texto)
    sem_acentos = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    ascii_limpo = re.sub(r"[^A-Za-z0-9 .,-]", " ", sem_acentos)
    colapsado = " ".join(ascii_limpo.split()).strip()
    resultado = colapsado[:limite].strip()
    return resultado or padrao[:limite]


def _tlv(campo_id: str, valor: str) -> str:
    tamanho = len(valor.encode("utf-8"))
    if tamanho > 99:
        raise ValueError(f"Campo EMV {campo_id} excedeu 99 bytes.")
    return f"{campo_id}{tamanho:02d}{valor}"


def crc16_ccitt(payload: str) -> str:
    """Calcula CRC16-CCITT-FALSE (polinômio 0x1021, inicial 0xFFFF) usado pelo Pix BR Code."""
    crc = 0xFFFF
    for byte in payload.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def txid_da_cobranca(cobranca_id: uuid.UUID) -> str:
    """Identificador determinístico de 25 caracteres alfanuméricos para o campo 62.05."""
    return cobranca_id.hex[:25].upper()


def gerar_pix_copia_e_cola(
    *,
    chave: str,
    nome_recebedor: str,
    cidade: str,
    valor: Decimal,
    cobranca_id: uuid.UUID,
) -> str:
    """Gera o código Pix Copia e Cola EMV (BR Code) com valor fixo e CRC16 válido."""
    if valor <= 0:
        raise ValueError("O valor do Pix precisa ser maior que zero.")

    nome = _normalizar_texto_emv(nome_recebedor, 25, padrao="CLUBE")
    cidade_limpa = _normalizar_texto_emv(cidade, 15, padrao="BRASIL")
    conta_pix = _tlv("00", "br.gov.bcb.pix") + _tlv("01", chave)
    adicional = _tlv("05", txid_da_cobranca(cobranca_id))

    sem_crc = (
        _tlv("00", "01")
        + _tlv("26", conta_pix)
        + _tlv("52", "0000")
        + _tlv("53", "986")
        + _tlv("54", f"{valor:.2f}")
        + _tlv("58", "BR")
        + _tlv("59", nome)
        + _tlv("60", cidade_limpa)
        + _tlv("62", adicional)
        + "6304"
    )
    return sem_crc + crc16_ccitt(sem_crc)
