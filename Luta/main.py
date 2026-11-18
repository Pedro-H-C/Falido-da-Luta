import pygame
import fighter as fighter_module
from fighter import Fighter

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

intro_count = 3
last_cout_update = pygame.time.get_ticks()
score = [0, 0] #p1, p2
round_over = False
round_over_time = 0
winner_text = ""
ROUND_OVER_COOLDOWN = 2000

MACEDO_SIZE = 250
MACEDO_SCALE = 1.5
MACEDO_OFFSET = [120, 70]
MACEDO_DATA = [MACEDO_SIZE, MACEDO_SCALE, MACEDO_OFFSET]

IGOR_SIZE = 250
IGOR_SCALE = 1.5
IGOR_OFFSET = [120, 70]
IGOR_DATA = [IGOR_SIZE, IGOR_SCALE, IGOR_OFFSET]


macedo_sheet = pygame.image.load("assets/images/Sprites/macedo.png").convert_alpha()
MACEDO_ANIMATION_STEPS = [4,6,5,4,5,4,5]
igor_sheet = pygame.image.load("assets/images/Sprites/igor.png").convert_alpha()
IGOR_ANIMATION_STEPS = [4,6,5,6,5,4,5]

# Redimensiona as imagens de fundo UMA vez (não a cada frame)
bg_image = pygame.image.load("assets/images/Backgrounds/bgArrudinha.png").convert_alpha()
bg_image = pygame.transform.scale(bg_image, (SCREEN_WIDTH, SCREEN_HEIGHT))
menu_image = pygame.image.load("assets/images/Menu/menu.png").convert()
menu_image = pygame.transform.scale(menu_image, (SCREEN_WIDTH, SCREEN_HEIGHT))
menu_image.set_alpha(80)  # 0 = invisível, 255 = opaco

# Camada escura por cima do jogo quando pausado
pause_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
pause_overlay.fill((0, 0, 0, 160))

count_font = pygame.font.Font("assets/fonts/Turok.ttf", 200)
score_font = pygame.font.Font("assets/fonts/Turok.ttf", 30)
menu_font = pygame.font.Font("assets/fonts/Turok.ttf", 50)
title_font = pygame.font.Font("assets/fonts/Turok.ttf", 90)

