PYTHON ?= python3
ARRANQUE_PORTA ?= 58000
ANEL_PORTA ?= 58001
ARRANQUE_IP ?= 192.168.56.21

.PHONY: all test unitarios integracao servidor no limpar

all: test

test:
	$(PYTHON) -m unittest discover -s tests -t . -v

unitarios:
	$(PYTHON) -m unittest tests.test_unitarios -v

integracao:
	$(PYTHON) -m unittest tests.test_integracao -v

servidor:
	$(PYTHON) servidor_arranque.py -p $(ARRANQUE_PORTA)

no:
	$(PYTHON) ddt.py -t $(ANEL_PORTA) -i $(ARRANQUE_IP) -p $(ARRANQUE_PORTA)

limpar:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
