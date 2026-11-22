"""Testes de integração: processos reais (servidor de arranque + nós ddt) em loopback."""

import os
import queue
import socket
import subprocess
import sys
import threading
import time
import unittest

import cliente_arranque as arranque

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IP = "127.0.0.1"


def porta_livre(tipo):
    with socket.socket(socket.AF_INET, tipo) as sock:
        sock.bind((IP, 0))
        return sock.getsockname()[1]


class Processo:
    """Processo filho com leitura assíncrona do stdout."""

    def __init__(self, *argumentos):
        self.proc = subprocess.Popen(
            [sys.executable, "-u", *argumentos], cwd=RAIZ, text=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.linhas = queue.Queue()
        threading.Thread(target=self._ler, daemon=True).start()

    def _ler(self):
        for linha in self.proc.stdout:
            self.linhas.put(linha.rstrip("\n"))

    def enviar(self, comando):
        self.proc.stdin.write(comando + "\n")
        self.proc.stdin.flush()

    def esperar(self, texto, tempo=5.0):
        """Consome linhas até encontrar uma que contenha `texto`."""
        limite = time.time() + tempo
        vistas = []
        while time.time() < limite:
            try:
                linha = self.linhas.get(timeout=0.1)
            except queue.Empty:
                continue
            vistas.append(linha)
            if texto in linha:
                return linha
        raise AssertionError(f"não apareceu {texto!r}; vistas: {vistas}")

    def comando(self, comando, esperado):
        self.enviar(comando)
        return self.esperar(esperado)

    def terminar(self):
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait()
        self.proc.stdout.close()
        self.proc.stdin.close()


class No(Processo):
    def __init__(self, porta_arranque, porta_tcp):
        super().__init__("ddt.py", "-t", str(porta_tcp), "-i", IP, "-p", str(porta_arranque))
        self.porta = porta_tcp
        self.id = None

    def juntar(self, anel, id):
        self.comando(f"join {anel} {id}", "Aderiu")
        self.id = id

    def estado(self):
        """Executa 'show' e devolve os campos num dicionário."""
        self.enviar("show")
        campos = {}
        while "Arranque" not in campos:
            linha = self.esperar(":")
            chave, _, valor = linha.partition(": ")
            campos[chave] = valor
        return campos

    def estado_estavel(self, tentativas=30):
        """Espera que o predecessor esteja estabelecido (fim da reconstrução do anel)."""
        for _ in range(tentativas):
            estado = self.estado()
            if estado["Predecessor"] != "-":
                return estado
            time.sleep(0.1)
        raise AssertionError("o predecessor nunca foi estabelecido")

    def responsavel(self, k):
        linha = self.comando(f"search {k}", f"Responsável por {k}:")
        return int(linha.split("nó ")[1].split()[0])


class BaseIntegracao(unittest.TestCase):
    def setUp(self):
        self.porta_arranque = porta_livre(socket.SOCK_DGRAM)
        self.arranque = Processo("servidor_arranque.py", "-p", str(self.porta_arranque))
        self.arranque.esperar("à escuta")
        self.endereco = (IP, self.porta_arranque)
        self.nos = []

    def tearDown(self):
        for no in self.nos:
            no.terminar()
        self.arranque.terminar()

    def novo_no(self):
        no = No(self.porta_arranque, porta_livre(socket.SOCK_STREAM))
        self.nos.append(no)
        return no

    def construir_anel(self, anel, ids):
        """Junta nós pela ordem dada, esperando que o anel estabilize a cada passo."""
        nos = {}
        for id in ids:
            no = self.novo_no()
            no.juntar(anel, id)
            nos[id] = no
            for outro in nos.values():
                outro.estado_estavel()
        return nos

    def verificar_anel(self, nos, tempo=5.0):
        """Cada nó tem como sucessor o seguinte do anel e como predecessor o anterior.

        O anel converge em milissegundos após uma adesão ou saída, por isso
        a verificação repete-se até haver convergência ou o tempo acabar.
        """
        limite = time.time() + tempo
        while True:
            try:
                return self._comparar_anel(nos)
            except AssertionError:
                if time.time() > limite:
                    raise
                time.sleep(0.1)

    def _comparar_anel(self, nos):
        ids = sorted(nos)
        for posicao, id in enumerate(ids):
            estado = nos[id].estado()
            self.assertEqual(int(estado["Sucessor"]), ids[(posicao + 1) % len(ids)], f"nó {id}")
            self.assertEqual(estado["Predecessor"], str(ids[posicao - 1]), f"nó {id}")


class TestNoUnico(BaseIntegracao):
    def test_adesao_pesquisa_e_saida(self):
        no = self.novo_no()
        no.juntar(1, 10)
        estado = no.estado()
        self.assertEqual((estado["Sucessor"], estado["Predecessor"], estado["Arranque"]),
                         ("10", "10", "sim"))
        self.assertEqual(arranque.consultar(self.endereco, 1).id, 10)
        for k in (0, 10, 33, 63):
            self.assertEqual(no.responsavel(k), 10)
        no.comando("leave", "Saiu")
        self.assertIsNone(arranque.consultar(self.endereco, 1))

    def test_pode_aderir_de_novo_depois_de_sair(self):
        no = self.novo_no()
        no.juntar(1, 10)
        no.comando("leave", "Saiu")
        no.juntar(2, 20)
        self.assertEqual(no.estado()["Anel"], "2")


class TestAnelComVariosNos(BaseIntegracao):
    def test_construcao_e_pesquisas(self):
        nos = self.construir_anel(1, [30, 10, 40, 20])
        self.verificar_anel(nos)
        esperado = {5: 10, 10: 10, 11: 20, 20: 20, 25: 30, 35: 40, 40: 40, 41: 10, 63: 10, 0: 10}
        for origem in nos.values():
            for k, id in esperado.items():
                self.assertEqual(origem.responsavel(k), id, f"nó {origem.id} a pesquisar {k}")

    def test_so_um_no_e_arranque(self):
        nos = self.construir_anel(1, [30, 10, 40])
        self.assertEqual(nos[30].estado()["Arranque"], "sim")
        self.assertEqual(nos[10].estado()["Arranque"], "não")

    def test_saida_de_nos_intermedios(self):
        nos = self.construir_anel(1, [30, 10, 40, 20])
        nos.pop(20).comando("leave", "Saiu")
        self.verificar_anel(nos)
        self.assertEqual(nos[10].responsavel(15), 30)

        nos.pop(40).comando("leave", "Saiu")
        self.verificar_anel(nos)
        self.assertEqual(nos[10].responsavel(35), 10)

    def test_saida_do_no_de_arranque_transfere_o_arranque(self):
        nos = self.construir_anel(1, [30, 10, 40])
        nos.pop(30).comando("leave", "Saiu")
        self.verificar_anel(nos)
        self.assertEqual(nos[40].estado()["Arranque"], "sim")
        self.assertEqual(arranque.consultar(self.endereco, 1).id, 40)

        novo = self.novo_no()  # a adesão posterior usa o novo nó de arranque
        novo.juntar(1, 50)
        nos[50] = novo
        self.verificar_anel(nos)

    def test_saida_do_no_de_arranque_com_dois_nos(self):
        nos = self.construir_anel(1, [30, 10])
        nos.pop(30).comando("leave", "Saiu")
        resto = nos[10].estado()
        self.assertEqual((resto["Sucessor"], resto["Predecessor"], resto["Arranque"]),
                         ("10", "10", "sim"))
        self.assertEqual(nos[10].responsavel(30), 10)

    def test_todos_saem_e_o_anel_e_anulado(self):
        nos = self.construir_anel(1, [5, 25, 45])
        for id in (25, 5, 45):
            nos.pop(id).comando("leave", "Saiu")
            for restante in nos.values():
                restante.estado_estavel()
        self.assertIsNone(arranque.consultar(self.endereco, 1))

    def test_aneis_independentes(self):
        a = self.construir_anel(1, [10, 20])
        b = self.construir_anel(2, [10, 20])
        self.verificar_anel(a)
        self.verificar_anel(b)

    def test_anel_completo_de_64_identificadores_ocupados(self):
        nos = self.construir_anel(1, [0, 63, 32, 31])
        self.verificar_anel(nos)
        self.assertEqual(nos[0].responsavel(1), 31)
        self.assertEqual(nos[0].responsavel(32), 32)
        self.assertEqual(nos[0].responsavel(33), 63)
        self.assertEqual(nos[0].responsavel(0), 0)

    def test_exit_sai_do_anel(self):
        nos = self.construir_anel(1, [10, 20, 30])
        saiu = nos.pop(20)
        saiu.enviar("exit")
        self.assertEqual(saiu.proc.wait(timeout=5), 0)
        self.verificar_anel(nos)


class TestAdesaoDirecta(BaseIntegracao):
    def test_join_com_sucessor_indicado(self):
        a = self.novo_no()
        a.juntar(7, 10)
        b = self.novo_no()
        b.comando(f"join 7 30 10 {IP} {a.porta}", "Aderiu")
        b.id = 30
        self.verificar_anel({10: a, 30: b})

    def test_join_directo_a_partir_de_um_no_sozinho(self):
        a = self.novo_no()
        a.comando("join 7 10 10 127.0.0.1 1", "Aderiu")
        self.assertEqual(a.estado()["Sucessor"], "10")


class TestErros(BaseIntegracao):
    def test_identificador_em_uso(self):
        nos = self.construir_anel(1, [10, 20, 30])
        for id_repetido in (10, 20, 30):
            novo = self.novo_no()
            novo.comando(f"join 1 {id_repetido}", "em uso")
            self.assertIn("não pertence", novo.comando("show", "Erro"))
        self.verificar_anel(nos)

    def test_comandos_invalidos(self):
        no = self.novo_no()
        no.comando("show", "não pertence a nenhum anel")
        no.comando("leave", "não pertence a nenhum anel")
        no.comando("search 5", "não pertence a nenhum anel")
        no.comando("join abc 3", "Argumentos inválidos")
        no.comando("join 1", "Comandos:")
        no.comando("banana", "Comandos:")
        no.comando("join 1 64", "entre 0 e 63")
        no.comando("join 1 -2", "entre 0 e 63")
        no.juntar(1, 5)
        no.comando("join 1 6", "já pertence")
        no.comando("search 64", "entre 0 e 63")
        no.comando("show", "Anel: 1")

    def test_servidor_de_arranque_inacessivel(self):
        no = No(porta_livre(socket.SOCK_DGRAM), porta_livre(socket.SOCK_STREAM))
        self.nos.append(no)
        no.enviar("join 1 5")
        no.esperar("não respondeu", tempo=8)
        no.comando("show", "não pertence")

    def test_porto_tcp_ocupado(self):
        ocupado = socket.socket()
        ocupado.bind((IP, 0))
        ocupado.listen()
        try:
            proc = Processo("ddt.py", "-t", str(ocupado.getsockname()[1]))
            self.nos.append(proc)
            proc.esperar("Não foi possível abrir")
            self.assertEqual(proc.proc.wait(timeout=5), 1)
        finally:
            ocupado.close()


class TestRobustez(BaseIntegracao):
    def enviar_cru(self, no, dados):
        with socket.create_connection((IP, no.porta), timeout=2) as sock:
            sock.sendall(dados)
            sock.settimeout(2)
            try:
                return sock.recv(100)  # b"" quando o nó fecha a sessão
            except ConnectionResetError:
                return b""  # fecho com dados por ler
            except socket.timeout:
                return None

    def test_mensagens_invalidas_de_um_par(self):
        nos = self.construir_anel(1, [10, 20])
        lixo = [b"LIXO\n", b"QRY 1\n", b"NEW 99 1.1.1.1 5\n", b"\xff\xfe\n",
                b"QRY 1 2\n", b"RSP 1 2 3 127.0.0.1 5\n", b"x" * 5000]
        for dados in lixo:
            self.assertEqual(self.enviar_cru(nos[10], dados), b"", dados[:20])
        self.verificar_anel(nos)
        self.assertEqual(nos[10].responsavel(15), 20)

    def test_sessao_fechada_sem_dizer_nada(self):
        nos = self.construir_anel(1, [10, 20])
        for _ in range(3):
            socket.create_connection((IP, nos[10].porta)).close()
        self.verificar_anel(nos)

    def test_queda_de_um_no_nao_derruba_os_restantes(self):
        nos = self.construir_anel(1, [10, 20, 30])
        nos[20].proc.kill()
        aviso = nos[10].esperar("[aviso]")
        self.assertIn("sucessor", aviso)
        nos[30].esperar("[aviso]")
        self.assertEqual(nos[10].estado()["Identificador"], "10")
        # a pesquisa que precisaria do nó caído falha com erro em vez de bloquear ou rebentar
        nos[10].enviar("search 15")
        nos[10].esperar("Erro")
        nos[10].comando("leave", "Saiu")

    def test_resposta_perdida_nao_bloqueia_adesao(self):
        """Um 'nó de arranque' que não responde ao ID provoca erro, não bloqueio."""
        with socket.socket() as falso:
            falso.bind((IP, 0))
            falso.listen()
            arranque.registar(self.endereco, 3, 7, IP, falso.getsockname()[1])
            no = self.novo_no()
            no.enviar("join 3 8")
            linha = no.esperar("Erro", tempo=8)
            self.assertIn("pesquisa do sucessor", linha)


if __name__ == "__main__":
    unittest.main()
