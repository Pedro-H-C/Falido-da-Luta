import random
from collections import namedtuple

import pygame

DEBUG = False  # F1 no jogo mostra/esconde as hitboxes

GRAVITY = 2
GROUND_MARGIN = 110

# Configuração dos golpes:
#   damage    -> dano base (multiplicado pelo dmg_mult do personagem)
#   range     -> alcance (multiplicador da largura do corpo)
#   cooldown  -> frames de espera depois do golpe
#   knockback -> força do empurrão no oponente
ATTACKS = {
    1: {"damage": 7,  "range": 1.6, "cooldown": 15, "knockback": 6},   # golpe rápido
    2: {"damage": 14, "range": 2.2, "cooldown": 40, "knockback": 14},  # golpe forte
}
BLOCK_DAMAGE_MULT = 0.25   # defendendo, toma só 25% do dano
HIT_RECOVERY = 10          # frames sem poder atacar após levar dano
TRAIL_DELAY = 30           # frames até a barra "fantasma" de vida começar a descer
TRAIL_SPEED = 0.8          # quanto a barra fantasma desce por frame

# Velocidade (ms por frame) de cada animação; o resto usa 100
ANIM_SPEED = {3: 80, 4: 110, 5: 90}

CONTROLS = {
    1: {"left": pygame.K_a, "right": pygame.K_d, "jump": pygame.K_w,
        "atk1": pygame.K_r, "atk2": pygame.K_t},
    2: {"left": pygame.K_LEFT, "right": pygame.K_RIGHT, "jump": pygame.K_UP,
        "atk1": pygame.K_n, "atk2": pygame.K_m},
}

# O que o lutador quer fazer neste frame. Vem do teclado (jogador) ou da IA (CPU).
INTENT_KEYS = ("left", "right", "jump", "block", "atk1", "atk2")

# Golpe que encostou no oponente; o main usa para hitstop, faíscas e tremor de tela.
#   kind: "hit" ou "block" | pos: ponto de contato | direction: +1 empurra p/ direita, -1 p/ esquerda
HitEvent = namedtuple("HitEvent", "kind attack_type pos direction ko")


# ---------------- PERSONAGENS ----------------
# data       -> [tamanho do frame na sheet, escala, offset do desenho em relação à hitbox]
# anim_steps -> frames de cada linha: idle, corrida, pulo, golpe 1, golpe 2, dano, morte
# stats      -> vida máxima, velocidade, força do pulo (negativo = para cima), multiplicador de dano
CHARACTERS = [
    {
        "id": "igor",
        "name": "Igor",
        "sheet_path": "assets/images/Sprites/igor.png",
        "data": [250, 1.5, [120, 70]],
        "anim_steps": [4, 6, 5, 6, 5, 4, 5],
        "stats": {"max_health": 110, "speed": 7, "jump_vel": -28, "dmg_mult": 1.15},
        "tagline": "Bruto, forte e lento",
    },
    {
        "id": "macedo",
        "name": "Macedo",
        "sheet_path": "assets/images/Sprites/macedo.png",
        "data": [250, 1.5, [120, 70]],
        "anim_steps": [4, 6, 5, 4, 5, 4, 5],
        "stats": {"max_health": 100, "speed": 9, "jump_vel": -31, "dmg_mult": 1.05},
        "tagline": "Forte e ágil",
    },
]
CHARACTERS_BY_ID = {char["id"]: char for char in CHARACTERS}


# ---------------- CACHE DE SPRITES ----------------
# Cada sheet é lida do disco uma única vez; a seleção e a luta reaproveitam as mesmas
# surfaces. Ninguém altera uma surface do cache (o draw sempre trabalha numa cópia).
_frame_cache = {}

# Paleta alternativa do P2 em luta espelho: a pele quase não muda e a roupa fica azul-marinho
ALT_PALETTE_MULT = (225, 220, 185)
ALT_PALETTE_ADD = (8, 18, 62)


