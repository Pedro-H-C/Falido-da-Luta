import math
import random
import unicodedata

import pygame

import fighter as fighter_module
from fighter import (CHARACTERS, CHARACTERS_BY_ID, DIFFICULTIES, DIFFICULTY_LABELS, GROUND_MARGIN,
                     Fighter, apply_alt_palette, get_frames, preload_characters)

pygame.init()

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 600
# SCALED: o jogo continua desenhando em 1000x600 e o pygame estica para a tela,
# então a tela cheia não bagunça posições, hitboxes nem o mouse.
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SCALED)
pygame.display.set_caption("Falido da luta")
pygame.display.set_icon(pygame.image.load("assets/images/Logo/logo.png"))

relogio = pygame.time.Clock()
FPS = 60

YELLOW = (255, 255, 0)
RED = (255, 0, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (120, 120, 120)
LIGHT_GRAY = (200, 200, 200)
DARK_GRAY = (45, 45, 52)
TRAIL_COLOR = (255, 235, 200)
P1_COLOR = (215, 45, 45)
P2_COLOR = (45, 110, 225)
CPU_COLOR = (150, 70, 200)

# ESTADOS DO JOGO
MAIN_MENU = "MAIN_MENU"
CHAR_SELECT = "CHAR_SELECT"
FIGHT = "FIGHT"
PAUSE = "PAUSE"
MATCH_OVER = "MATCH_OVER"

# MODOS
MODE_CPU = "cpu"
MODE_VERSUS = "versus"

# PARTIDA
ROUNDS_TO_WIN = 2            # melhor de 3
ROUND_OVER_COOLDOWN = 2200   # ms (tempo de jogo) entre o nocaute e o próximo round
FIGHT_BANNER_MS = 800        # tempo do "LUTEM!" na tela
READY_FLASH_MS = 900         # tempo do "PRONTO!" antes da luta começar

# SENSAÇÃO DOS GOLPES
HITSTOP_FRAMES = {1: 3, 2: 5}        # congelamento ao acertar (golpe rápido / forte)
BLOCK_HITSTOP_FRAMES = {1: 2, 2: 3}
KO_HITSTOP_FRAMES = 16
SLOWMO_FRAMES = 70                   # duração da câmera lenta do nocaute (frames reais)
SLOWMO_SCALE = 0.35                  # o jogo anda a 35% da velocidade
SHAKE_MARGIN = 12                    # sobra do fundo para o tremor não mostrar bordas
HIT_COLORS = ((255, 255, 255), (255, 240, 120), (255, 200, 40), (255, 140, 20))
BLOCK_COLORS = ((255, 255, 255), (170, 220, 255), (90, 170, 255))

# TELA DE SELEÇÃO
SELECT_PANEL_X = (30, 530)
SELECT_PANEL_Y = 72
SELECT_PANEL_W = 440
SELECT_PANEL_H = 410
PREVIEW_SIZE = 300
PREVIEW_FRAME_MS = 120
STAT_BAR_W = 150
# (rótulo, atributo, menor valor, maior valor) — o pulo usa o módulo da velocidade
STAT_BARS = (
    ("Vida", "max_health", 95, 110),
    ("Velocidade", "speed", 7, 9),
    ("Pulo", "jump_vel", 28, 32),
    ("Força", "dmg_mult", 0.9, 1.15),
)

# Redimensiona as imagens de fundo UMA vez (não a cada frame).
# O fundo da luta sobra um pouco em cada borda para o tremor de tela.
bg_image = pygame.image.load("assets/images/Backgrounds/bgArrudinha.png").convert()
bg_image = pygame.transform.scale(bg_image, (SCREEN_WIDTH + 2 * SHAKE_MARGIN, SCREEN_HEIGHT + 2 * SHAKE_MARGIN))
menu_image = pygame.image.load("assets/images/Menu/menu.png").convert()
menu_image = pygame.transform.scale(menu_image, (SCREEN_WIDTH, SCREEN_HEIGHT))
menu_image.set_alpha(80)  # 0 = invisível, 255 = opaco

# Camada escura por cima do jogo quando pausado
pause_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
pause_overlay.fill((0, 0, 0, 160))
# Clarão do nocaute (a transparência muda a cada frame)
flash_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
flash_overlay.fill(WHITE)
# Faixa escura atrás dos letreiros grandes (NOCAUTE!, PRONTO!)
banner_band = pygame.Surface((SCREEN_WIDTH, 200), pygame.SRCALPHA)
banner_band.fill((0, 0, 0, 130))
# Sombra no chão embaixo dos lutadores
shadow_image = pygame.Surface((150, 34), pygame.SRCALPHA)
pygame.draw.ellipse(shadow_image, (0, 0, 0, 95), shadow_image.get_rect())
preview_shadow = pygame.transform.smoothscale(shadow_image, (130, 28))
# Fundo dos painéis da seleção
panel_bg = pygame.Surface((SELECT_PANEL_W, SELECT_PANEL_H), pygame.SRCALPHA)
pygame.draw.rect(panel_bg, (0, 0, 0, 150), panel_bg.get_rect(), border_radius=14)

FONT_PATH = "assets/fonts/Turok.ttf"
count_font = pygame.font.Font(FONT_PATH, 200)
title_font = pygame.font.Font(FONT_PATH, 90)
menu_font = pygame.font.Font(FONT_PATH, 50)
name_font = pygame.font.Font(FONT_PATH, 46)
score_font = pygame.font.Font(FONT_PATH, 30)
small_font = pygame.font.Font(FONT_PATH, 22)
tiny_font = pygame.font.Font(FONT_PATH, 18)

# Botão de pausa: centralizado entre as barras de vida (que vão até x=420 e começam em x=580)
PAUSE_BUTTON = pygame.Rect(SCREEN_WIDTH // 2 - 25, 15, 50, 40)

fullscreen = False


# ---------------- SPRITES ----------------
# Lidos do disco uma única vez; seleção e luta usam o mesmo cache.
preload_characters()


def build_previews():
    """Idle da tela de seleção, derivado do cache de sprites (nada é relido do disco).

    Chave: (id, lado, paleta alternativa). O lado direito vem espelhado, olhando para o P1.
    """
    previews = {}
    for char in CHARACTERS:
        idle = [pygame.transform.smoothscale(frame, (PREVIEW_SIZE, PREVIEW_SIZE))
                for frame in get_frames(char["id"])[0]]
        mirrored = [pygame.transform.flip(frame, True, False) for frame in idle]
        previews[(char["id"], 0, False)] = idle
        previews[(char["id"], 1, False)] = mirrored
        previews[(char["id"], 1, True)] = [apply_alt_palette(frame) for frame in mirrored]
    return previews


preview_frames = build_previews()


# ---------------- TEXTO ----------------
# A Turok não tem letras acentuadas: o texto é renderizado sem acento e o acento é
# traçado por cima da letra, mantendo a mesma fonte no jogo inteiro.
DIACRITICS = {"́": "acute", "̀": "grave", "̂": "circumflex",
              "̃": "tilde", "̧": "cedilla"}


def render_text(text, font, color):
    base = ""
    marks = []
    for ch in unicodedata.normalize("NFD", text):
        if ch in DIACRITICS:
            if base:
                marks.append((len(base) - 1, DIACRITICS[ch]))
        else:
            base += ch
    img = font.render(base, True, color)
    if not marks:
        return img

    stroke = max(2, font.get_height() // 14)
    mark_h = max(2, font.get_height() // 6)
    mark_w = max(3, font.get_height() // 7)
    ascent = font.get_ascent()
    placed = []
    for index, kind in marks:
        minx, maxx, miny, maxy, _ = font.metrics(base[index])[0]
        cx = font.size(base[:index])[0] + (minx + maxx) / 2
        placed.append((cx, ascent - maxy, ascent - miny, kind))

    # só cresce a surface se o acento não couber (ex.: letra maiúscula acentuada)
    pad_top = max([0] + [mark_h + 2 * stroke - top for _, top, _, kind in placed if kind != "cedilla"])
    pad_bottom = max([0] + [bottom + mark_h + stroke - img.get_height()
                            for _, _, bottom, kind in placed if kind == "cedilla"])
    out = pygame.Surface((img.get_width(), img.get_height() + pad_top + pad_bottom), pygame.SRCALPHA)
    out.blit(img, (0, pad_top))
    for cx, top, bottom, kind in placed:
        y1 = top + pad_top - stroke * 1.2  # base do acento
        y0 = y1 - mark_h                   # topo do acento
        if kind == "acute":
            pygame.draw.line(out, color, (cx - mark_w * 0.4, y1), (cx + mark_w * 0.5, y0), stroke)
        elif kind == "grave":
            pygame.draw.line(out, color, (cx + mark_w * 0.4, y1), (cx - mark_w * 0.5, y0), stroke)
        elif kind == "circumflex":
            pygame.draw.lines(out, color, False,
                              [(cx - mark_w * 0.6, y1), (cx, y0), (cx + mark_w * 0.6, y1)], stroke)
        elif kind == "tilde":
            pygame.draw.lines(out, color, False, [(cx - mark_w * 0.7, y1), (cx - mark_w * 0.3, y0),
                                                  (cx + mark_w * 0.3, y1), (cx + mark_w * 0.7, y0)], stroke)
        else:  # cedilha, embaixo da letra
            y = bottom + pad_top
            pygame.draw.lines(out, color, False, [(cx, y), (cx + mark_w * 0.4, y + mark_h * 0.5),
                                                  (cx - mark_w * 0.2, y + mark_h)], stroke)
    return out


def draw_text(text, font, text_col, x, y, anchor="topleft", shadow=False):
    """Desenha o texto ancorado em (x, y) e retorna o retângulo ocupado."""
    img = render_text(text, font, text_col)
    rect = img.get_rect(**{anchor: (x, y)})
    if shadow:
        screen.blit(render_text(text, font, BLACK), rect.move(3, 3))
    screen.blit(img, rect)
    return rect


def draw_arrow(center, direction, size, color):
    """Triângulo com sombra apontando para a esquerda (-1) ou direita (+1). Retorna a área de clique."""
    cx, cy = center
    base_x = cx - direction * size * 0.6
    points = [(cx + direction * size, cy), (base_x, cy - size), (base_x, cy + size)]
    pygame.draw.polygon(screen, BLACK, [(x + 3, y + 3) for x, y in points])
    pygame.draw.polygon(screen, color, points)
    return pygame.Rect(0, 0, size * 3, size * 3).move(cx - size * 1.5, cy - size * 1.5)


def draw_badge(text, color, x, y, anchor="topleft"):
    """Etiqueta colorida (P1 / P2 / CPU)."""
    img = render_text(text, small_font, WHITE)
    rect = img.get_rect().inflate(16, 6)
    setattr(rect, anchor, (x, y))
    pygame.draw.rect(screen, color, rect, border_radius=6)
    pygame.draw.rect(screen, BLACK, rect, 2, border_radius=6)
    screen.blit(img, img.get_rect(center=rect.center))
    return rect


def draw_banner(text, font, color, center_y, scale=1.0):
    """Letreiro grande centralizado, com sombra, opcionalmente ampliado (efeito de 'pop')."""
    img = render_text(text, font, color)
    shade = render_text(text, font, BLACK)
    if scale != 1.0:
        img = pygame.transform.rotozoom(img, 0, scale)
        shade = pygame.transform.rotozoom(shade, 0, scale)
    rect = img.get_rect(center=(SCREEN_WIDTH // 2, center_y))
    screen.blit(shade, rect.move(4, 4))
    screen.blit(img, rect)


# ---------------- MENUS ----------------
def fullscreen_label():
    return "Tela cheia: " + ("ON" if fullscreen else "OFF")


def toggle_fullscreen():
    global fullscreen
    pygame.display.toggle_fullscreen()
    fullscreen = not fullscreen


def draw_options(options, selected, start_y, spacing=75):
    """Desenha uma lista de opções e retorna os retângulos (para clique do mouse)."""
    rects = []
    for i, opcao in enumerate(options):
        cor = YELLOW if i == selected else WHITE
        texto = ("> " + opcao + " <") if i == selected else opcao
        rect = draw_text(texto, menu_font, cor, SCREEN_WIDTH // 2, start_y + i * spacing, "center", shadow=True)
        rects.append(rect)
    return rects


def handle_menu_event(event, options, rects, selected):
    """Navegação por teclado/mouse. Retorna (nova seleção, opção escolhida ou None)."""
    choice = None
    if event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_UP, pygame.K_w):
            selected = (selected - 1) % len(options)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            selected = (selected + 1) % len(options)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            choice = options[selected]
    elif event.type == pygame.MOUSEMOTION:
        for i, rect in enumerate(rects):
            if rect.collidepoint(event.pos):
                selected = i
    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        for i, rect in enumerate(rects):
            if rect.collidepoint(event.pos):
                choice = options[i]
    return selected, choice


def draw_pause_button(highlight):
    cor = YELLOW if highlight else WHITE
    pygame.draw.rect(screen, BLACK, PAUSE_BUTTON, border_radius=8)
    pygame.draw.rect(screen, cor, PAUSE_BUTTON, 2, border_radius=8)
    # ícone de pausa (duas barras)
    cx, cy = PAUSE_BUTTON.center
    pygame.draw.rect(screen, cor, (cx - 10, cy - 10, 7, 20))
    pygame.draw.rect(screen, cor, (cx + 3, cy - 10, 7, 20))


def draw_health_bar(fighter, x, y, mirrored=False):
    """Barra de vida; a do P2 é espelhada (esvazia em direção ao centro da tela)."""
    def segment(ratio):
        width = int(400 * ratio)
        return (x + 400 - width if mirrored else x, y, width, 30)

    pygame.draw.rect(screen, BLACK, (x - 2, y - 2, 404, 34))
    pygame.draw.rect(screen, RED, (x, y, 400, 30))
    pygame.draw.rect(screen, TRAIL_COLOR, segment(fighter.health_trail / fighter.max_health))
    pygame.draw.rect(screen, YELLOW, segment(fighter.health / fighter.max_health))


# ---------------- EFEITOS ----------------
class Spark:
    """Faísca de impacto: um risco que voa, cai e afina até sumir."""
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "width")

    def __init__(self, x, y, vx, vy, life, color, width):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.color = color
        self.width = width


class Impact:
    """Onda de choque (anel que cresce), com estrela de impacto no centro nos acertos."""
    __slots__ = ("x", "y", "life", "max_life", "size", "color", "angle", "star")

    def __init__(self, x, y, size, color, star, life=12):
        self.x, self.y = x, y
        self.size = size
        self.color = color
        self.star = star
        self.angle = random.uniform(0, math.pi)
        self.life = self.max_life = life


def star_points(cx, cy, outer, inner, points, angle):
    pts = []
    for i in range(points * 2):
        radius = outer if i % 2 == 0 else inner
        a = angle + i * math.pi / points
        pts.append((cx + math.cos(a) * radius, cy + math.sin(a) * radius))
    return pts


class Effects:
    """Faíscas, tremor de tela, clarão, hitstop e câmera lenta de uma luta."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.sparks = []
        self.impacts = []
        self.hitstop = 0        # frames com o jogo congelado
        self.slowmo = 0         # frames restantes de câmera lenta
        self.slow_acc = 0.0
        self.flash = 0          # transparência do clarão branco
        self.shake_power = 0
        self.shake_frames = 0
        self.shake_total = 1

    def on_hit(self, event):
        x, y = event.pos
        heavy = event.attack_type == 2
        if event.kind == "block":
            self.hitstop = max(self.hitstop, BLOCK_HITSTOP_FRAMES[event.attack_type])
            # na defesa, as faíscas voltam na direção de quem atacou
            self._burst(x, y, -event.direction, BLOCK_COLORS, 10 + 6 * heavy, (3, 8), 1.2)
            self.impacts.append(Impact(x, y, 30 + 12 * heavy, (150, 200, 255), star=False))
            self._shake(2 + heavy, 6)
        else:
            self.hitstop = max(self.hitstop, HITSTOP_FRAMES[event.attack_type])
            self._burst(x, y, event.direction, HIT_COLORS, 16 + 12 * heavy, (4, 11 + 5 * heavy), 0.9)
            self.impacts.append(Impact(x, y, 46 + 24 * heavy, WHITE, star=True))
            self._shake(3 + 3 * heavy, 8 + 6 * heavy)
        if event.ko:
            self.hitstop = KO_HITSTOP_FRAMES
            self.slowmo = SLOWMO_FRAMES
            self.slow_acc = 0.0
            self.flash = 220
            self._burst(x, y, event.direction, HIT_COLORS, 40, (6, 18), math.pi)
            self.impacts.append(Impact(x, y, 120, YELLOW, star=True, life=18))
            self._shake(10, 28)

    def _burst(self, x, y, direction, colors, count, speed, spread):
        base = 0.0 if direction > 0 else math.pi
        for _ in range(count):
            angle = base + random.uniform(-spread, spread)
            velocity = random.uniform(*speed)
            self.sparks.append(Spark(x, y, math.cos(angle) * velocity, math.sin(angle) * velocity - 1.5,
                                     random.randint(10, 20), random.choice(colors), random.randint(3, 5)))

    def _shake(self, power, frames):
        if power >= self.shake_power * self.shake_frames / self.shake_total:
            self.shake_power = power
            self.shake_frames = self.shake_total = frames

    def update(self):
        """Roda em tempo real (inclusive durante hitstop e câmera lenta)."""
        for s in self.sparks:
            s.x += s.vx
            s.y += s.vy
            s.vy += 0.35
            s.vx *= 0.94
            s.life -= 1
        self.sparks = [s for s in self.sparks if s.life > 0]
        for impact in self.impacts:
            impact.life -= 1
        self.impacts = [i for i in self.impacts if i.life > 0]
        if self.shake_frames > 0:
            self.shake_frames -= 1
        self.flash = max(0, self.flash - 12)

    def shake_offset(self):
        if self.shake_frames <= 0:
            return 0, 0
        amp = round(min(SHAKE_MARGIN, self.shake_power * self.shake_frames / self.shake_total))
        return random.randint(-amp, amp), random.randint(-amp, amp)

    def draw(self, offset):
        ox, oy = offset
        for impact in self.impacts:
            t = 1 - impact.life / impact.max_life  # 0 -> 1
            cx, cy = impact.x + ox, impact.y + oy
            radius = int(impact.size * (0.35 + 0.65 * t))
            pygame.draw.circle(screen, impact.color, (cx, cy), radius, max(1, int(5 * (1 - t))))
            if impact.star and t < 0.6:
                outer = impact.size * 0.8 * (1 - t * 0.8)
                pygame.draw.polygon(screen, YELLOW, star_points(cx, cy, outer, outer * 0.4, 8, impact.angle))
                pygame.draw.polygon(screen, WHITE, star_points(cx, cy, outer * 0.55, outer * 0.22, 8, impact.angle))
        for s in self.sparks:
            width = max(1, round(s.width * s.life / s.max_life))
            tail = (s.x - s.vx * 1.8 + ox, s.y - s.vy * 1.8 + oy)
            pygame.draw.line(screen, s.color, tail, (s.x + ox, s.y + oy), width)

    def draw_flash(self):
        if self.flash > 0:
            flash_overlay.set_alpha(self.flash)
            screen.blit(flash_overlay, (0, 0))


# ---------------- PARTIDA ----------------
class Match:
    """Partida melhor de 3: lutadores, rounds, placar, efeitos e HUD."""

    def __init__(self, mode, p1_id, p2_id, cpu_diff):
        self.mode = mode
        self.characters = (CHARACTERS_BY_ID[p1_id], CHARACTERS_BY_ID[p2_id])
        self.mirror = p1_id == p2_id
        self.cpu_diff = cpu_diff
        self.tags = ("P1", "CPU" if mode == MODE_CPU else "P2")
        self.colors = (P1_COLOR, CPU_COLOR if mode == MODE_CPU else P2_COLOR)
        self.score = [0, 0]
        self.round_number = 0
        self.effects = Effects()
        self.finished = False
        self.winner = None
        self.start_round()

    def start_round(self):
        """Novo round: reseta lutadores e contagem, mantém o placar."""
        self.round_number += 1
        p1_char, p2_char = self.characters
        self.fighters = (
            Fighter(200, 200, 1, False, p1_char),
            Fighter(700, 200, 2, True, p2_char, is_cpu=self.mode == MODE_CPU,
                    cpu_diff=self.cpu_diff, alt_palette=self.mirror),
        )
        self.intro_count = 3
        self.last_count_update = pygame.time.get_ticks()
        self.fight_banner_until = 0
        self.round_over = False
        self.round_over_time = 0
        self.round_winner = None
        self.effects.reset()

    def fighter_label(self, side):
        """Nome para os letreiros; em luta espelho inclui P1/P2/CPU para não confundir."""
        name = self.characters[side]["name"].upper()
        return f"{name} ({self.tags[side]})" if self.mirror else name

    def shift_timers(self, ms):
        """Empurra os timers para frente (pausa, hitstop, câmera lenta), pra nada pular."""
        self.last_count_update += ms
        self.round_over_time += ms
        self.fight_banner_until += ms
        for f in self.fighters:
            f.update_time += ms

    def update(self, dt):
        """Um frame: aplica hitstop/câmera lenta e avança a lógica quando for a vez."""
        fx = self.effects
        fx.update()
        if fx.hitstop > 0:
            fx.hitstop -= 1
            self.shift_timers(dt)
            return
        if fx.slowmo > 0:
            fx.slowmo -= 1
            fx.slow_acc += SLOWMO_SCALE
            if fx.slow_acc < 1:
                self.shift_timers(dt)
                return
            fx.slow_acc -= 1
        self.step()

    def step(self):
        now = pygame.time.get_ticks()
        f1, f2 = self.fighters
        if self.intro_count > 0 and now - self.last_count_update >= 1000:
            self.last_count_update = now
            self.intro_count -= 1
            if self.intro_count == 0:
                self.fight_banner_until = now + FIGHT_BANNER_MS

        can_act = self.intro_count <= 0 and not self.round_over and not self.finished
        for attacker, defender in ((f1, f2), (f2, f1)):
            event = attacker.move(SCREEN_WIDTH, SCREEN_HEIGHT, defender, can_act)
            if event:
                self.effects.on_hit(event)
        f1.update()
        f2.update()

        if self.finished:
            return
        if not self.round_over:
            if not f1.alive or not f2.alive:
                self.round_winner = 0 if f1.alive else 1
                self.score[self.round_winner] += 1
                self.round_over = True
                self.round_over_time = now
        elif now - self.round_over_time > ROUND_OVER_COOLDOWN:
            if max(self.score) >= ROUNDS_TO_WIN:
                self.finished = True
                self.winner = self.round_winner
            else:
                self.start_round()

    # ---------- desenho ----------
    def draw(self):
        offset = self.effects.shake_offset()
        ox, oy = offset
        screen.blit(bg_image, (-SHAKE_MARGIN + ox, -SHAKE_MARGIN + oy))

        ground = SCREEN_HEIGHT - GROUND_MARGIN
        for f in self.fighters:
            height = ground - f.rect.bottom
            scale = max(0.45, 1 - height / 320)
            shadow = pygame.transform.smoothscale(shadow_image, (int(150 * scale), int(34 * scale)))
            center_x = f.rect.x - f.offset[0] + f.image.get_width() // 2
            screen.blit(shadow, shadow.get_rect(center=(center_x + ox, ground - 17 + oy)))

        # quem está atacando fica na frente
        for f in sorted(self.fighters, key=lambda fighter: fighter.attacking):
            f.draw(screen, offset)
        self.effects.draw(offset)

        self.draw_hud()
        if not self.finished:
            self.draw_banners()
        self.effects.draw_flash()

    def draw_hud(self):
        for side, f in enumerate(self.fighters):
            bar_x = 20 if side == 0 else 580
            draw_health_bar(f, bar_x, 20, mirrored=side == 1)
            name = f.name.upper()
            if side == 0:
                badge = draw_badge(self.tags[0], self.colors[0], 20, 58)
                draw_text(name, score_font, WHITE, badge.right + 10, badge.centery, "midleft", shadow=True)
            else:
                badge = draw_badge(self.tags[1], self.colors[1], SCREEN_WIDTH - 20, 58, "topright")
                draw_text(name, score_font, WHITE, badge.left - 10, badge.centery, "midright", shadow=True)
            # bolinhas de rounds vencidos, perto do centro
            for i in range(ROUNDS_TO_WIN):
                cx = 420 - 12 - i * 28 if side == 0 else 580 + 12 + i * 28
                pygame.draw.circle(screen, BLACK, (cx, 74), 11)
                pygame.draw.circle(screen, YELLOW if i < self.score[side] else DARK_GRAY, (cx, 74), 8)
                pygame.draw.circle(screen, WHITE, (cx, 74), 10, 2)
        draw_text(f"Rodada {self.round_number}", tiny_font, WHITE, SCREEN_WIDTH // 2, 74, "center", shadow=True)

    def draw_banners(self):
        now = pygame.time.get_ticks()
        if self.intro_count > 0:
            final = self.score == [ROUNDS_TO_WIN - 1] * 2
            draw_banner("RODADA FINAL" if final else f"RODADA {self.round_number}", menu_font, WHITE, 170)
            draw_banner(str(self.intro_count), count_font, RED, 300)
        elif now < self.fight_banner_until:
            t = 1 - (self.fight_banner_until - now) / FIGHT_BANNER_MS
            draw_banner("LUTEM!", title_font, YELLOW, 260, scale=1 + 0.6 * max(0.0, 1 - t * 5))
        if self.round_over:
            screen.blit(banner_band, (0, 160))
            draw_banner("NOCAUTE!", title_font, RED, 225)
            winner = self.fighter_label(self.round_winner)
            draw_banner(f"{winner} vence a rodada", menu_font, YELLOW, 310)


# ---------------- SELEÇÃO DE LUTADORES ----------------
def stat_ratio(stats, key, lo, hi):
    value = abs(stats[key])
    return 0.2 + 0.8 * max(0.0, min(1.0, (value - lo) / (hi - lo)))


class CharSelect:
    """P1 à esquerda, P2/CPU à direita, um virado para o outro.

    1P vs 2P: cada jogador escolhe no seu teclado ao mesmo tempo.
    1P vs CPU: o P1 escolhe o seu lutador e depois o da CPU (e a dificuldade).
    """
    P1_KEYS = {"prev": (pygame.K_a,), "next": (pygame.K_d,),
               "confirm": (pygame.K_r, pygame.K_t, pygame.K_SPACE)}
    P2_KEYS = {"prev": (pygame.K_LEFT,), "next": (pygame.K_RIGHT,),
               "confirm": (pygame.K_n, pygame.K_m, pygame.K_RETURN, pygame.K_KP_ENTER)}
    BACK_KEYS = (pygame.K_ESCAPE, pygame.K_BACKSPACE)

    def __init__(self, mode, picks, difficulty):
        self.mode = mode
        self.cursor = list(picks)       # índice no elenco de cada lado
        self.locked = [False, False]
        self.lock_order = []            # para desfazer o último "PRONTO" com Esc/Backspace
        self.lock_time = [0, 0]
        self.difficulty = DIFFICULTIES.index(difficulty)
        self.ready_time = None          # quando os dois lados confirmaram
        self.areas = []                 # (retângulo, ação, argumento) clicáveis do último desenho

    # ---------- regras ----------
    def active_side(self):
        """No modo CPU, o P1 controla um lado por vez (None quando os dois já confirmaram)."""
        for side in (0, 1):
            if not self.locked[side]:
                return side
        return None

    def can_control(self, side):
        if self.locked[side]:
            return False
        return self.mode == MODE_VERSUS or side == self.active_side()

    def cycle(self, side, step):
        if self.can_control(side):
            self.cursor[side] = (self.cursor[side] + step) % len(CHARACTERS)

    def lock(self, side):
        if self.can_control(side):
            self.locked[side] = True
            self.lock_order.append(side)
            self.lock_time[side] = pygame.time.get_ticks()
            if all(self.locked):
                self.ready_time = pygame.time.get_ticks()

    def unlock(self, side):
        # no modo CPU só dá para desfazer na ordem inversa (CPU antes do P1)
        if self.locked[side] and (self.mode == MODE_VERSUS or self.lock_order[-1] == side):
            self.locked[side] = False
            self.lock_order.remove(side)
            self.ready_time = None

    def unlock_last(self):
        """Desfaz o último "PRONTO". Retorna False se não havia nada para desfazer."""
        if not self.lock_order:
            return False
        self.unlock(self.lock_order[-1])
        return True

    def set_difficulty(self, index):
        if self.mode == MODE_CPU and not self.locked[1]:
            self.difficulty = max(0, min(len(DIFFICULTIES) - 1, index))

    def ready(self):
        return self.ready_time is not None and pygame.time.get_ticks() - self.ready_time >= READY_FLASH_MS

    def difficulty_key(self):
        return DIFFICULTIES[self.difficulty]

    # ---------- entrada ----------
    def handle_event(self, event):
        """Retorna "back" quando o jogador quer voltar ao menu principal."""
        if event.type == pygame.KEYDOWN:
            return self._handle_key(event.key)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_click(event.pos)
        return None

    def _handle_key(self, key):
        if key in self.BACK_KEYS:
            return None if self.unlock_last() else "back"
        if self.mode == MODE_CPU:
            side = self.active_side()
            if side is None:
                return None
            if key in (pygame.K_a, pygame.K_LEFT):
                self.cycle(side, -1)
            elif key in (pygame.K_d, pygame.K_RIGHT):
                self.cycle(side, 1)
            elif key in (pygame.K_w, pygame.K_UP):
                self.set_difficulty(self.difficulty + 1)
            elif key in (pygame.K_s, pygame.K_DOWN):
                self.set_difficulty(self.difficulty - 1)
            elif key in self.P1_KEYS["confirm"] + self.P2_KEYS["confirm"]:
                self.lock(side)
        else:
            for side, keys in enumerate((self.P1_KEYS, self.P2_KEYS)):
                if key in keys["prev"]:
                    self.cycle(side, -1)
                elif key in keys["next"]:
                    self.cycle(side, 1)
                elif key in keys["confirm"]:
                    self.lock(side)
        return None

    def _handle_click(self, pos):
        for rect, action, arg in self.areas:
            if not rect.collidepoint(pos):
                continue
            if action == "back":
                return None if self.unlock_last() else "back"
            if action == "arrow":
                self.cycle(*arg)
            elif action == "diff":
                self.set_difficulty(arg)
            elif action == "panel":
                if self.locked[arg]:
                    self.unlock(arg)
                else:
                    self.lock(arg)
            return None
        return None

    # ---------- desenho ----------
    def draw(self):
        now = pygame.time.get_ticks()
        mouse = pygame.mouse.get_pos()
        self.areas = []
        screen.fill(BLACK)
        screen.blit(menu_image, (0, 0))

        draw_text("Escolha seu lutador", menu_font, YELLOW, SCREEN_WIDTH // 2, 38, "center", shadow=True)
        back_area = pygame.Rect(14, 20, 120, 36)
        back_color = YELLOW if back_area.collidepoint(mouse) else LIGHT_GRAY
        draw_arrow((32, 38), -1, 9, back_color)
        draw_text("Voltar", small_font, back_color, 48, 38, "midleft", shadow=True)
        self.areas.append((back_area, "back", None))

        for side in (0, 1):
            self._draw_panel(side, now, mouse)
        draw_text("VS", menu_font, RED, SCREEN_WIDTH // 2, SELECT_PANEL_Y + 190, "center", shadow=True)
        self._draw_footer(mouse)

        if self.ready_time is not None:
            t = (now - self.ready_time) / READY_FLASH_MS
            screen.blit(banner_band, (0, 200))
            draw_banner("PRONTO!", title_font, YELLOW, 300, scale=1 + 0.4 * max(0.0, 1 - t * 4))

    def _draw_panel(self, side, now, mouse):
        char = CHARACTERS[self.cursor[side]]
        is_cpu = self.mode == MODE_CPU and side == 1
        color = CPU_COLOR if is_cpu else (P1_COLOR, P2_COLOR)[side]
        active = self.can_control(side)
        locked = self.locked[side]
        blink = (now // 400) % 2 == 0
        panel = pygame.Rect(SELECT_PANEL_X[side], SELECT_PANEL_Y, SELECT_PANEL_W, SELECT_PANEL_H)

        screen.blit(panel_bg, panel)
        border = YELLOW if locked else color if active else GRAY
        pygame.draw.rect(screen, border, panel, 4 if active or locked else 2, border_radius=14)

        # cabeçalho: quem escolhe e o estado
        badge = draw_badge("CPU" if is_cpu else f"P{side + 1}", color, panel.x + 16, panel.y + 14)
        label = "Computador" if is_cpu else f"Jogador {side + 1}"
        draw_text(label, small_font, WHITE, badge.right + 10, badge.centery, "midleft")
        if locked:
            status, status_color = "PRONTO!", YELLOW
        elif active:
            status, status_color = "Escolhendo", WHITE if blink else GRAY
        else:
            status, status_color = "Aguarde", GRAY
        draw_text(status, small_font, status_color, panel.right - 16, badge.centery, "midright")

        # sprite animado, virado para o centro
        alt = side == 1 and self.cursor[0] == self.cursor[1]
        frames = preview_frames[(char["id"], side, alt)]
        frame = frames[(now // PREVIEW_FRAME_MS) % len(frames)]
        lock_flash = 1 - (now - self.lock_time[side]) / 250
        if locked and lock_flash > 0:
            frame = frame.copy()
            glow = int(170 * lock_flash)
            frame.fill((glow, glow, glow), special_flags=pygame.BLEND_RGB_ADD)
        elif not active and not locked:
            frame = frame.copy()
            frame.fill((110, 110, 110), special_flags=pygame.BLEND_RGB_MULT)
        sprite_pos = (panel.x + 130 if side == 0 else panel.x + 10, panel.y + 34)
        screen.blit(preview_shadow, preview_shadow.get_rect(center=(sprite_pos[0] + PREVIEW_SIZE // 2, panel.y + 320)))
        screen.blit(frame, sprite_pos)

        # atributos no lado de fora do painel
        stats_x = panel.x + 22 if side == 0 else panel.right - 22 - STAT_BAR_W
        for i, (stat_label, key, lo, hi) in enumerate(STAT_BARS):
            y = panel.y + 92 + i * 54
            draw_text(stat_label, tiny_font, LIGHT_GRAY, stats_x, y)
            bar = pygame.Rect(stats_x, y + 24, STAT_BAR_W, 12)
            fill = bar.copy()
            fill.width = int(bar.width * stat_ratio(char["stats"], key, lo, hi))
            pygame.draw.rect(screen, DARK_GRAY, bar, border_radius=4)
            pygame.draw.rect(screen, color, fill, border_radius=4)
            pygame.draw.rect(screen, BLACK, bar, 1, border_radius=4)

        # nome com setas para trocar
        name_color = YELLOW if locked else WHITE
        draw_text(char["name"].upper(), name_font, name_color, panel.centerx, panel.y + 350, "center", shadow=True)
        if active:
            nudge = round(3 * math.sin(now / 150))  # setas "respiram" para mostrar que dá pra trocar
            for step in (-1, 1):
                center = (panel.centerx + step * (150 + nudge), panel.y + 350)
                hover = pygame.Rect(0, 0, 48, 48).move(center[0] - 24, center[1] - 24).collidepoint(mouse)
                area = draw_arrow(center, step, 14, YELLOW if hover else WHITE)
                self.areas.append((area.inflate(8, 8), "arrow", (side, step)))
        draw_text(char["tagline"], small_font, LIGHT_GRAY, panel.centerx, panel.y + 390, "center")

        if active or locked:
            self.areas.append((panel, "panel", side))

    def _draw_footer(self, mouse):
        y = SELECT_PANEL_Y + SELECT_PANEL_H + 30
        if self.mode == MODE_VERSUS:
            draw_text("A/D trocar  •  R/T/Espaço confirmar", tiny_font, LIGHT_GRAY, 250, y, "center", shadow=True)
            draw_text("Setas trocar  •  N/M/Enter confirmar", tiny_font, LIGHT_GRAY, 750, y, "center", shadow=True)
            hint = "Esc/Backspace: desfazer/voltar  •  Clique no painel para confirmar"
        else:
            step = "Escolha seu lutador" if not self.locked[0] else "Escolha a CPU"
            draw_text(f"{step}:  A/D trocar  •  Espaço confirmar", tiny_font, LIGHT_GRAY, 250, y, "center",
                      shadow=True)
            self._draw_difficulty(y, mouse)
            hint = "W/S: dificuldade  •  Esc/Backspace: desfazer/voltar"
        draw_text(hint, tiny_font, GRAY, SCREEN_WIDTH // 2, 578, "center", shadow=True)

    def _draw_difficulty(self, y, mouse):
        editable = not self.locked[1]
        draw_text("Dificuldade", tiny_font, WHITE, 540, y, "midleft", shadow=True)
        for i, key in enumerate(DIFFICULTIES):
            rect = pygame.Rect(0, 0, 96, 34)
            rect.center = (702 + i * 104, y)
            selected = i == self.difficulty
            hover = editable and rect.collidepoint(mouse)
            pygame.draw.rect(screen, CPU_COLOR if selected else DARK_GRAY, rect, border_radius=8)
            pygame.draw.rect(screen, YELLOW if selected or hover else GRAY, rect, 2, border_radius=8)
            draw_text(DIFFICULTY_LABELS[key], small_font, WHITE if selected else LIGHT_GRAY,
                      rect.centerx, rect.centery, "center")
            if editable:
                self.areas.append((rect, "diff", i))


# ---------------- JOGO ----------------
CONTROL_HINTS = (
    "P1:  A/D andar  •  W pular  •  R/T golpes",
    "P2:  Setas andar e pular  •  N/M golpes",
    "Segure para trás para defender  •  F1 hitboxes  •  F11 tela cheia",
)


class Game:
    """Máquina de estados: MAIN_MENU -> CHAR_SELECT -> FIGHT <-> PAUSE -> MATCH_OVER."""

    def __init__(self):
        self.state = MAIN_MENU
        self.running = True
        self.mode = MODE_CPU
        self.picks = [0, 1]          # índice no elenco (P1, P2/CPU); lembrado entre partidas
        self.difficulty = "normal"
        self.select = None
        self.match = None
        self.selected = 0            # opção destacada no menu do estado atual
        self.option_rects = []
        self.pause_start = 0

    def set_state(self, state):
        self.state = state
        self.selected = 0
        self.option_rects = []

    def menu_options(self):
        if self.state == MAIN_MENU:
            return ["1P vs CPU", "1P vs 2P", fullscreen_label(), "Sair"]
        if self.state == PAUSE:
            return ["Continuar", "Trocar lutadores", fullscreen_label(), "Menu principal"]
        return ["Revanche", "Trocar lutadores", "Menu principal"]

    # ---------- transições ----------
    def open_char_select(self, mode):
        self.mode = mode
        self.select = CharSelect(mode, self.picks, self.difficulty)
        self.set_state(CHAR_SELECT)

    def start_match(self):
        p1_id, p2_id = (CHARACTERS[i]["id"] for i in self.picks)
        self.match = Match(self.mode, p1_id, p2_id, self.difficulty)
        self.set_state(FIGHT)

    def pause_game(self):
        self.set_state(PAUSE)
        self.pause_start = pygame.time.get_ticks()

    def resume_game(self):
        """Despausa e 'empurra' os timers para frente, pra contagem/animações não pularem."""
        self.match.shift_timers(pygame.time.get_ticks() - self.pause_start)
        self.set_state(FIGHT)

    # ---------- eventos ----------
    @staticmethod
    def is_pause_toggle(event):
        clicou_pausa = (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                        and PAUSE_BUTTON.collidepoint(event.pos))
        tecla_pausa = event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_p)
        return clicou_pausa or tecla_pausa

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
            toggle_fullscreen()
        elif self.state == CHAR_SELECT:
            if self.select.handle_event(event) == "back":
                self.set_state(MAIN_MENU)
        elif self.state == FIGHT:
            if self.is_pause_toggle(event) or event.type == pygame.WINDOWFOCUSLOST:
                self.pause_game()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
                fighter_module.DEBUG = not fighter_module.DEBUG  # mostra hitboxes
        elif self.state == PAUSE and self.is_pause_toggle(event):
            self.resume_game()
        else:
            self.handle_menu_choice(event)

    def handle_menu_choice(self, event):
        self.selected, escolha = handle_menu_event(event, self.menu_options(), self.option_rects, self.selected)
        if escolha is None:
            return
        if escolha.startswith("Tela cheia"):
            toggle_fullscreen()
        elif escolha == "1P vs CPU":
            self.open_char_select(MODE_CPU)
        elif escolha == "1P vs 2P":
            self.open_char_select(MODE_VERSUS)
        elif escolha == "Sair":
            self.running = False
        elif escolha == "Continuar":
            self.resume_game()
        elif escolha == "Trocar lutadores":
            self.open_char_select(self.mode)
        elif escolha == "Revanche":
            self.start_match()
        elif escolha == "Menu principal":
            self.set_state(MAIN_MENU)

    # ---------- lógica ----------
    def update(self, dt):
        if self.state == CHAR_SELECT and self.select.ready():
            self.picks = list(self.select.cursor)
            self.difficulty = self.select.difficulty_key()
            self.start_match()
        elif self.state in (FIGHT, MATCH_OVER):  # na pausa tudo fica congelado
            self.match.update(dt)
            if self.state == FIGHT and self.match.finished:
                self.set_state(MATCH_OVER)

    # ---------- desenho ----------
    def draw(self):
        if self.state == MAIN_MENU:
            screen.fill(BLACK)
            screen.blit(menu_image, (0, 0))
            draw_text("Falido da Luta", title_font, RED, SCREEN_WIDTH // 2, 150, "center", shadow=True)
            self.option_rects = draw_options(self.menu_options(), self.selected, 285)
        elif self.state == CHAR_SELECT:
            self.select.draw()
        else:
            self.match.draw()
            if self.state == FIGHT:
                draw_pause_button(PAUSE_BUTTON.collidepoint(pygame.mouse.get_pos()))
            elif self.state == PAUSE:
                self.draw_pause_menu()
            else:
                self.draw_match_over()

    def draw_pause_menu(self):
        screen.blit(pause_overlay, (0, 0))
        draw_text("PAUSADO", title_font, YELLOW, SCREEN_WIDTH // 2, 130, "center", shadow=True)
        self.option_rects = draw_options(self.menu_options(), self.selected, 245)
        hints = CONTROL_HINTS if self.mode == MODE_VERSUS else (CONTROL_HINTS[0], CONTROL_HINTS[2])
        for i, hint in enumerate(hints):
            draw_text(hint, tiny_font, LIGHT_GRAY, SCREEN_WIDTH // 2, 578 - (len(hints) - 1 - i) * 22,
                      "center", shadow=True)
        draw_pause_button(True)

    def draw_match_over(self):
        match = self.match
        screen.blit(pause_overlay, (0, 0))
        draw_text(f"{match.fighter_label(match.winner)} venceu!", title_font, YELLOW,
                  SCREEN_WIDTH // 2, 140, "center", shadow=True)
        quem = {"P1": "Jogador 1", "P2": "Jogador 2", "CPU": "Computador"}[match.tags[match.winner]]
        if match.mode == MODE_CPU:
            quem += "  •  " + DIFFICULTY_LABELS[match.cpu_diff]
        draw_text(f"{quem}  •  Placar {match.score[0]} x {match.score[1]}", score_font, WHITE,
                  SCREEN_WIDTH // 2, 215, "center", shadow=True)
        self.option_rects = draw_options(self.menu_options(), self.selected, 320)

    # ---------- loop ----------
    def run(self):
        while self.running:
            dt = relogio.tick(FPS)  # limita a 60 FPS
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()


if __name__ == "__main__":
    Game().run()