# Botão de pausa: centralizado entre as barras de vida (que vão até x=420 e começam em x=580)
PAUSE_BUTTON = pygame.Rect(SCREEN_WIDTH // 2 - 25, 15, 50, 40)

fullscreen = False
paused = False
pause_start = 0
menu_selected = 0
pause_selected = 0
pause_rects = []


def fullscreen_label():
    return "Tela cheia: " + ("ON" if fullscreen else "OFF")

def toggle_fullscreen():
    global fullscreen
    pygame.display.toggle_fullscreen()
    fullscreen = not fullscreen

def draw_text(text, font, text_col, x,  y):
    img = font.render(text, True, text_col)
    screen.blit(img, (x, y))

def draw_health_bar(health, x, y):
    ratio = health / 100
    pygame.draw.rect(screen, BLACK, (x - 2, y - 2, 404, 34))
    pygame.draw.rect(screen, RED, (x, y, 400, 30))
    pygame.draw.rect(screen, YELLOW, (x, y, 400 * ratio, 30 ))

def draw_pause_button(highlight):
    cor = YELLOW if highlight else WHITE
    pygame.draw.rect(screen, BLACK, PAUSE_BUTTON, border_radius=8)
    pygame.draw.rect(screen, cor, PAUSE_BUTTON, 2, border_radius=8)
    # ícone de pausa (duas barras)
    cx, cy = PAUSE_BUTTON.center
    pygame.draw.rect(screen, cor, (cx - 10, cy - 10, 7, 20))
    pygame.draw.rect(screen, cor, (cx + 3, cy - 10, 7, 20))

def draw_options(options, selected, start_y):
    """Desenha uma lista de opções e retorna os retângulos (para clique do mouse)."""
    rects = []
    for i, opcao in enumerate(options):
        cor = YELLOW if i == selected else WHITE
        texto = ("> " + opcao + " <") if i == selected else opcao
        img = menu_font.render(texto, True, cor)
        rect = img.get_rect(center=(SCREEN_WIDTH // 2, start_y + i * 75))
        screen.blit(img, rect)
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
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
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

def start_game():
    """Reinicia lutadores, placar e contagem para uma nova partida."""
    global fighter_1, fighter_2, intro_count, last_cout_update, score, round_over, paused
    fighter_1 = Fighter(200, 200, 1, False, IGOR_DATA, igor_sheet, IGOR_ANIMATION_STEPS)
    fighter_2 = Fighter(700, 200, 2, True, MACEDO_DATA, macedo_sheet, MACEDO_ANIMATION_STEPS)
    intro_count = 3
    last_cout_update = pygame.time.get_ticks()
    score = [0, 0]
    round_over = False
    paused = False

def pause_game():
    global paused, pause_start, pause_selected
    paused = True
    pause_start = pygame.time.get_ticks()
    pause_selected = 0

def resume_game():
    """Despausa e 'empurra' os timers para frente, pra contagem/animações não pularem."""
    global paused, last_cout_update, round_over_time
    dt = pygame.time.get_ticks() - pause_start
    last_cout_update += dt
    round_over_time += dt
    fighter_1.update_time += dt
    fighter_2.update_time += dt
    paused = False


#CRIAR OS LUTADORES
fighter_1 = Fighter(200, 200, 1, False, IGOR_DATA, igor_sheet, IGOR_ANIMATION_STEPS)
fighter_2 = Fighter(700, 200, 2, True, MACEDO_DATA, macedo_sheet, MACEDO_ANIMATION_STEPS)


menu = True
run = True
while run:
    if menu:
        # ---------------- MENU PRINCIPAL ----------------
        menu_options = ["Jogar", fullscreen_label(), "Sair"]

        screen.fill(BLACK)
        screen.blit(menu_image, (0, 0))
        titulo = title_font.render("Falido da Luta", True, RED)
        screen.blit(titulo, titulo.get_rect(center=(SCREEN_WIDTH // 2, 150)))
        option_rects = draw_options(menu_options, menu_selected, 300)

        escolha = None
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                toggle_fullscreen()
            else:
                menu_selected, escolha = handle_menu_event(event, menu_options, option_rects, menu_selected)

            if escolha == "Jogar":
                start_game()
                menu = False
            elif escolha and escolha.startswith("Tela cheia"):
                toggle_fullscreen()
            elif escolha == "Sair":
                run = False
            escolha = None

    else:
        # ---------------- LÓGICA (congelada na pausa) ----------------
        if not paused:
            if intro_count <= 0:
                fighter_1.move(SCREEN_WIDTH, SCREEN_HEIGHT, screen, fighter_2, not round_over)
                fighter_2.move(SCREEN_WIDTH, SCREEN_HEIGHT, screen, fighter_1, not round_over)
            elif pygame.time.get_ticks() - last_cout_update >= 1000:
                last_cout_update = pygame.time.get_ticks()
                intro_count -= 1

            fighter_1.update()
            fighter_2.update()

            # FIM DE ROUND
            if not round_over:
                if not fighter_1.alive:
                    score[1] += 1
                    winner_text = "P2 VENCEU!"
                    round_over = True
                    round_over_time = pygame.time.get_ticks()
                elif not fighter_2.alive:
                    score[0] += 1
                    winner_text = "P1 VENCEU!"
                    round_over = True
                    round_over_time = pygame.time.get_ticks()
            elif pygame.time.get_ticks() - round_over_time > ROUND_OVER_COOLDOWN:
                # novo round: reseta lutadores mas mantém o placar
                round_over = False
                intro_count = 3
                last_cout_update = pygame.time.get_ticks()
                fighter_1 = Fighter(200, 200, 1, False, IGOR_DATA, igor_sheet, IGOR_ANIMATION_STEPS)
                fighter_2 = Fighter(700, 200, 2, True, MACEDO_DATA, macedo_sheet, MACEDO_ANIMATION_STEPS)

        # ---------------- DESENHO ----------------
        screen.blit(bg_image, (0, 0))

        fighter_1.draw(screen)
        fighter_2.draw(screen)

        draw_health_bar(fighter_1.health, 20, 20)
        draw_health_bar(fighter_2.health, 580, 20)
        draw_text("P1: " + str(score[0]), score_font, RED, 20, 60)
        draw_text("P2: " + str(score[1]), score_font, RED, 580, 60)

        if intro_count > 0:
            draw_text(str(intro_count), count_font, RED, SCREEN_WIDTH/2 - 40, SCREEN_HEIGHT/2 - 100)
        if round_over:
            img = title_font.render(winner_text, True, YELLOW)
            screen.blit(img, img.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50)))

        if paused:
            pause_options = ["Continuar", fullscreen_label(), "Menu principal"]
            screen.blit(pause_overlay, (0, 0))
            titulo = title_font.render("PAUSADO", True, YELLOW)
            screen.blit(titulo, titulo.get_rect(center=(SCREEN_WIDTH // 2, 170)))
            pause_rects = draw_options(pause_options, pause_selected, 300)

        mouse_sobre_botao = PAUSE_BUTTON.collidepoint(pygame.mouse.get_pos())
        draw_pause_button(paused or mouse_sobre_botao)

        # ---------------- EVENTOS ----------------
        for event in pygame.event.get():
            clicou_pausa = (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                            and PAUSE_BUTTON.collidepoint(event.pos))
            tecla_pausa = event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_p)

            if event.type == pygame.QUIT:
                run = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                toggle_fullscreen()
            elif paused:
                if clicou_pausa or tecla_pausa:
                    resume_game()
                    continue
                pause_selected, escolha = handle_menu_event(event, pause_options, pause_rects, pause_selected)
                if escolha == "Continuar":
                    resume_game()
                elif escolha and escolha.startswith("Tela cheia"):
                    toggle_fullscreen()
                elif escolha == "Menu principal":
                    paused = False
                    menu = True
            else:
                if clicou_pausa or tecla_pausa:
                    pause_game()
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
                    fighter_module.DEBUG = not fighter_module.DEBUG  # mostra hitboxes

    relogio.tick(FPS)  # Limit the frame rate to 60 FPS
    pygame.display.flip()

pygame.quit()