def apply_alt_palette(image):
    """Cópia da imagem com a paleta alternativa."""
    tinted = image.copy()
    tinted.fill(ALT_PALETTE_MULT, special_flags=pygame.BLEND_RGB_MULT)
    tinted.fill(ALT_PALETTE_ADD, special_flags=pygame.BLEND_RGB_ADD)
    return tinted


def _slice_sheet(char):
    size, scale, _ = char["data"]
    scaled_size = int(size * scale)
    sheet = pygame.image.load(char["sheet_path"]).convert_alpha()
    animations = []
    for row, steps in enumerate(char["anim_steps"]):
        frames = []
        for col in range(steps):
            frame = sheet.subsurface(col * size, row * size, size, size)
            frames.append(pygame.transform.scale(frame, (scaled_size, scaled_size)))
        animations.append(frames)
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


def preload_characters():
    """Carrega o elenco inteiro. Chamar uma vez, depois de pygame.display.set_mode()."""
    for char in CHARACTERS:
        get_frames(char["id"])


# ---------------- IA DA CPU ----------------
DIFFICULTIES = ("easy", "normal", "hard")
DIFFICULTY_LABELS = {"easy": "Fácil", "normal": "Normal", "hard": "Difícil"}

# think        -> frames entre decisões (menor = reage mais rápido)
# block        -> chance de defender um golpe que vai alcançar a CPU
# block_delay  -> frames até levantar a guarda depois de ver o golpe começar
# aggression   -> 0..1, peso de avançar/atacar em vez de esperar/recuar
# punish       -> chance de castigar o oponente preso na recuperação de um golpe
# anti_air     -> chance de responder a um pulo na direção da CPU
# anti_air_mix -> pesos da resposta ao pulo: (golpe, defesa, pulo)
# jump_in      -> peso de entrar pulando
AI_PROFILES = {
    "easy": {"think": (26, 44), "block": 0.15, "block_delay": (5, 9), "aggression": 0.3,
             "punish": 0.1, "anti_air": 0.2, "anti_air_mix": (1, 3, 1), "jump_in": 0.06},
    "normal": {"think": (14, 26), "block": 0.45, "block_delay": (3, 6), "aggression": 0.55,
               "punish": 0.4, "anti_air": 0.45, "anti_air_mix": (2, 2, 1), "jump_in": 0.1},
    "hard": {"think": (6, 13), "block": 0.75, "block_delay": (1, 3), "aggression": 0.8,
             "punish": 0.85, "anti_air": 0.75, "anti_air_mix": (4, 1, 1), "jump_in": 0.12},
}


class _CpuMemory:
    """O que a CPU lembra de um frame para o outro."""

    def __init__(self):
        self.plan = "wait"
        self.think_timer = 0
        self.jump_started = False
        self.threat_seen = False   # já sorteou a defesa contra o golpe atual do oponente?
        self.block_in = -1         # frames até levantar a guarda (-1 = não vai defender)
        self.guarding = False
        self.punish_seen = False   # já sorteou o castigo da recuperação atual do oponente?
        self.air_seen = False      # já sorteou o anti-aéreo do pulo atual do oponente?


