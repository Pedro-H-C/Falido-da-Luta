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

intro_count = 3
last_cout_update = pygame.time.get_ticks()

MACEDO_SIZE = 250
MACEDO_SCALE = 1
MACEDO_OFFSET = [90, 90]
MACEDO_DATA = [MACEDO_SIZE, MACEDO_SCALE, MACEDO_OFFSET]

IGOR_SIZE = 250
IGOR_SCALE = 1
IGOR_OFFSET = [90, 90]
IGOR_DATA = [IGOR_SIZE, IGOR_SCALE, IGOR_OFFSET]




macedo_sheet = pygame.image.load("assets/images/Sprites/macedo.png").convert_alpha()
MACEDO_ANIMATION_STEPS = [4,6,5,4,5,4,5]  
igor_sheet = pygame.image.load("assets/images/Sprites/igor.png").convert_alpha()
IGOR_ANIMATION_STEPS = [4,6,5,4,5,4,5] 

bg_image = pygame.image.load("assets/images/Backgrounds/bgArrudinha.png").convert_alpha()



count_font = pygame.font.Font("assets/fonts/Turok.ttf", 80)
score_font = pygame.font.Font("assets/fonts/Turok.ttf", 30)



def draw_bg(imagem):
    scaled_bg = pygame.transform.scale(imagem, (SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.blit(scaled_bg, (0, 0)) 

def draw_health_bar(health, x, y):
    ratio = health / 100
    pygame.draw.rect(screen, BLACK, (x - 2, y - 2, 404, 34))
    pygame.draw.rect(screen, RED, (x, y, 400, 30))
    pygame.draw.rect(screen, YELLOW, (x, y, 400 * ratio, 30 ))



#CRIAR OS LUTADORES
fighter_1 = Fighter(200, 310, 1, False, IGOR_DATA, igor_sheet, IGOR_ANIMATION_STEPS)
fighter_2 = Fighter(700, 310, 2, True, MACEDO_DATA, macedo_sheet, MACEDO_ANIMATION_STEPS)



run = True
while run:
    draw_bg(bg_image)

    draw_health_bar(fighter_1.health, 20, 20)
    draw_health_bar(fighter_2.health, 580, 20)

    if intro_count <= 0:
        fighter_1.move(SCREEN_WIDTH, SCREEN_HEIGHT, screen, fighter_2)
        fighter_2.move(SCREEN_WIDTH, SCREEN_HEIGHT, screen, fighter_1)
    else:
        if pygame.time.get_ticks() - last_cout_update >= 1000:
            last_cout_update = pygame.time.get_ticks()
            intro_count -= 1
            print(intro_count)

    fighter_1.update()
    fighter_2.update()

    fighter_1.draw(screen)
    fighter_2.draw(screen)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run=False
    
    relogio.tick(FPS)  # Limit the frame rate to 60 FPS
    pygame.display.flip()

pygame.quit()
