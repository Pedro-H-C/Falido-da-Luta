import math
import os
import random
from collections import namedtuple

import pygame

import audio

DEBUG = False  # F1 no jogo mostra/esconde as hitboxes

GRAVITY = 2
GROUND_MARGIN = 110
FRAME_MS = 1000 / 60

# Configuração dos golpes:
#   damage    -> dano base (multiplicado pelo dmg_mult do personagem)
#   range     -> alcance (multiplicador da largura do corpo)
#   cooldown  -> frames de espera depois do golpe
#   knockback -> força do empurrão no oponente
#   stamina   -> custo; com estamina suficiente o golpe gasta e o cooldown cai (STAMINA_COOLDOWN_MULT)
SUPER = 3
ATTACKS = {
    1: {"damage": 7,  "range": 1.6, "cooldown": 15, "knockback": 6,  "stamina": 12},  # golpe rápido
    2: {"damage": 14, "range": 2.2, "cooldown": 40, "knockback": 14, "stamina": 22},  # golpe forte
    SUPER: {"damage": 28, "range": 2.8, "cooldown": 30, "knockback": 28, "stamina": 0},
}
ATTACK_ACTION = {1: 3, 2: 4, SUPER: 7}   # golpe -> linha de animação
ATTACK_ACTIONS = set(ATTACK_ACTION.values())
HIT_RECOVERY = 10          # frames sem poder atacar após levar dano
TRAIL_DELAY = 30           # frames até a barra "fantasma" de vida começar a descer
TRAIL_SPEED = 0.8          # quanto a barra fantasma desce por frame

# PARRY: tocar para trás abre uma janela curta; o golpe que chegar nela não causa dano
PARRY_WINDOW = 9           # frames da janela depois de tocar para trás
PARRY_WHIFF_COOLDOWN = 24  # frames extras sem poder tentar de novo (contra apertar sem parar)
PARRY_STUN = 40            # frames que o atacante fica tonto depois de ser parado
PARRY_PUSHBACK = 8         # empurrão no atacante

# ESTAMINA
STAMINA_REGEN = 0.7            # por frame
STAMINA_REGEN_DELAY = 45       # frames sem gastar até começar a recarregar
STAMINA_COOLDOWN_MULT = 0.4    # cooldown do golpe que gastou estamina

# DASH: dois toques rápidos na mesma direção
DASH_COST = 30
DASH_FRAMES = 10
DASH_IFRAMES = 6           # primeiros frames do dash são invencíveis
DASH_SPEED = 24
DASH_TAP_WINDOW = 14       # frames entre os dois toques
DASH_COOLDOWN = 12

# SUPER: barra enche acertando, apanhando e (principalmente) com parry
SUPER_MAX = 100
SUPER_GAIN_HIT = {1: 8, 2: 14, SUPER: 0}
SUPER_GAIN_HURT = 5
SUPER_GAIN_PARRY = 25
SUPER_COLOR_DEFAULT = (255, 200, 60)
# SUPER aéreo (personagens com "launch"): os dois sobem e o golpe sai lá em cima
JUGGLE_PULL = 0.3          # quanto o oponente lançado é puxado por frame até ficar na frente
JUGGLE_MAX_WAIT = 45       # frames no máximo esperando o golpe no alto (segurança)
SUPER_AIR_POP = -16        # o golpe final ainda joga o oponente um pouco mais para cima
# SUPER sônico (personagens com "sonic"): uma rajada de vários acertos seguidos
SONIC_TICK_SHARE = 0.09    # cada acerto do meio da rajada tira ~9% do dano total; o último leva o resto
SONIC_TICK_PUSH = 3        # empurrão dos acertos do meio (o oponente fica dentro da rajada)
SONIC_FINAL_POP = -13      # o último acerto arremessa o oponente pelos ares
TREMOR_HIT = 18            # frames vibrando de quem leva um acerto da rajada
TREMOR_HIT_AMP = 7
TREMOR_SELF = 45           # quem solta a rajada também treme
TREMOR_SELF_AMP = 3
# SUPER bumerangue (personagens com "boomerang"): o chapéu voa, fura o oponente várias vezes,
# passa, volta e arrasta o oponente para perto de quem jogou
HAT_DECEL = 0.9            # velocidade (px/frame) que o chapéu perde por frame indo e ganha voltando
HAT_MAX_SPEED = 30
HAT_EDGE = 40              # o centro do chapéu não passa disso da borda da tela
HAT_LINE = 200             # altura do voo acima do chão (peito do oponente)
HAT_START_SCALE = 0.6      # sai da mão do tamanho do chapéu na cabeça e cresce...
HAT_GROW = 8               # ... em tantos frames; chegando na mão encolhe de novo
HAT_RISE = 260             # voltando, a essa distância da mão começa a subir até ela
HAT_GRIND_DEPTH = 30       # furando: centro do chapéu a isso do centro do oponente
HAT_TICK_SHARE = 0.1       # cada furada tira 10% do dano total; a volta leva o resto
HAT_TICK_PUSH = 3
HAT_TREMOR = 10
HAT_TREMOR_AMP = 4
HAT_PASS = 150             # depois de furar, passa isso além do oponente antes de voltar
HAT_HOLD = 60              # frames que o oponente fica preso na animação de dano esperando a volta
HAT_PULL_POP = -9          # a volta levanta o oponente um pouco...
HAT_PULL_GAP = 170         # ... e arrasta até essa distância de quem jogou
HAT_DRAG_TIMER = 8         # frames que o oponente ainda vai até o lugar depois de solto
HAT_RECOVER_EXTRA = 6      # depois de solto, levanta um pouco depois de quem jogou terminar a pose
HAT_LIFE = 300             # segurança: o chapéu some depois disso
HAT_TRAIL = 8              # posições guardadas para o rastro
# SUPER da enchente (personagens com "flood"): o oponente fica paralisado desde o começo até a
# água chegar; aí o tubarão morde várias vezes (como a rajada sônica) e o último acerto arremessa
PARALYZE_MARGIN = 12       # frames de folga da paralisia depois do impacto (segurança)
FLOOD_RECOVER_EXTRA = 4    # depois do último acerto, só levanta um pouco depois de quem soltou voltar

# Velocidade (ms por frame) de cada animação; o resto usa 100.
# O SUPER com sprite próprio usa o "frame_ms" do personagem.
ANIM_SPEED = {3: 80, 4: 110, 5: 90, 7: 110}

CONTROLS = {
    1: {"left": pygame.K_a, "right": pygame.K_d, "jump": pygame.K_w,
        "atk1": pygame.K_r, "atk2": pygame.K_t, "super": pygame.K_y},
    2: {"left": pygame.K_LEFT, "right": pygame.K_RIGHT, "jump": pygame.K_UP,
        "atk1": pygame.K_n, "atk2": pygame.K_m, "super": pygame.K_COMMA},
}

# Botões segurados num frame. No modo online é só isso que vai pela rede (6 bits por frame):
# cada computador calcula as intenções abaixo a partir dos botões dos dois jogadores.
BUTTONS = ("left", "right", "jump", "atk1", "atk2", "super")

# O que o lutador quer fazer neste frame. Vem dos botões (jogador) ou da IA (CPU).
#   parry -> True só no frame em que tocou para trás | dash -> -1, 0 ou +1
INTENT_KEYS = ("left", "right", "jump", "parry", "dash", "atk1", "atk2", "super")


def keyboard_buttons(*control_sets):
    """Botões segurados agora no teclado. Com mais de um conjunto de teclas, vale qualquer um."""
    key = pygame.key.get_pressed()
    return {name: any(key[controls[name]] for controls in control_sets) for name in BUTTONS}


def pack_buttons(held):
    return sum(1 << i for i, name in enumerate(BUTTONS) if held[name])


def unpack_buttons(bits):
    return {name: bool(bits >> i & 1) for i, name in enumerate(BUTTONS)}

# Golpe que encostou no oponente; o main usa para hitstop, faíscas e tremor de tela.
#   kind: "hit", "parry" ou "launch" (início do SUPER aéreo) | pos: ponto de contato
#   direction: +1 empurra p/ direita, -1 p/ esquerda | color: cor do SUPER (None nos golpes normais)
HitEvent = namedtuple("HitEvent", "kind attack_type pos direction ko color", defaults=(None,))


