"""Servidor UDP de arranque: associa o número de cada anel ao seu nó de arranque.

Uso: python3 servidor_arranque.py [-p porta]
"""

import argparse
import socket

from config import ARRANQUE_PORTA, TAMANHO_BUFFER
from erros import ErroProtocolo
from protocolo import analisar, formatar


class ServidorArranque:
    def __init__(self, porta=ARRANQUE_PORTA, ip="0.0.0.0", saida=print):
        self.aneis = {}
        self.saida = saida
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((ip, porta))
        self.porta = self.sock.getsockname()[1]

    def tratar(self, datagrama):
        """Processa um pedido e devolve a resposta (ou None se for de ignorar)."""
        try:
            tipo, args = analisar(datagrama)
        except ErroProtocolo as erro:
            self.saida(f"pedido ignorado: {erro}")
            return None

        if tipo == "BQRY":
            arranque = self.aneis.get(args[0])
            if arranque is None:
                return formatar("EMPTY")
            return formatar("BRSP", args[0], *arranque)
        if tipo == "REG":
            self.aneis[args[0]] = args[1:]
            return formatar("OK")
        if tipo == "UNR":
            self.aneis.pop(args[0], None)
            return formatar("OK")

        self.saida(f"pedido ignorado: {tipo} não é um pedido")
        return None

    def executar(self):
        self.saida(f"Servidor de arranque à escuta no porto UDP {self.porta}")
        while True:
            try:
                dados, origem = self.sock.recvfrom(TAMANHO_BUFFER)
            except OSError as erro:
                self.saida(f"erro de recepção: {erro}")
                continue
            texto = dados.decode("utf-8", "replace")
            resposta = self.tratar(texto)
            self.saida(f"{origem[0]}:{origem[1]} {texto.strip()!r} -> {(resposta or '-').strip()!r}")
            if resposta is not None:
                try:
                    self.sock.sendto(resposta.encode(), origem)
                except OSError as erro:
                    self.saida(f"erro de envio: {erro}")


def principal():
    parser = argparse.ArgumentParser(description="Servidor de arranque UDP")
    parser.add_argument("-p", type=int, default=ARRANQUE_PORTA, metavar="porta")
    args = parser.parse_args()
    try:
        servidor = ServidorArranque(args.p, saida=lambda t: print(t, flush=True))
        servidor.executar()
    except OSError as erro:
        print(f"Não foi possível iniciar o servidor: {erro}")
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(principal())
