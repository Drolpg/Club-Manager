"""Gerador puro de QR Code em SVG (ISO/IEC 18004, modo byte, correção de erro M)."""

from collections.abc import Callable

# Tabela ISO/IEC 18004 (nível M, versões 1 a 20):
# (total_dados, ec_por_bloco, blocos_g1, dados_g1, blocos_g2, dados_g2)
_TABELA_M: tuple[tuple[int, int, int, int, int, int], ...] = (
    (16, 10, 1, 16, 0, 0),  # v1
    (28, 16, 1, 28, 0, 0),  # v2
    (44, 26, 1, 44, 0, 0),  # v3
    (64, 18, 2, 32, 0, 0),  # v4
    (86, 24, 2, 43, 0, 0),  # v5
    (108, 16, 4, 27, 0, 0),  # v6
    (124, 18, 4, 31, 0, 0),  # v7
    (154, 22, 2, 38, 2, 39),  # v8
    (182, 22, 3, 36, 2, 37),  # v9
    (216, 26, 4, 43, 1, 44),  # v10
    (254, 30, 1, 50, 4, 51),  # v11
    (290, 22, 6, 36, 2, 37),  # v12
    (334, 22, 8, 37, 1, 38),  # v13
    (365, 24, 4, 40, 5, 41),  # v14
    (415, 24, 5, 41, 5, 42),  # v15
    (453, 28, 7, 45, 3, 46),  # v16
    (507, 28, 10, 46, 1, 47),  # v17
    (563, 26, 9, 43, 4, 44),  # v18
    (627, 26, 3, 44, 11, 45),  # v19
    (669, 26, 3, 41, 13, 42),  # v20
)

# Posições dos alignment patterns (ISO/IEC 18004, Table E.1, versões 1 a 20).
_ALINHAMENTO: tuple[tuple[int, ...], ...] = (
    (),
    (6, 18),
    (6, 22),
    (6, 26),
    (6, 30),
    (6, 34),
    (6, 22, 38),
    (6, 24, 42),
    (6, 26, 46),
    (6, 28, 50),
    (6, 30, 54),
    (6, 32, 58),
    (6, 34, 62),
    (6, 26, 46, 66),
    (6, 26, 48, 70),
    (6, 26, 50, 74),
    (6, 30, 54, 78),
    (6, 30, 56, 82),
    (6, 30, 58, 86),
    (6, 34, 62, 90),
)


def _construir_gf() -> tuple[list[int], list[int]]:
    exp = [0] * 512
    log = [0] * 256
    valor = 1
    for i in range(255):
        exp[i] = valor
        log[valor] = i
        valor <<= 1
        if valor & 0x100:
            valor ^= 0x11D
    for i in range(255, 512):
        exp[i] = exp[i - 255]
    return exp, log


_GF_EXP, _GF_LOG = _construir_gf()


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def _polinomio_rs(grau: int) -> list[int]:
    poly = [1]
    for i in range(grau):
        fator = [1, _GF_EXP[i]]
        proximo = [0] * (len(poly) + 1)
        for j, coef_p in enumerate(poly):
            for k, coef_f in enumerate(fator):
                proximo[j + k] ^= _gf_mul(coef_p, coef_f)
        poly = proximo
    return poly


def _calcular_ecc(dados: list[int], tamanho_ecc: int) -> list[int]:
    gen = _polinomio_rs(tamanho_ecc)
    reg = [*dados, *([0] * tamanho_ecc)]
    for i in range(len(dados)):
        coef = reg[i]
        if coef != 0:
            for j in range(1, len(gen)):
                reg[i + j] ^= _gf_mul(gen[j], coef)
    return reg[len(dados) :]


def _escolher_versao(tamanho_bytes: int) -> int:
    for versao in range(1, 21):
        bits_tamanho = 8 if versao <= 9 else 16
        capacidade_bits = _TABELA_M[versao - 1][0] * 8
        necessarios = 4 + bits_tamanho + tamanho_bytes * 8
        if necessarios <= capacidade_bits:
            return versao
    raise ValueError("Conteúdo excede a capacidade máxima suportada pelo QR Code.")


def _codificar_dados(dados: bytes, versao: int) -> list[int]:
    total_dados = _TABELA_M[versao - 1][0]
    bits: list[int] = []

    def _adicionar(valor: int, largura: int) -> None:
        for shift in range(largura - 1, -1, -1):
            bits.append((valor >> shift) & 1)

    _adicionar(0b0100, 4)  # Modo byte
    _adicionar(len(dados), 8 if versao <= 9 else 16)
    for byte in dados:
        _adicionar(byte, 8)

    limite_bits = total_dados * 8
    terminador = min(4, limite_bits - len(bits))
    bits.extend([0] * terminador)
    while len(bits) % 8 != 0:
        bits.append(0)

    codewords = [sum(bits[i + b] << (7 - b) for b in range(8)) for i in range(0, len(bits), 8)]
    pad_bytes = (0xEC, 0x11)
    idx_pad = 0
    while len(codewords) < total_dados:
        codewords.append(pad_bytes[idx_pad % 2])
        idx_pad += 1
    return codewords


