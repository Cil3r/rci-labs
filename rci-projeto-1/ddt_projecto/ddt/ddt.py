"""Aplicação ddt: base de dados distribuída em anel.

Uso: python3 ddt.py [-t ringport] [-i bootIP] [-p bootport]
"""

import argparse
import os
import select

from anel import Vizinho
from config import ANEL_PORTA, ARRANQUE_IP, ARRANQUE_PORTA, TAMANHO_BUFFER
from erros import ErroDdt
from ligacao import LeitorLinhas
from no import No

STDIN = 0

USO = (
    "Comandos:\n"
    "  join x i                      aderir ao anel x com o identificador i\n"
    "  join x i succ succIP succTCP  aderir indicando o sucessor\n"
    "  leave                         sair do anel\n"
    "  show                          mostrar o estado do nó\n"
    "  search k                      pesquisar o responsável pelo identificador k\n"
    "  exit                          fechar a aplicação"
)


def executar_comando(no, linha):
    """Executa um comando do utilizador. Devolve False quando é para terminar."""
    partes = linha.split()
    if not partes:
        return True
    comando, args = partes[0], partes[1:]
    try:
        if comando == "join" and len(args) == 2:
            no.juntar(int(args[0]), int(args[1]))
        elif comando == "join" and len(args) == 5:
            anel, id, succ, ip, porta = args
            no.juntar_com_sucessor(int(anel), int(id), Vizinho(int(succ), ip, int(porta)))
        elif comando == "leave" and not args:
            no.sair()
        elif comando == "show" and not args:
            no.mostrar()
        elif comando == "search" and len(args) == 1:
            no.pesquisar(int(args[0]))
        elif comando == "exit" and not args:
            return False
        else:
            no.saida(USO)
    except ValueError:
        no.saida("Argumentos inválidos.\n" + USO)
    except (ErroDdt, OSError) as erro:
        no.saida(f"Erro: {erro}")
    return True


def ler_teclado(no, leitor):
    """Processa o que o utilizador escreveu. Devolve False para terminar."""
    dados = os.read(STDIN, TAMANHO_BUFFER)
    if not dados:
        return False
    return all(executar_comando(no, linha) for linha in leitor.alimentar(dados))


def executar(no):
    leitor = LeitorLinhas()
    continuar = True
    while continuar:
        prontos, _, _ = select.select([STDIN, no.servidor] + no.ligacoes(), [], [])
        for pronto in prontos:
            if pronto == STDIN:
                continuar = ler_teclado(no, leitor)
            elif pronto is no.servidor:
                no.aceitar()
            elif pronto.aberta:
                no.atender(pronto)
            if not continuar:
                break


def principal():
    parser = argparse.ArgumentParser(description="Base de dados distribuída em anel")
    parser.add_argument("-t", type=int, default=ANEL_PORTA, metavar="ringport")
    parser.add_argument("-i", default=ARRANQUE_IP, metavar="bootIP")
    parser.add_argument("-p", type=int, default=ARRANQUE_PORTA, metavar="bootport")
    args = parser.parse_args()

    try:
        no = No(args.t, (args.i, args.p))
    except OSError as erro:
        print(f"Não foi possível abrir o servidor TCP no porto {args.t}: {erro}")
        return 1
    try:
        executar(no)
    except KeyboardInterrupt:
        pass
    finally:
        no.fechar()
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
