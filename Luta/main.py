import json
import math
import os
import random
import socket
import unicodedata
import zlib

import pygame

import audio
import fighter as fighter_module
from online import DEFAULT_PORT, RELAY_PORT, NetSession, local_addresses, parse_address
from fighter import (CHARACTERS, CHARACTERS_BY_ID, CONTROLS, DASH_COST, DIFFICULTIES, DIFFICULTY_LABELS, FRAME_MS,
                     GROUND_MARGIN, SUPER, SUPER_MAX, Fighter, apply_alt_palette, get_frames, get_sounds,
                     get_super_fx, keyboard_buttons, pack_buttons, preload_characters, unpack_buttons)

audio.pre_init()
pygame.init()
audio.setup()

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
ONLINE_MENU = "ONLINE_MENU"      # criar sala / entrar pelo IP / sala no servidor
ONLINE_FORM = "ONLINE_FORM"      # digitando IP ou código da sala
ONLINE_WAIT = "ONLINE_WAIT"      # esperando o outro jogador / conectando
ONLINE_SELECT = "ONLINE_SELECT"  # seleção de lutadores com o outro jogador
ONLINE_ERROR = "ONLINE_ERROR"    # aviso (conexão caiu, versão diferente...)

# MODOS
MODE_CPU = "cpu"
MODE_VERSUS = "versus"
MODE_ONLINE = "online"       # cada jogador no seu computador (pasta online/)

# PARTIDA
ROUNDS_TO_WIN = 2            # melhor de 3
ROUND_OVER_COOLDOWN = 2200   # ms (tempo de jogo) entre o nocaute e o próximo round
FIGHT_BANNER_MS = 800        # tempo do "LUTEM!" na tela
READY_FLASH_MS = 900         # tempo do "PRONTO!" antes da luta começar

# SENSAÇÃO DOS GOLPES
HITSTOP_FRAMES = {1: 3, 2: 5, SUPER: 12}   # congelamento ao acertar (rápido / forte / SUPER)
PARRY_HITSTOP_FRAMES = 12
LAUNCH_HITSTOP_FRAMES = 6            # lançamento do SUPER aéreo
KO_HITSTOP_FRAMES = 16
SUPER_FREEZE_FRAMES = 36             # o jogo congela com a tela escura quando alguém solta o SUPER
SUPER_DIM_ALPHA = 200
SIGNAL_SOUNDS = {"atk1": "atk1", "atk2": "atk2", "super_start": "super"}  # aviso do lutador -> som dele
SLOWMO_FRAMES = 70                   # duração da câmera lenta do nocaute (frames reais)
SLOWMO_SCALE = 0.35                  # o jogo anda a 35% da velocidade
SHAKE_MARGIN = 12                    # sobra do fundo para o tremor não mostrar bordas
HIT_COLORS = ((255, 255, 255), (255, 240, 120), (255, 200, 40), (255, 140, 20))
PARRY_COLORS = ((255, 255, 255), (170, 220, 255), (90, 170, 255))
PARRY_TEXT_COLOR = (140, 210, 255)

# SUPER SÔNICO (Zuzu): tudo treme
MULTI_HITSTOP_FRAMES = 3     # congelamento de cada acerto do meio da rajada
SONIC_RING_EVERY = 3         # frames entre uma onda sonora e outra
SONIC_RING_TIME = 36         # por quanto tempo saem ondas depois do estouro
SONIC_RING_SPEED = 15        # px por frame
SONIC_RING_LIFE = 44
SONIC_RING_SPAN = 0.95       # meia abertura do arco da onda (radianos)
SONIC_AFTER = 70             # frames que o efeito ainda dura depois da última onda
SONIC_MAGENTA = (255, 70, 200)   # franjas da onda (separação de cores)
SONIC_CYAN = (70, 230, 255)
QUAKE_MAX = 14               # px do tremor da tela INTEIRA (com o HUD) no máximo
QUAKE_CHARGE = 0.55          # até onde o tremor sobe enquanto o SUPER carrega
QUAKE_DECAY = 0.965
ZOOM_DECAY = 0.92
CHROMA_DECAY = 0.85
RIPPLE_DECAY = 0.975
RIPPLE_STRIP = 6             # altura das faixas do cenário ondulando
CUTIN_H = 170                # altura da faixa cinematográfica
GLINT_COLOR = (150, 235, 255)   # brilho dos óculos (Caio): no lutador e, maior, no retrato da faixa
GLINT_SIZE = 46
CUTIN_GLINT_SIZE = 75
ROOF_Y = (70, 135)           # de onde cai a poeira do teto
FLOOR_Y = (440, 596)         # onde pulam as pedrinhas do chão
DEBRIS_COLORS = ((150, 132, 112), (118, 108, 96), (92, 82, 72), (175, 160, 140))
DUST_COLORS = ((214, 208, 196), (190, 184, 172), (160, 152, 140))

# HUD
STAMINA_COLOR = (70, 210, 110)
STAMINA_LOW_COLOR = (230, 140, 40)   # abaixo do custo do dash
SUPER_COLOR = (255, 150, 20)
SUPER_FULL_COLOR = (255, 245, 150)
SUPER_BAR_W = 280
SUPER_KEYS = ("Y", "Vírgula")        # tecla do SUPER de cada jogador (mostrada na barra)

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
    ("Vida", "max_health", 90, 115),
    ("Velocidade", "speed", 6, 9),
    ("Pulo", "jump_vel", 25, 32),
    ("Força", "dmg_mult", 0.9, 1.25),
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
# Tela escura do SUPER (fica atrás dos lutadores)
dim_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
dim_overlay.fill((12, 6, 24))
# Camada transparente das ondas sonoras (limpa e redesenhada a cada frame)
sonic_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
# Câmera do SUPER sônico: superfícies criadas uma vez só (criar/copiar/pintar a tela inteira
# todo frame custa caro; blit é quase de graça). Cabem até 30% de zoom.
POST_SIZE = (int(SCREEN_WIDTH * 1.3), int(SCREEN_HEIGHT * 1.3))
post_frame = pygame.Surface(POST_SIZE).convert()
post_red = pygame.Surface(POST_SIZE).convert()
red_mask = pygame.Surface(POST_SIZE).convert()
red_mask.fill((255, 0, 0))
cyan_mask = pygame.Surface(POST_SIZE).convert()
cyan_mask.fill((0, 255, 255))
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
    # Todos usam a mesma proporção da luta (tomando o primeiro personagem como referência),
    # alinhados pelo offset: assim um lutador mais alto também aparece mais alto na seleção.
    ref_size, ref_scale, ref_offset = CHARACTERS[0]["data"]
    k = PREVIEW_SIZE / int(ref_size * ref_scale)
    previews = {}
    for char in CHARACTERS:
        offset = char["data"][2]
        pos = ((ref_offset[0] - offset[0]) * k, (ref_offset[1] - offset[1]) * k)
        idle = []
        for frame in get_frames(char["id"])[0]:
            size = round(frame.get_width() * k)
            canvas = pygame.Surface((PREVIEW_SIZE, PREVIEW_SIZE), pygame.SRCALPHA)
            canvas.blit(pygame.transform.smoothscale(frame, (size, size)), pos)
            idle.append(canvas)
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


BACK_CHOICES = ("Voltar", "Sair", "Sair da sala", "Menu principal")


def handle_menu_event(event, options, rects, selected):
    """Navegação por teclado/mouse. Retorna (nova seleção, opção escolhida ou None)."""
    before = selected
    selected, choice = _menu_navigation(event, options, rects, selected)
    if choice is not None:
        audio.play("back" if choice in BACK_CHOICES else "confirm")
    elif selected != before:
        audio.play("hover")
    return selected, choice


def _menu_navigation(event, options, rects, selected):
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


def draw_stamina_bar(fighter, x, y, mirrored=False):
    """Barra fina de estamina embaixo da vida; o tamanho mostra a estamina máxima do personagem.
    O risco branco marca o custo do dash."""
    width, height = int(2.6 * fighter.max_stamina), 8
    if mirrored:
        x = x + 400 - width
    pygame.draw.rect(screen, BLACK, (x - 2, y - 2, width + 4, height + 4))
    pygame.draw.rect(screen, DARK_GRAY, (x, y, width, height))
    fill = int(width * fighter.stamina / fighter.max_stamina)
    color = STAMINA_COLOR if fighter.stamina >= DASH_COST else STAMINA_LOW_COLOR
    pygame.draw.rect(screen, color, (x + width - fill if mirrored else x, y, fill, height))
    mark = int(width * DASH_COST / fighter.max_stamina)
    mark_x = x + width - mark if mirrored else x + mark
    pygame.draw.line(screen, WHITE, (mark_x, y), (mark_x, y + height - 1))