class Fighter():
    def __init__(self, x, y, player, flip, character, is_cpu=False, cpu_diff="normal", alt_palette=False):
        self.player = player
        self.character = character
        self.name = character["name"]
        self.controls = CONTROLS[player]
        self.offset = character["data"][2]
        stats = character["stats"]
        self.max_health = stats["max_health"]
        self.speed = stats["speed"]
        self.jump_vel = stats["jump_vel"]
        self.dmg_mult = stats["dmg_mult"]
        self.is_cpu = is_cpu
        self.cpu_diff = cpu_diff
        self.ai = _CpuMemory() if is_cpu else None
        self.flip = flip
        self.animation_list = get_frames(character["id"], alt_palette)
        self.action = 0  # 0: idle, 1: run, 2: jump, 3: attack1, 4: attack2, 5: hit, 6: death
        self.frame_index = 0
        self.image = self.animation_list[self.action][self.frame_index]
        self.update_time = pygame.time.get_ticks()
        self.rect = pygame.Rect((x, y, 100, 300))
        self.vel_y = 0
        self.last_dx = 0               # deslocamento horizontal do último frame (a IA usa)
        self.knockback = 0
        self.running = False
        self.jumping = False
        self.blocking = False
        self.attacking = False
        self.attack_type = 0
        self.attack_cooldown = 0
        self.attack_hit_done = False   # garante 1 acerto por golpe
        self.attack_landed = False     # o golpe atual encostou no oponente (acerto ou defesa)?
        self.attack_rect = None        # só para debug
        self.attack_rect_timer = 0
        self.hit = False
        self.flash_timer = 0           # pisca branco ao tomar dano
        self.block_flash = 0           # pisca azul ao defender
        self.health = self.max_health
        self.health_trail = self.max_health  # barra "fantasma" do HUD, desce atrasada
        self.trail_delay = 0
        self.alive = True

    def attack_reach(self, attack_type):
        return int(self.rect.width * ATTACKS[attack_type]["range"])

    def attack_startup(self, attack_type):
        """Tempo (ms) do início do golpe até o frame de impacto."""
        action = 3 if attack_type == 1 else 4
        return len(self.animation_list[action]) // 2 * ANIM_SPEED.get(action, 100)

    def move(self, screen_width, screen_height, target, can_act=True):
        """Controles + física de um frame. Retorna um HitEvent se um golpe encostou no oponente."""
        dx = 0
        dy = 0
        self.running = False
        self.blocking = False
        on_ground = not self.jumping
        hit_event = None

        # CONTROLES (bloqueados se estiver atacando, tomando dano ou morto)
        if can_act and self.alive and not self.hit and not self.attacking:
            inputs = self._compute_ai_inputs(target) if self.is_cpu else self._read_player_inputs(target)

            if inputs["left"]:
                dx = -self.speed
                self.running = True
            if inputs["right"]:
                dx = self.speed
                self.running = True

            # DEFESA: só no chão; anda mais devagar defendendo
            if inputs["block"] and on_ground:
                self.blocking = True
                dx = int(dx / 2)

            if inputs["jump"] and on_ground:
                self.vel_y = self.jump_vel
                self.jumping = True

            # ATAQUES
            if inputs["atk1"]:
                self.start_attack(1)
            elif inputs["atk2"]:
                self.start_attack(2)

        # O dano só sai no meio da animação do golpe (frame de impacto)
        if self.attacking and not self.attack_hit_done and self.action in (3, 4):
            impact_frame = len(self.animation_list[self.action]) // 2
            if self.frame_index >= impact_frame:
                self.attack_hit_done = True
                hit_event = self.resolve_attack(target)

        # FÍSICA (sempre roda, mesmo sem controle)
        self.vel_y += GRAVITY
        dy += self.vel_y

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

    def _read_player_inputs(self, target):
        """Teclado -> intenções. Defender = segurar para trás (longe do oponente)."""
        key = pygame.key.get_pressed()
        c = self.controls
        back_key = c["left"] if target.rect.centerx > self.rect.centerx else c["right"]
        return {
            "left": key[c["left"]],
            "right": key[c["right"]],
            "jump": key[c["jump"]],
            "block": key[back_key],
            "atk1": key[c["atk1"]],
            "atk2": key[c["atk2"]],
        }

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

        # 1) DEFESA: cada golpe do oponente é avaliado uma única vez
        if target.attacking and not target.attack_hit_done:
            if not mem.threat_seen:
                mem.threat_seen = True
                danger = target.attack_reach(target.attack_type) + self.rect.width // 2 + 40
                if dist <= danger and random.random() < profile["block"]:
                    mem.block_in = random.randint(*profile["block_delay"])
        elif not target.attacking:
            mem.threat_seen = False
            mem.punish_seen = False

        if mem.block_in > 0:
            mem.block_in -= 1
        elif mem.block_in == 0:
            mem.block_in = -1
            mem.guarding = True
        if mem.guarding:
            if target.attacking and not target.attack_hit_done:
                inputs["block"] = True
                return inputs
            mem.guarding = False

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
                plan = random.choices(("anti_air", "air_guard", "air_to_air"), weights=profile["anti_air_mix"])[0]
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
        """Sorteia o próximo plano conforme a distância (perto / meio / longe).

        Recuar também defende (mesma regra do jogador), então recuo e guarda pesam
        conforme a habilidade de defesa; a CPU passiva no fácil fica parada, aberta.
        """
        agg = profile["aggression"]
        skill = profile["block"]
        if self._ai_in_reach(target, 1, dist):
            # PERTO: mistura golpe rápido e forte, abre espaço ou fecha a guarda
            weights = {
                "atk1": 0.45 * agg + (0.3 * agg if target.hit else 0),
                "atk2": 0.3 * agg,
                "retreat": 0.25 * skill + 0.02,
                "guard": 0.25 * skill,
                "wait": 0.3 * (1 - agg) + 0.03,
            }
        elif dist <= self.attack_reach(2) + target.rect.width // 2 + 110:
            # MEIO: footsies (vai e volta na beira do alcance) e cutucadas
            weights = {
                "poke": 0.35 * agg + 0.05,
                "atk2": 0.25 * agg if self._ai_in_reach(target, 2, dist) else 0,
                "footsie": 0.05 + 0.4 * agg * skill,
                "approach": 0.2,
                "retreat": 0.2 * skill,
                "jump_in": profile["jump_in"],
                "wait": 0.3 * (1 - agg) + 0.03,
            }
        else:
            # LONGE: encurta a distância, às vezes pulando
            weights = {
                "approach": 0.35 + 0.5 * agg,
                "jump_in": profile["jump_in"] * 2,
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
            inputs["block"] = True  # andar para trás defende, igual ao jogador
        elif plan == "guard":
            inputs["block"] = True
        elif plan == "footsie":
            # fica na beira do alcance do golpe forte esperando o oponente errar
            ideal = self.attack_reach(2) + target.rect.width // 2 + 25
            if dist > ideal + 20:
                inputs[toward] = True
            elif dist < ideal - 20:
                inputs[away] = True
                inputs["block"] = True
        elif plan in ("atk1", "atk2", "poke"):
            attack = 2 if plan == "atk2" else 1
            if self._ai_in_reach(target, attack, dist):
                self._ai_press_attack(inputs, attack)
            else:
                inputs[toward] = True
        elif plan == "punish":
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
        elif plan == "air_guard":
            if target.jumping:
                inputs["block"] = True
            else:
                self._ai_set_plan("wait", 4)
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
        if self.attack_cooldown == 0:
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
        if self.attack_cooldown == 0:
            self.attacking = True
            self.attack_type = attack_type
            self.attack_hit_done = False
            self.attack_landed = False
            self.blocking = False
            # força a animação a começar do primeiro frame
            self.action = 3 if attack_type == 1 else 4
            self.frame_index = 0
            self.update_time = pygame.time.get_ticks()

    def resolve_attack(self, target):
        atk = ATTACKS[self.attack_type]
        reach = self.attack_reach(self.attack_type)
        if self.flip:  # virado para a esquerda
            attack_rect = pygame.Rect(self.rect.centerx - reach, self.rect.y, reach, self.rect.height)
        else:
            attack_rect = pygame.Rect(self.rect.centerx, self.rect.y, reach, self.rect.height)
        self.attack_rect = attack_rect
        self.attack_rect_timer = 8

        if not (target.alive and attack_rect.colliderect(target.rect)):
            return None

        direction = 1 if target.rect.centerx > self.rect.centerx else -1
        damage = max(1, round(atk["damage"] * self.dmg_mult))
        blocked = target.take_hit(damage, atk["knockback"], direction)
        self.attack_landed = True
        # ponto de contato: lado do oponente virado para o atacante, na altura do tronco
        contact_x = target.rect.left + 15 if direction > 0 else target.rect.right - 15
        contact_y = target.rect.y + random.randint(35, 105)
        kind = "block" if blocked else "hit"
        return HitEvent(kind, self.attack_type, (contact_x, contact_y), direction, not target.alive)

    def take_hit(self, damage, knockback, direction):
        """Aplica o golpe. Retorna True se foi defendido."""
        blocked = self.blocking
        if blocked:
            self.health -= max(1, round(damage * BLOCK_DAMAGE_MULT))
            self.knockback = direction * knockback * 0.5
            self.block_flash = 6
        else:
            self.health -= damage
            self.knockback = direction * knockback
            self.attacking = False  # levar golpe interrompe o seu ataque
            self.hit = True
            self.flash_timer = 6
            self.action = 5
            self.frame_index = 0
            self.update_time = pygame.time.get_ticks()

        self.trail_delay = TRAIL_DELAY
        self.health = max(0, self.health)
        if self.health == 0:
            self.alive = False
            self.hit = False
            self.attacking = False
        return blocked

    def update(self):
        if not self.alive:
            self.update_action(6)  # death
        elif self.hit:
            self.update_action(5)  # hit
        elif self.attacking:
            self.update_action(3 if self.attack_type == 1 else 4)
        elif self.jumping:
            self.update_action(2)
        elif self.running:
            self.update_action(1)
        else:
            self.update_action(0)

        animation_cooldown = ANIM_SPEED.get(self.action, 100)
        if pygame.time.get_ticks() - self.update_time > animation_cooldown:
            self.frame_index += 1
            self.update_time = pygame.time.get_ticks()

        if self.frame_index >= len(self.animation_list[self.action]):
            if not self.alive:
                self.frame_index = len(self.animation_list[self.action]) - 1
            else:
                self.frame_index = 0
                if self.action in (3, 4):
                    self.attacking = False
                    self.attack_cooldown = ATTACKS[self.attack_type]["cooldown"]
                elif self.action == 5:
                    self.hit = False
                    self.attack_cooldown = HIT_RECOVERY

        self.image = self.animation_list[self.action][self.frame_index]

        if self.flash_timer > 0:
            self.flash_timer -= 1
        if self.block_flash > 0:
            self.block_flash -= 1
        if self.attack_rect_timer > 0:
            self.attack_rect_timer -= 1

        if self.trail_delay > 0:
            self.trail_delay -= 1
        elif self.health_trail > self.health:
            self.health_trail = max(self.health, self.health_trail - TRAIL_SPEED)

    def update_action(self, new_action):
        if new_action != self.action:
            self.action = new_action
            self.frame_index = 0
            self.update_time = pygame.time.get_ticks()

    def draw(self, surface, offset=(0, 0)):
        """Desenha o lutador; offset desloca tudo (tremor de tela)."""
        ox, oy = offset
        img = pygame.transform.flip(self.image, self.flip, False)  # cópia: o cache fica intacto
        if self.flash_timer > 0:
            img.fill((150, 150, 150), special_flags=pygame.BLEND_RGB_ADD)    # clarão branco
        elif self.blocking or self.block_flash > 0:
            img.fill((140, 170, 255), special_flags=pygame.BLEND_RGB_MULT)   # tom azul de defesa

        surface.blit(img, (self.rect.x - self.offset[0] + ox, self.rect.y - self.offset[1] + oy))

        if DEBUG:
            pygame.draw.rect(surface, (255, 0, 0), self.rect.move(ox, oy), 2)
            if self.attack_rect_timer > 0 and self.attack_rect:
                pygame.draw.rect(surface, (0, 255, 0), self.attack_rect.move(ox, oy), 2)
