"""Sons e trilhas do jogo. Sem saída de áudio (ou com arquivo faltando) o jogo continua normal,
só sem aquele som.

Os sons são só efeito: tocam a partir dos avisos da luta, nunca decidem nada nela (no online
cada computador toca os seus, sem risco de dessincronizar).
"""
import math
import os
import random
import threading
from array import array
from operator import mul

import pygame

FREQUENCY = 44100
BUFFER = 512                 # menor = som mais colado na ação (e mais trabalho para o áudio)
MAX_SAMPLE = 32767
MIXER_CHANNELS = 16

# Canais reservados para os lutadores (índice = lado: 0 = P1, 1 = P2). Golpe novo corta o som do
# golpe anterior do mesmo lado; o SUPER tem canal próprio, então os golpes seguintes não cortam
# o som dele (que é bem mais longo que o golpe).
ATTACK_CHANNELS = (0, 1)
SUPER_CHANNELS = (2, 3)
FIGHTER_CHANNELS = ATTACK_CHANNELS + SUPER_CHANNELS

# ---------------- ALTURA DOS SONS ----------------
# "Altura" = volume médio do trecho de 0,3 s mais forte do som, contando menos os graves (abaixo
# de WEIGHT_HZ caixinhas e fones pequenos quase não tocam: um som só de grave parece mudo).
# Cada som é aumentado ou abaixado até a altura do tipo dele.
LEVELS = {
    "atk1": 4200,            # golpe rápido
    "atk2": 5450,            # golpe forte: um pouco mais alto
    "super": 7100,           # SUPER: mais alto ainda
    "parry": 5000,
    "cue": 3600,             # bipes da contagem (quando não há a voz)
    "voice": 5000,           # locutor: "3", "2", "1"...
    "voice_fight": 6000,     # ...e o "FIGHT!", mais forte
    "ui": 2600,              # menus
}
LOUD_WINDOW = 0.3            # s
BLOCK = 0.025                # s; pedaços em que o som é medido
WEIGHT_HZ = 150
DECIMATE = 4                 # mede 1 de cada 4 amostras (bem mais rápido, mesma altura)
LIMIT = 0.8                  # ao aumentar um som baixo, os picos acima de 80% do máximo são
                             # arredondados em vez de estourar...
OVERDRIVE = 1.6              # ...mas no máximo 1,6x além do ponto em que o pico encostaria no teto
SILENCE = 0.02               # abaixo de 2% do pico conta como silêncio no começo do arquivo
LEAD_IN = 0.004              # s de folga antes do som começar (não cortar o "ataque" do som)
FADE_OUT = 0.08              # s; parte cortada antes do fim some aos poucos (sem estalo)

# ---------------- EFEITOS ----------------
# nome -> (arquivo, tipo de altura). Trocar um som = trocar o arquivo aqui.
KENNEY = "assets/audio/GameSounds/sonsKeney/SonsInterfaceKenney"
EFFECTS = {
    "hover": (f"{KENNEY}/select_002.ogg", "ui"),             # trocar de opção / de lutador
    "confirm": ("assets/audio/GameSounds/clique.mp3", "ui"),  # escolher uma opção
    "back": (f"{KENNEY}/back_002.ogg", "ui"),                # voltar, sair, desfazer o PRONTO
    "ready": (f"{KENNEY}/confirmation_001.ogg", "ui"),       # lutador confirmado (PRONTO)
    "type": (f"{KENNEY}/tick_002.ogg", "ui"),                # digitar IP / código da sala
    "pause": (f"{KENNEY}/open_002.ogg", "ui"),               # abrir a pausa
    "resume": (f"{KENNEY}/close_002.ogg", "ui"),             # fechar a pausa
    "connected": (f"{KENNEY}/confirmation_002.ogg", "ui"),   # o outro jogador entrou na sala
    "error": (f"{KENNEY}/error_004.ogg", "ui"),              # aviso de erro (conexão, IP inválido)
    "count": (f"{KENNEY}/select_005.ogg", "cue"),            # bipe do 3, 2, 1 (sem a voz)
    "fight": (f"{KENNEY}/confirmation_003.ogg", "cue"),      # bipe do LUTE! (sem a voz)
    "parry": (f"{KENNEY}/glass_001.ogg", "parry"),
}

