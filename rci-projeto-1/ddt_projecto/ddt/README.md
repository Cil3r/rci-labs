# ddt — Base de Dados Distribuída em Anel

Projecto de Laboratório #1 de Redes de Computadores I (RC-I 2026-2027, ISPTEC).
Implementação em **Python 3** (apenas biblioteca padrão) de uma aplicação de camada de
aplicação sobre **sockets TCP e UDP**.

## 1. O que o projecto faz

Um conjunto de nós forma um **anel**. Cada nó tem um identificador entre 0 e 63
(`h = 6`, logo 64 identificadores, entendidos em círculo: ao 63 segue-se o 0).

- O nó `i` é responsável pelos identificadores em `(pred_i, i]`, isto é, desde o
  predecessor (exclusivo) até si próprio (inclusivo). Um nó sozinho é responsável por tudo.
- Cada nó mantém **duas sessões TCP**: uma com o sucessor e outra com o predecessor.
- Uma **pesquisa** de um identificador `k` viaja pelo anel (de sucessor em sucessor) até
  ao nó responsável, e a resposta volta pelo caminho inverso (de predecessor em predecessor).
- Para aderir a um anel, um nó consulta o **servidor de arranque UDP**, que sabe, para
  cada número de anel, qual é o nó de arranque (um nó já presente, que serve de porta de entrada).

```
        nó 10 ──QRY──▶ nó 20 ──QRY──▶ nó 30        (sessão TCP "para o sucessor")
        nó 10 ◀──RSP── nó 20 ◀──RSP── nó 30        (resposta pelo sentido inverso)
```

## 2. Estrutura

```
ddt/
├── ddt.py                 Aplicação: argumentos, interface de utilizador, ciclo select()
├── no.py                  O nó: estado e protocolos (pesquisa, adesão, saída)
├── servidor_arranque.py   Servidor UDP de arranque
├── cliente_arranque.py    Cliente UDP (BQRY / REG / UNR) usado pelo nó
├── protocolo.py           Formatação e análise das mensagens
├── ligacao.py             Sessões TCP orientadas à linha
├── anel.py                Aritmética do anel (responsabilidade e intervalos)
├── erros.py               Excepções da aplicação
├── config.py              Constantes (h, portas, tempos-limite)
├── tests/                 Testes unitários e de integração
├── Makefile               Atalhos: test, servidor, no
├── Vagrantfile            Ambiente virtual (4 máquinas)
└── scripts/provisionar.sh Instala o necessário nas máquinas virtuais
```

## 3. Como usar

### Servidor de arranque
```
python3 servidor_arranque.py [-p porta]        # por omissão 58000
```

### Nó
```
python3 ddt.py [-t ringport] [-i bootIP] [-p bootport]
```

| Opção | Significado | Omissão |
|---|---|---|
| `-t` | porta do servidor TCP do nó | 58001 |
| `-i` | IP do servidor de arranque | 192.168.56.21 |
| `-p` | porta UDP do servidor de arranque | 58000 |

Como o enunciado não fixa o valor por omissão de `ringport`, usa-se 58001. Em máquinas
diferentes serve sempre; numa mesma máquina cada nó precisa de um `-t` distinto.

### Comandos da interface

| Comando | Efeito |
|---|---|
| `join x i` | adere ao anel `x` com o identificador `i` (consulta o servidor de arranque) |
| `join x i succ succIP succTCP` | adere indicando o sucessor; não faz pesquisas nem contacta o servidor de arranque |
| `leave` | sai do anel |
| `show` | mostra anel, identificador, sucessor, predecessor (e se é nó de arranque) |
| `search k` | pesquisa o nó responsável por `k` |
| `exit` | fecha a aplicação (se o nó estiver num anel, sai primeiro dele) |

### Exemplo (um só computador, loopback)

Terminal 1: `python3 servidor_arranque.py`
Terminais 2, 3, 4: `python3 ddt.py -t 58010 -i 127.0.0.1`, `-t 58020`, `-t 58030`

Sessão real, obtida com três nós (10, 20 e 30) — o nó 20 acaba por sair:

