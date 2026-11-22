"""Excepções da aplicação."""


class ErroDdt(Exception):
    """Erro base; a mensagem pode ser mostrada ao utilizador."""


class ErroProtocolo(ErroDdt):
    """Mensagem mal formada ou inesperada."""


class ErroArranque(ErroDdt):
    """Falha na comunicação com o servidor de arranque."""


class ErroNo(ErroDdt):
    """Operação inválida ou impossível no estado actual do nó."""