# Locutor da contagem: um arquivo só com as 4 falas ("3", "2", "1", "FIGHT!") separadas por um
# pouco de silêncio. O jogo corta nos silêncios e toca cada fala junto com o número na tela
# (efeitos "count3", "count2", "count1" e "fight"). Sem o arquivo, ficam os bipes acima.
COUNTDOWN_VOICE = "assets/audio/GameSounds/3, 2, 1, FIGHT!.mp3"
COUNTDOWN_NAMES = ("count3", "count2", "count1", "fight")
SPLIT_SILENCE = 0.05         # abaixo de 5% do pico conta como silêncio entre as falas
SPLIT_BLOCK = 0.01           # s

# ---------------- TRILHAS ----------------
# Qualquer música dentro da pasta vale (com mais de uma, cada vez sorteia uma). O volume de cada
# uma é medido sozinho, em segundo plano, para todas ficarem na mesma altura.
MUSIC_DIRS = {
    "menu": "assets/audio/menuSounds",
    "fight": "assets/audio/GameSounds/fightingSongs",
}
MUSIC_EXTS = (".mp3", ".ogg", ".wav")
MUSIC_LEVEL = 2200           # volume médio das trilhas (bem abaixo dos golpes)
MUSIC_FADE_MS = 700          # troca de trilha: a anterior some e a nova aparece aos poucos
MUSIC_DUCK = 0.35            # na pausa a trilha fica com 35% do volume

_effects = {}
_tracks = {}                 # grupo -> lista de arquivos
_track_volume = {}           # arquivo -> volume (None = não deu para abrir)
_music = {"group": None, "next": None, "volume": 1.0, "duck": False}
_rng = random.Random()       # sorteio das trilhas (separado do random do jogo)


def pre_init():
    """Chamar antes do pygame.init(): buffer pequeno para o som não sair atrasado."""
    pygame.mixer.pre_init(FREQUENCY, -16, 2, BUFFER)


def available():
    return pygame.mixer.get_init() is not None


def setup():
    """Chamar depois do pygame.init()."""
    if not available():
        return
    pygame.mixer.set_num_channels(MIXER_CHANNELS)
    pygame.mixer.set_reserved(len(FIGHTER_CHANNELS))
    for name, (path, kind) in EFFECTS.items():
        sound = load(path, LEVELS[kind])
        if sound is not None:
            _effects[name] = sound
    voices = load_split(COUNTDOWN_VOICE, len(COUNTDOWN_NAMES),
                        [LEVELS["voice"]] * (len(COUNTDOWN_NAMES) - 1) + [LEVELS["voice_fight"]])
    for name, sound in zip(COUNTDOWN_NAMES, voices or ()):
        _effects[name] = sound
    for name in COUNTDOWN_NAMES[:-1]:    # sem a voz: o bipe em cada número
        if name not in _effects and "count" in _effects:
            _effects[name] = _effects["count"]
    for group, folder in MUSIC_DIRS.items():
        names = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
        _tracks[group] = [os.path.join(folder, n) for n in names if n.lower().endswith(MUSIC_EXTS)]
    threading.Thread(target=_measure_tracks, daemon=True).start()


# ---------------- CARREGAR E NIVELAR ----------------
def load(paths, level, starts=None, delay=0.0):
    """Som pronto para tocar: sem o silêncio do começo e na altura "level" (ver LEVELS).

    paths: um arquivo ou uma lista de partes (cada parte nivelada sozinha).
    starts: segundo em que cada parte entra, contado do começo da primeira (sem isso, uma
            depois da outra). O som acaba junto com a última parte: as que iriam além somem nela.
    delay: segundos de silêncio antes do som.
    None sem áudio ou com algum arquivo faltando.
    """
    if isinstance(paths, str):
        paths = [paths]
    if not available() or not all(os.path.exists(path) for path in paths):
        return None
    try:
        sounds = [pygame.mixer.Sound(path) for path in paths]
    except pygame.error:
        return None
    rate, size, channels = pygame.mixer.get_init()
    if size != -16:              # formato inesperado: toca como veio, só a primeira parte
        return sounds[0]

    parts = [_trim(array("h", sound.get_raw()), rate, channels) for sound in sounds]
    lead = array("h", bytes(2 * round(delay * rate) * channels))
    if len(parts) == 1:
        return _leveled(lead + parts[0], rate, channels, level)

    # partes: cada uma nivelada no trecho que realmente toca, depois o som inteiro nivelado de novo
    # (onde as partes se encontram elas somam e ficariam mais altas que o resto)
    if starts is None:
        positions = [sum(len(p) for p in parts[:i]) for i in range(len(parts))]
    else:
        positions = [round(t * rate) * channels for t in starts]
    end = positions[-1] + len(parts[-1])
    out = array("i")             # 32 bits: a soma das partes pode passar do máximo antes de nivelar
    for part, pos in zip(parts, positions):
        played = part[:max(0, end - pos)]
        scaled = _scale(played, _gain(played, rate, channels, level))
        if len(played) < len(part):
            _fade_out(scaled, rate, channels)
        _mix(out, scaled, pos)
    out = _scale(out, _gain(out, rate, channels, level))
    return pygame.mixer.Sound(buffer=(lead + out).tobytes())