def _intercalar_blocos(codewords: list[int], versao: int) -> list[int]:
    _, ec_por_bloco, g1, d1, g2, d2 = _TABELA_M[versao - 1]
    blocos_dados: list[list[int]] = []
    blocos_ecc: list[list[int]] = []
    pos = 0
    for qtd, tam in ((g1, d1), (g2, d2)):
        for _ in range(qtd):
            bloco = codewords[pos : pos + tam]
            pos += tam
            blocos_dados.append(bloco)
            blocos_ecc.append(_calcular_ecc(bloco, ec_por_bloco))

    final: list[int] = []
    max_dados = max(len(b) for b in blocos_dados)
    for i in range(max_dados):
        for bloco in blocos_dados:
            if i < len(bloco):
                final.append(bloco[i])
    for i in range(ec_por_bloco):
        for bloco_ec in blocos_ecc:
            final.append(bloco_ec[i])
    return final


def _bch(valor: int, _largura_info: int, polinomio: int, grau: int) -> int:
    reg = valor << grau
    while reg.bit_length() >= grau + 1:
        shift = reg.bit_length() - (grau + 1)
        reg ^= polinomio << shift
    return (valor << grau) | reg


def _bits_formato(mascara: int) -> int:
    # Nível M = 00 em 2 bits, seguido de 3 bits da máscara.
    dados = (0b00 << 3) | mascara
    return _bch(dados, 5, 0b10100110111, 10) ^ 0b101010000010010


def _bits_versao(versao: int) -> int:
    return _bch(versao, 6, 0b1111100100101, 12)


def _desenhar_base(versao: int) -> tuple[list[list[bool]], list[list[bool]]]:
    n = versao * 4 + 17
    matriz = [[False] * n for _ in range(n)]
    funcao = [[False] * n for _ in range(n)]

    def _fixar(linha: int, col: int, escuro: bool) -> None:
        if 0 <= linha < n and 0 <= col < n:
            matriz[linha][col] = escuro
            funcao[linha][col] = True

    # Finders + separadores brancos.
    for r0, c0 in ((0, 0), (0, n - 7), (n - 7, 0)):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                r, c = r0 + dr, c0 + dc
                if not (0 <= r < n and 0 <= c < n):
                    continue
                no_finder = 0 <= dr <= 6 and 0 <= dc <= 6
                borda = dr in (0, 6) or dc in (0, 6)
                miolo = 2 <= dr <= 4 and 2 <= dc <= 4
                _fixar(r, c, no_finder and (borda or miolo))

    # Timing patterns.
    for i in range(8, n - 8):
        escuro = i % 2 == 0
        _fixar(6, i, escuro)
        _fixar(i, 6, escuro)

    # Dark module obrigatório.
    _fixar(4 * versao + 9, 8, True)

    # Alignment patterns (v >= 2). Só pulam os três cantos dos finders; sobrepõem timing patterns.
    coords = _ALINHAMENTO[versao - 1]
    for r_centro in coords:
        for c_centro in coords:
            nos_finders = (
                (r_centro < 8 and c_centro < 8)
                or (r_centro < 8 and c_centro >= n - 8)
                or (r_centro >= n - 8 and c_centro < 8)
            )
            if nos_finders:
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    escuro = max(abs(dr), abs(dc)) in (0, 2)
                    _fixar(r_centro + dr, c_centro + dc, escuro)

    # Reserva das áreas de format info.
    for i in range(9):
        if not funcao[8][i]:
            funcao[8][i] = True
        if not funcao[i][8]:
            funcao[i][8] = True
    for i in range(8):
        funcao[8][n - 1 - i] = True
    for i in range(7):
        funcao[n - 1 - i][8] = True

    # Bits de versão (v >= 7).
    if versao >= 7:
        v_bits = _bits_versao(versao)
        for i in range(18):
            bit = bool((v_bits >> i) & 1)
            a, b = divmod(i, 3)
            _fixar(n - 11 + b, a, bit)
            _fixar(a, n - 11 + b, bit)

    return matriz, funcao


def _preencher_dados(matriz: list[list[bool]], funcao: list[list[bool]], final: list[int]) -> None:
    n = len(matriz)
    bits: list[bool] = []
    for cw in final:
        for shift in range(7, -1, -1):
            bits.append(bool((cw >> shift) & 1))

    idx = 0
    subindo = True
    col = n - 1
    while col >= 1:
        if col == 6:
            col -= 1
        linhas = range(n - 1, -1, -1) if subindo else range(n)
        for linha in linhas:
            for dc in (0, -1):
                c = col + dc
                if not funcao[linha][c]:
                    matriz[linha][c] = bits[idx] if idx < len(bits) else False
                    idx += 1
        col -= 2
        subindo = not subindo


