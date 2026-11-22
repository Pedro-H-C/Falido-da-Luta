"""Servidor de salas do Falido da Luta: junta dois jogadores pelo código da sala e repassa os
pacotes de um para o outro. Serve para jogar pela internet sem ninguém abrir porta no roteador.

Precisa rodar numa máquina que os dois alcancem (um VPS, ou um PC com a porta UDP aberta):
    python online/servidor_relay.py            (porta 50506)
    python online/servidor_relay.py 6000       (outra porta)

Só usa Python (não precisa de pygame). Para parar: Ctrl+C.
"""
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import protocolo as proto  # noqa: E402

IDLE = 30.0     # s sem pacote de um jogador = ele saiu (a sala é desfeita)


class Relay:
    def __init__(self, port=proto.RELAY_PORT, host="0.0.0.0", log=print):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if hasattr(socket, "SIO_UDP_CONNRESET"):
            self.sock.ioctl(socket.SIO_UDP_CONNRESET, False)
        self.sock.bind((host, port))
        self.sock.settimeout(1.0)
        self.port = self.sock.getsockname()[1]
        self.rooms = {}       # código -> [endereço do anfitrião, endereço do convidado]
        self.room_of = {}     # endereço -> código
        self.partner = {}     # endereço -> endereço do par
        self.seen = {}        # endereço -> última vez que mandou algo
        self.log = log
        self.running = True

    def serve(self):
        self.log(f"Servidor de salas ouvindo na porta UDP {self.port}. Ctrl+C para parar.")
        while self.running:
            try:
                data, address = self.sock.recvfrom(2048)
            except socket.timeout:
                self.cleanup()
                continue
            except OSError:
                continue
            self.seen[address] = time.monotonic()
            self.handle(data, address)
        self.sock.close()

    def handle(self, data, address):
        kind = proto.kind_of(data)
        if kind is None:
            return
        if kind == proto.ROOM:
            self.join(proto.read_text(data).strip().upper()[:16], address)
            return
        other = self.partner.get(address)
        if other is not None:
            self.sock.sendto(data, other)
            if kind == proto.BYE:  # alguém saiu: a sala fica livre para entrarem de novo
                self.dissolve(address)

    def join(self, code, address):
        if not code:
            return
        if self.room_of.get(address) not in (None, code):
            self.dissolve(address)
        room = self.rooms.setdefault(code, [])
        if address not in room:
            if len(room) >= 2:
                self.sock.sendto(proto.reject(f"A sala {code} já tem dois jogadores."), address)
                return
            room.append(address)
            self.room_of[address] = code
            self.log(f"sala {code}: {len(room)}/2 jogadores")
        if len(room) == 2:
            first, second = room
            self.partner[first], self.partner[second] = second, first
            role = 1 if address == first else 2
            self.sock.sendto(proto.paired(role), address)  # repetido a cada pedido (pacote pode se perder)

    def dissolve(self, address):
        code = self.room_of.get(address)
        for member in self.rooms.pop(code, []):
            self.room_of.pop(member, None)
            self.partner.pop(member, None)
        if code is not None:
            self.log(f"sala {code} desfeita")

    def cleanup(self):
        now = time.monotonic()
        for address in [a for a, t in self.seen.items() if now - t > IDLE]:
            self.seen.pop(address)
            if address in self.room_of:
                self.dissolve(address)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else proto.RELAY_PORT
    relay = Relay(port)
    try:
        relay.serve()
    except KeyboardInterrupt:
        print("\nServidor parado.")


if __name__ == "__main__":
    main()
