import pygame
from fighter import Fighter

pygame.init()

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Falido Fight")

relogio = pygame.time.Clock()
FPS = 60

bg_image = pygame.image.load("assets/images/bgArrudinha.png").convert_alpha()
def draw_bg(imagem):
    scaled_bg = pygame.transform.scale(imagem, (SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.blit(scaled_bg, (0, 0))



#CRIAR OS LUTADORES
fighter_1 = Fighter(200, 310)
fighter_2 = Fighter(700, 310)



run = True
while run:
    draw_bg(bg_image)

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