```
[nó 10] > join 1 10        Aderiu ao anel 1 com o identificador 10.
[nó 20] > join 1 20        Aderiu ao anel 1 com o identificador 20.
[nó 30] > join 1 30        Aderiu ao anel 1 com o identificador 30.
[nó 10] > show             Anel: 1 / Identificador: 10 / Sucessor: 20 / Predecessor: 30 / Arranque: sim
[nó 10] > search 25        Responsável por 25: nó 30 em 127.0.0.1:58930
[nó 30] > search 5         Responsável por 5: nó 10 em 127.0.0.1:58910
[nó 20] > leave            Saiu do anel 1.
[nó 10] > show             Anel: 1 / Identificador: 10 / Sucessor: 30 / Predecessor: 30 / Arranque: sim
[nó 10] > search 15        Responsável por 15: nó 30 em 127.0.0.1:58930
```

### Execução no Vagrant (ambiente de avaliação)

O `Vagrantfile` cria 4 máquinas Ubuntu 22.04 (Python 3.10) na rede host-only
192.168.56.0/24, com a pasta do projecto partilhada em `/home/vagrant/ddt`:

| Máquina | IP | Papel |
|---|---|---|
| `arranque` | 192.168.56.21 | servidor de arranque UDP |
| `no1` | 192.168.56.22 | nó ddt |
| `no2` | 192.168.56.23 | nó ddt |
| `no3` | 192.168.56.24 | nó ddt |

```
vagrant up                                  # cria e provisiona as 4 máquinas
vagrant ssh arranque -c "cd ddt && make servidor"
vagrant ssh no1      # depois, dentro da máquina:  cd ddt && make no
vagrant ssh no2      #                            cd ddt && make no
vagrant ssh no3      #                            cd ddt && make no
```

Como o IP por omissão do servidor de arranque já é 192.168.56.21, nos nós basta
`python3 ddt.py` (ou `make no`). O servidor de arranque tem de ser arrancado à mão,
porque o provisionamento não o lança.

Se o plugin `vagrant-vbguest` estiver instalado, o `Vagrantfile` desactiva a sua
actualização automática das Guest Additions. Essa actualização falha com versões
recentes do Vagrant e faz o `vagrant up` destruir a máquina. As Guest Additions da box
chegam para a pasta partilhada.

Sessão real nas máquinas virtuais (nó 10 em `no1`, nó 30 em `no2`, nó 50 em `no3`):

```
[no1] > join 1 10     Aderiu ao anel 1 com o identificador 10.
[no2] > join 1 30     Aderiu ao anel 1 com o identificador 30.
[no3] > join 1 50     Aderiu ao anel 1 com o identificador 50.
[no1] > show          Anel: 1 / Identificador: 10 / Sucessor: 30 / Predecessor: 50 / Arranque: sim
[no1] > search 40     Responsável por 40: nó 50 em 192.168.56.24:58001
[no1] > search 63     Responsável por 63: nó 10 em 192.168.56.22:58001
[no2] > search 5      Responsável por 5: nó 10 em 192.168.56.22:58001
[no3] > search 20     Responsável por 20: nó 30 em 192.168.56.23:58001
[no2] > leave         Saiu do anel 1.
[no1] > search 20     Responsável por 20: nó 50 em 192.168.56.24:58001
[no1] > leave         Saiu do anel 1.            (servidor: REG 1 50 192.168.56.24 58001)
[no3] > show          Sucessor: 50 / Predecessor: 50 / Arranque: sim
[no2] > join 1 50     Erro: o identificador 50 já está em uso no anel 1
[no2] > join 1 30     Aderiu ao anel 1 com o identificador 30.
[no2] > exit          Saiu do anel 1.
[no3] > exit          Saiu do anel 1.            (servidor: UNR 1 -> OK)
```

Quando um vizinho sai com `leave`, o nó mostra `[aviso] sessão com o predecessor
terminada`. É o fecho normal da sessão TCP do nó que saiu, não um erro.

### Testes
```
make test            # tudo (≈13 s em loopback, ≈24 s numa VM do Vagrant)
make unitarios       # só os unitários
make integracao      # só os de integração
```

## 4. Protocolos

