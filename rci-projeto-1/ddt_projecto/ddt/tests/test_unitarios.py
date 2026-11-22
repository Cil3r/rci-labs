"""Testes unitários: aritmética do anel, protocolo, leitor de linhas e servidor de arranque."""

import socket
import unittest

import cliente_arranque as arranque
from anel import Vizinho, entre, responsavel
from erros import ErroArranque, ErroProtocolo
from ligacao import LeitorLinhas
from protocolo import analisar, formatar
from servidor_arranque import ServidorArranque


class TestAnel(unittest.TestCase):
    """Exemplo da figura 1 do enunciado (h = 4, 16 identificadores)."""

    NOS = [1, 3, 4, 5, 8, 10, 12, 15]

    def responsavel_por(self, k):
        encontrados = []
        for i, no in enumerate(self.NOS):
            pred = self.NOS[i - 1]
            if responsavel(k, pred, no, n=16):
                encontrados.append(no)
        return encontrados

    def test_cada_identificador_tem_um_unico_responsavel(self):
        for k in range(16):
            self.assertEqual(len(self.responsavel_por(k)), 1, k)

    def test_exemplos_do_enunciado(self):
        for k in (13, 14, 15):
            self.assertEqual(self.responsavel_por(k), [15])
        for k in (0, 1):
            self.assertEqual(self.responsavel_por(k), [1])

    def test_no_sozinho_e_responsavel_por_tudo(self):
        self.assertTrue(all(responsavel(k, 7, 7) for k in range(64)))

    def test_entre_com_volta_ao_anel(self):
        self.assertTrue(entre(5, 60, 10))
        self.assertTrue(entre(62, 60, 10))
        self.assertFalse(entre(10, 60, 10))
        self.assertFalse(entre(60, 60, 10))
        self.assertFalse(entre(30, 60, 10))


class TestProtocolo(unittest.TestCase):
    def test_formatar(self):
        self.assertEqual(formatar("QRY", 3, 14), "QRY 3 14\n")
        self.assertEqual(formatar("BOOT"), "BOOT\n")

    def test_analisar_ida_e_volta(self):
        mensagens = [
            ("QRY", (3, 14)), ("RSP", (3, 14, 15, "10.0.0.1", 58001)), ("ID", (7,)),
            ("SUCC", (15, "10.0.0.1", 58001)), ("NEW", (7, "127.0.0.1", 1234)),
            ("CON", (7, "127.0.0.1", 1234)), ("BOOT", ()), ("BQRY", (2,)), ("EMPTY", ()),
            ("REG", (2, 9, "127.0.0.1", 5000)), ("OK", ()), ("BRSP", (2, 9, "127.0.0.1", 5000)),
            ("UNR", (2,)),
        ]
        for tipo, args in mensagens:
            self.assertEqual(analisar(formatar(tipo, *args)), (tipo, args))

    def test_mensagens_invalidas(self):
        invalidas = [
            "", "LIXO", "QRY 1", "QRY 1 2 3", "QRY a b", "QRY 64 1", "QRY -1 1",
            "NEW 1 999.1.1.1 80", "NEW 1 127.0.0.1 0", "NEW 1 127.0.0.1 70000",
            "BOOT extra", "BQRY -3",
        ]
        for linha in invalidas:
            with self.assertRaises(ErroProtocolo, msg=linha):
                analisar(linha)


class TestLeitorLinhas(unittest.TestCase):
    def test_junta_pedacos(self):
        leitor = LeitorLinhas()
        self.assertEqual(leitor.alimentar(b"QRY 1"), [])
        self.assertEqual(leitor.alimentar(b" 2\nBOOT\nNE"), ["QRY 1 2", "BOOT"])
        self.assertEqual(leitor.alimentar(b"W\n"), ["NEW"])

    def test_ignora_linhas_vazias(self):
        self.assertEqual(LeitorLinhas().alimentar(b"\n\r\nOK\r\n"), ["OK"])

    def test_linha_demasiado_longa(self):
        with self.assertRaises(ErroProtocolo):
            LeitorLinhas().alimentar(b"x" * 5000)


class TestServidorArranque(unittest.TestCase):
    def setUp(self):
        self.servidor = ServidorArranque(porta=0, ip="127.0.0.1", saida=lambda t: None)

    def tearDown(self):
        self.servidor.sock.close()

    def test_anel_vazio(self):
        self.assertEqual(self.servidor.tratar("BQRY 1"), "EMPTY\n")

    def test_registar_consultar_e_anular(self):
        self.assertEqual(self.servidor.tratar("REG 1 5 10.0.0.1 58001"), "OK\n")
        self.assertEqual(self.servidor.tratar("BQRY 1"), "BRSP 1 5 10.0.0.1 58001\n")
        self.assertEqual(self.servidor.tratar("REG 1 9 10.0.0.2 58002"), "OK\n")
        self.assertEqual(self.servidor.tratar("BQRY 1"), "BRSP 1 9 10.0.0.2 58002\n")
        self.assertEqual(self.servidor.tratar("BQRY 2"), "EMPTY\n")
        self.assertEqual(self.servidor.tratar("UNR 1"), "OK\n")
        self.assertEqual(self.servidor.tratar("BQRY 1"), "EMPTY\n")

    def test_pedidos_invalidos_sao_ignorados(self):
        for pedido in ("LIXO", "BQRY", "OK", "EMPTY", "BOOT"):
            self.assertIsNone(self.servidor.tratar(pedido))


class TestClienteArranque(unittest.TestCase):
    def test_cliente_contra_servidor_real(self):
        import threading
        servidor = ServidorArranque(porta=0, ip="127.0.0.1", saida=lambda t: None)
        endereco = ("127.0.0.1", servidor.porta)
        threading.Thread(target=servidor.executar, daemon=True).start()

        self.assertIsNone(arranque.consultar(endereco, 4))
        arranque.registar(endereco, 4, 12, "127.0.0.1", 6000)
        self.assertEqual(arranque.consultar(endereco, 4), Vizinho(12, "127.0.0.1", 6000))
        arranque.anular(endereco, 4)
        self.assertIsNone(arranque.consultar(endereco, 4))

    def test_servidor_inexistente(self):
        tmp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tmp.bind(("127.0.0.1", 0))
        endereco = tmp.getsockname()
        tmp.close()
        antigo = arranque.TEMPO_LIMITE
        arranque.TEMPO_LIMITE = 0.3
        try:
            with self.assertRaises(ErroArranque):
                arranque.consultar(endereco, 1)
        finally:
            arranque.TEMPO_LIMITE = antigo


if __name__ == "__main__":
    unittest.main()
