"""Luta online em "lockstep com atraso": os dois computadores rodam a MESMA luta, frame a frame,
com os botões dos dois jogadores.

Os botões apertados agora valem daqui a `delay` frames. Nesse meio tempo eles viajam pela internet
e chegam no outro computador antes de serem necessários. Se ainda não chegaram (internet
engasgou), a luta espera um pouco em vez de adivinhar: os dois nunca veem lutas diferentes.

De tempos em tempos cada um manda um resumo (crc) do estado da luta; se os resumos de um mesmo
frame forem diferentes, as duas lutas se separaram (bug) e a partida é interrompida.
"""

CHECK_EVERY = 30        # frames entre uma conferência e outra
KEEP_CHECKS = 40        # conferências guardadas esperando a do outro


class Lockstep:
    def __init__(self, match_no, local_side, delay):
        self.match_no = match_no
        self.local_side = local_side   # 0 = P1, 1 = P2
        self.delay = delay
        self.frame = 0                 # próximo frame a simular
        # botões por frame; os primeiros `delay` frames não têm botão nenhum (nos dois lados)
        self.local = {f: 0 for f in range(delay)}
        self.remote = {f: 0 for f in range(delay)}
        self.local_last = delay - 1    # último frame com botão local já definido
        self.remote_last = delay - 1   # último frame seguido (sem buracos) recebido do outro
        self.remote_ack = delay - 1    # último frame nosso que o outro confirmou ter recebido
        self.checks = {}               # frame -> nosso crc
        self.remote_checks = {}        # frame -> crc do outro
        self.last_check = (-1, 0)      # a conferência mais nova, vai em todo pacote
        self.desync_frame = None
        self.stalled = 0               # frames de tela seguidos esperando o outro
        self.remote_advantage = 0      # o quanto o outro acha que está na nossa frente

    # ---------- simulação ----------
    def can_step(self):
        return self.frame in self.remote

    def advance(self, buttons):
        """Guarda os botões locais de agora (valem em frame + delay) e devolve o frame a simular
        e os botões dos dois nele: (frame, botões do P1, botões do P2)."""
        frame = self.frame
        self.local[frame + self.delay] = buttons
        self.local_last = frame + self.delay
        mine, theirs = self.local[frame], self.remote.pop(frame)
        self.frame += 1
        # botão local só pode ser esquecido depois que o outro confirmou que recebeu
        for old in [f for f in self.local if f < min(self.frame, self.remote_ack + 1)]:
            del self.local[old]
        return (frame,) + ((mine, theirs) if self.local_side == 0 else (theirs, mine))

    def advantage(self):
        """Quantos frames estamos na frente do último frame do outro que conhecemos. Inclui o tempo
        de viagem do pacote, por isso sozinho não diz quem está adiantado."""
        return self.frame - (self.remote_last - self.delay + 1)

    def balance(self):
        """Quantos frames estamos REALMENTE na frente (negativo = atrás). Os dois lados medem com o
        mesmo erro (a viagem do pacote); a metade da diferença entre as duas medidas cancela esse erro."""
        return (self.advantage() - self.remote_advantage) / 2

    def record_check(self, frame, crc):
        self.checks[frame] = crc
        self.last_check = (frame, crc)
        self._compare(frame)
        for old in [f for f in self.checks if f < frame - CHECK_EVERY * KEEP_CHECKS]:
            del self.checks[old]

    def _compare(self, frame):
        if frame in self.checks and frame in self.remote_checks:
            if self.checks[frame] != self.remote_checks.pop(frame) and self.desync_frame is None:
                self.desync_frame = frame

    # ---------- rede ----------
    def outgoing(self):
        """Dados do próximo pacote: ack, primeiro frame, conferência, vantagem e botões ainda não
        confirmados."""
        first = self.remote_ack + 1
        buttons = [self.local[f] for f in range(first, self.local_last + 1)]
        return self.remote_last, first, self.last_check, self.advantage(), buttons

    def unconfirmed(self):
        return self.local_last > self.remote_ack

    def receive(self, ack, first, check_frame, check, advantage, buttons):
        self.remote_ack = max(self.remote_ack, min(ack, self.local_last))
        self.remote_advantage = advantage
        for i, bits in enumerate(buttons):
            frame = first + i
            if frame >= self.frame and frame not in self.remote:
                self.remote[frame] = bits
        while self.remote_last + 1 in self.remote:
            self.remote_last += 1
        if check_frame >= 0:
            self.remote_checks[check_frame] = check
            self._compare(check_frame)
            for old in [f for f in self.remote_checks if f < self.frame - CHECK_EVERY * KEEP_CHECKS]:
                del self.remote_checks[old]