Todas as mensagens são **uma linha de texto** terminada em `\n`, com campos separados por
espaços (os sinais `<` `>` do enunciado são apenas notação). Em TCP as mensagens são
recebidas por fluxo, por isso `ligacao.LeitorLinhas` reconstrói as linhas.

### 4.1 Pesquisa (TCP)

| Situação | Acção |
|---|---|
| Utilizador de `i` pede `search k` | se `i` é responsável, responde logo; senão envia `QRY i k` ao sucessor |
| `i` recebe `QRY j k` | se é responsável, envia `RSP j k i i.IP i.TCP` ao predecessor; senão reenvia `QRY j k` ao sucessor |
| `i` recebe `RSP j k l l.IP l.TCP` | se `j = i`, entrega o resultado ao utilizador; senão reenvia ao predecessor |

### 4.2 Adesão (`join x i`)

1. `BQRY x` ao servidor de arranque (UDP).
   - `EMPTY`: o anel não existe. O nó envia `REG x i IP porta` (resposta `OK`) e passa a ser
     o único nó e nó de arranque.
   - `BRSP x j IP porta`: `j` é o nó de arranque. Se `j = i`, o identificador está em uso.
2. O nó liga-se por TCP a `j` e envia `ID i`. `j` faz a pesquisa `QRY j i` pelo anel e
   responde `SUCC l l.IP l.TCP`. O nó fecha a sessão. Se `l = i`, o identificador está em uso.
3. O nó liga-se a `l` e envia `NEW i IP porta`: `l` passa a ser sucessor de `i`.
   `l` envia `CON i IP porta` ao antigo predecessor `m` e fecha a sessão com ele.
   `m` liga-se a `i` e envia `NEW m IP porta`: `i` passa a ter `m` como predecessor.

```
antes:   m ──▶ l
depois:  m ──▶ i ──▶ l
```

### 4.3 Saída (`leave`)

- Nó **único**: envia `UNR x` ao servidor de arranque (resposta `OK`).
- Caso contrário, se for o **nó de arranque**: envia `REG x succ IP porta` ao servidor e
  `BOOT` ao sucessor, que passa a ser o nó de arranque.
- Fecha a sessão com o sucessor e envia `CON succ succIP succTCP` ao predecessor, que se
  liga ao sucessor com `NEW pred IP porta`, fechando o anel sem o nó que saiu.

### 4.4 Servidor de arranque (UDP)

| Pedido | Resposta |
|---|---|
| `BQRY x` | `EMPTY` ou `BRSP x j IP porta` |
| `REG x j IP porta` | `OK` (substitui o nó de arranque do anel `x`) |
| `UNR x` | `OK` (esquece o anel `x`) |

Pedidos inválidos são ignorados (e registados). O cliente espera 5 s por resposta.

## 5. Explicação do código

### `config.py`
Constantes: `H = 6`, `NUM_IDENTIFICADORES = 64`, valores por omissão das portas e do
servidor de arranque, tempo-limite (5 s) e tamanhos de buffer.

### `erros.py`
Hierarquia `ErroDdt` → `ErroProtocolo` (mensagem má), `ErroArranque` (servidor UDP) e
`ErroNo` (operação inválida). A interface apanha `ErroDdt`/`OSError` e mostra
`Erro: ...` sem terminar a aplicação.

### `anel.py`
- `responsavel(k, pred, eu)`: `k ∈ (pred, eu]` em aritmética módulo 64. Sozinho, devolve sempre verdadeiro.
- `entre(x, a, b)`: `x` pertence ao intervalo aberto `(a, b)` do anel. É usado para
  distinguir uma **adesão** (novo nó entre o antigo predecessor e mim) de um simples
  **restabelecimento** do anel após uma saída (ver 6.2).
- `Vizinho(id, ip, porta)`: a "localização" de um nó.

### `protocolo.py`
`FORMATOS` descreve, para cada tipo de mensagem, os conversores dos seus argumentos
(identificador 0–63, porta 1–65535, IP válido, número de anel ≥ 0).
`formatar(tipo, *args)` constrói a linha e `analisar(linha)` devolve `(tipo, args)` ou
levanta `ErroProtocolo`. Assim, **nenhuma mensagem mal formada chega à lógica do nó**.

