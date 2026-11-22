"""Modo online (PVP pela internet): conexão UDP, troca de botões e servidor de salas.
Veja COMO_JOGAR_ONLINE.md nesta pasta."""
from .lockstep import CHECK_EVERY, Lockstep  # noqa: F401
from .protocolo import DEFAULT_PORT, RELAY_PORT  # noqa: F401
from .sessao import NetSession, local_addresses, parse_address  # noqa: F401