# ---------------- PERSONAGENS ----------------
# data       -> [tamanho do frame na sheet, escala, offset do desenho em relação à hitbox]
# anim_steps -> frames de cada linha: idle, corrida, pulo, golpe 1, golpe 2, dano, morte
# stats      -> vida máxima, velocidade, força do pulo (negativo = para cima), multiplicador de dano, estamina
# super      -> (opcional) sprite próprio do SUPER, montado com tools/montar_super.py:
#   rect     -> (x, y, largura, altura) do frame do SUPER em relação ao frame normal (pixels do jogo)
#   frame_ms -> duração de cada frame; o golpe acerta no frame do meio (len // 2)
#   range    -> alcance do SUPER
#   color    -> cor dos efeitos (anéis, faíscas)
#   impact   -> (à frente do centro, acima do chão) onde estoura o impacto quando não há "fx"
#   ground_wave -> explosões correndo pelo chão até o alcance do golpe
#   fx       -> efeito desenhado à frente no impacto: origin = (à frente do centro, acima do chão)
#               onde fica o canto esquerdo do efeito na linha "ground" da imagem
#   launch   -> SUPER aéreo: no frame "frame" uma explosão lança os dois "rise" px para cima, com o
#               oponente a "gap" px na frente; o golpe (frame do meio) acerta no alto. "damage" é o
#               dano do lançamento (sai do dano total do SUPER). Se o lançamento errar, o SUPER sai no chão.
#   damage   -> dano total do SUPER (sem isso, o de ATTACKS)
#   impact_frame -> frame em que o golpe acerta (sem isso, o do meio)
#   freeze   -> frames de congelamento no começo (sem isso, o padrão do main)
#   name, cutin -> faixa cinematográfica no congelamento: nome do golpe e recorte (x, y, largura,
#               altura) do rosto no frame "frame" do SUPER, ou na imagem "sheet" em tamanho cheio
#   sonic    -> rajada sônica: "hits" acertos, um a cada "every" frames; as ondas saem de "origin"
#               (à frente do centro, acima do chão)
#   glint    -> brilho de lente no começo: pixel (x, y) do frame 0 do SUPER
#   boomerang -> o golpe é um objeto que voa e volta (sheet de frames "size" girando). Pixels do
#               frame do SUPER: "hand" = onde ele está no frame antes do impact_frame (sai dali) e
#               "catch" = onde fica no frame seguinte (volta para lá). "reach" = distância máxima,
#               "hits" furadas na ida (uma a cada "every" frames), "box" = hitbox (largura, altura).
#               O personagem segura o frame impact_frame até o objeto voltar.
#   beam     -> raio (laser dos olhos): a imagem "sheet_path" (um frame "size", ponta para a direita)
#               é esticada dos olhos até o oponente ou o alcance. "eyes" = {frame do SUPER: pixel
#               de onde o raio sai}; o raio aparece só nesses frames. "height" = espessura na tela.
#               Acerta como a rajada sônica: "hits" acertos, um a cada "every" frames.
#   flood    -> enchente: no começo do SUPER o oponente fica paralisado (parado no tempo) até o
#               impacto; aí acerta como a rajada sônica ("hits" acertos, um a cada "every" frames)
#               e o oponente só levanta quando a animação acaba. O resto é desenho (main.py):
#               "teleport" = sheet do teletransporte (frames "size"; "base" = linha do chão no
#               frame), que troca quem aparece nos frames "swap"; "water_fx" = água das mãos
#               (frames "size", canto de cada um no frame do SUPER em "spots", "vortex" = miolo
#               do redemoinho), na ordem redemoinho, jato, tubarão, tubarão desfazendo;
#               "waves" = pasta com a água que enche a arena (frame1..5), "surface" = linha da
#               superfície em cada onda, "fade" = quanto a onda some embaixo (a textura continua);
#               "timeline" = frames do SUPER de cada fase: redemoinho, jato, tubarão nadando,
#               mordidas, água baixando.
#   shadow   -> x (no frame do SUPER) do meio entre os pés em cada frame: a sombra acompanha
# Sem "super", o SUPER usa o golpe forte com brilho dourado.
# sounds    -> sons do lutador (arquivos em SOUND_DIR): "atk1" (golpe rápido), "atk2" (golpe forte),
#             "super". Os que faltarem ficam mudos; o volume é nivelado sozinho (audio.LEVELS).
#             Em vez do nome do arquivo pode ser {"files": ..., "delay": s, "starts": (...)}:
#             delay = segundos de espera antes de tocar; files com várias partes + starts = em que
#             segundo cada parte entra (o som acaba junto com a última parte); "keep": fração do
#             arquivo que toca, do começo (0.5 = primeira metade); "with_super": True no som do
#             SUPER = ele some quando o golpe acaba (mesmo interrompido), em vez de tocar até o fim.
# row_scale -> {linha da sheet: fator}: amplia os frames de uma linha desenhada menor que as
#             outras (o pé fica no lugar). Só o desenho; a hitbox não muda.
# height    -> tamanho na tela em relação à sprite (1.0 = como está na sheet). O pé continua no chão
#             e a hitbox não muda: é só o desenho (para as alturas ficarem proporcionais).
SOUND_DIR = "assets/audio/FightersSounds"
FEET_Y = 290        # onde fica o pé de todos os lutadores, em pixels abaixo do topo da hitbox
CHARACTERS = [
    {
        "id": "igor",
        "name": "Igor",
        "sheet_path": "assets/images/Sprites/igor.png",
        "sounds": {"atk1": "igorAttack1.mp3", "atk2": "igorAttack2.mp3",
                   "super": "igorSuper.mp3"},
        "data": [250, 1.5, [120, 70]],
        "height": 1.038,
        "anim_steps": [4, 6, 5, 6, 5, 4, 5],
        "stats": {"max_health": 110, "speed": 7, "jump_vel": -28, "dmg_mult": 1.15, "stamina": 90},
        "tagline": "Gordo e preguento",
        "super": {
            "sheet_path": "assets/images/Sprites/igor_super.png",
            "rect": (57, -103, 342, 470),
            "frame_ms": (90, 90, 170, 160, 150, 130),
            "range": 3.6,
            "color": (255, 200, 60),
            "freeze": 50,
            "name": "RODÍZIO EXPLOSIVO",
            "cutin": {"frame": 1, "box": (105, 150, 120, 115)},
            "fx": {"sheet_path": "assets/images/Sprites/igor_super_fx.png", "size": (381, 311),
                   "ground": 306, "origin": (24, -6), "frame_ticks": 5},
        },
    },
    {
        "id": "macedo",
        "name": "Macedo",
        "sheet_path": "assets/images/Sprites/macedo.png",
        # SUPER: feito pelo Felipe Macedo; começa 0,8 s depois e acaba junto com o golpe
        "sounds": {"atk1": "macedoAttack1.mp3", "atk2": "macedoAttack2.mp3",
                   "super": {"files": "macedoSuper.mp3", "delay": 0.8, "with_super": True}},
        "data": [250, 1.5, [120, 70]],
        "height": 1.006,
        "anim_steps": [4, 6, 5, 4, 5, 4, 5],
        "stats": {"max_health": 100, "speed": 8, "jump_vel": -31, "dmg_mult": 1.12, "stamina": 120},
        "tagline": "Forte e ágil",
        "super": {
            "sheet_path": "assets/images/Sprites/macedo_super.png",
            "rect": (16, -245, 468, 617),
            "frame_ms": (90, 90, 210, 170, 150, 120, 130),
            "range": 2.0,
            "color": (90, 170, 255),
            "freeze": 50,
            "name": "UPPERCUT REI CASTOR",
            "cutin": {"frame": 2, "box": (185, 275, 95, 95)},
            "impact": (70, 280),      # punho do uppercut, lá em cima
            "launch": {"frame": 2, "rise": 150, "gap": 125, "damage": 30},
        },
    },
    {
        "id": "manko",
        "name": "Manko",
        "sheet_path": "assets/images/Sprites/manko.png",
        "sounds": {"atk1": "mankoAttack1.mp3", "atk2": "mankoAttack2.mp3",
                   # a parte 2 entra 1 s depois da 1; a 1 acaba junto com a 2
                   "super": {"files": ["mankoSuperPARTE1.mp3", "mankoSuperPARTE2.mp3"], "starts": (0, 1.0)}},
        "data": [250, 1.5, [120, 70]],
        "height": 0.972,
        "anim_steps": [4, 4, 5, 4, 4, 4, 5],
        "stats": {"max_health": 95, "speed": 6, "jump_vel": -25, "dmg_mult": 1.25, "stamina": 100},
        "tagline": "Muito forte, mas lento",
        "super": {
            "sheet_path": "assets/images/Sprites/manko_super.png",
            "rect": (18, 7, 439, 383),
            "frame_ms": (90, 90, 170, 160, 140, 130, 130),
            "range": 2.6,
            "color": (235, 60, 70),
            "freeze": 50,
            "name": "MULETADA SÍSMICA",
            "cutin": {"frame": 2, "box": (205, 70, 125, 120)},
            "impact": (40, 15),       # muletada no chão, logo à frente
            "ground_wave": True,      # explosões correndo pelo chão até o alcance
        },
    },
    {
        # sheet em resolução dobrada (frames de 500px); escala menor deixa ele ~8% mais alto que os outros
        "id": "zuzu",
        "name": "Zuzu",
        "sheet_path": "assets/images/Sprites/zuzu.png",
        "sounds": {"atk1": "zuzuAttack1.mp3", "atk2": "zuzuAttack2.mp3",
                   "super": "zuzuSuper.mp3"},
        "data": [500, 0.74, [118, 76]],
        "height": 0.988,
        "anim_steps": [4, 4, 5, 4, 4, 4, 5],
        "stats": {"max_health": 115, "speed": 9, "jump_vel": -31, "dmg_mult": 1.2, "stamina": 100},
        "tagline": "O mais poderoso de todos",
        "super": {
            "sheet_path": "assets/images/Sprites/zuzu_super.png",
            "rect": (119, -64, 332, 436),
            # orelha incha, vibra, ESTOURO, cabelo voando, orelha volta, tonto
            "frame_ms": (130, 150, 260, 300, 170, 170),
            "impact_frame": 2,
            "range": 4.2,
            "damage": 32,
            "color": (160, 120, 255),
            "freeze": 66,
            "name": "ESTOURO SÔNICO",
            "cutin": {"frame": 2, "box": (60, 0, 170, 215)},
            "sonic": {"origin": (173, 335), "hits": 6, "every": 5},
        },
    },
    {
        # sheet de 500px como a do Zuzu; escala deixa o corpo do tamanho dos outros (o chapéu sobra)
        "id": "caio",
        "name": "Caio",
        "sheet_path": "assets/images/Sprites/caio.png",
        "sounds": {"atk1": "caioAttack1.mp3", "atk2": "caioAttack2.mp3",
                   "super": {"files": "caioSuper.mp3", "delay": 1.0}},
        "data": [500, 0.72, [112, 66]],
        "height": 1.0,
        "anim_steps": [4, 4, 5, 4, 4, 4, 5],
        # rápida e o pulo mais alto do elenco, mas com pouca vida
        "stats": {"max_health": 90, "speed": 9, "jump_vel": -32, "dmg_mult": 1.05, "stamina": 110},
        "tagline": "Nerd ágil do chapéu voador",
        "super": {
            # montado com: python tools/montar_super.py caio --pecas --projetil
            # (raw/caio_super_raw.png tem as lentes do 1º frame preenchidas à mão: o reflexo
            # apagava o contorno dos óculos e o remover_fundo deixava um buraco ali)
            "sheet_path": "assets/images/Sprites/caio_super.png",
            "rect": (66, -42, 317, 404),
            # óculos brilham, gira o chapéu, prepara, arremessa, espera o chapéu, pega, pose
            "frame_ms": (110, 130, 150, 90, 120, 160, 300),
            "impact_frame": 4,
            "range": 6.5,
            "damage": 30,
            "color": (70, 225, 255),
            "freeze": 56,
            "name": "CHAPÉU BUMERANGUE",
            "cutin": {"frame": 0, "box": (52, 50, 126, 112)},
            "glint": (131, 97),
            "boomerang": {"sheet_path": "assets/images/Sprites/caio_super_fx.png", "size": (152, 108),
                          "hand": (273, 126), "catch": (115, 37), "reach": 640, "hits": 4, "every": 5,
                          "box": (80, 46)},
        },
    },
    {
        "id": "antonio",
        "name": "Antonio",
        "sheet_path": "assets/images/Sprites/antonio.png",
        # atk1: primeira metade do som do SUPER do Macedo. atk2: "Blazing Fire" (Pixabay).
        # Ainda sem som de SUPER.
        "sounds": {"atk1": "antonioAttack1.mp3", "atk2": "antonioAttack2.mp3"},
        "data": [250, 1.5, [120, 70]],
        "height": 1.0,
        "anim_steps": [4, 4, 5, 4, 4, 4, 5],
        "row_scale": {4: 1.2},   # golpe forte desenhado menor na sheet
        "stats": {"max_health": 95, "speed": 9, "jump_vel": -29, "dmg_mult": 1.05, "stamina": 100},
        "tagline": "Tyler durden",
        "super": {
            # montado com: python tools/montar_super.py antonio
            # (raw/antonio_super_fx_raw.png teve o miolo branco do raio preenchido: o fundo
            # também era branco e o remover_fundo tinha deixado ele transparente)
            "sheet_path": "assets/images/Sprites/antonio_super.png",
            "rect": (65, -5, 370, 370),
            # olhos acendem, energia sobe, dispara, joga a cabeça para trás, volta
            "frame_ms": (110, 150, 260, 300, 220),
            "impact_frame": 2,
            "range": 5.5,
            "damage": 30,
            "color": (235, 40, 50),
            "freeze": 56,
            "name": "RAIO LAZER",
            "cutin": {"frame": 1, "box": (105, 30, 130, 125)},
            "beam": {"sheet_path": "assets/images/Sprites/antonio_super_fx.png", "size": (1662, 362),
                     "eyes": {2: (215, 103), 3: (118, 100)}, "height": 110, "hits": 6, "every": 5},
        },
    },
    {
        "id": "luba",
        "name": "Luba",
        "sheet_path": "assets/images/Sprites/luba.png",
        "sounds": {"atk1": "lubaAttack1.mp3"},   # ainda sem som de golpe forte e de SUPER
        "data": [500, 0.72, [112, 63]],
        "height": 1.0,
        "anim_steps": [4, 4, 5, 4, 4, 4, 5],
        "row_scale": {4: 1.33},  # golpe forte desenhado menor na sheet
        "stats": {"max_health": 100, "speed": 8, "jump_vel": -30, "dmg_mult": 1.1, "stamina": 100},
        "tagline": "Novo na briga",
        "super": {
            # montado com: python tools/montar_super_luba.py (originais em raw/luba_*_original.png
            # e raw/luba_agua_original/). O Luba chama o pai pelo teletransporte, o pai solta um
            # tubarão e a arena enche de água por um instante.
            "sheet_path": "assets/images/Sprites/luba_super.png",
            "rect": (-2, -2, 377, 364),
            # Luba some, pai parado, prepara, empurra, redemoinho, jato, tubarão nadando,
            # mordidas, guarda (água baixando), guarda (teletransporte de volta), Luba
            "frame_ms": (230, 250, 190, 160, 260, 190, 270, 430, 300, 170, 300),
            "impact_frame": 7,
            "range": 12.0,            # a água enche a arena: pega o oponente em qualquer lugar
            "damage": 28,
            "color": (40, 170, 255),
            "freeze": 56,
            "name": "SÓ DEPENDE DE LUBA",
            "cutin": {"sheet": "assets/images/Sprites/luba.png", "box": (205, 40, 115, 110)},
            "shadow": (181, 180, 182, 214, 216, 220, 216, 216, 214, 214, 181),
            "flood": {
                "hits": 5, "every": 5,
                "teleport": {"sheet_path": "assets/images/Sprites/luba_super_fx.png", "size": (252, 444),
                             "base": 407, "center": (181, 354), "swap": (1, 10)},
                "water_fx": {"sheet_path": "assets/images/Sprites/luba_tubarao_fx.png", "size": (196, 160),
                             "spots": ((271, 76), (306, 47), (301, 87), (282, 68)), "vortex": (40, 56)},
                # linha da superfície em cada onda; embaixo, a onda some em "fade" px sobre a textura
                "waves": "assets/images/Sprites/lubaAgua", "surface": {1: 318, 2: 189, 4: 148, 5: 318},
                "fade": 90,
                "timeline": {"vortex": 4, "splash": 5, "shark": 6, "bite": 7, "drain": 8},
            },
        },
    },
]
CHARACTERS_BY_ID = {char["id"]: char for char in CHARACTERS}