def draw_super_bar(fighter, side, key_label):
    """Barra de SUPER no canto de baixo; cheia, ela pulsa e mostra a tecla."""
    now = pygame.time.get_ticks()
    width, height, y = SUPER_BAR_W, 16, 562
    x = 20 if side == 0 else SCREEN_WIDTH - 20 - width
    full = fighter.super_meter >= SUPER_MAX
    pygame.draw.rect(screen, BLACK, (x - 3, y - 3, width + 6, height + 6), border_radius=6)
    pygame.draw.rect(screen, DARK_GRAY, (x, y, width, height), border_radius=4)
    fill = int(width * fighter.super_meter / SUPER_MAX)
    if full:
        pulse = (math.sin(now / 90) + 1) / 2
        color = tuple(int(a + (b - a) * pulse) for a, b in zip(SUPER_COLOR, SUPER_FULL_COLOR))
    else:
        color = SUPER_COLOR
    if fill > 0:
        pygame.draw.rect(screen, color, (x + width - fill if side == 1 else x, y, fill, height), border_radius=4)
    for i in range(1, 4):  # divisões em quartos
        div_x = x + width * i // 4
        pygame.draw.line(screen, BLACK, (div_x, y), (div_x, y + height - 1), 2)

    anchor, label_x = ("bottomleft", x) if side == 0 else ("bottomright", x + width)
    if full:
        label = "SUPER PRONTO!" + (f" [{key_label}]" if key_label else "")
        label_color = YELLOW if (now // 250) % 2 == 0 else WHITE
    else:
        label, label_color = "SUPER", LIGHT_GRAY
    draw_text(label, tiny_font, label_color, label_x, y - 4, anchor, shadow=True)


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


class Popup:
    """Texto que sobe e some (PARRY!, SUPER!)."""
    __slots__ = ("image", "x", "y", "life", "max_life")

    def __init__(self, image, x, y, life=40):
        self.image = image
        self.x, self.y = x, y
        self.life = self.max_life = life


class SpriteAnim:
    """Animação de sprite solta no cenário (onda do SUPER). x, y = canto de cima à esquerda."""
    __slots__ = ("frames", "x", "y", "ticks", "age")

    def __init__(self, frames, x, y, ticks):
        self.frames = frames
        self.x, self.y = x, y
        self.ticks = ticks  # frames reais por imagem
        self.age = 0


class SonicRing:
    """Onda sonora: arco grosso que cresce a partir da cabeça, com franjas magenta e ciano.
    span = meia abertura do arco; com span >= pi vira um anel completo."""
    __slots__ = ("x", "y", "angle", "span", "speed", "width", "age", "life", "color")

    def __init__(self, x, y, angle, color, span=SONIC_RING_SPAN, speed=SONIC_RING_SPEED,
                 width=12, life=SONIC_RING_LIFE):
        self.x, self.y = x, y
        self.angle, self.span = angle, span
        self.speed, self.width = speed, width
        self.color = color
        self.age = 0
        self.life = life


class GroundRing:
    """Anel achatado no chão (o chão vibrando em volta dos pés)."""
    __slots__ = ("x", "y", "color", "age", "life", "size")

    def __init__(self, x, y, color, size=280, life=34):
        self.x, self.y = x, y
        self.color = color
        self.size = size
        self.age = 0
        self.life = life


class Debris:
    """Pedrinha que pula do chão (quica uma vez) ou poeira que cai do teto (floor=None)."""
    __slots__ = ("x", "y", "vx", "vy", "gravity", "floor", "life", "max_life", "size", "color", "bounced")

    def __init__(self, x, y, vx, vy, gravity, floor, life, size, color):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.gravity = gravity
        self.floor = floor
        self.life = self.max_life = life
        self.size = size
        self.color = color
        self.bounced = False


def arc_points(cx, cy, radius, width, angle, span, steps=20):
    """Polígono de um arco grosso (pedaço de anel) em volta de (cx, cy)."""
    outer, inner = radius + width / 2, max(1.0, radius - width / 2)
    angles = [angle - span + 2 * span * i / steps for i in range(steps + 1)]
    points = [(cx + math.cos(a) * outer, cy + math.sin(a) * outer) for a in angles]
    points += [(cx + math.cos(a) * inner, cy + math.sin(a) * inner) for a in reversed(angles)]
    return points


def star_points(cx, cy, outer, inner, points, angle):
    pts = []
    for i in range(points * 2):
        radius = outer if i % 2 == 0 else inner
        a = angle + i * math.pi / points
        pts.append((cx + math.cos(a) * radius, cy + math.sin(a) * radius))
    return pts


class Glint:
    """Brilho de lente (óculos do Caio): estrela fina que abre, pulsa girando devagar e fecha."""
    __slots__ = ("x", "y", "size", "life", "max_life")

    def __init__(self, x, y, size, life):
        self.x, self.y = x, y
        self.size = size
        self.life = self.max_life = life


def glint_shape(t, age):
    """Tamanho (0..1) e ângulo do brilho em t = 0 -> 1 da vida dele."""
    grow = 1 - (1 - min(1.0, t / 0.12)) ** 3
    fade = min(1.0, (1 - t) / 0.2)
    return grow * fade * (1 + 0.12 * math.sin(age * 0.5)), 0.15 + t * 1.1


def draw_glint(surface, x, y, size, angle, color):
    """Estrela de 4 pontas comprida com raios menores na diagonal e miolo branco."""
    if size < 2:
        return
    pygame.draw.polygon(surface, color, star_points(x, y, size, size * 0.13, 4, angle))
    pygame.draw.polygon(surface, WHITE, star_points(x, y, size * 0.75, size * 0.07, 4, angle))
    pygame.draw.polygon(surface, WHITE, star_points(x, y, size * 0.42, size * 0.07, 4, angle + math.pi / 4))
    pygame.draw.circle(surface, WHITE, (x, y), max(2, size * 0.13))


class Effects:
    """Faíscas, tremor de tela, clarão, hitstop e câmera lenta de uma luta.

    Além do tremor do cenário (shake), há a "câmera" do SUPER sônico, aplicada na tela pronta
    (post_process): tremor da tela inteira com o HUD, zoom no ponto de foco e separação de cores.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.sparks = []
        self.impacts = []
        self.popups = []
        self.anims = []
        self.rings = []         # ondas sonoras
        self.ground_rings = []
        self.debris = []        # pedrinhas do chão e poeira do teto
        self.glints = []        # brilho dos óculos
        self.sonic = None       # rajada sônica em andamento
        self.combo = 0          # acertos seguidos do SUPER (rajada, furadas do chapéu)
        self.cutin = None       # faixa cinematográfica do SUPER
        self.hitstop = 0        # frames com o jogo congelado
        self.slowmo = 0         # frames restantes de câmera lenta
        self.slow_acc = 0.0
        self.flash = 0          # transparência do clarão branco
        self.dim = 0            # transparência da tela escura do SUPER
        self.dim_hold = 0
        self.shake_power = 0
        self.shake_frames = 0
        self.shake_total = 1
        self.quake = 0.0        # tremor da tela inteira, com o HUD (0..1)
        self.quake_build = False
        self.quake_xy = (0, 0)
        self.zoom = 0.0         # zoom extra da câmera (0.1 = 10%)
        self.focus = (SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        self.chroma = 0.0       # separação de cores (px)
        self.ripple = 0.0       # cenário ondulando (0..1)
        self.ripple_t = 0

    def popup(self, text, color, x, y, font=score_font):
        img = render_text(text, font, color)
        surf = pygame.Surface((img.get_width() + 3, img.get_height() + 3), pygame.SRCALPHA)
        surf.blit(render_text(text, font, BLACK), (3, 3))
        surf.blit(img, (0, 0))
        self.popups.append(Popup(surf, x, y))

    @staticmethod
    def palette(color):
        """Cores das faíscas a partir da cor do SUPER: branco, clarinho e a cor."""
        if color is None:
            return HIT_COLORS
        light = tuple(min(255, c + (255 - c) // 2) for c in color)
        return (WHITE, light, color)

    def on_hit(self, event):
        x, y = event.pos
        if event.kind == "parry":
            audio.play("parry")
            self.hitstop = max(self.hitstop, PARRY_HITSTOP_FRAMES)
            # as faíscas voltam na direção de quem atacou
            self._burst(x, y, -event.direction, PARRY_COLORS, 24, (4, 12), 1.4)
            self.impacts.append(Impact(x, y, 70, (150, 210, 255), star=False, life=16))
            self.impacts.append(Impact(x, y, 36, WHITE, star=False, life=10))
            self._shake(4, 8)
            self.popup("PARRY!", PARRY_TEXT_COLOR, x, y - 50)
            return
        if event.kind == "launch":
            # explosão no chão que joga os dois para cima
            self.hitstop = max(self.hitstop, LAUNCH_HITSTOP_FRAMES)
            self._burst(x, y, event.direction, self.palette(event.color), 30, (6, 16), 0.6, angle=-math.pi / 2)
            self.impacts.append(Impact(x, y, 90, event.color, star=False, life=16))
            self.impacts.append(Impact(x, y, 50, WHITE, star=False, life=10))
            self._shake(6, 12)
        elif event.kind == "multi":
            # acerto do meio de uma sequência do SUPER (rajada sônica, furadas do chapéu)
            self.hitstop = max(self.hitstop, MULTI_HITSTOP_FRAMES)
            self.combo += 1
            self._burst(x, y, event.direction, self.palette(event.color), 12, (3, 10), 1.1)
            self.impacts.append(Impact(x, y, 44, event.color or WHITE, star=False, life=10))
            if self.sonic is not None:  # rajada: cada acerto sacode mais a tela inteira
                self.quake = min(1.0, self.quake + 0.25)
                self.chroma = max(self.chroma, 4.0)
                self.zoom = min(0.16, self.zoom + 0.015)
            else:
                self._shake(3, 6)
            self.popup(str(self.combo), WHITE, x + random.randint(-24, 24), y - 70)
        else:
            heavy = event.attack_type >= 2
            is_super = event.attack_type == SUPER
            self.hitstop = max(self.hitstop, HITSTOP_FRAMES[event.attack_type])
            self._burst(x, y, event.direction, self.palette(event.color), 16 + 12 * heavy + 20 * is_super,
                        (4, 11 + 5 * heavy + 6 * is_super), 0.9 + 0.6 * is_super)
            self.impacts.append(Impact(x, y, 46 + 24 * heavy + 40 * is_super, WHITE, star=True))
            self._shake(3 + 3 * heavy + 5 * is_super, 8 + 6 * heavy + 10 * is_super)
            if is_super and self.combo:
                # último acerto de uma sequência: o maior de todos
                self.combo += 1
                self.popup(f"{self.combo} ACERTOS!", event.color or YELLOW, x, y - 100, menu_font)
                self.combo = 0
            if is_super and self.sonic is not None:
                self.rings.append(SonicRing(x, y, 0.0, WHITE, span=math.pi, speed=22, width=14, life=26))
                self.quake = 1.0
                self.chroma = max(self.chroma, 10.0)
                self.zoom = min(0.18, self.zoom + 0.06)
                self.flash = max(self.flash, 120)
        if event.ko:
            self.hitstop = KO_HITSTOP_FRAMES
            self.slowmo = SLOWMO_FRAMES
            self.slow_acc = 0.0
            self.flash = 220
            self._burst(x, y, event.direction, HIT_COLORS, 40, (6, 18), math.pi)
            self.impacts.append(Impact(x, y, 120, YELLOW, star=True, life=18))
            self._shake(10, 28)

    def on_super_start(self, fighter):
        """Congela o jogo com a tela escura enquanto o lutador junta energia."""
        data = fighter.super_data or {}
        freeze = data.get("freeze", SUPER_FREEZE_FRAMES)
        self.hitstop = max(self.hitstop, freeze)
        self.dim = SUPER_DIM_ALPHA
        self.dim_hold = freeze
        cx, cy = fighter.rect.centerx, fighter.rect.centery
        self.impacts.append(Impact(cx, cy, 190, fighter.super_color, star=False, life=24))
        self.impacts.append(Impact(cx, cy, 120, WHITE, star=False, life=16))
        self._burst(cx, cy, 1, self.palette(fighter.super_color), 18, (3, 9), math.pi)
        self.popup("SUPER!", YELLOW, cx, fighter.rect.y - 60, menu_font)
        self._shake(3, 10)
        self.combo = 0
        if "glint" in data:  # os óculos brilham durante todo o congelamento
            gx, gy = fighter.super_point(*data["glint"])
            self.glints.append(Glint(gx, gy, GLINT_SIZE, freeze + 8))
        if "cutin" in data:
            self.start_cutin(fighter, data, freeze)
        if fighter.sonic:
            # o chão começa a tremer já na carga, cada vez mais forte até o estouro
            self.quake = max(self.quake, 0.12)
            self.quake_build = True
            self.focus = (cx, cy)

    def start_cutin(self, fighter, data, frames):
        """Faixa cinematográfica: rosto de quem soltou o SUPER e o nome do golpe, cruzando a tela."""
        cut = data["cutin"]
        face = fighter.animation_list[7][cut["frame"]].subsurface(pygame.Rect(cut["box"]))
        scale = CUTIN_H * 1.25 / face.get_height()
        portrait = pygame.transform.smoothscale(face, (round(face.get_width() * scale), round(face.get_height() * scale)))
        if fighter.flip:
            portrait = pygame.transform.flip(portrait, True, False)
        color = fighter.super_color
        name = data.get("name", "SUPER")
        front = render_text(name, title_font, WHITE)
        name_img = pygame.Surface((front.get_width() + 6, front.get_height() + 6), pygame.SRCALPHA)
        name_img.blit(render_text(name, title_font, color), (6, 6))
        name_img.blit(front, (0, 0))
        room = SCREEN_WIDTH - portrait.get_width() - 150  # nome comprido diminui para não cobrir o rosto
        if name_img.get_width() > room:
            ratio = room / name_img.get_width()
            name_img = pygame.transform.smoothscale(name_img, (room, round(name_img.get_height() * ratio)))
        lines = [[random.uniform(0, SCREEN_WIDTH), random.uniform(4, CUTIN_H - 4), random.uniform(80, 280),
                  random.uniform(28, 60), random.choice((1, 1, 2, 3)),
                  random.choice(((255, 255, 255, 150), (*color, 170), (255, 255, 255, 70)))] for _ in range(30)]
        glint = None
        if "glint" in data and cut["frame"] == 0:  # o brilho da lente também aparece no retrato
            box_x, box_y = cut["box"][:2]
            gx = (data["glint"][0] - box_x) * scale
            glint = (portrait.get_width() - gx if fighter.flip else gx, (data["glint"][1] - box_y) * scale)
        self.cutin = {"portrait": portrait, "name": name_img, "color": color, "glint": glint,
                      "label": render_text(fighter.name.upper(), score_font, color),
                      "side": -1 if fighter.flip else 1, "life": frames, "max_life": frames, "lines": lines}

    def on_super_impact(self, fighter, target=None):
        """Frame de impacto do SUPER: onda de choque (sprite do personagem ou genérica)."""
        if fighter.sonic:
            self.start_sonic(fighter, target)
            return
        if fighter.hat is not None:
            self.start_hat(fighter)
            return
        direction = -1 if fighter.flip else 1
        ground = fighter.rect.bottom
        frames = get_super_fx(fighter.character["id"])
        if frames:
            fx = fighter.super_data["fx"]
            width = fx["size"][0]
            front, rise = fx["origin"]
            x = fighter.rect.centerx + direction * front
            if direction < 0:
                frames = [pygame.transform.flip(frame, True, False) for frame in frames]
                x -= width
            self.anims.append(SpriteAnim(frames, x, ground + rise - fx["ground"], fx["frame_ticks"]))
        elif fighter.super_data and "impact" in fighter.super_data:
            # sprite próprio sem efeito separado (a aura já está no desenho): estouro no ponto do golpe
            front, height = fighter.super_data["impact"]
            px, py = fighter.rect.centerx + direction * front, ground - height
            self.impacts.append(Impact(px, py, 120, fighter.super_color, star=False, life=18))
            self._burst(px, py, direction, self.palette(fighter.super_color), 24, (5, 14), 0.7,
                        angle=-math.pi / 2 + direction * 0.5)
        if not frames and (not fighter.super_data or fighter.super_data.get("ground_wave")):
            # explosões correndo pelo chão até o alcance do golpe (também o SUPER genérico)
            reach = fighter.attack_reach(SUPER)
            for i in range(5):
                px = fighter.rect.centerx + direction * (40 + i * reach // 5)
                self.impacts.append(Impact(px, ground - 30, 50 + i * 10, fighter.super_color,
                                           star=not fighter.super_data, life=12 + i * 3))
                self._burst(px, ground - 20, direction, self.palette(fighter.super_color), 6, (3, 9), 1.2)
        self._shake(6, 16)

    def start_sonic(self, fighter, target):
        """ESTOURO: ondas sonoras saindo da cabeça na direção do oponente, e o mundo inteiro treme."""
        direction = -1 if fighter.flip else 1
        front, height = fighter.sonic["origin"]
        x = fighter.rect.centerx + direction * front
        y = fighter.rect.bottom - height
        aim = 0.0
        if target is not None:  # inclina as ondas para o tronco do oponente (com limite)
            reach = max(60, abs(target.rect.centerx - x))
            aim = max(-0.6, min(0.6, math.atan2(target.rect.centery - y, reach)))
        angle = aim if direction > 0 else math.pi - aim
        color = fighter.super_color
        self.sonic = {"x": x, "y": y, "angle": angle, "color": color, "age": 0,
                      "feet": (fighter.rect.centerx, fighter.rect.bottom)}
        self.combo = 0

        self.rings.append(SonicRing(x, y, angle, WHITE, span=math.pi, speed=26, width=16, life=30))
        self.rings.append(SonicRing(x, y, angle, color, span=math.pi, speed=19, width=12, life=36))
        self.rings.append(SonicRing(x, y, angle, WHITE, speed=SONIC_RING_SPEED + 4, width=18))
        self.impacts.append(Impact(x, y, 150, WHITE, star=False, life=16))
        self.impacts.append(Impact(x, y, 90, color, star=False, life=12))
        self._burst(x, y, direction, self.palette(color), 30, (6, 16), 0.9, angle=angle)
        self.ground_rings.append(GroundRing(*self.sonic["feet"], color, size=420, life=40))
        self.flash = max(self.flash, 110)
        self.quake_build = False
        self.quake = 1.0
        self.zoom = max(self.zoom, 0.12)
        self.chroma = max(self.chroma, 10.0)
        self.ripple = 1.0
        if target is not None:  # câmera entre a cabeça dele e o oponente
            self.focus = ((x + target.rect.centerx) / 2, (y + target.rect.centery) / 2)
        else:
            self.focus = (x, y)
        self._shake(10, 30)
        self.spawn_rocks(fighter.rect.centerx, 46)

    def start_hat(self, fighter):
        """Arremesso do chapéu: estouro de energia saindo da mão."""
        hat, color = fighter.hat, fighter.super_color
        self._burst(hat.x, hat.y, hat.direction, self.palette(color), 22, (5, 14), 0.5)
        self.impacts.append(Impact(hat.x, hat.y, 90, color, star=False, life=14))
        self.impacts.append(Impact(hat.x, hat.y, 46, WHITE, star=False, life=10))
        self._shake(4, 10)

    def on_hat_fly(self, fighter):
        """Purpurina caindo atrás do chapéu em voo (chamado a cada frame de jogo)."""
        hat = fighter.hat
        if hat.state == "grind":
            return
        back = -hat.direction if hat.state == "out" else hat.direction  # oposto ao movimento
        colors = self.palette(fighter.super_color)
        for _ in range(2):
            self.sparks.append(Spark(hat.x + random.uniform(-30, 30) * hat.scale,
                                     hat.y + random.uniform(-16, 16) * hat.scale,
                                     back * random.uniform(1, 4), random.uniform(-2.5, 0.5),
                                     random.randint(8, 16), random.choice(colors), 2))

    def on_hat_catch(self, fighter):
        """O chapéu volta para a mão."""
        x, y = fighter.hat_caught_at
        self._burst(x, y, 1, self.palette(fighter.super_color), 14, (2, 7), math.pi)
        self.impacts.append(Impact(x, y, 50, fighter.super_color, star=False, life=12))

    def spawn_rocks(self, center_x, count):
        """Pedrinhas pulando do chão da arena inteira (mais alto perto de quem estourou)."""
        for _ in range(count):
            x = random.uniform(0, SCREEN_WIDTH)
            floor = random.uniform(*FLOOR_Y)
            near = 1 - min(1.0, abs(x - center_x) / SCREEN_WIDTH)
            self.debris.append(Debris(x, floor, random.uniform(-1.5, 1.5), -random.uniform(4, 11) * (0.5 + near),
                                      0.45, floor, random.randint(50, 90), random.randint(2, 5),
                                      random.choice(DEBRIS_COLORS)))

    def on_land(self, fighter):
        """Quem foi lançado pelo SUPER aéreo bate no chão."""
        x, y = fighter.rect.centerx, fighter.rect.bottom - 6
        for direction in (-1, 1):
            self._burst(x, y, direction, ((210, 200, 180), (170, 160, 140), WHITE), 8, (2, 7), 0.4)
        self._shake(5, 10)

    def _burst(self, x, y, direction, colors, count, speed, spread, angle=None):
        """Faíscas saindo de (x, y): para o lado da direção, ou no ângulo dado (radianos)."""
        base = angle if angle is not None else (0.0 if direction > 0 else math.pi)
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
        for popup in self.popups:
            popup.y -= 1.2
            popup.life -= 1
        self.popups = [p for p in self.popups if p.life > 0]
        for anim in self.anims:
            anim.age += 1
        self.anims = [a for a in self.anims if a.age < len(a.frames) * a.ticks]
        for glint in self.glints:
            glint.life -= 1
        self.glints = [g for g in self.glints if g.life > 0]
        if self.shake_frames > 0:
            self.shake_frames -= 1
        self.flash = max(0, self.flash - 12)
        if self.dim_hold > 0:
            self.dim_hold -= 1
        else:
            self.dim = max(0, self.dim - 10)
        self._update_sonic()
        self._update_camera()
        self._update_cutin()

    def _update_sonic(self):
        for ring in self.rings:
            ring.age += 1
        self.rings = [r for r in self.rings if r.age < r.life]
        for ring in self.ground_rings:
            ring.age += 1
        self.ground_rings = [r for r in self.ground_rings if r.age < r.life]
        for d in self.debris:
            d.vy += d.gravity
            d.x += d.vx
            d.y += d.vy
            d.life -= 1
            if d.floor is not None and d.y >= d.floor and d.vy > 0:  # pedrinha quica uma vez e para
                d.y = d.floor
                d.vy = -d.vy * 0.35 if not d.bounced else 0
                d.vx *= 0.6
                d.bounced = True
        self.debris = [d for d in self.debris if d.life > 0]

        sonic = self.sonic
        if sonic is None:
            return
        sonic["age"] += 1
        age = sonic["age"]
        if age <= SONIC_RING_TIME:
            if age % SONIC_RING_EVERY == 0:  # onda sim, onda não: uma branca, uma da cor do golpe
                color = WHITE if (age // SONIC_RING_EVERY) % 2 else sonic["color"]
                self.rings.append(SonicRing(sonic["x"], sonic["y"], sonic["angle"], color))
            if age % 9 == 0:
                self.ground_rings.append(GroundRing(*sonic["feet"], sonic["color"]))
        elif age > SONIC_RING_TIME + SONIC_AFTER:
            self.sonic = None

    def _update_camera(self):
        """Tremor da tela inteira, zoom, separação de cores e cenário ondulando (decaem sozinhos)."""
        if self.quake_build:
            self.quake = min(QUAKE_CHARGE, self.quake + 0.008)
        else:
            self.quake = self.quake * QUAKE_DECAY if self.quake > 0.02 else 0.0
        self.zoom = self.zoom * ZOOM_DECAY if self.zoom > 0.002 else 0.0
        self.chroma = self.chroma * CHROMA_DECAY if self.chroma > 0.5 else 0.0
        self.ripple = self.ripple * RIPPLE_DECAY if self.ripple > 0.02 else 0.0
        self.ripple_t += 1
        # sorteado aqui (e não no desenho) para a tela não tremer com o jogo pausado
        amp = QUAKE_MAX * self.quake
        self.quake_xy = (random.uniform(-amp, amp), random.uniform(-amp, amp) * 0.7) if amp >= 0.5 else (0, 0)
        # com a terra tremendo, cai poeira do teto da quadra
        if self.quake > 0.15:
            for _ in range(int(self.quake * 3 + random.random())):
                self.debris.append(Debris(random.uniform(0, SCREEN_WIDTH), random.uniform(*ROOF_Y),
                                          random.uniform(-0.3, 0.3), random.uniform(0.3, 1.6), 0.05, None,
                                          random.randint(70, 110), random.randint(1, 3), random.choice(DUST_COLORS)))

    def _update_cutin(self):
        cutin = self.cutin
        if cutin is None:
            return
        cutin["life"] -= 1
        for line in cutin["lines"]:  # linhas de velocidade correm contra o retrato
            line[0] -= cutin["side"] * line[3]
            if line[0] < -line[2]:
                line[0] += SCREEN_WIDTH + line[2]
            elif line[0] > SCREEN_WIDTH:
                line[0] -= SCREEN_WIDTH + line[2]
        if cutin["life"] <= 0:
            self.cutin = None

    def shake_offset(self):
        if self.shake_frames <= 0:
            return 0, 0
        amp = round(min(SHAKE_MARGIN, self.shake_power * self.shake_frames / self.shake_total))
        return random.randint(-amp, amp), random.randint(-amp, amp)

    def draw(self, offset):
        ox, oy = offset
        for anim in self.anims:
            screen.blit(anim.frames[anim.age // anim.ticks], (anim.x + ox, anim.y + oy))
        for d in self.debris:
            fade = min(1.0, d.life / 20)
            color = tuple(int(c * (0.4 + 0.6 * fade)) for c in d.color) if d.floor is None else d.color
            pygame.draw.circle(screen, color, (d.x + ox, d.y + oy), d.size)
        self._draw_sonic(ox, oy)
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
        for glint in self.glints:
            size, angle = glint_shape(1 - glint.life / glint.max_life, glint.max_life - glint.life)
            draw_glint(screen, glint.x + ox, glint.y + oy, glint.size * size, angle, GLINT_COLOR)
        for popup in self.popups:
            popup.image.set_alpha(min(255, popup.life * 20))
            screen.blit(popup.image, popup.image.get_rect(center=(popup.x + ox, popup.y + oy)))

    def _draw_sonic(self, ox, oy):
        """Feixe, ondas sonoras e anéis no chão, numa camada transparente."""
        sonic = self.sonic
        beam = sonic is not None and sonic["age"] <= SONIC_RING_TIME
        if not (self.rings or self.ground_rings or beam):
            return
        sonic_overlay.fill((0, 0, 0, 0))
        if beam:  # cone de som saindo da cabeça, pulsando
            pulse = 0.6 + 0.4 * math.sin(sonic["age"] * 0.9)
            x, y, angle = sonic["x"], sonic["y"], sonic["angle"]
            for span, alpha, color in ((0.55, 34, WHITE), (0.28, 60, sonic["color"])):
                points = [(x, y)] + [(x + math.cos(angle + s) * 1400, y + math.sin(angle + s) * 1400)
                                     for s in (-span, span)]
                pygame.draw.polygon(sonic_overlay, (*color, int(alpha * pulse)), points)
        for ring in self.ground_rings:
            t = ring.age / ring.life
            radius = ring.size * (0.15 + 0.85 * t)
            rect = pygame.Rect(0, 0, radius * 2, radius * 0.24)
            rect.center = (ring.x, ring.y)
            pygame.draw.ellipse(sonic_overlay, (*ring.color, int(200 * (1 - t))), rect, max(1, int(5 * (1 - t))))
        for ring in self.rings:
            t = ring.age / ring.life
            radius = 16 + ring.speed * ring.age
            width = max(2.0, ring.width * (1 - t))
            alpha = int(255 * (1 - t) ** 1.3)
            # franja magenta atrás, ciano na frente e a onda por cima: parece som distorcendo
            for shift, color, thick in ((-4, SONIC_MAGENTA, 1.0), (4, SONIC_CYAN, 1.0), (0, ring.color, 0.7)):
                cx = ring.x + math.cos(ring.angle) * shift
                cy = ring.y + math.sin(ring.angle) * shift
                if ring.span >= math.pi:
                    pygame.draw.circle(sonic_overlay, (*color, alpha), (cx, cy), radius, max(1, int(width * thick)))
                else:
                    pygame.draw.polygon(sonic_overlay, (*color, alpha),
                                        arc_points(cx, cy, radius, width * thick, ring.angle, ring.span))
        screen.blit(sonic_overlay, (ox, oy))

    def draw_cutin(self):
        """Faixa cinematográfica durante o congelamento do SUPER (abre, segura e fecha)."""
        cutin = self.cutin
        if cutin is None:
            return
        t = 1 - cutin["life"] / cutin["max_life"]  # 0 -> 1
        opening = 1 - (1 - min(1.0, t / 0.15)) ** 3
        closing = max(0.0, (t - 0.85) / 0.15)
        height = int(CUTIN_H * opening * (1 - closing ** 2))
        if height < 2:
            return
        top = SCREEN_HEIGHT // 2 - height // 2
        color, side = cutin["color"], cutin["side"]
        band = pygame.Surface((SCREEN_WIDTH, height), pygame.SRCALPHA)
        band.fill((14, 8, 30, 225))
        pygame.draw.rect(band, (*color, 45), (0, height // 3, SCREEN_WIDTH, height // 3))
        for x, y, length, _, thick, line_color in cutin["lines"]:
            y = int(y * height / CUTIN_H)
            pygame.draw.line(band, line_color, (x, y), (x + length, y), thick)
        screen.blit(band, (0, top))

        screen.set_clip(pygame.Rect(0, top, SCREEN_WIDTH, height))
        # rosto entra pelo lado de quem soltou o SUPER e continua andando devagar
        portrait = cutin["portrait"]
        width = portrait.get_width()
        slide = 1 - (1 - min(1.0, t / 0.22)) ** 3
        if side > 0:
            px = -width + (width + 30) * slide + 40 * t
        else:
            px = SCREEN_WIDTH - (width + 30) * slide - 40 * t
        py = SCREEN_HEIGHT // 2 - portrait.get_height() // 2 + 12
        screen.blit(portrait, (px, py))
        if cutin["glint"]:  # brilho dos óculos: acende quando o rosto termina de entrar
            gt = max(0.0, (t - 0.18) / 0.82)
            size, angle = glint_shape(gt, cutin["max_life"] - cutin["life"])
            gx, gy = cutin["glint"]
            draw_glint(screen, px + gx, py + gy, CUTIN_GLINT_SIZE * size, angle, GLINT_COLOR)
        # nome do golpe entra pelo outro lado, um pouco depois
        name, label = cutin["name"], cutin["label"]
        slide = 1 - (1 - min(1.0, max(0.0, (t - 0.08) / 0.22))) ** 3
        if side > 0:
            target = SCREEN_WIDTH - name.get_width() - 40
            nx = SCREEN_WIDTH + (target - SCREEN_WIDTH) * slide - 30 * t
        else:
            nx = -name.get_width() + (40 + name.get_width()) * slide + 30 * t
        ny = SCREEN_HEIGHT // 2 - name.get_height() // 2 + 14
        screen.blit(label, (nx + 4, ny - label.get_height() + 10))
        screen.blit(name, (nx, ny))
        screen.set_clip(None)
        for y, line_color in ((top, color), (top + height - 3, color), (top + 4, WHITE), (top + height - 6, WHITE)):
            pygame.draw.line(screen, line_color, (0, y), (SCREEN_WIDTH, y), 3 if line_color == color else 1)

    def post_process(self):
        """Câmera do SUPER sônico na tela pronta: tremor geral (com o HUD), zoom e separação de cores."""
        amp = QUAKE_MAX * self.quake
        shift = int(self.chroma)
        qx, qy = round(self.quake_xy[0]), round(self.quake_xy[1])
        if self.zoom <= 0.004 and shift < 1:
            if qx or qy:  # só tremor: rolar a tela é quase de graça (a borda repete uns pixels)
                screen.scroll(qx, qy)
            return
        # zoom mínimo para o tremor e a separação de cores nunca mostrarem a borda da tela
        zoom = min(1.3, max(1 + self.zoom, 1 + 2 * (amp + shift + 2) / SCREEN_HEIGHT))
        width, height = round(SCREEN_WIDTH * zoom), round(SCREEN_HEIGHT * zoom)
        frame = post_frame.subsurface((0, 0, width, height))
        pygame.transform.scale(screen, (width, height), frame)  # sem suavizar: rápido, e tremendo ninguém nota
        fx, fy = self.focus  # o ponto de foco fica parado na tela enquanto o resto cresce em volta
        x = min(-shift, max(SCREEN_WIDTH - width + shift, round(fx - fx * zoom) + qx))
        y = min(0, max(SCREEN_HEIGHT - height, round(fy - fy * zoom) + qy))
        if shift < 1:
            screen.blit(frame, (x, y))
            return
        # separação de cores: vermelho para um lado, ciano para o outro
        red = post_red.subsurface((0, 0, width, height))
        red.blit(frame, (0, 0))
        red.blit(red_mask, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        frame.blit(cyan_mask, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        screen.blit(frame, (x + shift, y))
        screen.blit(red, (x - shift, y), special_flags=pygame.BLEND_RGB_ADD)

    def draw_dim(self):
        if self.dim > 0:
            dim_overlay.set_alpha(self.dim)
            screen.blit(dim_overlay, (0, 0))

    def draw_flash(self):
        if self.flash > 0:
            flash_overlay.set_alpha(self.flash)
            screen.blit(flash_overlay, (0, 0))


# ---------------- PARTIDA ----------------
class Match:
    """Partida melhor de 3: lutadores, rounds, placar, efeitos e HUD."""

    def __init__(self, mode, p1_id, p2_id, cpu_diff, local_side=None):
        self.mode = mode
        self.local_side = local_side   # online: lado de quem joga neste computador (0 = P1, 1 = P2)
        self.characters = (CHARACTERS_BY_ID[p1_id], CHARACTERS_BY_ID[p2_id])
        self.mirror = p1_id == p2_id
        self.cpu_diff = cpu_diff
        self.tags = ("P1", "CPU" if mode == MODE_CPU else "P2")
        self.colors = (P1_COLOR, CPU_COLOR if mode == MODE_CPU else P2_COLOR)
        self.score = [0, 0]
        self.super_carry = [0, 0]   # a barra de SUPER passa de um round para o outro
        self.round_number = 0
        # relógio de jogo em frames: só anda quando a luta anda (parado na pausa, no hitstop e mais
        # devagar na câmera lenta). Não usa o relógio do computador, então no online os dois
        # jogadores contam exatamente o mesmo tempo.
        self.clock_frames = 0
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
        for f, meter in zip(self.fighters, self.super_carry):
            f.super_meter = meter
        self.intro_count = 3
        audio.play("count")
        self.last_count_update = self.clock_ms()
        self.fight_banner_until = 0
        self.round_over = False
        self.round_over_time = 0
        self.round_winner = None
        self.effects.reset()

    def fighter_label(self, side):
        """Nome para os letreiros; em luta espelho inclui P1/P2/CPU para não confundir."""
        name = self.characters[side]["name"].upper()
        return f"{name} ({self.tags[side]})" if self.mirror else name

    def update(self, inputs=None):
        """Um frame: aplica hitstop/câmera lenta e avança a lógica quando for a vez.
        inputs: (botões do P1, botões do P2) deste frame (online); None = teclado/CPU."""
        fx = self.effects
        fx.update()
        if fx.hitstop > 0:  # frame congelado: os botões dele não são lidos (igual ao teclado)
            fx.hitstop -= 1
            return
        if fx.slowmo > 0:
            fx.slowmo -= 1
            fx.slow_acc += SLOWMO_SCALE
            if fx.slow_acc < 1:
                return
            fx.slow_acc -= 1
        self.step(inputs)

    def checksum(self):
        """Resumo da luta inteira; no online os dois computadores têm que chegar no mesmo número."""
        state = (self.round_number, self.score, self.intro_count, self.round_over, self.finished,
                 self.effects.hitstop, self.effects.slowmo, [f.sync_state() for f in self.fighters])
        return zlib.crc32(repr(state).encode())

    def clock_ms(self):
        return self.clock_frames * FRAME_MS

    def step(self, inputs=None):
        self.clock_frames += 1
        now = self.clock_ms()
        f1, f2 = self.fighters
        if self.intro_count > 0 and now - self.last_count_update >= 1000:
            self.last_count_update = now
            self.intro_count -= 1
            audio.play("count" if self.intro_count else "fight")
            if self.intro_count == 0:
                self.fight_banner_until = now + FIGHT_BANNER_MS

        can_act = self.intro_count <= 0 and not self.round_over and not self.finished
        for side, (attacker, defender) in enumerate(((f1, f2), (f2, f1))):
            held = inputs[side] if inputs else None
            event = attacker.move(SCREEN_WIDTH, SCREEN_HEIGHT, defender, can_act, held)
            if event:
                self.effects.on_hit(event)
            for signal in attacker.pop_signals():
                if signal in SIGNAL_SOUNDS:
                    name = SIGNAL_SOUNDS[signal]
                    audio.play_fighter(get_sounds(attacker.character["id"]).get(name), side, name)
                if signal == "super_start":
                    self.effects.on_super_start(attacker)
                elif signal == "super_impact":
                    self.effects.on_super_impact(attacker, defender)
                elif signal == "land":
                    self.effects.on_land(attacker)
                elif signal == "hat_catch":
                    self.effects.on_hat_catch(attacker)
            if attacker.hat is not None:
                self.effects.on_hat_fly(attacker)
        f1.update()
        f2.update()

        if self.finished:
            return
        if not self.round_over:
            if not f1.alive or not f2.alive:
                self.round_winner = 0 if f1.alive else 1
                self.score[self.round_winner] += 1
                self.super_carry = [f1.super_meter, f2.super_meter]
                self.round_over = True
                self.round_over_time = now
        elif now - self.round_over_time > ROUND_OVER_COOLDOWN:
            if max(self.score) >= ROUNDS_TO_WIN:
                self.finished = True
                self.winner = self.round_winner
            else:
                self.start_round()

    # ---------- desenho ----------
    def draw_background(self, offset):
        """Cenário; durante o SUPER sônico ele ondula em faixas, como se o ar vibrasse."""
        ox, oy = offset
        fx = self.effects
        if fx.ripple <= 0:
            screen.blit(bg_image, (-SHAKE_MARGIN + ox, -SHAKE_MARGIN + oy))
            return
        amp = (SHAKE_MARGIN - 2) * min(1.0, fx.ripple)
        focus_y = fx.focus[1]
        width = bg_image.get_width()
        for y in range(-SHAKE_MARGIN, SCREEN_HEIGHT + SHAKE_MARGIN, RIPPLE_STRIP):
            wave = math.sin((y - focus_y) * 0.045 - fx.ripple_t * 0.55)
            screen.blit(bg_image, (-SHAKE_MARGIN + ox + round(amp * wave), y + oy),
                        (0, y + SHAKE_MARGIN, width, RIPPLE_STRIP))

    def draw(self):
        offset = self.effects.shake_offset()
        ox, oy = offset
        self.draw_background(offset)
        self.effects.draw_dim()

        ground = SCREEN_HEIGHT - GROUND_MARGIN
        for f in self.fighters:
            height = ground - f.rect.bottom
            scale = max(0.45, 1 - height / 320)
            shadow = pygame.transform.smoothscale(shadow_image, (int(150 * scale), int(34 * scale)))
            screen.blit(shadow, shadow.get_rect(center=(f.visual_center_x() + ox, ground - 17 + oy)))

        # quem está atacando fica na frente
        for f in sorted(self.fighters, key=lambda fighter: fighter.attacking):
            f.draw(screen, offset)
        for f in self.fighters:
            f.draw_hat(screen, offset)
        self.effects.draw(offset)
        self.effects.draw_cutin()

        self.draw_hud()
        if not self.finished:
            self.draw_banners()
        self.effects.draw_flash()
        self.effects.post_process()  # por último: o tremor do SUPER sônico sacode até o HUD

    def draw_hud(self):
        for side, f in enumerate(self.fighters):
            bar_x = 20 if side == 0 else 580
            draw_health_bar(f, bar_x, 20, mirrored=side == 1)
            draw_stamina_bar(f, bar_x, 58, mirrored=side == 1)
            name = f.name.upper()
            if side == 0:
                badge = draw_badge(self.tags[0], self.colors[0], 20, 74)
                draw_text(name, score_font, WHITE, badge.right + 10, badge.centery, "midleft", shadow=True)
            else:
                badge = draw_badge(self.tags[1], self.colors[1], SCREEN_WIDTH - 20, 74, "topright")
                draw_text(name, score_font, WHITE, badge.left - 10, badge.centery, "midright", shadow=True)
            # bolinhas de rounds vencidos, perto do centro
            for i in range(ROUNDS_TO_WIN):
                cx = 420 - 12 - i * 28 if side == 0 else 580 + 12 + i * 28
                pygame.draw.circle(screen, BLACK, (cx, 88), 11)
                pygame.draw.circle(screen, YELLOW if i < self.score[side] else DARK_GRAY, (cx, 88), 8)
                pygame.draw.circle(screen, WHITE, (cx, 88), 10, 2)
            # tecla do SUPER: só para quem joga neste teclado
            if self.mode == MODE_ONLINE:
                key_label = SUPER_KEYS[0] if side == self.local_side else None
            else:
                key_label = SUPER_KEYS[side] if self.tags[side] != "CPU" else None
            draw_super_bar(f, side, key_label)
        draw_text(f"Rodada {self.round_number}", tiny_font, WHITE, SCREEN_WIDTH // 2, 88, "center", shadow=True)

    def draw_banners(self):
        now = self.clock_ms()
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
    Online: cada um controla só o seu lado (local_side); o lado do outro vem pela rede (set_remote).
    """
    P1_KEYS = {"prev": (pygame.K_a,), "next": (pygame.K_d,),
               "confirm": (pygame.K_r, pygame.K_t, pygame.K_SPACE)}
    P2_KEYS = {"prev": (pygame.K_LEFT,), "next": (pygame.K_RIGHT,),
               "confirm": (pygame.K_n, pygame.K_m, pygame.K_RETURN, pygame.K_KP_ENTER)}
    BACK_KEYS = (pygame.K_ESCAPE, pygame.K_BACKSPACE)

    def __init__(self, mode, picks, difficulty, local_side=None, net_info=None):
        self.mode = mode
        self.local_side = local_side    # online: 0 (P1) ou 1 (P2)
        self.net_info = net_info        # online: função que devolve o texto de ping
        self.remote_known = False       # online: já chegou o estado do outro?
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
        if self.mode == MODE_ONLINE:
            return side == self.local_side
        return self.mode == MODE_VERSUS or side == self.active_side()

    def cycle(self, side, step):
        if self.can_control(side):
            self.cursor[side] = (self.cursor[side] + step) % len(CHARACTERS)
            audio.play("hover")

    def lock(self, side):
        if self.can_control(side):
            audio.play("ready")
            self.locked[side] = True
            self.lock_order.append(side)
            self.lock_time[side] = pygame.time.get_ticks()
            if all(self.locked):
                self.ready_time = pygame.time.get_ticks()

    def unlock(self, side):
        # no modo CPU só dá para desfazer na ordem inversa (CPU antes do P1); online, só o seu lado
        if self.mode == MODE_ONLINE and side != self.local_side:
            return
        if self.locked[side] and (self.mode != MODE_CPU or self.lock_order[-1] == side):
            audio.play("back")
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
            index = max(0, min(len(DIFFICULTIES) - 1, index))
            if index != self.difficulty:
                audio.play("hover")
            self.difficulty = index

    def ready(self):
        return self.ready_time is not None and pygame.time.get_ticks() - self.ready_time >= READY_FLASH_MS

    def set_remote(self, cursor, locked):
        """Online: o que o outro jogador está escolhendo (chega pela rede)."""
        side = 1 - self.local_side
        self.remote_known = True
        self.cursor[side] = cursor % len(CHARACTERS)
        if locked != self.locked[side]:
            audio.play("ready" if locked else "back")
            self.locked[side] = locked
            self.lock_time[side] = pygame.time.get_ticks()
            if all(self.locked):
                self.ready_time = pygame.time.get_ticks()
            elif not locked:
                self.ready_time = None

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
        if self.mode == MODE_ONLINE:  # qualquer um dos dois conjuntos de teclas
            side = self.local_side
            if key in self.P1_KEYS["prev"] + self.P2_KEYS["prev"]:
                self.cycle(side, -1)
            elif key in self.P1_KEYS["next"] + self.P2_KEYS["next"]:
                self.cycle(side, 1)
            elif key in self.P1_KEYS["confirm"] + self.P2_KEYS["confirm"]:
                self.lock(side)
            return None
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
        if self.mode == MODE_ONLINE:
            label = "Você" if side == self.local_side else "Oponente"
        else:
            label = "Computador" if is_cpu else f"Jogador {side + 1}"
        draw_text(label, small_font, WHITE, badge.right + 10, badge.centery, "midleft")
        remote = self.mode == MODE_ONLINE and side != self.local_side
        if locked:
            status, status_color = "PRONTO!", YELLOW
        elif active:
            status, status_color = "Escolhendo", WHITE if blink else GRAY
        elif remote:
            status, status_color = ("Escolhendo", LIGHT_GRAY) if self.remote_known else ("Conectando", GRAY)
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
        elif not active and not locked and not remote:
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
        if self.mode == MODE_ONLINE:
            draw_text("A/D ou Setas trocar  •  Espaço/Enter confirmar", tiny_font, LIGHT_GRAY,
                      SCREEN_WIDTH // 2, y, "center", shadow=True)
            hint = "Esc: desfazer / sair da sala"
            if self.net_info:
                hint += "  •  " + self.net_info()
        elif self.mode == MODE_VERSUS:
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


# ---------------- ONLINE ----------------
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".falido_da_luta.json")  # últimos IP/sala usados
STALL_NOTICE = 20            # frames travado esperando o outro até mostrar o aviso


def game_fingerprint():
    """Impressão dos arquivos que decidem a luta: no online os dois precisam ter os mesmos
    (senão cada computador calcularia uma luta diferente)."""
    crc = 0
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("fighter.py", "main.py", os.path.join("online", "lockstep.py")):
        with open(os.path.join(here, name), "rb") as f:
            crc = zlib.crc32(f.read().replace(b"\r", b""), crc)  # tanto faz o fim de linha do git
    return crc


GAME_ID = game_fingerprint()


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(config):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def wrap_text(text, font, width):
    """Quebra o texto em linhas que cabem na largura."""
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            attempt = f"{line} {word}".strip()
            if line and font.size(attempt)[0] > width:
                lines.append(line)
                line = word
            else:
                line = attempt
        lines.append(line)
    return lines


class TextForm:
    """Tela com campos de texto (IP, servidor, código da sala).
    Tab/setas trocam de campo, Enter conecta, Esc volta, Ctrl+V cola."""

    def __init__(self, title, fields, notes):
        self.title = title
        self.fields = [list(field) for field in fields]   # [rótulo, valor, tamanho máximo]
        self.notes = notes
        self.active = 0
        self.error = ""
        self.areas = []

    def values(self):
        return [field[1].strip() for field in self.fields]

    def handle_event(self, event):
        """Retorna "ok" (conectar), "back" (voltar) ou None."""
        field = self.fields[self.active]
        if event.type == pygame.TEXTINPUT:
            field[1] = (field[1] + event.text)[:field[2]]
            self.error = ""
            audio.play("type")
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "back"
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return "ok"
            if event.key == pygame.K_BACKSPACE:
                if field[1]:
                    audio.play("type")
                field[1] = field[1][:-1]
                self.error = ""
            elif event.key in (pygame.K_TAB, pygame.K_DOWN):
                self.active = (self.active + 1) % len(self.fields)
                audio.play("hover")
            elif event.key == pygame.K_UP:
                self.active = (self.active - 1) % len(self.fields)
                audio.play("hover")
            elif event.key == pygame.K_v and event.mod & pygame.KMOD_CTRL:
                field[1] = (field[1] + self._clipboard())[:field[2]]
                audio.play("type")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, action in self.areas:
                if rect.collidepoint(event.pos):
                    if isinstance(action, int):
                        if action != self.active:
                            audio.play("hover")
                        self.active = action
                    else:
                        return action
        return None

    @staticmethod
    def _clipboard():
        try:
            text = pygame.scrap.get_text() or ""
        except (AttributeError, pygame.error):
            return ""
        return text.strip().splitlines()[0] if text.strip() else ""

    def draw(self):
        now = pygame.time.get_ticks()
        mouse = pygame.mouse.get_pos()
        self.areas = []
        screen.fill(BLACK)
        screen.blit(menu_image, (0, 0))
        draw_text(self.title, menu_font, YELLOW, SCREEN_WIDTH // 2, 70, "center", shadow=True)
        y = 150
        for i, (label, value, _) in enumerate(self.fields):
            draw_text(label, small_font, LIGHT_GRAY, 200, y)
            box = pygame.Rect(200, y + 30, 600, 48)
            active = i == self.active
            pygame.draw.rect(screen, (20, 20, 28), box, border_radius=8)
            pygame.draw.rect(screen, YELLOW if active else GRAY, box, 3 if active else 2, border_radius=8)
            cursor = "|" if active and (now // 450) % 2 == 0 else ""
            draw_text(value + cursor, score_font, WHITE, box.x + 14, box.centery, "midleft")
            self.areas.append((box, i))
            y += 110
        if self.error:
            for k, line in enumerate(wrap_text(self.error, small_font, 760)):
                draw_text(line, small_font, (255, 110, 110), SCREEN_WIDTH // 2, y + k * 26, "center", shadow=True)
            y += 26 * (k + 1) + 8
        for k, line in enumerate(self.notes):
            draw_text(line, tiny_font, LIGHT_GRAY, SCREEN_WIDTH // 2, y + 10 + k * 24, "center", shadow=True)
        for label, action, x in (("Conectar", "ok", 620), ("Voltar", "back", 380)):
            hover = pygame.Rect(0, 0, 200, 50).move(x - 100, 520 - 25).collidepoint(mouse)
            rect = draw_text(label, menu_font, YELLOW if hover else WHITE, x, 520, "center", shadow=True)
            self.areas.append((rect.inflate(20, 10), action))
        draw_text("Enter: conectar  •  Tab: trocar de campo  •  Ctrl+V: colar  •  Esc: voltar", tiny_font, GRAY,
                  SCREEN_WIDTH // 2, 578, "center", shadow=True)


# ---------------- JOGO ----------------
CONTROL_HINTS = (
    "P1:  A/D andar  •  W pular  •  R/T golpes  •  Y super",
    "P2:  Setas andar e pular  •  N/M golpes  •  Vírgula super",
    "Toque para trás na hora do golpe: PARRY  •  Dois toques numa direção: dash",
    "F1 hitboxes  •  F11 tela cheia",
)
ONLINE_HINTS = (
    "Você joga com qualquer um dos dois conjuntos de teclas:",
    "A/D ou Setas andar  •  W ou Cima pular  •  R/T ou N/M golpes  •  Y ou Vírgula super",
    CONTROL_HINTS[2],
    "No online a luta não para enquanto este menu está aberto.",
)
ONLINE_MENU_NOTES = (
    "Criar sala: você espera e passa o seu IP para o amigo (mesma rede, VPN ou porta aberta).",
    "Entrar pelo IP: digite o IP de quem criou a sala.",
    "Sala no servidor: os dois usam o mesmo servidor e o mesmo código (ninguém abre porta).",
    "Guia completo: online/COMO_JOGAR_ONLINE.md",
)


class Game:
    """Máquina de estados: MAIN_MENU -> CHAR_SELECT -> FIGHT <-> PAUSE -> MATCH_OVER.
    Online: MAIN_MENU -> ONLINE_MENU -> (ONLINE_FORM) -> ONLINE_WAIT -> ONLINE_SELECT -> FIGHT
    -> MATCH_OVER -> ONLINE_SELECT... (ONLINE_ERROR quando a conexão cai)."""

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
        # online
        self.config = load_config()
        self.session = None
        self.form = None
        self.form_kind = None        # "join" ou "relay"
        self.online_menu = False     # menu aberto por cima da luta online (a luta continua)
        self.message = ("", "")      # (título, texto) da tela de aviso
        self.note = None             # aviso rápido na seleção online (ex.: luta dessincronizada)
        self.wait_started = 0
        self.local_ips = []
        audio.music("menu")

    def set_state(self, state):
        # sons da luta (o do SUPER dura segundos): param com a pausa e acabam ao sair da luta
        if state == PAUSE:
            audio.pause_fighters()
        elif state == FIGHT and self.state == PAUSE:
            audio.resume_fighters()
        elif state != MATCH_OVER:
            audio.stop_fighters()
        audio.music("fight" if state in (FIGHT, PAUSE, MATCH_OVER) else "menu")
        audio.duck_music(state == PAUSE)
        self.state = state
        self.selected = 0
        self.option_rects = []

    @property
    def online(self):
        return self.mode == MODE_ONLINE

    def menu_options(self):
        if self.state == MAIN_MENU:
            return ["1P vs CPU", "1P vs 2P", "Online", fullscreen_label(), "Sair"]
        if self.state == ONLINE_MENU:
            return ["Criar sala", "Entrar pelo IP", "Sala no servidor", "Voltar"]
        if self.state == ONLINE_ERROR:
            return ["OK"]
        if self.state == FIGHT:  # só com o menu do online aberto
            return ["Continuar", "Sair da sala"]
        if self.state == PAUSE:
            return ["Continuar", "Trocar lutadores", fullscreen_label(), "Menu principal"]
        if self.online:
            return ["Revanche", "Sair da sala"]
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

    def resume_game(self):
        self.set_state(FIGHT)  # o relógio da luta só anda com ela rodando: nada pula

    # ---------- online: conectar ----------
    def open_form(self, kind):
        self.form_kind = kind
        if kind == "join":
            self.form = TextForm("Entrar pelo IP", [["IP de quem criou a sala (ex.: 192.168.0.10)",
                                                     self.config.get("ip", ""), 60]],
                                 ["Mesma rede: o IP que aparece na tela de quem criou.",
                                  "Pela internet: IP da VPN (Radmin, Tailscale, ZeroTier) ou o IP público",
                                  f"de quem abriu a porta UDP {DEFAULT_PORT} no roteador."])
        else:
            self.form = TextForm("Sala no servidor", [["Servidor (ex.: meuservidor.com ou 1.2.3.4)",
                                                       self.config.get("servidor", ""), 60],
                                                      ["Código da sala (o mesmo para os dois)",
                                                       self.config.get("sala", ""), 16]],
                                 ["O servidor roda online/servidor_relay.py numa máquina com IP público.",
                                  "Quem chegar primeiro na sala é o P1."])
        self.set_state(ONLINE_FORM)

    def submit_form(self):
        try:
            if self.form_kind == "join":
                (text,) = self.form.values()
                address = parse_address(text, DEFAULT_PORT)
                self.config["ip"] = text
                session = NetSession.join(GAME_ID, address)
            else:
                server_text, code = self.form.values()
                server = parse_address(server_text, RELAY_PORT)
                code = code.upper()
                if not code:
                    raise ValueError("Escolha um código para a sala (ex.: FALIDOS).")
                self.config["servidor"], self.config["sala"] = server_text, code
                session = NetSession.relay(GAME_ID, server, code)
        except ValueError as error:
            self.form.error = str(error)
            audio.play("error")
            return
        save_config(self.config)
        self.begin_session(session)

    def start_host(self):
        self.begin_session(NetSession.host(GAME_ID))

    def begin_session(self, session):
        self.session = session
        self.mode = MODE_ONLINE
        if session.closed:
            self.show_error("Não deu para criar a sala", session.close_reason)
            return
        self.wait_started = pygame.time.get_ticks()
        self.local_ips = local_addresses() if session.role == 1 and session.server is None else []
        self.set_state(ONLINE_WAIT)

    def open_online_select(self):
        self.select = CharSelect(MODE_ONLINE, self.picks, self.difficulty,
                                 local_side=self.session.role - 1, net_info=self.net_info)
        self.set_state(ONLINE_SELECT)

    def start_online_match(self, go):
        p1, p2, _ = go
        self.picks = [p1, p2]
        self.match = Match(MODE_ONLINE, CHARACTERS[p1]["id"], CHARACTERS[p2]["id"], self.difficulty,
                           local_side=self.session.role - 1)
        self.online_menu = False
        self.note = None
        self.set_state(FIGHT)

    def leave_online(self, state=ONLINE_MENU):
        if self.session is not None:
            self.session.close()
            self.session = None
        self.online_menu = False
        self.set_state(state)

    def show_error(self, title, text):
        if self.session is not None:
            self.session.close()
            self.session = None
        self.message = (title, text or "A conexão foi encerrada.")
        audio.play("error")
        self.online_menu = False
        self.set_state(ONLINE_ERROR)

    def net_info(self):
        session = self.session
        if session is None:
            return ""
        text = f"Ping {round(session.rtt_ms)} ms"
        if self.state == FIGHT and session.lockstep:
            text += f"  •  atraso dos botões {session.lockstep.delay} frames"
        return text

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
                audio.play("back")
                self.set_state(MAIN_MENU)
        elif self.state == ONLINE_SELECT:
            if self.select.handle_event(event) == "back":
                audio.play("back")
                self.leave_online()
        elif self.state == ONLINE_FORM:
            action = self.form.handle_event(event)
            if action == "ok":
                audio.play("confirm")
                self.submit_form()
            elif action == "back":
                audio.play("back")
                self.set_state(ONLINE_MENU)
        elif self.state == ONLINE_WAIT:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                audio.play("back")
                self.leave_online()
        elif self.state == FIGHT:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
                fighter_module.DEBUG = not fighter_module.DEBUG  # mostra hitboxes
            elif self.online:
                # online não pausa (o outro continua jogando): o menu abre por cima da luta
                if self.is_pause_toggle(event):
                    self.online_menu = not self.online_menu
                    self.selected = 0
                    audio.play("pause" if self.online_menu else "resume")
                elif self.online_menu:
                    self.handle_menu_choice(event)
            elif self.is_pause_toggle(event):
                audio.play("pause")
                self.pause_game()
            elif event.type == pygame.WINDOWFOCUSLOST:
                self.pause_game()
        elif self.state == PAUSE and self.is_pause_toggle(event):
            audio.play("resume")
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
        elif escolha == "Online":
            self.set_state(ONLINE_MENU)
        elif escolha == "Criar sala":
            self.start_host()
        elif escolha == "Entrar pelo IP":
            self.open_form("join")
        elif escolha == "Sala no servidor":
            self.open_form("relay")
        elif escolha == "Voltar":
            self.set_state(MAIN_MENU)
        elif escolha == "OK":
            self.set_state(ONLINE_MENU)
        elif escolha == "Sair":
            self.running = False
        elif escolha == "Continuar":
            if self.state == FIGHT:
                self.online_menu = False
            else:
                self.resume_game()
        elif escolha == "Sair da sala":
            self.leave_online()
        elif escolha == "Trocar lutadores":
            self.open_char_select(self.mode)
        elif escolha == "Revanche":
            if self.online:
                self.open_online_select()  # os dois escolhem de novo (pode repetir o lutador)
            else:
                self.start_match()
        elif escolha == "Menu principal":
            self.set_state(MAIN_MENU)

    # ---------- lógica ----------
    def update(self):
        if self.online and self.session is not None:
            self.update_online()
            return
        if self.state == CHAR_SELECT and self.select.ready():
            self.picks = list(self.select.cursor)
            self.difficulty = self.select.difficulty_key()
            self.start_match()
        elif self.state in (FIGHT, MATCH_OVER):  # na pausa tudo fica congelado
            self.match.update()
            if self.state == FIGHT and self.match.finished:
                self.set_state(MATCH_OVER)

    def local_buttons(self):
        """Botões deste computador no online (qualquer um dos dois conjuntos de teclas)."""
        if self.online_menu:
            return 0  # navegando no menu: o lutador fica parado
        return pack_buttons(keyboard_buttons(CONTROLS[1], CONTROLS[2]))

    def update_online(self):
        session = self.session
        session.poll()
        if session.closed:
            self.show_error("Conexão encerrada", session.close_reason)
            return
        if self.state == ONLINE_WAIT and session.connected:
            audio.play("connected")
            self.open_online_select()
        elif self.state == ONLINE_SELECT:
            select = self.select
            side = select.local_side
            session.set_select(select.cursor[side], select.locked[side])
            if session.remote_select is not None:
                select.set_remote(*session.remote_select)
            if session.role == 1 and select.ready():
                session.start_match(*select.cursor)  # o anfitrião manda começar (e já começa abaixo)
            go = session.take_go()
            if go:
                self.start_online_match(go)
        elif self.state == FIGHT:
            match = self.match
            session.step_match(self.local_buttons(),
                               lambda p1, p2: match.update((unpack_buttons(p1), unpack_buttons(p2))),
                               match.checksum)
            if session.lockstep.desync_frame is not None:
                audio.play("error")
                self.open_online_select()
                self.note = ("A luta dessincronizou (os dois computadores calcularam lutas diferentes) "
                             "e foi interrompida. Confiram se os dois têm a mesma versão do jogo.")
            elif match.finished:
                self.online_menu = False
                self.set_state(MATCH_OVER)
        elif self.state == MATCH_OVER:
            self.match.update()  # só a animação local; a luta já acabou nos dois

    # ---------- desenho ----------
    def draw(self):
        if self.state in (MAIN_MENU, ONLINE_MENU, ONLINE_ERROR):
            self.draw_menu_screen()
        elif self.state == CHAR_SELECT:
            self.select.draw()
        elif self.state == ONLINE_SELECT:
            self.select.draw()
            if self.note:
                self.draw_note(self.note)
        elif self.state == ONLINE_FORM:
            self.form.draw()
        elif self.state == ONLINE_WAIT:
            self.draw_waiting()
        else:
            self.match.draw()
            if self.state == FIGHT:
                if self.online:
                    self.draw_online_fight()
                else:
                    draw_pause_button(PAUSE_BUTTON.collidepoint(pygame.mouse.get_pos()))
            elif self.state == PAUSE:
                self.draw_pause_menu()
            else:
                self.draw_match_over()

    def draw_menu_screen(self):
        screen.fill(BLACK)
        screen.blit(menu_image, (0, 0))
        if self.state == MAIN_MENU:
            draw_text("Falido da Luta", title_font, RED, SCREEN_WIDTH // 2, 150, "center", shadow=True)
            self.option_rects = draw_options(self.menu_options(), self.selected, 270, spacing=66)
        elif self.state == ONLINE_MENU:
            draw_text("Online", title_font, YELLOW, SCREEN_WIDTH // 2, 110, "center", shadow=True)
            self.option_rects = draw_options(self.menu_options(), self.selected, 220, spacing=66)
            for i, line in enumerate(ONLINE_MENU_NOTES):
                draw_text(line, tiny_font, LIGHT_GRAY, SCREEN_WIDTH // 2, 482 + i * 24, "center", shadow=True)
        else:
            title, text = self.message
            draw_text(title, menu_font, RED, SCREEN_WIDTH // 2, 150, "center", shadow=True)
            for i, line in enumerate(wrap_text(text, score_font, 820)):
                draw_text(line, score_font, WHITE, SCREEN_WIDTH // 2, 240 + i * 40, "center", shadow=True)
            self.option_rects = draw_options(self.menu_options(), self.selected, 470)

    def draw_waiting(self):
        session = self.session
        screen.fill(BLACK)
        screen.blit(menu_image, (0, 0))
        dots = "." * (1 + (pygame.time.get_ticks() // 400) % 3)
        seconds = (pygame.time.get_ticks() - self.wait_started) // 1000
        lines = []
        if session.state == "linking":
            title = "Conectado! Medindo a conexão" + dots
        elif session.state == "room":
            title = f"Na sala {session.room_code}" + dots
            lines = ["Esperando o outro jogador entrar com o mesmo código.",
                     f"Servidor: {session.server[0]}:{session.server[1]}"]
        elif session.role == 1 and session.server is None:
            title = "Sala criada! Esperando o oponente" + dots
            lines = ["Passe para o seu amigo um destes endereços:"]
            lines += list(self.local_ips) or ["(não achei o IP desta máquina)"]
            lines += ["", f"Porta UDP {session.port}.  Pela internet: VPN (Radmin, Tailscale, ZeroTier)",
                      "ou abra essa porta no roteador e passe o seu IP público."]
        elif session.role == 1:
            title = "Oponente encontrado! Conectando" + dots
        else:
            title = "Conectando" + dots
            if session.server is None:
                lines = [f"Endereço: {session.peer[0]}:{session.peer[1]}", f"{seconds} s"]
        draw_text(title, menu_font, YELLOW, SCREEN_WIDTH // 2, 120, "center", shadow=True)
        for i, line in enumerate(lines):
            font = score_font if line[:1].isdigit() and "." in line and " " not in line else small_font
            draw_text(line, font, WHITE, SCREEN_WIDTH // 2, 210 + i * 36, "center", shadow=True)
        draw_text("Esc: cancelar", small_font, LIGHT_GRAY, SCREEN_WIDTH // 2, 560, "center", shadow=True)

    def draw_note(self, text):
        lines = wrap_text(text, small_font, 860)
        band = pygame.Surface((SCREEN_WIDTH, 30 * len(lines) + 20), pygame.SRCALPHA)
        band.fill((90, 0, 0, 210))
        screen.blit(band, (0, 470 - 10))
        for i, line in enumerate(lines):
            draw_text(line, small_font, WHITE, SCREEN_WIDTH // 2, 470 + i * 30, "midtop", shadow=True)

    def draw_online_fight(self):
        session = self.session
        draw_text(self.net_info(), tiny_font, LIGHT_GRAY, SCREEN_WIDTH // 2, 112, "center", shadow=True)
        if session.lockstep.stalled > STALL_NOTICE:
            draw_banner("Esperando o oponente" + "." * (1 + (pygame.time.get_ticks() // 400) % 3),
                        menu_font, WHITE, 200)
        if self.online_menu:
            screen.blit(pause_overlay, (0, 0))
            draw_text("PARTIDA ONLINE", title_font, YELLOW, SCREEN_WIDTH // 2, 130, "center", shadow=True)
            self.option_rects = draw_options(self.menu_options(), self.selected, 260)
            for i, hint in enumerate(ONLINE_HINTS):
                draw_text(hint, tiny_font, LIGHT_GRAY, SCREEN_WIDTH // 2, 578 - (len(ONLINE_HINTS) - 1 - i) * 22,
                          "center", shadow=True)
        draw_pause_button(self.online_menu or PAUSE_BUTTON.collidepoint(pygame.mouse.get_pos()))

    def draw_pause_menu(self):
        screen.blit(pause_overlay, (0, 0))
        draw_text("PAUSADO", title_font, YELLOW, SCREEN_WIDTH // 2, 130, "center", shadow=True)
        self.option_rects = draw_options(self.menu_options(), self.selected, 245)
        hints = CONTROL_HINTS if self.mode == MODE_VERSUS else (CONTROL_HINTS[0],) + CONTROL_HINTS[2:]
        for i, hint in enumerate(hints):
            draw_text(hint, tiny_font, LIGHT_GRAY, SCREEN_WIDTH // 2, 578 - (len(hints) - 1 - i) * 22,
                      "center", shadow=True)
        draw_pause_button(True)

    def draw_match_over(self):
        match = self.match
        screen.blit(pause_overlay, (0, 0))
        if match.mode == MODE_ONLINE:
            title = "Você venceu!" if match.winner == match.local_side else "Você perdeu!"
            quem = f"{match.fighter_label(match.winner)} venceu"
        else:
            title = f"{match.fighter_label(match.winner)} venceu!"
            quem = {"P1": "Jogador 1", "P2": "Jogador 2", "CPU": "Computador"}[match.tags[match.winner]]
            if match.mode == MODE_CPU:
                quem += "  •  " + DIFFICULTY_LABELS[match.cpu_diff]
        draw_text(title, title_font, YELLOW, SCREEN_WIDTH // 2, 140, "center", shadow=True)
        draw_text(f"{quem}  •  Placar {match.score[0]} x {match.score[1]}", score_font, WHITE,
                  SCREEN_WIDTH // 2, 215, "center", shadow=True)
        self.option_rects = draw_options(self.menu_options(), self.selected, 320)

    # ---------- loop ----------
    def run(self):
        while self.running:
            relogio.tick(FPS)  # limita a 60 FPS
            for event in pygame.event.get():
                self.handle_event(event)
            self.update()
            audio.update()
            self.draw()
            pygame.display.flip()
        if self.session is not None:
            self.session.close()
        pygame.quit()


if __name__ == "__main__":
    Game().run()
