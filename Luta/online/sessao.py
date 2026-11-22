"""Conexão com o outro jogador por UDP, sem travar o jogo: o socket não bloqueia e tudo que
chegou é lido uma vez por frame em poll().

Três jeitos de conectar:
- host(): cria a sala e espera na porta DEFAULT_PORT (o amigo precisa alcançar essa porta:
  mesma rede, VPN como Radmin/Tailscale/ZeroTier, ou porta aberta no roteador);
- join(endereço): entra na sala de quem criou, pelo IP;
- relay(servidor, código): os dois entram numa sala com o mesmo código num servidor de salas
  (online/servidor_relay.py), que repassa os pacotes; ninguém precisa abrir porta.

Estados: "waiting" (anfitrião esperando), "connecting" (entrando), "room" (esperando o par no
servidor), "linking" (medindo o ping), "ready" (conectado) e "closed" (acabou; ver close_reason).
O anfitrião é sempre o P1 e quem entrou é o P2.
"""
import random
import socket
import statistics
import time

from . import protocolo as proto
from .lockstep import CHECK_EVERY, Lockstep

RESEND = 0.25            # s entre tentativas de conexão / pedidos de sala
SELECT_EVERY = 0.1       # s entre envios do estado da seleção (perdeu um, vem outro)
GO_EVERY = 0.1           # s entre repetições do "começar" até o outro confirmar
PING_FAST = 0.1          # s entre pings enquanto mede a conexão
PING_SLOW = 0.5          # s entre pings depois de conectado
PING_SAMPLES = 6
TIMEOUT = 8.0            # s sem notícia do outro = conexão perdida
JOIN_TIMEOUT = 20.0      # s tentando entrar numa sala que não responde
MIN_DELAY, MAX_DELAY = 2, 9
AHEAD = 1.0              # frames na frente do outro a partir dos quais vale segurar...
AHEAD_WAIT_EVERY = 4     # ... um frame a cada tantos
BEHIND = 3.0             # frames atrás a partir dos quais roda 2 frames por vez


def local_addresses():
    """IPs desta máquina (rede local, VPN), para o anfitrião passar ao amigo."""
    found = []
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))  # UDP não manda nada: só descobre a placa de rede usada
        found.append(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(info[4][0])
    except OSError:
        pass
    return [ip for i, ip in enumerate(found) if not ip.startswith("127.") and ip not in found[:i]]


def parse_address(text, default_port):
    """"1.2.3.4", "1.2.3.4:5000" ou "nome.com:5000" -> (ip, porta). Erro: ValueError com o motivo."""
    text = text.strip()
    if not text:
        raise ValueError("Digite o endereço.")
    host, port = text, default_port
    if text.count(":") == 1:
        host, port_text = text.split(":")
        if not port_text.isdigit() or not 0 < int(port_text) < 65536:
            raise ValueError("Porta inválida.")
        port = int(port_text)
    try:
        info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_DGRAM)
    except OSError:
        raise ValueError(f"Não achei o endereço \"{host}\".") from None
    return info[0][4]


def choose_delay(rtt_ms):
    """Atraso dos botões (frames): o tempo de ida do pacote + folga para variações da internet."""
    one_way = rtt_ms / 2 / (1000 / 60)
    return max(MIN_DELAY, min(MAX_DELAY, round(one_way) + 2))