# ---------------- CACHE DE SPRITES ----------------
# Cada sheet é lida do disco uma única vez; a seleção e a luta reaproveitam as mesmas
# surfaces. Ninguém altera uma surface do cache (o draw sempre trabalha numa cópia).
_frame_cache = {}
_fx_cache = {}

# Paleta alternativa do P2 em luta espelho: a pele quase não muda e a roupa fica azul-marinho
ALT_PALETTE_MULT = (225, 220, 185)
ALT_PALETTE_ADD = (8, 18, 62)


def apply_alt_palette(image):
    """Cópia da imagem com a paleta alternativa."""
    tinted = image.copy()
    tinted.fill(ALT_PALETTE_MULT, special_flags=pygame.BLEND_RGB_MULT)
    tinted.fill(ALT_PALETTE_ADD, special_flags=pygame.BLEND_RGB_ADD)
    return tinted


def _gold_tint(image):
    """SUPER genérico (sem sprite próprio): golpe forte dourado."""
    tinted = image.copy()
    tinted.fill((255, 225, 140), special_flags=pygame.BLEND_RGB_MULT)
    tinted.fill((70, 50, 0), special_flags=pygame.BLEND_RGB_ADD)
    return tinted


def _strip(path, width, height):
    """Frames de uma sheet de uma linha só."""
    sheet = pygame.image.load(path).convert_alpha()
    return [sheet.subsurface(i * width, 0, width, height).copy() for i in range(sheet.get_width() // width)]


def _slice_sheet(char):
    size, scale, _ = char["data"]
    scaled_size = int(size * scale)
    sheet = pygame.image.load(char["sheet_path"]).convert_alpha()
    animations = []
    for row, steps in enumerate(char["anim_steps"]):
        frames = []
        side = round(scaled_size * char.get("row_scale", {}).get(row, 1.0))
        for col in range(steps):
            frame = sheet.subsurface(col * size, row * size, size, size)
            frames.append(pygame.transform.scale(frame, (side, side)))
        animations.append(frames)

    # linha 7: SUPER (sprite próprio ou o golpe forte dourado)
    sup = char.get("super")
    if sup:
        animations.append(_strip(sup["sheet_path"], sup["rect"][2], sup["rect"][3]))
    else:
        animations.append([_gold_tint(frame) for frame in animations[4]])
    return animations


def get_frames(char_id, alt_palette=False):
    """Animações do personagem já recortadas e escaladas.

    alt_palette=True deriva (uma vez) a paleta alternativa a partir do cache em memória,
    sem reler o disco.
    """
    key = (char_id, alt_palette)
    if key not in _frame_cache:
        if alt_palette:
            base = get_frames(char_id)
            _frame_cache[key] = [[apply_alt_palette(frame) for frame in anim] for anim in base]
        else:
            _frame_cache[key] = _slice_sheet(CHARACTERS_BY_ID[char_id])
    return _frame_cache[key]


def get_super_fx(char_id):
    """Frames do efeito do SUPER (onda do Igor, chapéu do Caio), olhando para a direita, ou None."""
    if char_id not in _fx_cache:
        sup = CHARACTERS_BY_ID[char_id].get("super", {})
        fx = sup.get("fx") or sup.get("boomerang") or sup.get("beam")
        _fx_cache[char_id] = _strip(fx["sheet_path"], *fx["size"]) if fx else None
    return _fx_cache[char_id]


_flood_cache = {}


def get_flood_art(char_id):
    """Desenhos do SUPER da enchente (teletransporte, água das mãos, ondas), olhando para a
    direita, ou None. waves: {1, 2, 4, 5: onda}, texture: o "tudo água" (sem transparência)."""
    if char_id not in _flood_cache:
        flood = CHARACTERS_BY_ID[char_id].get("super", {}).get("flood")
        art = None
        if flood:
            tele, water, folder = flood["teleport"], flood["water_fx"], flood["waves"]
            art = {"teleport": _strip(tele["sheet_path"], *tele["size"]),
                   "water": _strip(water["sheet_path"], *water["size"]),
                   "waves": {n: pygame.image.load(os.path.join(folder, f"frame{n}.png")).convert_alpha()
                             for n in (1, 2, 4, 5)},
                   "texture": pygame.image.load(os.path.join(folder, "frame3.png")).convert()}
        _flood_cache[char_id] = art
    return _flood_cache[char_id]


_scaled_cache = {}
_sized_cache = {}


def sized_frame(image, factor):
    """Frame do cache no tamanho `factor` (height do personagem), guardado para reuso."""
    if factor == 1.0:
        return image
    key = (id(image), factor)
    if key not in _sized_cache:
        size = (max(1, round(image.get_width() * factor)), max(1, round(image.get_height() * factor)))
        _sized_cache[key] = pygame.transform.smoothscale(image, size)
    return _sized_cache[key]


def scaled_frame(image, scale, flip=False, ghost=False):
    """Cópia escalada (em passos de 5%) e espelhada de um frame do cache, guardada para reuso.
    ghost=True devolve uma cópia separada, azulada, para o rastro (quem usa muda o alfa dela)."""
    step = max(1, round(scale * 20))
    key = (id(image), step, flip, ghost)
    if key not in _scaled_cache:
        if step == 20:
            scaled = image.copy()
        else:
            size = (max(1, round(image.get_width() * step / 20)), max(1, round(image.get_height() * step / 20)))
            scaled = pygame.transform.smoothscale(image, size)
        scaled = pygame.transform.flip(scaled, flip, False)
        if ghost:
            scaled.fill((0, 40, 70), special_flags=pygame.BLEND_RGB_ADD)
        _scaled_cache[key] = scaled
    return _scaled_cache[key]


_sound_cache = {}


def get_sounds(char_id):
    """Sons do lutador já carregados e nivelados ({"atk1": Sound, ...}); vazio sem áudio."""
    if char_id not in _sound_cache:
        files = CHARACTERS_BY_ID[char_id].get("sounds", {})
        loaded = {}
        for name, spec in files.items():
            spec = spec if isinstance(spec, dict) else {"files": spec}
            names = [spec["files"]] if isinstance(spec["files"], str) else spec["files"]
            loaded[name] = audio.load([os.path.join(SOUND_DIR, n) for n in names], audio.LEVELS[name],
                                      starts=spec.get("starts"), delay=spec.get("delay", 0.0),
                                      keep=spec.get("keep", 1.0))
        _sound_cache[char_id] = {name: sound for name, sound in loaded.items() if sound is not None}
    return _sound_cache[char_id]


def preload_characters():
    """Carrega o elenco inteiro. Chamar uma vez, depois de pygame.display.set_mode()."""
    for char in CHARACTERS:
        get_frames(char["id"])
        get_super_fx(char["id"])
        get_flood_art(char["id"])
        get_sounds(char["id"])


# ---------------- IA DA CPU ----------------
DIFFICULTIES = ("easy", "normal", "hard")
DIFFICULTY_LABELS = {"easy": "Fácil", "normal": "Normal", "hard": "Difícil"}

# think        -> frames entre decisões (menor = reage mais rápido)
# parry        -> chance de tentar o parry num golpe que vai alcançar a CPU
# parry_error  -> erro máximo (frames) no tempo do parry; acerta se errar até PARRY_WINDOW // 2
# aggression   -> 0..1, peso de avançar/atacar em vez de esperar/recuar
# punish       -> chance de castigar o oponente preso na recuperação de um golpe
# anti_air     -> chance de responder a um pulo na direção da CPU
# anti_air_mix -> pesos da resposta ao pulo: (golpe, pulo, dash para trás)
# jump_in      -> peso de entrar pulando
# dash         -> peso de usar o dash para entrar/sair
# super        -> peso de soltar o SUPER quando a barra está cheia e o oponente está no alcance
AI_PROFILES = {
    "easy": {"think": (26, 44), "parry": 0.3, "parry_error": 9, "aggression": 0.3, "punish": 0.1,
             "anti_air": 0.2, "anti_air_mix": (1, 1, 1), "jump_in": 0.06, "dash": 0.04, "super": 0.3},
    "normal": {"think": (14, 26), "parry": 0.55, "parry_error": 6, "aggression": 0.55, "punish": 0.4,
               "anti_air": 0.45, "anti_air_mix": (2, 1, 1), "jump_in": 0.1, "dash": 0.1, "super": 0.7},
    "hard": {"think": (6, 13), "parry": 0.8, "parry_error": 5, "aggression": 0.8, "punish": 0.85,
             "anti_air": 0.75, "anti_air_mix": (4, 1, 1), "jump_in": 0.12, "dash": 0.18, "super": 1.0},
}


class _CpuMemory:
    """O que a CPU lembra de um frame para o outro."""

    def __init__(self):
        self.plan = "wait"
        self.think_timer = 0
        self.jump_started = False
        self.threat_seen = None    # chave do último golpe do oponente em que já sorteou o parry
        self.parry_in = -1         # frames até tocar para trás (-1 = não vai tentar)
        self.bracing = False       # já tocou para trás: fica parada esperando o golpe
        self.punish_seen = False   # já sorteou o castigo da recuperação atual do oponente?
        self.air_seen = False      # já sorteou o anti-aéreo do pulo atual do oponente?


class Hat:
    """Chapéu do SUPER bumerangue em voo. x, y = centro na tela; direction = lado para onde foi.

    state: "out" (indo, cada vez mais devagar), "grind" (furando o oponente; quem move é o
    Fighter) ou "back" (voltando, cada vez mais rápido, e no fim subindo até a mão)."""
    __slots__ = ("x", "y", "base_y", "line_y", "direction", "speed", "state", "passes", "hits_left",
                 "clock", "touched", "dead", "dragging", "age", "scale", "trail")

    def __init__(self, x, y, line_y, direction, speed):
        self.x, self.y = x, y
        self.base_y = y            # altura sem a subida final para a mão
        self.line_y = line_y
        self.direction = direction
        self.speed = speed
        self.state = "out"
        self.passes = 0            # 0 = ida, 1 = volta
        self.hits_left = 0
        self.clock = 0
        self.touched = False       # já encostou no oponente nesta passada
        self.dead = False          # levou parry: volta sem acertar mais nada
        self.dragging = False      # a volta pegou o oponente e vem arrastando
        self.age = 0
        self.scale = HAT_START_SCALE
        self.trail = []            # (x, y, escala) dos últimos frames

    def copy(self):
        hat = Hat(self.x, self.y, self.line_y, self.direction, self.speed)
        for name in ("base_y", "state", "passes", "touched", "age", "scale"):
            setattr(hat, name, getattr(self, name))
        return hat

    def box(self, size):
        rect = pygame.Rect(0, 0, round(size[0] * self.scale), round(size[1] * self.scale))
        rect.center = (round(self.x), round(self.y))
        return rect

    def step(self, catch, screen_width):
        """Anda um frame. catch = (x, y) da mão de quem jogou. Retorna True ao chegar na mão."""
        self.age += 1
        self.scale = min(1.0, self.scale + (1 - HAT_START_SCALE) / HAT_GROW)
        self.base_y += (self.line_y - self.base_y) * 0.15  # desce da mão para a altura do voo
        self.y = self.base_y
        if self.state == "out":
            self.x += self.direction * self.speed
            self.speed -= HAT_DECEL
            low, high = HAT_EDGE, screen_width - HAT_EDGE
            if self.speed <= 0 or not low <= self.x <= high:
                self.x = min(high, max(low, self.x))
                self.state, self.speed, self.passes, self.touched = "back", 0.0, 1, False
        elif self.state == "back":
            self.speed = min(HAT_MAX_SPEED, self.speed + HAT_DECEL)
            self.x -= self.direction * self.speed
            ahead = (self.x - catch[0]) * self.direction  # quanto falta (positivo = ainda na frente)
            if ahead <= 0:
                self.x, self.y = catch
                return True
            if ahead < HAT_RISE:  # perto da mão: sobe até ela e volta ao tamanho de chapéu na mão
                t = 1 - ahead / HAT_RISE
                t = t * t * (3 - 2 * t)
                self.y = self.base_y + (catch[1] - self.base_y) * t
                self.scale = min(self.scale, 1 - (1 - HAT_START_SCALE) * t)
        return False

    def swept_box(self, size, before):
        """Hitbox cobrindo o caminho do frame (de before até aqui): rápido, não atravessa ninguém."""
        return before.union(self.box(size))

    def frames_to_touch(self, rect, size, catch, screen_width, limit=160):
        """Em quantos frames encosta em rect (parado lá), seguindo o voo; None se voltar sem encostar."""
        hat = self.copy()
        for frame in range(limit):
            before = hat.box(size)
            if hat.step(catch, screen_width):
                return None
            if hat.swept_box(size, before).colliderect(rect):
                return frame
        return None


class Fighter():
    def __init__(self, x, y, player, flip, character, is_cpu=False, cpu_diff="normal", alt_palette=False):
        self.player = player
        self.character = character
        self.name = character["name"]
        self.controls = CONTROLS[player]
        self.offset = character["data"][2]
        self.frame_size = int(character["data"][0] * character["data"][1])
        self.height_factor = character.get("height", 1.0)
        self.super_data = character.get("super")
        self.super_range = (self.super_data or {}).get("range", ATTACKS[SUPER]["range"])
        self.super_color = (self.super_data or {}).get("color", SUPER_COLOR_DEFAULT)
        self.super_damage = (self.super_data or {}).get("damage", ATTACKS[SUPER]["damage"])
        self.launch = (self.super_data or {}).get("launch")
        self.sonic = (self.super_data or {}).get("sonic")
        self.boomerang = (self.super_data or {}).get("boomerang")
        self.beam = (self.super_data or {}).get("beam")
        self.flood = (self.super_data or {}).get("flood")
        self.rapid = self.sonic or self.beam or self.flood   # SUPER de vários acertos seguidos
        stats = character["stats"]
        self.max_health = stats["max_health"]
        self.speed = stats["speed"]
        self.jump_vel = stats["jump_vel"]
        self.dmg_mult = stats["dmg_mult"]
        self.max_stamina = stats.get("stamina", 100)
        self.is_cpu = is_cpu
        self.cpu_diff = cpu_diff
        self.alt_palette = alt_palette
        self.ai = _CpuMemory() if is_cpu else None
        self.flip = flip
        self.animation_list = get_frames(character["id"], alt_palette)
        self.feet_y = self.animation_list[0][0].get_bounding_rect().bottom   # pé no frame parado
        # 0: idle, 1: run, 2: jump, 3: attack1, 4: attack2, 5: hit, 6: death, 7: super
        self.action = 0
        self.frame_index = 0
        self.image = self.animation_list[self.action][self.frame_index]
        self.anim_ms = 0.0             # tempo de jogo (ms) no frame atual da animação
        self.rect = pygame.Rect((x, y, 100, 300))
        self.vel_y = 0
        self.last_dx = 0               # deslocamento horizontal do último frame (a IA usa)
        self.knockback = 0
        self.running = False
        self.jumping = False
        self.attacking = False
        self.attack_type = 0
        self.attack_id = 0             # conta os golpes (a CPU avalia o parry de cada um uma vez)
        self.attack_cooldown = 0
        self.attack_fast = False       # o golpe atual gastou estamina (cooldown menor)
        self.attack_hit_done = False   # garante 1 acerto por golpe
        self.attack_landed = False     # o golpe atual encostou no oponente (acerto ou parry)?
        self.attack_rect = None        # só para debug
        self.attack_rect_timer = 0
        self.hit = False
        self.stun_timer = 0            # tonto depois de ter o golpe parado
        self.flash_timer = 0           # pisca branco ao tomar dano
        self.parry_timer = 0           # janela de parry aberta
        self.parry_cooldown = 0
        self.parry_flash = 0           # brilho azul do parry certo
        self.stamina = self.max_stamina
        self.stamina_delay = 0
        self.dash_timer = 0
        self.dash_dir = 0
        self.dash_cooldown = 0
        self.ghosts = []               # rastro do dash: [x, y, imagem, flip, vida]
        self.super_meter = 0
        self.launch_done = False       # SUPER aéreo: já tentou lançar?
        self.super_air = False         # SUPER aéreo: lançou e está no alto
        self.juggled = False           # foi lançado pelo SUPER de alguém (sem controle até cair)
        self.juggle_x = None           # onde ficar (centro) esperando o golpe no alto
        self.juggle_timer = 0
        self.multi_left = 0            # SUPER sônico: acertos que ainda faltam na rajada
        self.multi_clock = 0
        self.hat = None                # SUPER bumerangue: o chapéu em voo (Hat)
        self.hat_caught_at = (0, 0)    # onde o chapéu chegou na mão (o main solta faíscas ali)
        self.hitstun = 0               # frames preso na animação de dano (esperando a volta do chapéu)
        self.paralyzed = 0             # frames parado no tempo (SUPER da enchente de alguém)
        self.arena_width = 1000        # largura da tela (vem do move; a IA usa na previsão do chapéu)
        self.tremor = 0                # frames vibrando (sprite treme no lugar)
        self.tremor_amp = 0
        self.tremor_xy = (0, 0)
        self.signals = []              # avisos para o main: "atk1", "atk2", "super_start", "super_impact",
        #                                "land", "hat_catch"
        self.tick = 0
        self.prev_held = {}            # teclas do frame anterior (para saber o instante do toque)
        self.last_tap = None           # última direção tocada (dash)
        self.last_tap_tick = 0
        self.health = self.max_health
        self.health_trail = self.max_health  # barra "fantasma" do HUD, desce atrasada
        self.trail_delay = 0
        self.alive = True

    # ---------------- CONSULTAS ----------------
    def attack_reach(self, attack_type):
        mult = self.super_range if attack_type == SUPER else ATTACKS[attack_type]["range"]
        return int(self.rect.width * mult)

    def frame_ms(self, action, index):
        if action == 7 and self.super_data:
            timings = self.super_data["frame_ms"]
            return timings[min(index, len(timings) - 1)]
        return ANIM_SPEED.get(action, 100)

    def attack_startup(self, attack_type):
        """Tempo (ms) do início do golpe até o frame de impacto."""
        action = ATTACK_ACTION[attack_type]
        impact = len(self.animation_list[action]) // 2
        return sum(self.frame_ms(action, i) for i in range(impact))

    def impact_frame(self):
        """Frame em que o golpe atual encosta (no SUPER aéreo, primeiro vem o lançamento)."""
        if self.attack_type == SUPER and self.launch and not self.launch_done:
            return self.launch["frame"]
        if self.attack_type == SUPER and self.super_data and "impact_frame" in self.super_data:
            return self.super_data["impact_frame"]
        return len(self.animation_list[self.action]) // 2

    def frames_to_impact(self):
        """Frames até o golpe atual encostar (0 se não está atacando ou já passou do impacto)."""
        if not self.attacking or self.attack_hit_done:
            return 0
        ms = sum(self.frame_ms(self.action, i) for i in range(self.frame_index, self.impact_frame()))
        ms -= self.anim_ms
        return max(0, round(ms / FRAME_MS))

    def floating(self):
        """SUPER aéreo: quem lançou fica parado no alto durante o golpe, e o lançado espera o golpe lá."""
        if self.vel_y < 0:
            return False
        if self.super_air and self.attacking:
            impact = len(self.animation_list[7]) // 2
            return self.frame_index in (impact, impact + 1)
        return self.juggled and self.juggle_x is not None

    def super_ready(self):
        return self.super_meter >= SUPER_MAX

    def can_dash(self):
        return self.dash_cooldown == 0 and self.stamina >= DASH_COST and not self.jumping

    def invulnerable(self):
        """Início do dash e começo do SUPER (até o impacto) não podem ser acertados."""
        dodging = self.dash_timer > DASH_FRAMES - DASH_IFRAMES
        super_startup = self.attacking and self.attack_type == SUPER and not self.attack_hit_done
        return dodging or super_startup

    def visual_center_x(self):
        """Centro do desenho (a sombra usa), igual para frames normais e do SUPER; com "shadow",
        o meio entre os pés do frame atual do SUPER."""
        shadow = (self.super_data or {}).get("shadow")
        if self.action == 7 and shadow and self.frame_index < len(shadow):
            return self.super_point(shadow[self.frame_index], 0)[0]
        return self.rect.x - self.offset[0] + self.frame_size // 2

    def super_start_ms(self, index):
        """Tempo de jogo (ms) do começo do SUPER até o começo do frame index."""
        return sum(self.frame_ms(7, i) for i in range(index))

    def super_elapsed_ms(self):
        """Tempo de jogo (ms) desde o começo do SUPER, ou None fora dele."""
        if self.action != 7 or not self.attacking:
            return None
        return self.super_start_ms(self.frame_index) + self.anim_ms

    def frames_to_end(self):
        """Frames de jogo até o fim da animação atual."""
        frames = len(self.animation_list[self.action])
        ms = sum(self.frame_ms(self.action, i) for i in range(self.frame_index, frames)) - self.anim_ms
        return max(0, round(ms / FRAME_MS))

    def super_point(self, px, py):
        """Onde o pixel (px, py) de um frame do SUPER aparece na tela agora (espelhado se virado)."""
        left, top, _, _ = self.super_data["rect"]
        x0 = self.rect.x - self.offset[0]
        x = x0 + self.frame_size - left - px if self.flip else x0 + left + px
        return self.grow(self.rect.x, self.rect.y, x, self.rect.y - self.offset[1] + top + py)

    def grow(self, rect_x, rect_y, x, y):
        """Ponto (x, y) do desenho no tamanho do personagem: afasta do pé, que fica parado."""
        k = self.height_factor
        ax = rect_x - self.offset[0] + self.frame_size // 2
        ay = rect_y + FEET_Y
        return ax + (x - ax) * k, ay + (y - ay) * k

    def threat(self, target):
        """Golpe deste lutador que vai encostar em target: (chave, frames até encostar) ou None.
        A chave muda a cada golpe e a cada passada do chapéu; a CPU sorteia o parry uma vez por chave."""
        hat = self.hat
        if hat is not None:
            if hat.dead or hat.touched or hat.state == "grind":
                return None
            frames = hat.frames_to_touch(target.rect, self.boomerang["box"],
                                         self.super_point(*self.boomerang["catch"]), self.arena_width)
            return None if frames is None else ((self.attack_id, hat.passes), frames)
        if not self.attacking or self.attack_hit_done:
            return None
        if self.attack_type == SUPER and self.boomerang:
            # ainda na preparação: o chapéu vai sair da mão no frame do arremesso
            flight = self._new_hat().frames_to_touch(target.rect, self.boomerang["box"],
                                                     self.super_point(*self.boomerang["catch"]), self.arena_width)
            return None if flight is None else ((self.attack_id, 0), self.frames_to_impact() + flight)
        dist = abs(target.rect.centerx - self.rect.centerx)
        if dist > self.attack_reach(self.attack_type) + target.rect.width // 2 + 40:
            return None
        return (self.attack_id, 0), self.frames_to_impact()

    def pop_signals(self):
        signals, self.signals = self.signals, []
        return signals

    def sync_state(self):
        """Números que definem a luta (o online compara os dos dois computadores)."""
        hat = self.hat
        return (self.rect.x, self.rect.y, self.health, self.action, self.frame_index, round(self.anim_ms),
                self.vel_y, round(self.knockback * 100), round(self.stamina * 100), self.super_meter,
                self.attack_cooldown, self.parry_timer, self.dash_timer, self.stun_timer, self.hitstun,
                self.paralyzed, self.attacking, self.hit, self.jumping, self.juggled, self.flip,
                None if hat is None else (round(hat.x), round(hat.y), hat.state))

    def spend_stamina(self, amount):
        self.stamina = max(0, self.stamina - amount)
        self.stamina_delay = STAMINA_REGEN_DELAY

    def gain_super(self, amount):
        self.super_meter = min(SUPER_MAX, self.super_meter + amount)

    # ---------------- MOVIMENTO ----------------
    def move(self, screen_width, screen_height, target, can_act=True, held=None):
        """Controles + física de um frame. Retorna um HitEvent se um golpe encostou no oponente.
        held: botões deste frame (dict de BUTTONS) vindos de fora (rede); None = ler o teclado."""
        self.arena_width = screen_width
        if self.paralyzed > 0:
            # parado no tempo pelo SUPER da enchente: nada anda (nem cai, nem o golpe, nem o chapéu)
            self.running = False
            return None
        dx = 0
        dy = 0
        self.running = False
        self.tick += 1
        on_ground = not self.jumping
        hit_event = None
        if self.parry_timer > 0:
            self.parry_timer -= 1
        if self.parry_cooldown > 0:
            self.parry_cooldown -= 1
        if self.dash_cooldown > 0:
            self.dash_cooldown -= 1

        # os botões são lidos todo frame para perceber o instante exato do toque
        player_inputs = None if self.is_cpu else self._read_player_inputs(target, held)

        if self.dash_timer > 0:
            # DASH: rápido no começo e desacelerando; sem controle até acabar
            self.dash_timer -= 1
            dx = round(self.dash_dir * DASH_SPEED * (0.4 + 0.6 * self.dash_timer / DASH_FRAMES))
            self.running = True
            if self.tick % 2 == 0:
                self.ghosts.append([self.rect.x, self.rect.y, self.image, self.flip, 10])
        elif can_act and self.alive and not self.hit and not self.attacking:
            inputs = self._compute_ai_inputs(target) if self.is_cpu else player_inputs

            if inputs["dash"] and on_ground and self.can_dash():
                self.start_dash(inputs["dash"])
            else:
                if inputs["left"]:
                    dx = -self.speed
                    self.running = True
                if inputs["right"]:
                    dx = self.speed
                    self.running = True

                # PARRY: só no chão; segurar para trás não defende, só o toque conta
                if inputs["parry"] and on_ground and self.parry_cooldown == 0:
                    self.parry_timer = PARRY_WINDOW
                    self.parry_cooldown = PARRY_WINDOW + PARRY_WHIFF_COOLDOWN

                if inputs["jump"] and on_ground:
                    self.vel_y = self.jump_vel
                    self.jumping = True

                # ATAQUES
                if inputs["super"] and on_ground and self.super_ready():
                    self.start_attack(SUPER)
                    if self.flood and target.alive:  # o oponente para no tempo até a água chegar
                        target.get_paralyzed(self.frames_to_impact() + PARALYZE_MARGIN)
                elif inputs["atk1"]:
                    self.start_attack(1)
                elif inputs["atk2"]:
                    self.start_attack(2)

        # SUPER aéreo: antes do golpe vem o lançamento
        if (self.attacking and self.attack_type == SUPER and self.launch and not self.launch_done
                and self.frame_index >= self.launch["frame"]):
            self.launch_done = True
            hit_event = self.try_launch(target, screen_width)

        # O dano só sai no meio da animação do golpe (frame de impacto)
        if self.attacking and not self.attack_hit_done and self.action in ATTACK_ACTIONS:
            if self.frame_index >= self.impact_frame():
                self.attack_hit_done = True
                if self.attack_type == SUPER:
                    self.signals.append("super_impact")
                    if self.rapid:  # começa a rajada: este é o 1º acerto, os outros vêm depois
                        self.multi_left = self.rapid["hits"] - 1
                        self.multi_clock = self.rapid["every"]
                        if not self.flood:  # quem solta a rajada/o raio treme junto
                            self.tremor, self.tremor_amp = TREMOR_SELF, TREMOR_SELF_AMP
                if self.attack_type == SUPER and self.boomerang:
                    self.hat = self._new_hat()  # o chapéu sai da mão; quem acerta é ele
                else:
                    hit_event = self.resolve_attack(target) or hit_event

        # SUPER bumerangue: o chapéu voa sozinho (mesmo se quem jogou apanhar)
        if self.hat is not None:
            hit_event = self._update_hat(target) or hit_event

        # SUPER sônico: os outros acertos da rajada, um a cada "every" frames
        if self.multi_left > 0:
            if not (self.attacking and self.attack_type == SUPER):
                self.multi_left = 0  # levou golpe ou acabou a animação
            else:
                self.multi_clock -= 1
                if self.multi_clock <= 0:
                    self.multi_left -= 1
                    self.multi_clock = self.rapid["every"]
                    hit_event = self.resolve_attack(target) or hit_event

        # FÍSICA (sempre roda, mesmo sem controle)
        if self.floating():
            self.vel_y = 0
        else:
            self.vel_y += GRAVITY
        dy += self.vel_y

        # lançado pelo SUPER aéreo: vai para a frente de quem lançou e espera o golpe no alto
        if self.juggle_x is not None:
            dx += round((self.juggle_x - self.rect.centerx) * JUGGLE_PULL)
            self.juggle_timer -= 1
            if self.juggle_timer <= 0:
                self.juggle_x = None

        if abs(self.knockback) > 0.5:
            dx += round(self.knockback)
            self.knockback *= 0.8
        else:
            self.knockback = 0

        # COLISÕES COM A TELA
        if self.rect.left + dx < 0:
            dx = -self.rect.left
        if self.rect.right + dx > screen_width:
            dx = screen_width - self.rect.right
        if self.rect.bottom + dy > screen_height - GROUND_MARGIN:
            self.vel_y = 0
            dy = screen_height - GROUND_MARGIN - self.rect.bottom
            self.jumping = False
            if self.juggled:
                self.juggled = False
                self.juggle_x = None
                self.signals.append("land")

        # Olha para o oponente (mas não vira no meio do golpe)
        if not self.attacking and self.alive:
            self.flip = target.rect.centerx < self.rect.centerx

        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1

        self.last_dx = dx
        self.rect.x += dx
        self.rect.y += dy

        # COLISÃO ENTRE OS CORPOS (não atravessa o oponente)
        if self.rect.colliderect(target.rect):
            if self.rect.centerx < target.rect.centerx:
                self.rect.right = target.rect.left
            else:
                self.rect.left = target.rect.right
            self.rect.left = max(0, self.rect.left)
            self.rect.right = min(screen_width, self.rect.right)

        return hit_event

    def _read_player_inputs(self, target, held=None):
        """Botões -> intenções. Parry = TOCAR para trás (longe do oponente); dash = 2 toques."""
        if held is None:
            held = keyboard_buttons(self.controls)
        pressed = {name: down and not self.prev_held.get(name, False) for name, down in held.items()}
        self.prev_held = held

        back = "left" if target.rect.centerx > self.rect.centerx else "right"
        dash = 0
        for name, direction in (("left", -1), ("right", 1)):
            if pressed[name]:
                if self.last_tap == name and self.tick - self.last_tap_tick <= DASH_TAP_WINDOW:
                    dash = direction
                    self.last_tap = None
                else:
                    self.last_tap = name
                    self.last_tap_tick = self.tick
        return {
            "left": held["left"],
            "right": held["right"],
            "jump": held["jump"],
            "parry": pressed[back],
            "dash": dash,
            "atk1": held["atk1"],
            "atk2": held["atk2"],
            "super": pressed["super"],
        }

    def start_dash(self, direction):
        self.spend_stamina(DASH_COST)
        self.dash_timer = DASH_FRAMES
        self.dash_dir = direction
        self.dash_cooldown = DASH_FRAMES + DASH_COOLDOWN
        self.parry_timer = 0

    # ---------------- IA ----------------
    def _compute_ai_inputs(self, target):
        """Intenções da CPU. Reações têm atraso e chance (pela dificuldade); as demais
        decisões só são revistas de tempos em tempos, nunca perfeitas a cada frame."""
        profile = AI_PROFILES[self.cpu_diff]
        mem = self.ai
        inputs = dict.fromkeys(INTENT_KEYS, False)
        dist = abs(target.rect.centerx - self.rect.centerx)
        toward = "right" if target.rect.centerx > self.rect.centerx else "left"
        away = "left" if toward == "right" else "right"

        # 1) PARRY: cada golpe do oponente que vai alcançar a CPU (e cada passada do chapéu do
        #    SUPER bumerangue) é avaliado uma única vez. A CPU mira no meio da janela, mas erra o
        #    tempo conforme a dificuldade (às vezes toca cedo ou tarde demais).
        threat = target.threat(self)
        if threat and mem.threat_seen != threat[0]:
            mem.threat_seen = threat[0]
            if random.random() < profile["parry"]:
                err = profile["parry_error"]
                aim = threat[1] - (PARRY_WINDOW + 1) // 2
                mem.parry_in = max(0, aim + random.randint(-err, err))
        if not target.attacking:
            mem.punish_seen = False

        if threat and (mem.parry_in >= 0 or mem.bracing):
            if mem.parry_in == 0:
                inputs["parry"] = True
                mem.bracing = True
            if mem.parry_in >= 0:
                mem.parry_in -= 1
            return inputs  # parada, esperando o golpe
        mem.parry_in = -1
        mem.bracing = False

        # 2) CASTIGO: o golpe do oponente já passou do impacto e ele está preso na animação
        if target.attacking and target.attack_hit_done and not mem.punish_seen:
            mem.punish_seen = True
            if random.random() < profile["punish"]:
                self._ai_set_plan("punish", 24)

        # 3) ANTI-AÉREO: oponente pulando na direção da CPU
        if target.jumping and not mem.air_seen:
            mem.air_seen = True
            coming = target.last_dx * (self.rect.centerx - target.rect.centerx) > 0
            if (dist < 260 or (coming and dist < 450)) and random.random() < profile["anti_air"]:
                plan = random.choices(("anti_air", "air_to_air", "dash_away"), weights=profile["anti_air_mix"])[0]
                self._ai_set_plan(plan, 45)
        elif not target.jumping:
            mem.air_seen = False

        # 4) DECISÃO no ritmo da dificuldade
        mem.think_timer -= 1
        if mem.think_timer <= 0:
            plan = self._ai_choose_plan(target, dist, profile)
            frames = random.randint(*profile["think"])
            if plan == "retreat":
                frames = min(frames, random.randint(8, 16))  # recuo curto, só para abrir espaço
            self._ai_set_plan(plan, frames)

        return self._ai_follow_plan(inputs, target, dist, toward, away)

    def _ai_set_plan(self, plan, frames):
        self.ai.plan = plan
        self.ai.think_timer = frames
        self.ai.jump_started = False

    def _ai_choose_plan(self, target, dist, profile):
        """Sorteia o próximo plano conforme a distância (perto / meio / longe)."""
        agg = profile["aggression"]
        skill = profile["parry"]
        dash = profile["dash"] if self.stamina >= DASH_COST + 15 else 0
        super_w = profile["super"] if self.super_ready() and self._ai_in_reach(target, SUPER, dist) else 0
        if self._ai_in_reach(target, 1, dist):
            # PERTO: mistura golpe rápido e forte, abre espaço ou espera o golpe para dar parry
            weights = {
                "atk1": 0.45 * agg + (0.3 * agg if target.hit else 0),
                "atk2": 0.3 * agg,
                "super": super_w * (2 if target.stun_timer > 0 else 1),
                "retreat": 0.25 * skill + 0.02,
                "dash_out": dash,
                "wait": 0.3 * (1 - agg) + 0.2 * skill + 0.03,
            }
        elif dist <= self.attack_reach(2) + target.rect.width // 2 + 110:
            # MEIO: footsies (vai e volta na beira do alcance) e cutucadas
            weights = {
                "poke": 0.35 * agg + 0.05,
                "atk2": 0.25 * agg if self._ai_in_reach(target, 2, dist) else 0,
                "super": super_w,
                "footsie": 0.05 + 0.4 * agg * skill,
                "approach": 0.2,
                "dash_in": dash * 0.6,
                "retreat": 0.2 * skill,
                "jump_in": profile["jump_in"],
                "wait": 0.3 * (1 - agg) + 0.03,
            }
        else:
            # LONGE: encurta a distância, às vezes pulando ou com dash
            weights = {
                "approach": 0.35 + 0.5 * agg,
                "jump_in": profile["jump_in"] * 2,
                "dash_in": dash * 1.5,
                "super": super_w,
                "wait": 0.45 * (1 - agg) + 0.03,
            }
        plans = list(weights)
        return random.choices(plans, weights=[weights[p] for p in plans])[0]

    def _ai_follow_plan(self, inputs, target, dist, toward, away):
        """Transforma o plano atual nas intenções deste frame."""
        mem = self.ai
        plan = mem.plan
        if plan == "approach":
            inputs[toward] = True
        elif plan == "retreat":
            inputs[away] = True
        elif plan == "footsie":
            # fica na beira do alcance do golpe forte esperando o oponente errar
            ideal = self.attack_reach(2) + target.rect.width // 2 + 25
            if dist > ideal + 20:
                inputs[toward] = True
            elif dist < ideal - 20:
                inputs[away] = True
        elif plan in ("dash_in", "dash_out", "dash_away"):
            direction = toward if plan == "dash_in" else away
            if self.can_dash():
                inputs["dash"] = 1 if direction == "right" else -1
                self._ai_set_plan("wait", 6)
            else:
                inputs[direction] = True
        elif plan == "super":
            if self.super_ready() and self._ai_in_reach(target, SUPER, dist):
                self._ai_press_attack(inputs, SUPER)
            elif self.super_ready():
                inputs[toward] = True
            else:
                self._ai_set_plan("wait", 4)
        elif plan in ("atk1", "atk2", "poke"):
            attack = 2 if plan == "atk2" else 1
            if self._ai_in_reach(target, attack, dist):
                self._ai_press_attack(inputs, attack)
            else:
                inputs[toward] = True
        elif plan == "punish":
            # oponente tonto depois do parry: no normal/difícil a CPU gasta o SUPER se tiver
            if (target.stun_timer > 0 and self.super_ready() and self.cpu_diff != "easy"
                    and self._ai_in_reach(target, SUPER, dist)):
                self._ai_press_attack(inputs, SUPER)
            else:
                attack = self._ai_fastest_attack(target, dist)
                if attack:
                    self._ai_press_attack(inputs, attack)
                else:
                    inputs[toward] = True
        elif plan == "anti_air":
            # espera o oponente descer para dentro do alcance e solta o golpe
            attack = self._ai_fastest_attack(target, dist, slack=70)
            if not target.jumping:
                self._ai_set_plan("wait", 4)
            elif attack and target.vel_y > -8:
                self._ai_press_attack(inputs, attack)
        elif plan in ("jump_in", "air_to_air"):
            if not mem.jump_started:
                mem.jump_started = True
                inputs["jump"] = True
                if plan == "jump_in":
                    inputs[toward] = True
            elif self.jumping:
                if plan == "jump_in":
                    inputs[toward] = True
                if self._ai_in_reach(target, 1, dist) and (self.vel_y > 0 or plan == "air_to_air"):
                    self._ai_press_attack(inputs, 1)
            else:
                self._ai_set_plan("wait", 4)
        return inputs

    def _ai_press_attack(self, inputs, attack):
        if attack == SUPER:
            inputs["super"] = True
            self.ai.plan = "wait"
        elif self.attack_cooldown == 0:
            inputs["atk1" if attack == 1 else "atk2"] = True
            self.ai.plan = "wait"

    def _ai_in_reach(self, target, attack, dist, slack=0):
        return dist <= self.attack_reach(attack) + target.rect.width // 2 - 10 + slack

    def _ai_fastest_attack(self, target, dist, slack=0):
        """Entre os golpes que alcançam, o que chega mais rápido no impacto (None se nenhum)."""
        options = [a for a in (1, 2) if self._ai_in_reach(target, a, dist, slack)]
        return min(options, key=self.attack_startup, default=None)

    # ---------------- COMBATE ----------------
    def start_attack(self, attack_type):
        # o SUPER ignora o cooldown (dá para usar logo depois de apanhar)
        if attack_type != SUPER and self.attack_cooldown > 0:
            return
        self.attacking = True
        self.attack_type = attack_type
        self.attack_id += 1
        self.attack_hit_done = False
        self.attack_landed = False
        self.parry_timer = 0
        cost = ATTACKS[attack_type]["stamina"]
        self.attack_fast = bool(cost) and self.stamina >= cost
        if self.attack_fast:
            self.spend_stamina(cost)
        if attack_type == SUPER:
            self.super_meter = 0
            self.launch_done = False
            self.super_air = False
            self.signals.append("super_start")
        else:
            self.signals.append(f"atk{attack_type}")  # o main toca o som do golpe
        # força a animação a começar do primeiro frame
        self.action = ATTACK_ACTION[attack_type]
        self.frame_index = 0
        self.anim_ms = 0.0

    def _attack_box(self, target):
        """Hitbox do golpe atual. Retorna (direção, ponto de contato) se pegou o oponente, senão None."""
        reach = self.attack_reach(self.attack_type)
        top, height = self.rect.y, self.rect.height
        if self.attack_type == SUPER and self.flood:  # a água enche a arena: pega lá no alto também
            top, height = self.rect.bottom - 1000, 1000
        if self.flip:  # virado para a esquerda
            attack_rect = pygame.Rect(self.rect.centerx - reach, top, reach, height)
        else:
            attack_rect = pygame.Rect(self.rect.centerx, top, reach, height)
        self.attack_rect = attack_rect
        self.attack_rect_timer = 8
        if not (target.alive and attack_rect.colliderect(target.rect)):
            return None
        if target.invulnerable() and not target.paralyzed:  # paralisado não escapa (nem no dash)
            return None
        self.attack_landed = True
        direction = 1 if target.rect.centerx > self.rect.centerx else -1
        # ponto de contato: lado do oponente virado para o atacante, na altura do tronco
        contact_x = target.rect.left + 15 if direction > 0 else target.rect.right - 15
        return direction, (contact_x, target.rect.y + random.randint(35, 105))

    def _parried(self, target, direction, contact):
        """PARRY: sem dano; o atacante é empurrado e fica tonto (o SUPER só é anulado)."""
        target.on_parry()
        self.knockback = -direction * PARRY_PUSHBACK
        if self.attack_type == SUPER:
            self.attack_hit_done = True  # o resto do SUPER não acerta mais
            self.multi_left = 0
        else:
            self.get_stunned()
        return HitEvent("parry", self.attack_type, contact, direction, False)

    def resolve_attack(self, target):
        hit = self._attack_box(target)
        if not hit:
            return None
        direction, contact = hit
        if target.parry_timer > 0 and not target.attacking and not target.hit:
            return self._parried(target, direction, contact)

        atk = ATTACKS[self.attack_type]
        base = self.super_damage if self.attack_type == SUPER else atk["damage"]
        knockback = atk["knockback"]
        kind = "hit"
        sonic = self.attack_type == SUPER and self.rapid
        if sonic:
            tick = round(base * SONIC_TICK_SHARE)
            if self.multi_left > 0:  # acerto do meio da rajada: pouco dano, segura o oponente
                base, knockback, kind = tick, SONIC_TICK_PUSH, "multi"
            else:                    # último acerto: o resto do dano e arremessa
                base -= tick * (self.rapid["hits"] - 1)
            target.tremor, target.tremor_amp = TREMOR_HIT, TREMOR_HIT_AMP
        if self.super_air:
            base -= self.launch["damage"]  # parte do dano já saiu no lançamento
        damage = max(1, round(base * self.dmg_mult))
        target.take_hit(damage, knockback, direction, meter=kind == "hit")
        if self.super_air:
            target.vel_y = SUPER_AIR_POP
            target.juggle_x = None
        if sonic and kind == "hit" and target.alive:
            target.vel_y = SONIC_FINAL_POP
            target.jumping = True
            target.juggled = True  # segura a animação de dano até cair (e levanta poeira)
            if self.flood:  # enchente: só levanta depois que quem soltou voltar à base
                target.hitstun = max(target.hitstun, self.frames_to_end() + FLOOD_RECOVER_EXTRA)
        self.gain_super(SUPER_GAIN_HIT[self.attack_type])
        color = self.super_color if self.attack_type == SUPER else None
        return HitEvent(kind, self.attack_type, contact, direction, not target.alive, color)

    def try_launch(self, target, screen_width):
        """Começo do SUPER aéreo: se o oponente está perto, uma explosão lança os dois para cima.
        Se errar, o SUPER continua no chão; se levar parry, é anulado."""
        hit = self._attack_box(target)
        if not hit:
            return None
        direction, contact = hit
        if target.parry_timer > 0 and not target.attacking and not target.hit:
            return self._parried(target, direction, contact)

        rise = -math.sqrt(2 * GRAVITY * self.launch["rise"])
        self.vel_y = rise
        self.jumping = True
        self.super_air = True
        target.take_hit(max(1, round(self.launch["damage"] * self.dmg_mult)), 0, direction)
        target.vel_y = rise
        target.jumping = True
        if target.alive:
            target.juggled = True
            margin = target.rect.width // 2
            gap_x = self.rect.centerx + direction * self.launch["gap"]
            target.juggle_x = max(margin, min(screen_width - margin, gap_x))
            target.juggle_timer = JUGGLE_MAX_WAIT
        ground_contact = (target.rect.centerx, target.rect.bottom - 20)
        return HitEvent("launch", SUPER, ground_contact, direction, not target.alive, self.super_color)

    # ---------------- SUPER BUMERANGUE ----------------
    def _new_hat(self):
        """Chapéu saindo da mão (onde ele está no frame do arremesso), com força para ir até o
        alcance máximo ou a parede, o que vier antes."""
        x, y = self.super_point(*self.boomerang["hand"])
        direction = -1 if self.flip else 1
        room = self.arena_width - HAT_EDGE - x if direction > 0 else x - HAT_EDGE
        reach = max(30, min(self.boomerang["reach"], room))
        return Hat(x, y, self.rect.bottom - HAT_LINE, direction, math.sqrt(2 * HAT_DECEL * reach))

    def _update_hat(self, target):
        """Um frame do chapéu: anda, fura/acerta o oponente, arrasta e chega na mão."""
        hat = self.hat
        if not self.alive or hat.age > HAT_LIFE:
            self._end_hat(target)
            return None
        hat.trail.append((hat.x, hat.y, hat.scale))
        del hat.trail[:-HAT_TRAIL]
        event = None
        size = self.boomerang["box"]
        before = hat.box(size)
        if hat.state == "grind":
            hat.step(None, self.arena_width)
            hat.x = target.rect.centerx - hat.direction * HAT_GRIND_DEPTH  # vai junto com o empurrão
            hat.clock -= 1
            if hat.clock <= 0:
                event = self._hat_tick(target)
        elif hat.step(self.super_point(*self.boomerang["catch"]), self.arena_width):
            self.hat_caught_at = (hat.x, hat.y)
            self._end_hat(target)
            self.signals.append("hat_catch")
            if self.attacking and self.action == 7:  # pega o chapéu: sai do frame de espera
                self.frame_index = self.impact_frame() + 1
                self.anim_ms = 0.0
            return None
        elif (not hat.dead and not hat.touched and target.alive and not target.invulnerable()
              and hat.swept_box(size, before).colliderect(target.rect)):
            event = self._hat_contact(target)

        if hat.dragging:
            if target.alive and target.juggled:
                # arrasta junto (o oponente vem um pouco atrás), mas para antes de encostar
                gap_x = self.rect.centerx + hat.direction * HAT_PULL_GAP
                target.juggle_x = hat.x if (hat.x - gap_x) * hat.direction > 0 else gap_x
                target.juggle_timer = HAT_DRAG_TIMER
            else:
                hat.dragging = False
        return event

    def _end_hat(self, target):
        """O chapéu sumiu (chegou na mão ou quem jogou caiu): solta quem estava sendo arrastado.
        Ele ainda vai até perto de quem jogou e fica caído até o fim da pose."""
        hat = self.hat
        self.hat = None
        if hat is not None and hat.dragging and target.alive and target.juggled:
            target.juggle_x = self.rect.centerx + hat.direction * HAT_PULL_GAP
            target.juggle_timer = HAT_DRAG_TIMER
            if self.attacking and self.action == 7:
                rest = sum(self.frame_ms(7, i) for i in range(self.impact_frame() + 1, len(self.animation_list[7])))
                target.hitstun = max(target.hitstun, round(rest / FRAME_MS) + HAT_RECOVER_EXTRA)

    def _hat_contact_point(self, target):
        hat = self.hat
        x = target.rect.centerx - hat.direction * (25 if hat.passes == 0 else -25)
        return x, round(hat.y) + random.randint(-14, 14)

    def _hat_contact(self, target):
        """Chapéu encostou no oponente: parry, começo das furadas (ida) ou o puxão (volta)."""
        hat = self.hat
        hat.touched = True
        moving = hat.direction if hat.passes == 0 else -hat.direction  # para onde o chapéu anda
        if target.parry_timer > 0 and not target.attacking and not target.hit:
            target.on_parry()
            hat.dead = True
            if hat.state == "out":  # ricocheteia de volta para a mão, sem acertar mais
                hat.state, hat.speed, hat.passes = "back", 0.0, 1
            return HitEvent("parry", SUPER, self._hat_contact_point(target), moving, False)
        if hat.passes == 0:
            hat.state = "grind"
            hat.hits_left = self.boomerang["hits"]
            return self._hat_tick(target)
        return self._hat_pull(target)

    def _hat_tick_damage(self):
        return round(self.super_damage * HAT_TICK_SHARE)

    def _hat_tick(self, target):
        """Uma furada: pouco dano, empurra de leve e segura o oponente até a volta."""
        hat = self.hat
        hat.hits_left -= 1
        hat.clock = self.boomerang["every"]
        target.take_hit(max(1, round(self._hat_tick_damage() * self.dmg_mult)), HAT_TICK_PUSH,
                        hat.direction, meter=False)
        target.flash_timer = 3  # pisca a cada furada em vez de ficar branco direto
        target.tremor, target.tremor_amp = HAT_TREMOR, HAT_TREMOR_AMP
        if target.alive:
            target.hitstun = HAT_HOLD
        if hat.hits_left <= 0 or not target.alive:  # atravessa e vai um pouco além antes de voltar
            hat.state = "out"
            hat.speed = math.sqrt(2 * HAT_DECEL * HAT_PASS)
        return HitEvent("multi", SUPER, self._hat_contact_point(target), hat.direction,
                        not target.alive, self.super_color)

    def _hat_pull(self, target):
        """Volta: o resto do dano, e o oponente é levantado e arrastado até perto de quem jogou."""
        hat = self.hat
        pull = -hat.direction
        base = self.super_damage - self._hat_tick_damage() * self.boomerang["hits"]
        target.take_hit(max(1, round(base * self.dmg_mult)), 0, pull)
        target.hitstun = 0
        if target.alive:
            target.vel_y = HAT_PULL_POP
            target.jumping = True
            target.juggled = True
            target.juggle_x = target.rect.centerx
            target.juggle_timer = HAT_DRAG_TIMER
            hat.dragging = True
        else:
            target.knockback = pull * 12
        self.gain_super(SUPER_GAIN_HIT[SUPER])
        return HitEvent("hit", SUPER, self._hat_contact_point(target), pull, not target.alive, self.super_color)

    def on_parry(self):
        """Parry certo: janela fecha, pode tentar de novo e contra-atacar na hora."""
        self.parry_timer = 0
        self.parry_cooldown = 0
        self.parry_flash = 12
        self.attack_cooldown = 0
        self.gain_super(SUPER_GAIN_PARRY)
        if self.is_cpu:
            self.ai.bracing = False
            self.ai.parry_in = -1
            self._ai_set_plan("punish", 30)

    def get_paralyzed(self, frames):
        """SUPER da enchente de alguém: parado no tempo por `frames` (ou até levar o golpe).
        A janela de parry e o dash acabam: paralisado não defende nem escapa."""
        self.paralyzed = frames
        self.parry_timer = 0
        self.dash_timer = 0

    def get_stunned(self):
        self.attacking = False
        self.hit = True
        self.stun_timer = PARRY_STUN
        self.dash_timer = 0
        self.action = 5
        self.frame_index = 0
        self.anim_ms = 0.0

    def take_hit(self, damage, knockback, direction, meter=True):
        """meter=False: não enche a barra de SUPER (acertos do meio de uma rajada)."""
        self.health = max(0, self.health - damage)
        self.knockback = direction * knockback
        self.attacking = False  # levar golpe interrompe o seu ataque
        self.hit = True
        self.paralyzed = 0      # o golpe tira da paralisia
        self.super_air = False
        self.dash_timer = 0
        self.parry_timer = 0
        self.flash_timer = 6
        self.action = 5
        self.frame_index = 0
        self.anim_ms = 0.0
        if meter:
            self.gain_super(SUPER_GAIN_HURT)
        self.trail_delay = TRAIL_DELAY
        if self.health == 0:
            self.alive = False
            self.hit = False
            self.attacking = False
            self.stun_timer = 0

    # ---------------- ANIMAÇÃO ----------------
    def update(self):
        if self.paralyzed > 0:  # parado no tempo: nem a animação nem os contadores andam
            self.paralyzed -= 1
            return
        if not self.alive:
            self.update_action(6)  # death
        elif self.hit:
            self.update_action(5)  # hit / tonto
        elif self.attacking:
            self.update_action(ATTACK_ACTION[self.attack_type])
        elif self.jumping:
            self.update_action(2)
        elif self.running:
            self.update_action(1)
        else:
            self.update_action(0)

        # o tempo das animações conta quadros de jogo (e não o relógio do computador): assim os
        # dois jogadores do modo online veem exatamente a mesma luta
        self.anim_ms += FRAME_MS
        if self.anim_ms > self.frame_ms(self.action, self.frame_index):
            self.frame_index += 1
            self.anim_ms = 0.0

        frames = len(self.animation_list[self.action])
        if self.action == 7 and self.super_air and self.jumping and self.frame_index >= frames - 1:
            self.frame_index = frames - 2  # SUPER aéreo: segura o penúltimo frame até pousar
        if self.action == 7 and self.hat is not None and self.frame_index > self.impact_frame():
            self.frame_index = self.impact_frame()  # braço esticado esperando o chapéu voltar
        if self.frame_index >= frames:
            if not self.alive:
                self.frame_index = frames - 1
            elif self.action == 5 and (self.stun_timer > 0 or self.juggled or self.hitstun > 0):
                self.frame_index = frames - 1  # tonto, no ar ou preso: segura o último frame
            else:
                self.frame_index = 0
                if self.action in ATTACK_ACTIONS:
                    self.attacking = False
                    self.super_air = False
                    cooldown = ATTACKS[self.attack_type]["cooldown"]
                    self.attack_cooldown = round(cooldown * STAMINA_COOLDOWN_MULT) if self.attack_fast else cooldown
                elif self.action == 5:
                    self.hit = False
                    self.attack_cooldown = HIT_RECOVERY

        self.image = self.animation_list[self.action][self.frame_index]

        for timer in ("flash_timer", "parry_flash", "attack_rect_timer", "stun_timer", "hitstun"):
            if getattr(self, timer) > 0:
                setattr(self, timer, getattr(self, timer) - 1)

        if self.stamina_delay > 0:
            self.stamina_delay -= 1
        elif self.stamina < self.max_stamina:
            self.stamina = min(self.max_stamina, self.stamina + STAMINA_REGEN)

        for ghost in self.ghosts:
            ghost[4] -= 1
        self.ghosts = [g for g in self.ghosts if g[4] > 0]

        # tremor: sorteado aqui (e não no desenho) para não tremer com o jogo pausado
        if self.tremor > 0:
            self.tremor -= 1
            amp = max(1, round(self.tremor_amp * min(1.0, self.tremor / 10)))
            self.tremor_xy = (random.randint(-amp, amp), random.randint(-amp, amp) // 2)
        else:
            self.tremor_xy = (0, 0)

        if self.trail_delay > 0:
            self.trail_delay -= 1
        elif self.health_trail > self.health:
            self.health_trail = max(self.health, self.health_trail - TRAIL_SPEED)

    def update_action(self, new_action):
        if new_action != self.action:
            self.action = new_action
            self.frame_index = 0
            self.anim_ms = 0.0

    def draw(self, surface, offset=(0, 0)):
        """Desenha o lutador; offset desloca tudo (tremor de tela)."""
        ox, oy = offset[0] + self.tremor_xy[0], offset[1] + self.tremor_xy[1]

        # rastro azul do dash
        for gx, gy, image, flip, life in self.ghosts:
            ghost = pygame.transform.flip(sized_frame(image, self.height_factor), flip, False)
            ghost.fill((40, 90, 200), special_flags=pygame.BLEND_RGB_ADD)
            ghost.set_alpha(int(110 * life / 10))
            x, y = self.grow(gx, gy, gx - self.offset[0], gy - self.offset[1])
            surface.blit(ghost, (round(x) + ox, round(y) + oy))

        img = pygame.transform.flip(sized_frame(self.image, self.height_factor), self.flip, False)  # cópia
        if self.paralyzed > 0:
            # parado no tempo: perde a cor, fica azulado e com um brilho frio pulsando
            pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 85)
            img.fill((115, 150, 220), special_flags=pygame.BLEND_RGB_MULT)
            img.fill((int(12 + 12 * pulse), int(38 + 24 * pulse), int(75 + 45 * pulse)),
                     special_flags=pygame.BLEND_RGB_ADD)
        elif self.flash_timer > 0:
            img.fill((150, 150, 150), special_flags=pygame.BLEND_RGB_ADD)    # clarão branco
        elif self.parry_flash > 0:
            img.fill((90, 140, 255), special_flags=pygame.BLEND_RGB_ADD)     # parry certo
        elif self.parry_timer > 0:
            img.fill((170, 200, 255), special_flags=pygame.BLEND_RGB_MULT)  # janela de parry aberta
        elif self.action == 7 and not self.super_data:
            glow = int(45 + 35 * math.sin(pygame.time.get_ticks() / 60))
            img.fill((glow, int(glow * 0.75), 0), special_flags=pygame.BLEND_RGB_ADD)

        x = self.rect.x - self.offset[0]
        y = self.rect.y - self.offset[1]
        extra = self.image.get_width() - self.frame_size
        if extra > 0 and self.action != 7:
            # linha ampliada (row_scale): cresce a partir do meio do pé, que fica no lugar
            x -= extra / 2
            y -= extra * self.feet_y / self.frame_size
        if self.action == 7 and self.super_data:
            # frame do SUPER é maior que o normal; rect diz onde ele fica em relação ao frame normal
            left, top, width, _ = self.super_data["rect"]
            x += self.frame_size - left - width if self.flip else left
            y += top
        x, y = self.grow(self.rect.x, self.rect.y, x, y)   # canto do desenho, no tamanho do personagem
        surface.blit(img, (round(x) + ox, round(y) + oy))

        # estrelinhas de tonto
        if self.stun_timer > 0 and self.alive:
            t = pygame.time.get_ticks() / 160
            _, head = self.grow(self.rect.x, self.rect.y, 0, self.rect.y - 34)
            cx, cy = self.rect.centerx + ox, head + oy
            for i in range(3):
                angle = t + i * 2 * math.pi / 3
                point = (cx + math.cos(angle) * 34, cy + math.sin(angle) * 9)
                pygame.draw.circle(surface, (255, 220, 50), point, 6)
                pygame.draw.circle(surface, (255, 255, 255), point, 3)

        if DEBUG:
            pygame.draw.rect(surface, (255, 0, 0), self.rect.move(ox, oy), 2)
            if self.attack_rect_timer > 0 and self.attack_rect:
                pygame.draw.rect(surface, (0, 255, 0), self.attack_rect.move(ox, oy), 2)

    def draw_hat(self, surface, offset=(0, 0)):
        """Chapéu do SUPER bumerangue girando, com rastro azulado (desenhado por cima dos dois)."""
        hat = self.hat
        if hat is None:
            return
        frames = get_super_fx(self.character["id"])
        ox, oy = offset
        flip = hat.direction < 0
        index = (hat.age // 2) % len(frames)
        # rastro: o chapéu de alguns frames atrás, cada vez mais apagado
        for alpha, (x, y, scale) in zip((120, 80, 45), hat.trail[-3::-2]):
            ghost = scaled_frame(frames[index], scale, flip, ghost=True)
            ghost.set_alpha(alpha)
            surface.blit(ghost, ghost.get_rect(center=(round(x + ox), round(y + oy))))
        image = scaled_frame(frames[index], hat.scale, flip)
        surface.blit(image, image.get_rect(center=(round(hat.x + ox), round(hat.y + oy))))
        if DEBUG:
            pygame.draw.rect(surface, (0, 255, 0), hat.box(self.boomerang["box"]).move(ox, oy), 2)
