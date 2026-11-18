import pygame
import fighter as fighter_module
from fighter import Fighter

pygame.init()

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
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

bg_image = pygame.image.load("assets/images/Backgrounds/bgArrudinha.png").convert_alpha()
menu_image = pygame.image.load("assets/images/Menu/menu.png").convert()
# Redimensiona UMA vez e aplica o alpha na imagem já escalada
menu_image = pygame.transform.scale(menu_image, (SCREEN_WIDTH, SCREEN_HEIGHT))
menu_image.set_alpha(80)  # 0 = invisível, 255 = opaco

count_font = pygame.font.Font("assets/fonts/Turok.ttf", 200)
score_font = pygame.font.Font("assets/fonts/Turok.ttf", 30)
menu_font = pygame.font.Font("assets/fonts/Turok.ttf", 50)
title_font = pygame.font.Font("assets/fonts/Turok.ttf", 90)

MENU_OPTIONS = ["Jogar", "Sair"]
menu_selected = 0

def draw_text(text, font, text_col, x,  y):
    img = font.render(text, True, text_col)
    screen.blit(img, (x, y))

def draw_bg(imagem):
    scaled_bg = pygame.transform.scale(imagem, (SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.blit(scaled_bg, (0, 0)) 

def draw_health_bar(health, x, y):
    ratio = health / 100
    pygame.draw.rect(screen, BLACK, (x - 2, y - 2, 404, 34))
    pygame.draw.rect(screen, RED, (x, y, 400, 30))
    pygame.draw.rect(screen, YELLOW, (x, y, 400 * ratio, 30 ))

def draw_menu(selected):
    """Desenha o menu e retorna os retângulos de cada opção (para clique do mouse)."""
    screen.fill(BLACK)
    screen.blit(menu_image, (0, 0))

    titulo = title_font.render("Falido da Luta", True, RED)
    screen.blit(titulo, titulo.get_rect(center=(SCREEN_WIDTH // 2, 150)))

    rects = []
    for i, opcao in enumerate(MENU_OPTIONS):
        cor = YELLOW if i == selected else WHITE
        texto = ("> " + opcao + " <") if i == selected else opcao
        img = menu_font.render(texto, True, cor)
        rect = img.get_rect(center=(SCREEN_WIDTH // 2, 320 + i * 80))
        screen.blit(img, rect)
        rects.append(rect)
    return rects

def start_game():
    """Reinicia lutadores, placar e contagem para uma nova partida."""
    global fighter_1, fighter_2, intro_count, last_cout_update, score, round_over
    fighter_1 = Fighter(200, 200, 1, False, IGOR_DATA, igor_sheet, IGOR_ANIMATION_STEPS)
    fighter_2 = Fighter(700, 200, 2, True, MACEDO_DATA, macedo_sheet, MACEDO_ANIMATION_STEPS)
    intro_count = 3
    last_cout_update = pygame.time.get_ticks()
    score = [0, 0]
    round_over = False



#CRIAR OS LUTADORES
fighter_1 = Fighter(200, 200, 1, False, IGOR_DATA, igor_sheet, IGOR_ANIMATION_STEPS)
fighter_2 = Fighter(700, 200, 2, True, MACEDO_DATA, macedo_sheet, MACEDO_ANIMATION_STEPS)


menu = True
run = True
while run:
    if menu:
        option_rects = draw_menu(menu_selected)
        escolha = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    menu_selected = (menu_selected - 1) % len(MENU_OPTIONS)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    menu_selected = (menu_selected + 1) % len(MENU_OPTIONS)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    escolha = MENU_OPTIONS[menu_selected]
            elif event.type == pygame.MOUSEMOTION:
                for i, rect in enumerate(option_rects):
                    if rect.collidepoint(event.pos):
                        menu_selected = i
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, rect in enumerate(option_rects):
                    if rect.collidepoint(event.pos):
                        escolha = MENU_OPTIONS[i]

        if escolha == "Jogar":
            start_game()
            menu = False
        elif escolha == "Sair":
            run = False

        relogio.tick(FPS)  # Limit the frame rate to 60 FPS
        pygame.display.flip()

    else:
        draw_bg(bg_image)

        draw_health_bar(fighter_1.health, 20, 20)
        draw_health_bar(fighter_2.health, 580, 20)
        draw_text("P1: " + str(score[0]), score_font, RED, 20, 60 )
        draw_text("P2: " + str(score[1]), score_font, RED, 580, 60 )
        





        if intro_count <= 0:
            fighter_1.move(SCREEN_WIDTH, SCREEN_HEIGHT, screen, fighter_2, not round_over)
            fighter_2.move(SCREEN_WIDTH, SCREEN_HEIGHT, screen, fighter_1, not round_over)
        else:
            draw_text(str(intro_count), count_font, RED, SCREEN_WIDTH/2 - 40, SCREEN_HEIGHT/2 - 100)
            if pygame.time.get_ticks() - last_cout_update >= 1000:
                last_cout_update = pygame.time.get_ticks()
                intro_count -= 1
                print(intro_count)


        fighter_1.update()
        fighter_2.update()

        fighter_1.draw(screen)
        fighter_2.draw(screen)

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
        else:
            img = title_font.render(winner_text, True, YELLOW)
            screen.blit(img, img.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50)))
            if pygame.time.get_ticks() - round_over_time > ROUND_OVER_COOLDOWN:
                # novo round: reseta lutadores mas mantém o placar
                round_over = False
                intro_count = 3
                last_cout_update = pygame.time.get_ticks()
                fighter_1 = Fighter(200, 200, 1, False, IGOR_DATA, igor_sheet, IGOR_ANIMATION_STEPS)
                fighter_2 = Fighter(700, 200, 2, True, MACEDO_DATA, macedo_sheet, MACEDO_ANIMATION_STEPS)



        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run=False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                menu = True  # ESC volta para o menu
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
                fighter_module.DEBUG = not fighter_module.DEBUG  # mostra hitboxes

        relogio.tick(FPS)  # Limit the frame rate to 60 FPS
        pygame.display.flip()

pygame.quit()