class NetSession:
    def __init__(self, game_id, sim_loss=0.0, sim_latency_ms=0):
        self.game_id = game_id
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        if hasattr(socket, "SIO_UDP_CONNRESET"):
            # Windows: sem isso, um pacote que não chegou faz o próximo recvfrom dar erro
            self.sock.ioctl(socket.SIO_UDP_CONNRESET, False)
        self.state = "closed"
        self.role = 0                  # 1 = anfitrião (P1), 2 = convidado (P2)
        self.peer = None               # para onde mandar (o outro jogador ou o servidor de salas)
        self.server = None
        self.room_code = ""
        self.port = None
        self.close_reason = None
        self.rtt_ms = 0.0
        self.samples = []
        self.match_no = 0              # lutas já começadas nesta sala
        self.go = None                 # (número, P1, P2, atraso) da luta atual
        self.go_confirmed = True
        self.go_taken = 0              # última luta que o jogo já começou
        self.lockstep = None
        self.remote_select = None      # (cursor, pronto) do outro na seleção
        self.remote_seq = -1
        self.local_select = (0, False)
        self.select_seq = 0
        self.started = time.monotonic()
        self.last_recv = self.started
        self.next_send = {}
        self.frame_tick = 0
        # simulação de internet ruim (só para testes)
        self.sim_loss = sim_loss
        self.sim_latency = sim_latency_ms / 1000
        self.outbox = []

    # ---------- abrir ----------
    @classmethod
    def host(cls, game_id, port=proto.DEFAULT_PORT, **sim):
        session = cls(game_id, **sim)
        try:
            session.sock.bind(("0.0.0.0", port))
        except OSError:
            session._close(f"A porta {port} já está em uso (o jogo está aberto duas vezes?).")
            return session
        session.port = session.sock.getsockname()[1]
        session.role = 1
        session.state = "waiting"
        return session

    @classmethod
    def join(cls, game_id, address, **sim):
        session = cls(game_id, **sim)
        session.sock.bind(("0.0.0.0", 0))
        session.peer = address
        session.role = 2
        session.state = "connecting"
        return session

    @classmethod
    def relay(cls, game_id, server, code, **sim):
        session = cls(game_id, **sim)
        session.sock.bind(("0.0.0.0", 0))
        session.server = server
        session.room_code = code
        session.state = "room"
        return session

    @property
    def closed(self):
        return self.state == "closed"

    @property
    def connected(self):
        return self.state == "ready"

    def close(self, reason=None):
        """Sai da sala avisando o outro (algumas vezes, caso um pacote se perca)."""
        if self.peer is not None and self.state in ("linking", "ready"):
            for _ in range(3):
                self._raw_send(proto.bye(), self.peer)
        self._close(reason)

    def _close(self, reason):
        if self.state != "closed":
            self.state = "closed"
            self.close_reason = reason
        try:
            self.sock.close()
        except OSError:
            pass

    # ---------- envio ----------
    def _raw_send(self, data, address):
        try:
            self.sock.sendto(data, address)
        except OSError:
            pass

    def _send(self, data, address=None):
        address = address or self.peer
        if self.sim_loss and random.random() < self.sim_loss:
            return
        if self.sim_latency:
            jitter = random.uniform(0, self.sim_latency * 0.2)
            self.outbox.append((time.monotonic() + self.sim_latency + jitter, data, address))
        else:
            self._raw_send(data, address)

    def _due(self, name, every, now):
        """True no máximo uma vez a cada `every` segundos para a mensagem `name`."""
        if now >= self.next_send.get(name, 0):
            self.next_send[name] = now + every
            return True
        return False

    # ---------- a cada frame ----------
    def poll(self):
        """Lê tudo que chegou e manda o que estiver na hora (chamar uma vez por frame)."""
        if self.closed:
            return
        now = time.monotonic()
        if self.outbox:
            ready = [item for item in self.outbox if item[0] <= now]
            self.outbox = [item for item in self.outbox if item[0] > now]
            for _, data, address in ready:
                self._raw_send(data, address)
        while not self.closed:
            try:
                data, address = self.sock.recvfrom(2048)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                continue  # Windows avisa de pacotes que não chegaram; não é erro nosso
            self._handle(data, address, now)
        if not self.closed:
            self._periodic(now)

    def _periodic(self, now):
        if self.state == "room" and self._due("room", RESEND, now):
            self._send(proto.room(self.room_code), self.server)
        elif self.state == "connecting":
            if now - self.started > JOIN_TIMEOUT:
                self._close("Ninguém respondeu nesse endereço. Confira o IP e se a sala foi criada.")
            elif self._due("hello", RESEND, now):
                self._send(proto.hello(self.game_id))
        elif self.state in ("linking", "ready"):
            if now - self.last_recv > TIMEOUT:
                self._close("O outro jogador parou de responder (conexão perdida).")
                return
            if self._due("ping", PING_FAST if self.state == "linking" else PING_SLOW, now):
                self._send(proto.ping(proto.PING, now))
            if self.state == "ready":
                self._periodic_ready(now)

    def _periodic_ready(self, now):
        if self._due("select", SELECT_EVERY, now):
            self._send_select()
        if self.role == 1 and self.go and not self.go_confirmed and self._due("go", GO_EVERY, now):
            self._send(proto.go(*self.go))
        # botões ainda não confirmados pelo outro (ex.: a luta acabou aqui e lá ainda não)
        if self.lockstep and self.lockstep.unconfirmed() and self._due("inputs", 0.05, now):
            self.send_inputs()

    # ---------- recebimento ----------
    def _handle(self, data, address, now):
        kind = proto.kind_of(data)
        if kind is None:
            return
        if self.state == "room":
            if kind == proto.PAIRED and address == self.server:
                self.peer = self.server
                self.role = proto.read_paired(data)
                self.state = "waiting" if self.role == 1 else "connecting"
                self.started = now
            elif kind == proto.REJECT and address == self.server:
                self._close(proto.read_text(data))
            return
        if self.state == "waiting":
            if kind == proto.HELLO and (self.server is None or address == self.server):
                self._accept(data, address, now)
            return
        if address != self.peer:
            return
        self.last_recv = now
        if kind == proto.WELCOME and self.state == "connecting":
            self.state = "linking"
        elif kind == proto.REJECT:
            self._close(proto.read_text(data))
        elif kind == proto.HELLO and self.role == 1:
            self._raw_send(proto.welcome(), address)  # o "aceito" anterior se perdeu
        elif kind == proto.BYE:
            self._close("O outro jogador saiu da sala.")
        elif kind == proto.PING:
            self._send(proto.ping(proto.PONG, proto.read_ping(data)))
        elif kind == proto.PONG:
            self._on_pong(now - proto.read_ping(data))
        elif kind == proto.SELECT:
            self._on_select(data)
        elif kind == proto.GO and self.role == 2:
            self._on_go(data)
        elif kind == proto.INPUTS:
            self._on_inputs(data)

    def _accept(self, data, address, now):
        version, game_id = proto.read_hello(data)
        if version != proto.VERSION or game_id != self.game_id:
            self._raw_send(proto.reject("O jogo de vocês está em versões diferentes. Usem a mesma "
                                        "versão (mesmos arquivos) nos dois computadores."), address)
            return
        self.peer = address
        self.last_recv = now
        self.state = "linking"
        self._raw_send(proto.welcome(), address)

    def _on_pong(self, rtt):
        self.samples = (self.samples + [rtt * 1000])[-PING_SAMPLES:]
        self.rtt_ms = statistics.median(self.samples)
        if self.state == "linking" and len(self.samples) >= PING_SAMPLES:
            self.state = "ready"

    def _on_select(self, data):
        lobby, seq, cursor, locked = proto.read_select(data)
        if lobby == self.match_no and seq > self.remote_seq:
            self.remote_seq = seq
            self.remote_select = (cursor, locked)

    def _on_go(self, data):
        match_no, p1, p2, delay = proto.read_go(data)
        if match_no > self.match_no:
            self._begin(match_no, p1, p2, delay)

    def _on_inputs(self, data):
        match_no, ack, first, check_frame, check, advantage, buttons = proto.read_inputs(data)
        if self.lockstep and match_no == self.lockstep.match_no:
            self.go_confirmed = True  # o convidado já está lutando: pode parar de repetir o GO
            self.lockstep.receive(ack, first, check_frame, check, advantage, buttons)

    # ---------- seleção e luta ----------
    def set_select(self, cursor, locked):
        """Estado da seleção deste jogador (mandado na hora se mudou, e depois de tempos em tempos)."""
        if (cursor, locked) != self.local_select:
            self.local_select = (cursor, locked)
            if self.connected:
                self._send_select()

    def _send_select(self):
        self.select_seq += 1
        self._send(proto.select(self.match_no, self.select_seq, *self.local_select))

    def start_match(self, p1, p2):
        """Anfitrião: começa uma luta com esses lutadores (índices do elenco)."""
        self._begin(self.match_no + 1, p1, p2, choose_delay(self.rtt_ms))
        self.go_confirmed = False
        self._send(proto.go(*self.go))

    def _begin(self, match_no, p1, p2, delay):
        self.match_no = match_no
        self.go = (match_no, p1, p2, delay)
        self.lockstep = Lockstep(match_no, self.role - 1, delay)
        self.remote_select = None
        self.remote_seq = -1
        self.local_select = (self.local_select[0], False)

    def take_go(self):
        """Luta nova que o jogo ainda não começou: (P1, P2, atraso) uma vez só; senão None."""
        if self.go and self.go[0] > self.go_taken:
            self.go_taken = self.go[0]
            return self.go[1:]
        return None

    def send_inputs(self):
        ls = self.lockstep
        ack, first, (check_frame, check), advantage, buttons = ls.outgoing()
        self._send(proto.inputs(ls.match_no, ack, first, check_frame, check, advantage, buttons))

    def step_match(self, buttons, simulate, checksum):
        """Avança a luta o que der neste frame de tela e retorna quantos frames rodou.
        buttons: botões locais agora (bits); simulate(p1, p2): roda um frame da luta com os bits
        dos dois; checksum(): resumo da luta, para conferir se os dois continuam iguais.

        Ritmo: quem está na frente segura um frame de vez em quando, para o outro alcançar antes
        de a luta ter que travar esperando; quem ficou bem para trás (janela arrastada, engasgo)
        roda 2 frames de uma vez até alcançar."""
        ls = self.lockstep
        self.frame_tick += 1
        balance = ls.balance()
        if balance <= -BEHIND:
            steps = 2
        elif balance >= AHEAD and self.frame_tick % AHEAD_WAIT_EVERY == 0:
            steps = 0
        else:
            steps = 1
        done = 0
        for _ in range(steps):
            if not ls.can_step():
                break
            frame, p1, p2 = ls.advance(buttons)
            simulate(p1, p2)
            if frame % CHECK_EVERY == 0:
                ls.record_check(frame, checksum())
            done += 1
        if steps:
            ls.stalled = 0 if done else ls.stalled + 1
        self.send_inputs()
        return done
