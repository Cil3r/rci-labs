"""Cliente UDP do servidor de arranque."""

import socket

from anel import Vizinho
from config import TAMANHO_BUFFER, TEMPO_LIMITE
from erros import ErroArranque, ErroProtocolo
from protocolo import analisar, formatar


def _pedir(endereco, tipo, *argumentos):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(TEMPO_LIMITE)
            sock.sendto(formatar(tipo, *argumentos).encode(), endereco)
            dados, _ = sock.recvfrom(TAMANHO_BUFFER)
        return analisar(dados.decode("utf-8", "replace"))
    except socket.timeout:
        raise ErroArranque("o servidor de arranque não respondeu") from None
    except OSError as erro:
        raise ErroArranque(f"erro de rede com o servidor de arranque: {erro}") from None
    except ErroProtocolo as erro:
        raise ErroArranque(f"resposta inválida do servidor de arranque: {erro}") from None


def _esperar_ok(endereco, tipo, *argumentos):
    resposta, _ = _pedir(endereco, tipo, *argumentos)
    if resposta != "OK":
        raise ErroArranque(f"resposta inesperada ao {tipo}: {resposta}")


def consultar(endereco, anel):
    """Devolve o nó de arranque do anel (Vizinho) ou None se o anel estiver vazio."""
    tipo, argumentos = _pedir(endereco, "BQRY", anel)
    if tipo == "EMPTY":
        return None
    if tipo == "BRSP" and argumentos[0] == anel:
        return Vizinho(*argumentos[1:])
    raise ErroArranque(f"resposta inesperada ao BQRY: {tipo}")


def registar(endereco, anel, identificador, ip, porta):
    _esperar_ok(endereco, "REG", anel, identificador, ip, porta)


def anular(endereco, anel):
    _esperar_ok(endereco, "UNR", anel)


def ip_local(endereco):
    """Endereço IP local usado para alcançar o servidor de arranque."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(endereco)
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