def _leveled(samples, rate, channels, level):
    """Sound com as amostras na altura level."""
    gain = _gain(samples, rate, channels, level)
    if gain <= 1:                # só abaixar: o próprio volume do Sound resolve
        sound = pygame.mixer.Sound(buffer=samples.tobytes())
        sound.set_volume(gain)
        return sound
    return pygame.mixer.Sound(buffer=_scale(samples, gain).tobytes())


def load_split(path, count, levels):
    """Corta um arquivo com `count` falas separadas por silêncio (nos count-1 silêncios mais
    longos) e devolve uma lista de Sounds, cada fala na sua altura (levels[i]).
    None sem áudio, sem o arquivo ou se não achar silêncios suficientes."""
    if not available() or not os.path.exists(path):
        return None
    try:
        raw = array("h", pygame.mixer.Sound(path).get_raw())
    except pygame.error:
        return None
    rate, size, channels = pygame.mixer.get_init()
    if size != -16:
        return None
    peak = _peak(raw)
    step = round(SPLIT_BLOCK * rate) * channels
    quiet = [_peak(raw[i:i + step]) < peak * SPLIT_SILENCE for i in range(0, len(raw), step)]
    loud = [i for i, q in enumerate(quiet) if not q]
    if not loud:
        return None
    gaps = []                    # (tamanho, começo, fim) de cada silêncio entre a 1ª e a última fala
    start = None
    for i in range(loud[0], loud[-1] + 1):
        if quiet[i] and start is None:
            start = i
        elif not quiet[i] and start is not None:
            gaps.append((i - start, start, i))
            start = None
    if len(gaps) < count - 1:
        return None
    cuts = sorted((a + b) // 2 * step for _, a, b in sorted(gaps, reverse=True)[:count - 1])
    bounds = [0] + cuts + [len(raw)]
    # cada fala começa onde ela fica forte (o eco da fala anterior não atrasa a próxima)
    return [_leveled(_trim(raw[a:b], rate, channels, SPLIT_SILENCE * 2), rate, channels, level)
            for a, b, level in zip(bounds, bounds[1:], levels)]


def _trim(samples, rate, channels, silence=SILENCE):
    """Tira o silêncio do começo (deixando LEAD_IN de folga); abaixo de `silence` do pico é silêncio."""
    peak = _peak(samples)
    if not peak:
        return samples
    start = next(i for i, v in enumerate(samples) if abs(v) > peak * silence)
    start = max(0, start - int(LEAD_IN * rate) * channels)
    start -= start % channels
    return samples[start:]


def _peak(samples):
    return max(max(samples, default=0), -min(samples, default=0))


def _loudness(samples, rate, channels):
    """Altura do som (ver LEVELS): graves pesam menos, conta o trecho de LOUD_WINDOW mais forte."""
    step = channels * DECIMATE
    x = samples[::step]
    if channels == 2:        # média dos dois canais
        x = [(left + right) * 0.5 for left, right in zip(x, samples[1::step])]
    fs = rate / DECIMATE
    # passa-altas de 2ª ordem (Butterworth) em WEIGHT_HZ
    w0 = 2 * math.pi * WEIGHT_HZ / fs
    alpha = math.sin(w0) / math.sqrt(2)
    cos0 = math.cos(w0)
    a0 = 1 + alpha
    b0, b1, a1, a2 = (1 + cos0) / 2 / a0, -(1 + cos0) / a0, -2 * cos0 / a0, (1 - alpha) / a0
    weighted = []
    x1 = x2 = y1 = y2 = 0.0
    for v in x:
        y = b0 * (v + x2) + b1 * x1 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, v, y1, y
        weighted.append(y)
    size = max(1, round(BLOCK * fs))
    energy = [sum(map(mul, block, block)) for block in
              (weighted[i:i + size] for i in range(0, len(weighted), size))]
    if not energy:
        return 0.0
    count = max(1, round(LOUD_WINDOW / BLOCK))
    window = best = sum(energy[:count])
    for i in range(count, len(energy)):
        window += energy[i] - energy[i - count]
        best = max(best, window)
    return (best / (count * size)) ** 0.5


def _gain(samples, rate, channels, level):
    loudness = _loudness(samples, rate, channels)
    peak = _peak(samples)
    if not loudness or not peak:
        return 1.0
    return min(level / loudness, MAX_SAMPLE / peak * OVERDRIVE)


def _scale(samples, gain):
    """Amostras multiplicadas por gain; acima de LIMIT do máximo os picos são arredondados."""
    knee = LIMIT * MAX_SAMPLE
    room = MAX_SAMPLE - knee
    if _peak(samples) * gain <= knee:
        return array("h", [int(v * gain) for v in samples])

    def bend(v):
        bent = knee + room * math.tanh((abs(v) - knee) / room)
        return int(bent if v > 0 else -bent)

    edge = knee / gain       # só as amostras que passariam do joelho chamam bend (são poucas)
    return array("h", [int(v * gain) if -edge <= v <= edge else bend(v * gain) for v in samples])


def _fade_out(samples, rate, channels):
    count = min(len(samples), round(FADE_OUT * rate) * channels)
    start = len(samples) - count
    for i in range(count):
        samples[start + i] = int(samples[start + i] * (count - i) / count)


def _mix(out, samples, start):
    """Soma samples em out a partir de start (out cresce se precisar)."""
    if start > len(out):
        out.extend([0] * (start - len(out)))
    overlap = min(len(samples), len(out) - start)
    for i in range(overlap):
        out[start + i] += samples[i]
    out.extend(iter(samples[overlap:]))


# ---------------- TOCAR ----------------
def play_fighter(sound, side, kind):
    """Som de lutador (side 0 = P1, 1 = P2); kind "super" vai para o canal do SUPER."""
    if sound is not None and available():
        channels = SUPER_CHANNELS if kind == "super" else ATTACK_CHANNELS
        pygame.mixer.Channel(channels[side]).play(sound)


def pause_fighters():
    if available():
        for index in FIGHTER_CHANNELS:
            pygame.mixer.Channel(index).pause()


def resume_fighters():
    if available():
        for index in FIGHTER_CHANNELS:
            pygame.mixer.Channel(index).unpause()


def stop_fighters():
    """Corta os sons da luta (sair dela no meio de um SUPER, revanche...)."""
    if available():
        for index in FIGHTER_CHANNELS:
            channel = pygame.mixer.Channel(index)
            channel.unpause()
            channel.stop()


def play(name):
    """Efeito do jogo (ver EFFECTS), se o arquivo existir."""
    sound = _effects.get(name)
    if sound is not None:
        sound.play()


# ---------------- TRILHAS ----------------
def _measure_tracks():
    """Volume de cada trilha (roda em segundo plano: abrir uma música leva uns décimos de segundo)."""
    for paths in list(_tracks.values()):
        for path in paths:
            try:
                raw = array("h", pygame.mixer.Sound(path).get_raw())
            except (pygame.error, MemoryError):
                _track_volume[path] = None
                continue
            sample = raw[::63]   # passo ímpar: pega os dois canais
            rms = (sum(map(mul, sample, sample)) / max(1, len(sample))) ** 0.5
            _track_volume[path] = min(1.0, MUSIC_LEVEL / rms) if rms else 1.0


def music(group):
    """Trilha do momento ("menu" ou "fight"). Se já é a do grupo, continua sem recomeçar; senão
    a atual some aos poucos e a nova entra (em update)."""
    if not available() or group == _music["group"]:
        return
    _music["group"] = group
    tracks = _tracks.get(group) or []
    _music["next"] = _rng.choice(tracks) if tracks else None
    if pygame.mixer.music.get_busy():
        pygame.mixer.music.fadeout(MUSIC_FADE_MS)


def duck_music(on):
    """Abaixa a trilha (pausa) ou volta ao normal."""
    if on != _music["duck"] and available():
        _music["duck"] = on
        pygame.mixer.music.set_volume(_music_volume())


def _music_volume():
    return _music["volume"] * (MUSIC_DUCK if _music["duck"] else 1.0)


def update():
    """Chamar todo frame: começa a trilha nova quando a anterior acabou de sumir."""
    path = _music["next"]
    if path is None or not available() or pygame.mixer.music.get_busy() or path not in _track_volume:
        return
    _music["next"] = None
    volume = _track_volume[path]
    if volume is None:
        return
    try:
        pygame.mixer.music.load(path)
    except pygame.error:
        return
    _music["volume"] = volume
    pygame.mixer.music.set_volume(_music_volume())
    pygame.mixer.music.play(loops=-1, fade_ms=MUSIC_FADE_MS)
    pygame.mixer.music.set_volume(_music_volume())
