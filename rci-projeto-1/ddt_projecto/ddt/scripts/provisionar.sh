#!/bin/sh
# Prepara o ambiente de execução: Python 3, make e ferramentas de depuração.
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 make netcat-openbsd telnet
