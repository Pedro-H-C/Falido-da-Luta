import pygame

DEBUG = False  # F1 no jogo mostra/esconde as hitboxes

GRAVITY = 2
SPEED = 8
JUMP_VEL = -30
GROUND_MARGIN = 110

# Configuração dos golpes:
#   damage    -> dano causado
#   range     -> alcance (multiplicador da largura do corpo)
#   cooldown  -> frames de espera depois do golpe
#   knockback -> força do empurrão no oponente
ATTACKS = {
    1: {"damage": 7,  "range": 1.6, "cooldown": 15, "knockback": 6},   # golpe rápido
    2: {"damage": 14, "range": 2.2, "cooldown": 40, "knockback": 14},  # golpe forte
}
BLOCK_DAMAGE_MULT = 0.25   # defendendo, toma só 25% do dano
HIT_RECOVERY = 10          # frames sem poder atacar após levar dano

# Velocidade (ms por frame) de cada animação; o resto usa 100
ANIM_SPEED = {3: 80, 4: 110, 5: 90}

CONTROLS = {
    1: {"left": pygame.K_a, "right": pygame.K_d, "jump": pygame.K_w,
        "atk1": pygame.K_r, "atk2": pygame.K_t},
    2: {"left": pygame.K_LEFT, "right": pygame.K_RIGHT, "jump": pygame.K_UP,
        "atk1": pygame.K_n, "atk2": pygame.K_m},
}


class Fighter():
    def __init__(self, x, y, player, flip, data, sprite_sheet, animation_steps):
        self.player = player
        self.controls = CONTROLS[player]
        self.size = data[0]
        self.image_scale = data[1]
        self.offset = data[2]
        self.flip = flip
        self.animation_list = self.load_images(sprite_sheet, animation_steps)
        self.action = 0  # 0: idle, 1: run, 2: jump, 3: attack1, 4: attack2, 5: hit, 6: death
        self.frame_index = 0
        self.image = self.animation_list[self.action][self.frame_index]
        self.update_time = pygame.time.get_ticks()
        self.rect = pygame.Rect((x, y, 100, 300))
        self.vel_y = 0
        self.knockback = 0
        self.running = False
        self.jumping = False
        self.blocking = False
        self.attacking = False
        self.attack_type = 0
        self.attack_cooldown = 0
        self.attack_hit_done = False   # garante 1 acerto por golpe
        self.attack_rect = None        # só para debug
        self.attack_rect_timer = 0
        self.hit = False
        self.flash_timer = 0           # pisca branco ao tomar dano
        self.block_flash = 0           # pisca azul ao defender
        self.health = 100
        self.alive = True

    def load_images(self, sprite_sheet, animation_steps):
        animation_list = []
        for y, animation in enumerate(animation_steps):
            temp_img_list = []
            for x in range(animation):
                temp_img = sprite_sheet.subsurface(x * self.size, y * self.size, self.size, self.size)
                temp_img_list.append(pygame.transform.scale(temp_img, (self.size * self.image_scale, self.size * self.image_scale)))
            animation_list.append(temp_img_list)
        return animation_list

    def move(self, screen_width, screen_height, surface, target, can_act=True):
        dx = 0
        dy = 0
        self.running = False
        self.blocking = False
        key = pygame.key.get_pressed()
        c = self.controls
        on_ground = not self.jumping

        # CONTROLES (bloqueados se estiver atacando, tomando dano ou morto)
        if can_act and self.alive and not self.hit and not self.attacking:
            facing_right = target.rect.centerx > self.rect.centerx
            back_key = c["left"] if facing_right else c["right"]

            if key[c["left"]]:
                dx = -SPEED
                self.running = True
            if key[c["right"]]:
                dx = SPEED
                self.running = True

            # DEFESA: segurar para trás (longe do oponente) no chão
            if key[back_key] and on_ground:
                self.blocking = True
                dx = dx // 2  # anda mais devagar defendendo

            if key[c["jump"]] and on_ground:
                self.vel_y = JUMP_VEL
                self.jumping = True

            # ATAQUES
            if key[c["atk1"]]:
                self.start_attack(1)
            elif key[c["atk2"]]:
                self.start_attack(2)

        # O dano só sai no meio da animação do golpe (frame de impacto)
        if self.attacking and not self.attack_hit_done and self.action in (3, 4):
            impact_frame = len(self.animation_list[self.action]) // 2
            if self.frame_index >= impact_frame:
                self.attack_hit_done = True
                self.resolve_attack(target)

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

    def start_attack(self, attack_type):
        if self.attack_cooldown == 0:
            self.attacking = True
            self.attack_type = attack_type
            self.attack_hit_done = False
            self.blocking = False
            # força a animação a começar do primeiro frame
            self.action = 3 if attack_type == 1 else 4
            self.frame_index = 0
            self.update_time = pygame.time.get_ticks()

    def resolve_attack(self, target):
        atk = ATTACKS[self.attack_type]
        reach = int(self.rect.width * atk["range"])
        if self.flip:  # virado para a esquerda
            attack_rect = pygame.Rect(self.rect.centerx - reach, self.rect.y, reach, self.rect.height)
        else:
            attack_rect = pygame.Rect(self.rect.centerx, self.rect.y, reach, self.rect.height)
        self.attack_rect = attack_rect
        self.attack_rect_timer = 8

        if target.alive and attack_rect.colliderect(target.rect):
            direction = 1 if target.rect.centerx > self.rect.centerx else -1
            target.take_hit(atk["damage"], atk["knockback"], direction)

    def take_hit(self, damage, knockback, direction):
        if self.blocking:
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

        self.health = max(0, self.health)
        if self.health == 0:
            self.alive = False
            self.hit = False
            self.attacking = False

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

    def update_action(self, new_action):
        if new_action != self.action:
            self.action = new_action
            self.frame_index = 0
            self.update_time = pygame.time.get_ticks()

    def draw(self, surface):
        img = pygame.transform.flip(self.image, self.flip, False)
        if self.flash_timer > 0:
            img.fill((150, 150, 150), special_flags=pygame.BLEND_RGB_ADD)    # clarão branco
        elif self.blocking or self.block_flash > 0:
            img.fill((140, 170, 255), special_flags=pygame.BLEND_RGB_MULT)   # tom azul de defesa

        if DEBUG:
            pygame.draw.rect(surface, (255, 0, 0), self.rect, 2)
            if self.attack_rect_timer > 0 and self.attack_rect:
                pygame.draw.rect(surface, (0, 255, 0), self.attack_rect, 2)

        surface.blit(img, (self.rect.x - self.offset[0], self.rect.y - self.offset[1]))