_MASCARAS: tuple[Callable[[int, int], bool], ...] = (
    lambda r, c: (r + c) % 2 == 0,
    lambda r, _c: r % 2 == 0,
    lambda _r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: ((r // 2) + (c // 3)) % 2 == 0,
    lambda r, c: ((r * c) % 2 + (r * c) % 3) == 0,
    lambda r, c: (((r * c) % 2) + ((r * c) % 3)) % 2 == 0,
    lambda r, c: (((r + c) % 2) + ((r * c) % 3)) % 2 == 0,
)


def _aplicar_mascara_e_formato(
    base: list[list[bool]], funcao: list[list[bool]], mascara_idx: int
) -> list[list[bool]]:
    n = len(base)
    regra = _MASCARAS[mascara_idx]
    grade = [[base[r][c] ^ (not funcao[r][c] and regra(r, c)) for c in range(n)] for r in range(n)]
    fmt = _bits_formato(mascara_idx)
    for i in range(15):
        bit = bool((fmt >> i) & 1)
        if i < 6:
            grade[i][8] = bit
        elif i < 8:
            grade[i + 1][8] = bit
        else:
            grade[n - 15 + i][8] = bit

        if i < 8:
            grade[8][n - 1 - i] = bit
        elif i < 9:
            grade[8][7] = bit
        else:
            grade[8][14 - i] = bit
    return grade


def _penalidade_linhas(grade: list[list[bool]]) -> int:
    n = len(grade)
    total = 0
    for linha in grade:
        atual = linha[0]
        seq = 1
        for val in linha[1:]:
            if val == atual:
                seq += 1
            else:
                if seq >= 5:
                    total += 3 + (seq - 5)
                atual = val
                seq = 1
        if seq >= 5:
            total += 3 + (seq - 5)
    for c in range(n):
        atual = grade[0][c]
        seq = 1
        for r in range(1, n):
            if grade[r][c] == atual:
                seq += 1
            else:
                if seq >= 5:
                    total += 3 + (seq - 5)
                atual = grade[r][c]
                seq = 1
        if seq >= 5:
            total += 3 + (seq - 5)
    return total


def _penalidade(grade: list[list[bool]]) -> int:
    n = len(grade)
    pontos = _penalidade_linhas(grade)

    for r in range(n - 1):
        for c in range(n - 1):
            v = grade[r][c]
            if grade[r][c + 1] == v and grade[r + 1][c] == v and grade[r + 1][c + 1] == v:
                pontos += 3

    padrao1 = (True, False, True, True, True, False, True, False, False, False, False)
    padrao2 = (False, False, False, False, True, False, True, True, True, False, True)
    for r in range(n):
        for c in range(n - 10):
            trecho = tuple(grade[r][c + k] for k in range(11))
            if trecho in (padrao1, padrao2):
                pontos += 40
    for c in range(n):
        for r in range(n - 10):
            trecho = tuple(grade[r + k][c] for k in range(11))
            if trecho in (padrao1, padrao2):
                pontos += 40

    escuros = sum(1 for r in range(n) for c in range(n) if grade[r][c])
    percentual = (escuros * 100) / (n * n)
    prev5 = int(percentual // 5) * 5
    next5 = prev5 + 5
    pontos += min(abs(prev5 - 50) // 5, abs(next5 - 50) // 5) * 10
    return pontos


def gerar_qrcode_svg(codigo: str) -> str:
    """Gera o SVG determinístico do QR Code para `codigo` (ISO/IEC 18004, ECC M)."""
    if not codigo:
        raise ValueError("Código para QR Code não pode ser vazio.")

    dados = codigo.encode("utf-8")
    versao = _escolher_versao(len(dados))
    codewords = _codificar_dados(dados, versao)
    final = _intercalar_blocos(codewords, versao)
    base, funcao = _desenhar_base(versao)
    _preencher_dados(base, funcao, final)

    melhor_grade = _aplicar_mascara_e_formato(base, funcao, 0)
    menor_penalidade = _penalidade(melhor_grade)
    for mascara_idx in range(1, 8):
        candidata = _aplicar_mascara_e_formato(base, funcao, mascara_idx)
        pen = _penalidade(candidata)
        if pen < menor_penalidade:
            menor_penalidade = pen
            melhor_grade = candidata

    quiet = 4
    total = len(melhor_grade) + quiet * 2
    comandos = [
        f"M{c + quiet} {r + quiet}h1v1h-1z"
        for r, linha in enumerate(melhor_grade)
        for c, escuro in enumerate(linha)
        if escuro
    ]
    caminho = "".join(comandos)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {total}" '
        f'shape-rendering="crispEdges" role="img" aria-label="QR Code Pix">'
        f'<rect width="100%" height="100%" fill="#ffffff"/>'
        f'<path fill="#000000" d="{caminho}"/>'
        f"</svg>"
    )
