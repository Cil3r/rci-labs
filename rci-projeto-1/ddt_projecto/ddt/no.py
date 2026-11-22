"""Nó do anel: estado local e protocolos de pesquisa, adesão e saída."""

import socket

import cliente_arranque as arranque
from anel import Vizinho, entre, responsavel
from config import NUM_IDENTIFICADORES
from erros import ErroArranque, ErroDdt, ErroNo, ErroProtocolo
from ligacao import Ligacao
from protocolo import analisar


def imprimir(texto):
    print(texto, flush=True)


class No:
    """Um nó do anel.

    Sessões TCP: `succ_lig` é a sessão que este nó abriu para o sucessor (envia
    QRY/BOOT, recebe RSP/CON); `pred_lig` é a sessão aceite do predecessor
    (recebe QRY/BOOT, envia RSP/CON).
    """

    def __init__(self, porta, endereco_arranque, saida=imprimir):
        self.porta = porta
        self.endereco_arranque = endereco_arranque
        self.saida = saida
        self.ip = arranque.ip_local(endereco_arranque)
        self.servidor = self._criar_servidor(porta)
        self.pendentes = []  # sessões aceites que ainda não se identificaram
        self.succ_lig = self.pred_lig = None
        self._esquecer_anel()

    @property
    def eu(self):
        return Vizinho(self.id, self.ip, self.porta)

    def ligacoes(self):
        activas = [self.pred_lig, self.succ_lig]
        return self.pendentes + [lig for lig in activas if lig is not None]

    # ---------------------------------------------------------------- comandos

    def juntar(self, anel, id):
        """join x i: adesão com pesquisa do sucessor via nó de arranque."""
        self._validar_adesao(anel, id)
        vizinho = arranque.consultar(self.endereco_arranque, anel)
        if vizinho is None:
            arranque.registar(self.endereco_arranque, anel, id, self.ip, self.porta)
            self._definir_estado(anel, id, arranque=True)
            self.saida(f"Aderiu ao anel {anel} com o identificador {id}.")
            return
        if vizinho.id == id:
            raise ErroNo(f"o identificador {id} já está em uso no anel {anel}")
        sucessor = self._pedir_sucessor(vizinho, id)
        if sucessor.id == id:
            raise ErroNo(f"o identificador {id} já está em uso no anel {anel}")
        self._ligar_ao_sucessor(anel, id, sucessor)

    def juntar_com_sucessor(self, anel, id, sucessor):
        """join x i succ ip porta: adesão sem pesquisas nem servidor de arranque."""
        self._validar_adesao(anel, id)
        if sucessor.id == id:
            self._definir_estado(anel, id)
            self.saida(f"Aderiu ao anel {anel} com o identificador {id}.")
        else:
            self._ligar_ao_sucessor(anel, id, sucessor)

    def sair(self):
        """leave: protocolo de saída do nó."""
        self._exigir_no_anel()
        anel = self.anel
        if self.succ.id == self.id:
            self._tentar_arranque(arranque.anular, anel)
        else:
            if self.arranque:
                self._tentar_arranque(arranque.registar, anel, *self.succ)
                self._tentar_enviar(self.succ_lig, "BOOT")
            if self.succ_lig is not None:
                self.succ_lig.fechar()
            self._tentar_enviar(self.pred_lig, "CON", *self.succ)
        self._esquecer_anel()
        self.saida(f"Saiu do anel {anel}.")

    def mostrar(self):
        self._exigir_no_anel()
        pred = "-" if self.pred is None else self.pred.id
        self.saida(
            f"Anel: {self.anel}\n"
            f"Identificador: {self.id}\n"
            f"Sucessor: {self.succ.id}\n"
            f"Predecessor: {pred}\n"
            f"Arranque: {'sim' if self.arranque else 'não'}"
        )

    def pesquisar(self, k):
        """search k: o resultado é impresso quando a resposta chega."""
        self._exigir_no_anel()
        self._validar_identificador(k)
        self._pesquisar(k, lambda r: self.saida(
            f"Responsável por {k}: nó {r.id} em {r.ip}:{r.porta}"))

    def fechar(self):
        """exit: sai do anel (se pertencer a um) e liberta os recursos."""
        if self.anel is not None:
            try:
                self.sair()
            except (ErroDdt, OSError) as erro:
                self.saida(f"Erro ao sair do anel: {erro}")
                self._esquecer_anel()
        for lig in self.pendentes:
            lig.fechar()
        self.pendentes = []
        self.servidor.close()

    # ----------------------------------------------------- eventos de rede

    def aceitar(self):
        try:
            conexao, _ = self.servidor.accept()
        except OSError as erro:
            self.saida(f"Erro ao aceitar sessão: {erro}")
            return
        self.pendentes.append(Ligacao(conexao))

    def atender(self, lig):
        """Lê e processa as mensagens que chegaram a uma sessão."""
        try:
            linhas = lig.receber()
        except (OSError, ErroProtocolo) as erro:
            self._perder(lig, erro)
            return
        for linha in linhas:
            if not lig.aberta:
                break
            try:
                tipo, args = analisar(linha)
                self._despachar(lig, tipo, args)
            except ErroProtocolo as erro:
                self._perder(lig, erro)
                break
            except (ErroDdt, OSError) as erro:
                self.saida(f"Erro ao tratar {linha.split()[0]}: {erro}")

    def _despachar(self, lig, tipo, args):
        if self.anel is None:
            self._descartar(lig)
            return
        if lig in self.pendentes:
            tratadores = {"ID": self._tratar_id, "NEW": self._tratar_new}
        elif lig is self.pred_lig:
            tratadores = {"QRY": self._tratar_qry, "BOOT": self._tratar_boot}
        else:
            tratadores = {"RSP": self._tratar_rsp, "CON": self._tratar_con}
        tratador = tratadores.get(tipo)
        if tratador is None:
            raise ErroProtocolo(f"{tipo} inesperada nesta sessão")
        tratador(lig, *args)

    def _perder(self, lig, motivo):
        if lig is self.pred_lig:
            self.pred_lig = None
            self.saida(f"[aviso] sessão com o predecessor terminada: {motivo}")
        elif lig is self.succ_lig:
            self.succ_lig = None
            self.saida(f"[aviso] sessão com o sucessor terminada: {motivo}")
        self._descartar(lig)

    def _descartar(self, lig):
        if lig in self.pendentes:
            self.pendentes.remove(lig)
        lig.fechar()

    # ----------------------------------------- tratamento de mensagens

    def _tratar_id(self, lig, id):
        """Nó de arranque: pesquisa o sucessor de `id` e responde com SUCC."""
        def responder(resultado):
            self._tentar_enviar(lig, "SUCC", *resultado)
            self._descartar(lig)
        self._pesquisar(id, responder)

    def _tratar_qry(self, lig, j, k):
        if responsavel(k, self.pred.id, self.id):
            self.pred_lig.enviar("RSP", j, k, *self.eu)
        else:
            self._enviar_sucessor("QRY", j, k)

    def _tratar_rsp(self, lig, j, k, id, ip, porta):
        if j == self.id:
            for callback in self.pesquisas.pop(k, []):
                callback(Vizinho(id, ip, porta))
        else:
            self._enviar_predecessor("RSP", j, k, id, ip, porta)

    def _tratar_new(self, lig, id, ip, porta):
        """O remetente passa a ser o nosso predecessor."""
        novo = Vizinho(id, ip, porta)
        antigo, antigo_lig = self.pred, self.pred_lig
        self.pendentes.remove(lig)
        self.pred, self.pred_lig = novo, lig

        if antigo is not None and antigo.id == self.id:
            self._tratar_con(None, *novo)  # estávamos sozinhos: o sucessor também é o novo nó
        elif antigo_lig is not None:
            if entre(id, antigo.id, self.id):  # adesão: o antigo predecessor tem de se religar
                self._tentar_enviar(antigo_lig, "CON", *novo)
            antigo_lig.fechar()

    def _tratar_con(self, lig, id, ip, porta):
        """O nosso sucessor passou a ser o nó indicado."""
        if id == self.id:
            self._ficar_sozinho()
            return
        if self.succ_lig is not None:
            self.succ_lig.fechar()
        self.succ_lig = None
        self.succ = Vizinho(id, ip, porta)
        self.succ_lig = Ligacao.conectar(ip, porta)
        self.succ_lig.enviar("NEW", *self.eu)

    def _tratar_boot(self, lig):
        self.arranque = True

    # --------------------------------------------------------- auxiliares

    def _pesquisar(self, k, callback):
        if self.pred is None:
            raise ErroNo("o anel ainda está a ser reconstruído, tente de novo")
        if responsavel(k, self.pred.id, self.id):
            callback(self.eu)
            return
        nova = k not in self.pesquisas
        self.pesquisas.setdefault(k, []).append(callback)
        if nova:
            try:
                self._enviar_sucessor("QRY", self.id, k)
            except OSError:
                del self.pesquisas[k]
                raise

    def _pedir_sucessor(self, vizinho, id):
        """Pergunta ao nó de arranque quem será o sucessor de `id`."""
        try:
            lig = Ligacao.conectar(vizinho.ip, vizinho.porta)
        except OSError as erro:
            raise ErroNo(f"não foi possível contactar o nó de arranque: {erro}") from None
        try:
            lig.enviar("ID", id)
            tipo, args = lig.esperar_mensagem()
        except (OSError, ErroProtocolo) as erro:
            raise ErroNo(f"falha na pesquisa do sucessor: {erro}") from None
        finally:
            lig.fechar()
        if tipo != "SUCC":
            raise ErroNo(f"resposta inesperada do nó de arranque: {tipo}")
        return Vizinho(*args)

    def _ligar_ao_sucessor(self, anel, id, sucessor):
        try:
            lig = Ligacao.conectar(sucessor.ip, sucessor.porta)
        except OSError as erro:
            raise ErroNo(f"não foi possível ligar ao sucessor: {erro}") from None
        self._definir_estado(anel, id, sucessor, lig)
        try:
            lig.enviar("NEW", *self.eu)
        except OSError as erro:
            self._esquecer_anel()
            raise ErroNo(f"falha ao contactar o sucessor: {erro}") from None
        self.saida(f"Aderiu ao anel {anel} com o identificador {id}.")

    def _definir_estado(self, anel, id, succ=None, succ_lig=None, arranque=False):
        """Sem sucessor indicado, o nó forma um anel sozinho."""
        self.anel, self.id, self.arranque = anel, id, arranque
        self.succ_lig = succ_lig
        if succ is None:
            self.succ = self.pred = self.eu
        else:
            self.succ, self.pred = succ, None

    def _esquecer_anel(self):
        for lig in (self.succ_lig, self.pred_lig):
            if lig is not None:
                lig.fechar()
        self.anel = self.id = self.succ = self.pred = None
        self.succ_lig = self.pred_lig = None
        self.arranque = False
        self.pesquisas = {}  # identificador pesquisado -> callbacks à espera

    def _ficar_sozinho(self):
        """Único nó restante: é, por definição, o nó de arranque."""
        for lig in (self.succ_lig, self.pred_lig):
            if lig is not None:
                lig.fechar()
        self.succ_lig = self.pred_lig = None
        self.succ = self.pred = self.eu
        self.arranque = True

    def _enviar_sucessor(self, tipo, *args):
        if self.succ_lig is None:
            raise ConnectionError("sem sessão com o sucessor")
        self.succ_lig.enviar(tipo, *args)

    def _enviar_predecessor(self, tipo, *args):
        if self.pred_lig is None:
            raise ConnectionError("sem sessão com o predecessor")
        self.pred_lig.enviar(tipo, *args)

    def _tentar_enviar(self, lig, tipo, *args):
        """Envio sem consequências se a sessão já não existir."""
        if lig is None:
            return
        try:
            lig.enviar(tipo, *args)
        except OSError:
            pass

    def _tentar_arranque(self, operacao, *args):
        try:
            operacao(self.endereco_arranque, *args)
        except ErroArranque as erro:
            self.saida(f"[aviso] {erro}")

    def _exigir_no_anel(self):
        if self.anel is None:
            raise ErroNo("o nó não pertence a nenhum anel")

    def _validar_adesao(self, anel, id):
        if self.anel is not None:
            raise ErroNo(f"o nó já pertence ao anel {self.anel}")
        if anel < 0:
            raise ErroNo("o número do anel não pode ser negativo")
        self._validar_identificador(id)

    @staticmethod
    def _validar_identificador(id):
        if not 0 <= id < NUM_IDENTIFICADORES:
            raise ErroNo(f"o identificador tem de estar entre 0 e {NUM_IDENTIFICADORES - 1}")

    @staticmethod
    def _criar_servidor(porta):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", porta))
            sock.listen()
        except OSError:
            sock.close()
            raise
        return sock
