"""Aritmética de identificadores em anel."""

from collections import namedtuple

from config import NUM_IDENTIFICADORES

Vizinho = namedtuple("Vizinho", "id ip porta")


def entre(x, a, b, n=NUM_IDENTIFICADORES):
    """Indica se x pertence ao intervalo aberto (a, b) do anel."""
    return 0 < (x - a) % n < (b - a) % n


def responsavel(k, pred, eu, n=NUM_IDENTIFICADORES):
    """Indica se o nó `eu`, cujo predecessor é `pred`, é responsável por k.

    O nó é responsável pelo intervalo (pred, eu]. Sozinho, é responsável por tudo.
    """
    if pred == eu:
        return True
    return 0 < (k - pred) % n <= (eu - pred) % n