### `ligacao.py`
- `LeitorLinhas`: acumula bytes e devolve linhas completas (limite de 1024 bytes por linha).
- `Ligacao`: envolve um socket TCP. `enviar` (`sendall`), `receber` (`recv`, levanta
  `ConnectionError` quando o par fecha), `esperar_mensagem` (leitura bloqueante com
  tempo-limite, usada na adesão) e `fechar`. Tem `fileno()`, por isso entra directamente no `select`.

### `cliente_arranque.py`
Funções `consultar`, `registar` e `anular` (uma por pedido UDP), todas sobre `_pedir`, que
envia o datagrama, espera a resposta com tempo-limite e converte falhas de rede em
`ErroArranque`. `ip_local` descobre o IP local usado para chegar ao servidor de arranque
(é o IP anunciado aos outros nós).

### `servidor_arranque.py`
`ServidorArranque.tratar(datagrama)` é uma função pura de pedido → resposta sobre o
dicionário `aneis` (fácil de testar). `executar` é o ciclo `recvfrom`/`sendto`.

### `no.py` — o núcleo
`No` guarda o estado: `anel`, `id`, `succ`, `pred` (os `Vizinho`), as sessões
`succ_lig` e `pred_lig`, as sessões `pendentes` (aceites mas ainda sem papel), as
`pesquisas` em curso (`k → callbacks`) e a flag `arranque`.

- **Comandos** (`juntar`, `juntar_com_sucessor`, `sair`, `mostrar`, `pesquisar`, `fechar`).
- **Eventos de rede**: `aceitar` guarda a nova sessão como pendente; `atender` lê as linhas,
  analisa-as e entrega-as a `_despachar`.
- **Despacho por papel da sessão**: uma sessão pendente só admite `ID` e `NEW`; a do
  predecessor admite `QRY` e `BOOT`; a do sucessor admite `RSP` e `CON`. Qualquer outra
  mensagem é um erro de protocolo.
- **Tratadores** `_tratar_id`, `_tratar_qry`, `_tratar_rsp`, `_tratar_new`, `_tratar_con`,
  `_tratar_boot`: um por mensagem, a seguir de perto a secção 2 do enunciado.
- **Pesquisa**: `_pesquisar` responde localmente se for responsável, senão regista o
  `callback` e envia `QRY`. Pesquisas simultâneas do mesmo `k` partilham um único `QRY`.
  O mesmo mecanismo serve o comando `search` (imprime) e o `ID` (responde `SUCC`).

### `ddt.py`
`executar_comando` interpreta uma linha do utilizador. O ciclo `executar` faz
`select.select` sobre **o teclado (fd 0), o servidor TCP e todas as sessões**, tudo num
único processo e numa única thread. O teclado é lido com `os.read` e o mesmo
`LeitorLinhas`, para que vários comandos colados de uma vez não fiquem retidos em
buffers do Python (o que bloquearia o `select`).

## 6. Decisões de desenho

1. **Uma só thread com `select`**, como o enunciado sugere. Não há concorrência, logo
   não há trincos nem corridas internas; as operações bloqueantes (adesão) têm tempo-limite.
2. **O estado só se altera quando a adesão tem sucesso.** Se o identificador estiver em
   uso ou houver erro de rede, o nó continua fora do anel e pode tentar outro `i`.
3. **Nó sozinho a receber `NEW`** (segundo nó a aderir): não tem sessão consigo próprio,
   por isso trata o seu próprio `CON` localmente, ligando-se ao recém-chegado como sucessor.
4. **Quando mandar `CON` ao antigo predecessor.** `NEW` tem dois significados: *adesão*
   (o novo nó fica entre o predecessor e eu) e *restabelecimento* após saída (o
   predecessor do que saiu liga-se a mim). Só no primeiro caso o antigo predecessor deve
   receber `CON`. Distingue-se com `entre(novo, antigo_pred, eu)`, o que também elimina
   a dependência da ordem de chegada entre o fecho da sessão do nó que saiu e o `NEW` do restabelecimento.
5. **Último nó restante** (`CON` que aponta para si próprio): fecha as sessões, fica
   sozinho e assume-se nó de arranque. Isto evita perder o `BOOT` se este chegar depois do `CON`
   (vêm por sessões diferentes, sem garantia de ordem).
