import pygame
from fighter import Fighter

pygame.init()

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Falido Fight")

relogio = pygame.time.Clock()
FPS = 60

YELLOW = (255, 255, 0)
RED = (255, 0, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

MACEDO_SIZE = 250
MACEDO_DATA = [MACEDO_SIZE]


bg_image = pygame.image.load("assets/images/Backgrounds/bgArrudinha.png").convert_alpha()

macedo_sheet = pygame.image.load("assets/images/Sprites/macedo.png").convert_alpha()
MACEDO_ANIMATION_STEPS = [8, 6, 4, 10, 10, 8]  # Number of frames for each animation


def draw_bg(imagem):
    scaled_bg = pygame.transform.scale(imagem, (SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.blit(scaled_bg, (0, 0))

def draw_health_bar(health, x, y):
    ratio = health / 100
    pygame.draw.rect(screen, BLACK, (x - 2, y - 2, 404, 34))
    pygame.draw.rect(screen, RED, (x, y, 400, 30))
    pygame.draw.rect(screen, YELLOW, (x, y, 400 * ratio, 30 ))



#CRIAR OS LUTADORES
fighter_1 = Fighter(200, 310, MACEDO_DATA, macedo_sheet, MACEDO_ANIMATION_STEPS)
fighter_2 = Fighter(700, 310, MACEDO_DATA, macedo_sheet, MACEDO_ANIMATION_STEPS)



run = True
while run:
    draw_bg(bg_image)

    draw_health_bar(fighter_1.health, 20, 20)
    draw_health_bar(fighter_2.health, 580, 20)

    fighter_1.move(SCREEN_WIDTH, SCREEN_HEIGHT, screen, fighter_2)
    #fighter_2.move(SCREEN_WIDTH, SCREEN_HEIGHT, screen, fighter_1)

    fighter_1.draw(screen)
    fighter_2.draw(screen)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run=False
    
    relogio.tick(FPS)  # Limit the frame rate to 60 FPS
    pygame.display.flip()

pygame.quit()
