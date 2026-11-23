"""Formato dos pacotes UDP do modo online. O jogo e o servidor de salas usam este mesmo arquivo
(ele não depende do pygame, para o servidor rodar em qualquer máquina só com Python).

Todo pacote começa com MAGIC (2 bytes) e o tipo (1 byte); os números vão em little-endian.
"""
import struct

MAGIC = b"FL"
VERSION = 1                # muda quando o formato dos pacotes mudar
DEFAULT_PORT = 50505       # porta de quem cria a sala (UDP)
RELAY_PORT = 50506         # porta do servidor de salas (UDP)
MAX_INPUTS = 200           # botões por pacote, no máximo

# conexão
HELLO = b"H"     # quem entra -> anfitrião: versão, impressão do jogo (crc dos arquivos da luta)
WELCOME = b"W"   # anfitrião -> quem entrou: aceito
REJECT = b"X"    # recusado (texto com o motivo)
PING = b"P"      # t (relógio de quem mandou); a resposta devolve o mesmo t
PONG = b"Q"
BYE = b"B"       # saiu da sala
# seleção de lutadores e começo da luta
SELECT = b"S"    # rodada da sala, seq, lutador no cursor, confirmado
GO = b"G"        # anfitrião -> os dois: número da luta, lutador do P1, lutador do P2, atraso (frames)
# luta
INPUTS = b"I"    # número da luta, ack, primeiro frame, conferência (frame, crc), vantagem, botões
# servidor de salas (o servidor repassa todo o resto de um jogador para o outro)
CREATE = b"C"    # jogador -> servidor: cria a sala com este código e espera (repetido até parear)
JOIN = b"J"      # jogador -> servidor: entra na sala com este código
ROOM_OK = b"o"   # servidor -> quem criou: sala criada, esperando o outro
PAIRED = b"r"    # servidor -> jogador: a sala encheu; papel 1 (quem criou, P1) ou 2 (quem entrou, P2)

_HELLO = struct.Struct("<HI")
_PING = struct.Struct("<d")
_SELECT = struct.Struct("<HIBB")
_GO = struct.Struct("<HBBB")
_INPUTS = struct.Struct("<HiiiIb")
_PAIRED = struct.Struct("<B")


def kind_of(data):
    """Tipo do pacote (1 byte) ou None se não for do jogo."""
    if len(data) < 3 or data[:2] != MAGIC:
        return None
    return data[2:3]


def _pack(kind, layout=None, *values):
    return MAGIC + kind + (layout.pack(*values) if layout else b"")


def _body(data, layout):
    return layout.unpack_from(data, 3)


def hello(game_id):
    return _pack(HELLO, _HELLO, VERSION, game_id)


def read_hello(data):
    return _body(data, _HELLO)  # (versão, impressão do jogo)


def welcome():
    return _pack(WELCOME)


def reject(reason):
    return MAGIC + REJECT + reason.encode("utf-8")[:300]


def read_text(data):
    return data[3:].decode("utf-8", errors="replace")


def ping(kind, t):
    return _pack(kind, _PING, t)


def read_ping(data):
    return _body(data, _PING)[0]


def bye():
    return _pack(BYE)


def select(lobby, seq, cursor, locked):
    return _pack(SELECT, _SELECT, lobby, seq, cursor, int(locked))


def read_select(data):
    lobby, seq, cursor, locked = _body(data, _SELECT)
    return lobby, seq, cursor, bool(locked)


def go(match_no, p1, p2, delay):
    return _pack(GO, _GO, match_no, p1, p2, delay)


def read_go(data):
    return _body(data, _GO)


def inputs(match_no, ack, first, check_frame, check, advantage, buttons):
    """advantage: quantos frames quem manda acha que está na frente do outro (-127..127)."""
    advantage = max(-127, min(127, advantage))
    return (_pack(INPUTS, _INPUTS, match_no, ack, first, check_frame, check, advantage)
            + bytes(buttons[:MAX_INPUTS]))


def read_inputs(data):
    match_no, ack, first, check_frame, check, advantage = _body(data, _INPUTS)
    return match_no, ack, first, check_frame, check, advantage, data[3 + _INPUTS.size:]


def room(kind, code):
    """Pedido ao servidor de salas: kind CREATE ou JOIN."""
    return MAGIC + kind + code.encode("utf-8")[:32]


def room_ok():
    return _pack(ROOM_OK)


def paired(role):
    return _pack(PAIRED, _PAIRED, role)


def read_paired(data):
    return _body(data, _PAIRED)[0]
