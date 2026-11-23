"""Servidor de salas do Falido da Luta: quem cria a sala recebe um código, quem entra com esse
código é ligado a ele, e o servidor repassa os pacotes de um para o outro. Assim ninguém precisa
abrir porta no roteador.

Precisa rodar numa máquina que os dois alcancem (um VPS como o Oracle Cloud, ou um PC com a
porta UDP aberta):
    python3 servidor_relay.py            (porta 50506)
    python3 servidor_relay.py 6000       (outra porta)

Só usa Python (não precisa de pygame): bastam este arquivo e o protocolo.py na mesma pasta.
Para parar: Ctrl+C. Para instalar como serviço no Ubuntu: instalar_servidor.sh.
"""
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import protocolo as proto  # noqa: E402

IDLE = 30.0          # s sem pacote de um jogador = ele saiu (a sala é desfeita)
CLEANUP_EVERY = 5.0  # s entre faxinas das salas abandonadas
MAX_ROOMS = 2000     # proteção contra quem tentar encher a memória do servidor
MAX_CODE = 16


class Relay:
    def __init__(self, port=proto.RELAY_PORT, host="0.0.0.0", log=print):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if hasattr(socket, "SIO_UDP_CONNRESET"):
            self.sock.ioctl(socket.SIO_UDP_CONNRESET, False)
        self.sock.bind((host, port))
        self.sock.settimeout(1.0)
        self.port = self.sock.getsockname()[1]
        self.rooms = {}       # código -> [endereço de quem criou, endereço de quem entrou]
        self.room_of = {}     # endereço -> código
        self.partner = {}     # endereço -> endereço do par
        self.seen = {}        # endereço -> última vez que mandou algo
        self.log = log
        self.running = True
        self.next_cleanup = time.monotonic() + CLEANUP_EVERY

    def serve(self):
        self.log(f"Servidor de salas ouvindo na porta UDP {self.port}. Ctrl+C para parar.")
        while self.running:
            try:
                data, address = self.sock.recvfrom(2048)
            except socket.timeout:
                data = None
            except OSError:
                data = None
            if data is not None:
                self.handle(data, address)
            if time.monotonic() >= self.next_cleanup:
                self.cleanup()
        self.sock.close()

    def handle(self, data, address):
        kind = proto.kind_of(data)
        if kind is None:
            return
        self.seen[address] = time.monotonic()
        if kind in (proto.CREATE, proto.JOIN):
            code = proto.read_text(data).strip().upper()[:MAX_CODE]
            if code:
                (self.create if kind == proto.CREATE else self.join)(code, address)
            return
        other = self.partner.get(address)
        if other is not None:
            self.sock.sendto(data, other)
        if kind == proto.BYE:  # alguém saiu (ou desistiu de esperar): a sala acaba
            self.dissolve(address)

    def _leave_other_room(self, code, address):
        if self.room_of.get(address) not in (None, code):
            self.dissolve(address)

    def create(self, code, address):
        self._leave_other_room(code, address)
        room = self.rooms.get(code)
        if room is None:
            if len(self.rooms) >= MAX_ROOMS:
                self.sock.sendto(proto.reject("O servidor está cheio agora. Tente de novo daqui a pouco."),
                                 address)
                return
            room = self.rooms[code] = [address]
            self.room_of[address] = code
            self.log(f"sala {code} criada ({len(self.rooms)} salas)")
        elif room[0] != address:
            self.sock.sendto(proto.reject(f"Já existe uma sala {code}. Crie outra."), address)
            return
        # repetido a cada pedido (um pacote pode se perder)
        self.sock.sendto(proto.paired(1) if len(room) == 2 else proto.room_ok(), address)

    def join(self, code, address):
        self._leave_other_room(code, address)
        room = self.rooms.get(code)
        if room is None:
            self.sock.sendto(proto.reject(f"Não existe sala {code}. Confira o código com quem criou "
                                          "(e se a sala dele ainda está aberta)."), address)
            return
        if address not in room:
            if len(room) >= 2:
                self.sock.sendto(proto.reject(f"A sala {code} já tem dois jogadores."), address)
                return
            room.append(address)
            self.room_of[address] = code
            host = room[0]
            self.partner[host], self.partner[address] = address, host
            self.sock.sendto(proto.paired(1), host)  # avisa quem criou na hora
            self.log(f"sala {code}: dois jogadores, luta liberada")
        if room[0] != address:
            self.sock.sendto(proto.paired(2), address)

    def dissolve(self, address):
        code = self.room_of.get(address)
        for member in self.rooms.pop(code, []):
            self.room_of.pop(member, None)
            self.partner.pop(member, None)
        if code is not None:
            self.log(f"sala {code} desfeita")

    def cleanup(self):
        now = time.monotonic()
        self.next_cleanup = now + CLEANUP_EVERY
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
