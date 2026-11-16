import pygame

class Fighter():
    def __init__(self, x, y):
        self.rect = pygame.Rect((x, y, 50, 150))  # Define the rectangle for the fighter
        self.vel_y = 0
    def move(self, screen_width):
        SPEED = 10
        dx = 0 
        dy = 0

        #MOVIMENTOS
        key = pygame.key.get_pressed()
        if key[pygame.K_a]:
            dx = -SPEED
        if key[pygame.K_d]:
            dx = SPEED

        if key[pygame.K_w] and self.vel_y == 0:
            self.vel_y = -30  # Jumping velocity
        dy+=self.vel_y

    

        #COLISOES
        if self.rect.left + dx<0:
            dx = -self.rect.left
        if self.rect.right + dx>screen_width:
            dx = screen_width - self.rect.right

        self.rect.x += dx
        self.rect.y += dy

    def draw(self, surface):
        pygame.draw.rect(surface, (255, 0, 0), self.rect)  # Draw the fighter as a red rectangle
       