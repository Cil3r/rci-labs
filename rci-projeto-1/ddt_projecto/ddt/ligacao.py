"""Sessões TCP orientadas à linha."""

import socket

from config import TAMANHO_BUFFER, TAMANHO_MAXIMO_LINHA, TEMPO_LIMITE
from erros import ErroProtocolo
from protocolo import analisar, formatar


class LeitorLinhas:
    """Reconstrói linhas terminadas em '\\n' a partir de pedaços de bytes."""

    def __init__(self):
        self._resto = b""

    def alimentar(self, dados):
        *linhas, self._resto = (self._resto + dados).split(b"\n")
        if len(self._resto) > TAMANHO_MAXIMO_LINHA:
            raise ErroProtocolo("linha demasiado longa")
        textos = (linha.decode("utf-8", "replace").strip() for linha in linhas)
        return [texto for texto in textos if texto]


class Ligacao:
    """Sessão TCP com leitura por linhas e envio de mensagens do protocolo."""

    def __init__(self, sock):
        self.sock = sock
        self.aberta = True
        self._leitor = LeitorLinhas()

    @classmethod
    def conectar(cls, ip, porta):
        sock = socket.create_connection((ip, porta), timeout=TEMPO_LIMITE)
        sock.settimeout(None)
        return cls(sock)

    def fileno(self):
        return self.sock.fileno()

    def enviar(self, tipo, *argumentos):
        self.sock.sendall(formatar(tipo, *argumentos).encode())

    def receber(self):
        """Lê o que estiver disponível; devolve as linhas completas."""
        dados = self.sock.recv(TAMANHO_BUFFER)
        if not dados:
            raise ConnectionError("sessão fechada pelo par")
        return self._leitor.alimentar(dados)

    def esperar_mensagem(self, tempo=TEMPO_LIMITE):
        """Bloqueia até chegar uma mensagem completa e devolve (tipo, argumentos)."""
        self.sock.settimeout(tempo)
        try:
            linhas = []
            while not linhas:
                linhas = self.receber()
        finally:
            self.sock.settimeout(None)
        return analisar(linhas[0])

    def fechar(self):
        if self.aberta:
            self.aberta = False
            self.sock.close()
