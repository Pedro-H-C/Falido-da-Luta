import pygame

pygame.init()

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Falido Fight")

run = True
while run:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            run=False

    screen.fill((0, 0, 0))
    pygame.display.flip()

pygame.quit()
