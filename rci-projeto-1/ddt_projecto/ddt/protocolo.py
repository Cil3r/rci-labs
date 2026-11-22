"""Formatação e análise das mensagens (TCP e UDP). Cada mensagem é uma linha."""

import ipaddress

from config import NUM_IDENTIFICADORES
from erros import ErroProtocolo


def _identificador(texto):
    valor = int(texto)
    if not 0 <= valor < NUM_IDENTIFICADORES:
        raise ValueError("identificador fora do intervalo")
    return valor


def _anel(texto):
    valor = int(texto)
    if valor < 0:
        raise ValueError("número de anel negativo")
    return valor


def _porta(texto):
    valor = int(texto)
    if not 0 < valor < 65536:
        raise ValueError("porta inválida")
    return valor


def _ip(texto):
    return str(ipaddress.ip_address(texto))


FORMATOS = {
    # anel (TCP)
    "QRY": (_identificador, _identificador),
    "RSP": (_identificador, _identificador, _identificador, _ip, _porta),
    "ID": (_identificador,),
    "SUCC": (_identificador, _ip, _porta),
    "NEW": (_identificador, _ip, _porta),
    "CON": (_identificador, _ip, _porta),
    "BOOT": (),
    # servidor de arranque (UDP)
    "BQRY": (_anel,),
    "EMPTY": (),
    "REG": (_anel, _identificador, _ip, _porta),
    "OK": (),
    "BRSP": (_anel, _identificador, _ip, _porta),
    "UNR": (_anel,),
}


def formatar(tipo, *argumentos):
    """Constrói a linha de uma mensagem, por exemplo 'QRY 3 14\\n'."""
    return " ".join([tipo, *map(str, argumentos)]) + "\n"


def analisar(linha):
    """Decompõe uma linha em (tipo, argumentos convertidos)."""
    partes = linha.split()
    if not partes or partes[0] not in FORMATOS:
        raise ErroProtocolo(f"mensagem desconhecida: {linha[:40]!r}")
    tipo, brutos = partes[0], partes[1:]
    conversores = FORMATOS[tipo]
    if len(brutos) != len(conversores):
        raise ErroProtocolo(f"{tipo}: número de argumentos inválido")
    try:
        return tipo, tuple(c(b) for c, b in zip(conversores, brutos))
    except ValueError as erro:
        raise ErroProtocolo(f"{tipo}: argumento inválido ({erro})") from None
