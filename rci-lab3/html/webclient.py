# -*- coding: utf-8 -*-
"""
Lab3 - Servidor e Cliente Web

Cliente Web HTTP simples.
Uso: python webclient.py server_host server_port filename
Ex.: python webclient.py 192.168.56.21 6789 /index.html
"""

from socket import *  # importa o módulo socket
import sys # Para ler os argumentos e terminar o programa

# Verifica os argumentos da linha de comando
if len(sys.argv) != 4:
	print('Uso: python webclient.py server_host server_port filename')
	sys.exit(1)

serverHost = sys.argv[1]       # endereço IP ou nome do host do servidor
serverPort = int(sys.argv[2])  # porta onde o servidor está a escutar
filename = sys.argv[3]         # caminho do objecto pedido no servidor

# Garante que o caminho começa por '/'
if not filename.startswith('/'):
	filename = '/' + filename

# Cria um socket TCP do cliente
#(AF_INET é utilizado para o protocolo IPv4)
#(SOCK_STREAM é utilizado para o TCP)
clientSocket = socket(AF_INET, SOCK_STREAM)

# Estabelece a conexão TCP com o servidor (three-way handshake)
clientSocket.connect((serverHost, serverPort))

# Constrói o pedido HTTP GET
request = "GET " + filename + " HTTP/1.1\r\n" \
          "Host: " + serverHost + ":" + str(serverPort) + "\r\n" \
          "Connection: close\r\n\r\n"

# Envia o pedido HTTP ao servidor
clientSocket.send(request.encode())

# Recebe a resposta do servidor até este fechar a conexão
response = b''
while True:
	data = clientSocket.recv(1024)
	if not data:
		break
	response += data

# Apresenta a resposta do servidor (cabeçalhos + corpo)
print(response.decode())

# Fecha o socket do cliente
clientSocket.close()
sys.exit()# Encerra o programa