6. **`join x i succ ...` não contacta o servidor de arranque**, como o enunciado indica
   ("sem efectuar pesquisas"). Se `succ = i`, cria um anel de um só nó sem o registar.
7. **`exit` sai primeiro do anel**, para não deixar o anel partido.
8. **Falhas tratadas sem terminar a aplicação** (secção 3.1 do enunciado):
   - mensagem inválida de um par → a sessão é fechada e o nó continua;
   - sessão fechada de forma imprevista → aviso `[aviso] ...` e o nó continua;
   - erro numa chamada ao sistema → `Erro: ...` ao utilizador;
   - servidor de arranque ou nó de arranque inacessíveis → erro com tempo-limite (5 s).

## 7. Testes

`tests/test_unitarios.py` (15 testes): aritmética do anel (com o exemplo da Figura 1,
`h = 4`), formatação/análise de todas as mensagens, mensagens inválidas, leitor de
linhas e servidor/cliente de arranque.

`tests/test_integracao.py` (21 testes): lança **processos reais** (`servidor_arranque.py`
e vários `ddt.py`) em loopback e comanda-os pelo `stdin`:

- nó único: adesão, `show`, `search`, `leave`, anulação do anel e nova adesão;
- anéis de 2 a 4 nós com adesões por ordem arbitrária; verificação de sucessor e predecessor
  de cada nó e de `search` a partir de **todos** os nós, incluindo a volta ao anel (41→10, 63→10, 0→10);
- saída de nós intermédios, do nó de arranque (com 2 e com 3 nós) e de todos os nós;
- `exit` a sair do anel; dois anéis independentes; `join` com sucessor indicado;
- erros: identificador em uso, comandos inválidos, servidor de arranque inacessível,
  porto TCP ocupado, nó de arranque que não responde;
- robustez: lixo e mensagens inesperadas enviados por TCP, sessões abertas e fechadas sem dados,
  e um nó que morre (`kill`) sem os restantes caírem.

Foi ainda corrido (fora da bateria) um teste aleatório com 10 nós, em que se alternaram
saídas e adesões e se confirmou cada resposta de `search` contra o resultado esperado.
A bateria completa foi repetida 8 vezes seguidas sem falhas.

**No ambiente Vagrant** (Ubuntu 22.04, Python 3.10.12):
- `make test` na máquina `no1`: **36 testes, todos OK** (≈24 s);
- teste entre máquinas, com o servidor de arranque em `arranque` e um nó em cada uma de
  `no1`, `no2` e `no3`, todos com as opções por omissão. Cobriu a adesão via servidor
  de arranque, `show`, `search` a partir de cada nó (incluindo a volta ao anel), a saída
  de um nó intermédio, a saída do nó de arranque (com `REG` do sucessor e `BOOT`), o
  identificador em uso, a nova adesão e `exit` com anulação do anel (`UNR`).
  O resultado está no exemplo da secção 3.

Os testes de integração precisam de Linux (ou outro Unix), porque o `select()` sobre o
teclado não funciona no Windows. No Windows só correm os testes unitários.

## 8. Limitações

- **Falha de um nó sem `leave`** (por exemplo, `kill`): o protocolo do enunciado não
  inclui reparação do anel, por isso o anel fica partido. Os restantes nós detectam a
  perda, avisam e continuam a responder; as pesquisas que precisem do troço partido
  falham com erro.
- **Consistência eventual**: logo após uma adesão ou saída, durante alguns
  milissegundos, `show` pode ainda mostrar o predecessor antigo, e pesquisas concorrentes
  com a reconstrução podem ser perdidas (a pesquisa fica sem resposta; basta repetir).
- Um só anel por nó (como pedido) e um só nó de arranque registado por anel.
- A aplicação usa `select()` sobre o teclado e por isso só corre em Linux/Unix (como
  nas máquinas Vagrant), não no Windows.

## 9. Entrega

Repositório GitHub **privado**, partilhado com `joaojdacosta`, contendo o código-fonte,
o `Makefile`, o `Vagrantfile` e `scripts/`. O relatório em PDF é submetido por cada
membro no Google Classroom até 13/11/2026 (modelo ainda por disponibilizar no enunciado).
