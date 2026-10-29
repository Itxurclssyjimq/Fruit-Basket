"""
FRUIT CATCHER - CPROG 1 Final Project
-------------------------------------
Move the basket left/right to catch fruit and avoid bombs.

Controls:
    LEFT / RIGHT (or A / D) ... move basket
    P ......................... pause / resume
    ENTER ..................... start / restart
    ESC ....................... quit

Program structure (easy way to explain it):
    1. Constants ........ settings you can tweak in one place
    2. Sound helper ..... creates the .wav files in /assets on first run
    3. Player class ..... the basket
    4. Falling class .... fruits and bombs (one class, two kinds)
    5. Game class ....... the main loop: events -> update -> draw
"""

import math
import os
import random
import struct
import sys
import wave

import pygame

# ----------------------------------------------------------------------
# 1. CONSTANTS  (change these to tweak the game quickly)
# ----------------------------------------------------------------------
WIDTH, HEIGHT = 640, 480
FPS = 60

FALL_SPEED_BASE = 3       # falling objects move at (FALL_SPEED_BASE + level)
PLAYER_SPEED_BASE = 3     # basket moves at (PLAYER_SPEED_BASE + level),
                          # so it stays just fast enough to keep up
START_LIVES = 3
POINTS_PER_FRUIT = 10
FRUITS_PER_LEVEL = 5      # catch this many to go up a level
BOMB_CHANCE = 0.25        # 25% of spawned objects are bombs
SPAWN_DELAY_START = 900   # milliseconds between spawns (gets shorter)

# Colors (R, G, B)
WHITE = (255, 255, 255)
BLACK = (20, 20, 30)
SKY = (135, 206, 235)
GRASS = (80, 170, 90)
BROWN = (150, 100, 50)
RED = (220, 50, 50)
ORANGE = (255, 150, 30)
YELLOW = (250, 220, 60)
GREEN = (60, 190, 80)

# Folder paths (assets live inside the project folder)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(BASE_DIR, "assets")
HIGHSCORE_FILE = os.path.join(BASE_DIR, "highscore.txt")


# ----------------------------------------------------------------------
# 2. SOUND HELPER  (generates simple beep sounds so no download needed)
# ----------------------------------------------------------------------
def make_tone(filename, frequencies, duration=0.15, volume=0.4):
    """Write a .wav file made of sine-wave beeps (one per frequency)."""
    path = os.path.join(ASSET_DIR, filename)
    if os.path.exists(path):
        return path
    rate = 22050
    with wave.open(path, "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        for freq in frequencies:
            for i in range(int(rate * duration)):
                sample = volume * math.sin(2 * math.pi * freq * i / rate)
                f.writeframes(struct.pack("<h", int(sample * 32767)))
    return path


def load_sounds():
    """Create (if missing) and load all sound effects. Returns a dict."""
    os.makedirs(ASSET_DIR, exist_ok=True)
    return {
        "catch": pygame.mixer.Sound(make_tone("catch.wav", [660, 880], 0.07)),
        "bomb": pygame.mixer.Sound(make_tone("bomb.wav", [200, 120], 0.2)),
        "level": pygame.mixer.Sound(make_tone("level.wav", [440, 550, 660, 880], 0.1)),
        "over": pygame.mixer.Sound(make_tone("over.wav", [400, 300, 200, 100], 0.25)),
    }


# ----------------------------------------------------------------------
# 3. PLAYER CLASS
# ----------------------------------------------------------------------
class Player:
    """The basket the user controls."""

    def __init__(self):
        self.width, self.height = 90, 40
        self.rect = pygame.Rect(0, 0, self.width, self.height)
        self.speed = PLAYER_SPEED_BASE + 1   # Game updates this each level
        self.reset()

    def reset(self):
        """Put the basket back in the bottom-center of the screen."""
        self.rect.midbottom = (WIDTH // 2, HEIGHT - 20)

    def update(self, keys):
        """Move left/right based on keys currently held down."""
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.rect.x -= self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.rect.x += self.speed
        # Keep the basket inside the window
        self.rect.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))

    def draw(self, surface):
        pygame.draw.rect(surface, BROWN, self.rect, border_radius=8)
        pygame.draw.rect(surface, BLACK, self.rect, 3, border_radius=8)
        # Weave lines to make it look like a basket
        for x in range(self.rect.left + 15, self.rect.right, 20):
            pygame.draw.line(surface, BLACK, (x, self.rect.top + 5),
                             (x, self.rect.bottom - 5), 2)


# ----------------------------------------------------------------------
# 4. FALLING OBJECT CLASS  (fruit or bomb)
# ----------------------------------------------------------------------
class Falling:
    """Anything that falls from the top. kind is 'fruit' or 'bomb'."""

    FRUIT_COLORS = [RED, ORANGE, YELLOW, GREEN]

    def __init__(self, kind, speed):
        self.kind = kind
        self.radius = 16
        self.speed = speed
        self.color = random.choice(self.FRUIT_COLORS) if kind == "fruit" else BLACK
        x = random.randint(self.radius, WIDTH - self.radius)
        self.rect = pygame.Rect(x - self.radius, -2 * self.radius,
                                2 * self.radius, 2 * self.radius)

    def update(self):
        self.rect.y += self.speed

    def is_off_screen(self):
        return self.rect.top > HEIGHT

    def draw(self, surface):
        if self.kind == "fruit":
            pygame.draw.circle(surface, self.color, self.rect.center, self.radius)
            # little green leaf on top
            pygame.draw.ellipse(surface, GREEN,
                                (self.rect.centerx, self.rect.top - 4, 10, 6))
        else:
            pygame.draw.circle(surface, BLACK, self.rect.center, self.radius)
            # fuse with a red spark
            fuse_end = (self.rect.centerx + 8, self.rect.top - 6)
            pygame.draw.line(surface, BROWN, (self.rect.centerx, self.rect.top),
                             fuse_end, 3)
            pygame.draw.circle(surface, RED, fuse_end, 4)


# ----------------------------------------------------------------------
# 5. GAME CLASS  (main loop + game states)
# ----------------------------------------------------------------------
class Game:
    """Controls everything. State is one of: 'menu', 'playing', 'paused', 'over'."""

    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Fruit Catcher")
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("arial", 24, bold=True)
        self.big_font = pygame.font.SysFont("arial", 56, bold=True)

        self.sounds = load_sounds()
        self.player = Player()
        self.high_score = self.load_high_score()
        self.state = "menu"
        self.reset_game()

    # ---------- setup / saving ----------
    def reset_game(self):
        """Reset all values for a brand-new round."""
        self.score = 0
        self.lives = START_LIVES
        self.level = 1
        self.caught_this_level = 0
        self.objects = []
        self.spawn_delay = SPAWN_DELAY_START
        self.last_spawn = pygame.time.get_ticks()
        self.player.reset()
        self.player.speed = PLAYER_SPEED_BASE + self.level   # match falling speed

    def load_high_score(self):
        try:
            with open(HIGHSCORE_FILE) as f:
                return int(f.read())
        except (FileNotFoundError, ValueError):
            return 0

    def save_high_score(self):
        with open(HIGHSCORE_FILE, "w") as f:
            f.write(str(self.high_score))

    # ---------- main loop ----------
    def run(self):
        while True:
            self.handle_events()   # 1. input
            self.update()          # 2. game logic
            self.draw()            # 3. drawing
            self.clock.tick(FPS)   # keep a steady 60 FPS

    # ---------- 1. events ----------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.quit()
                elif event.key == pygame.K_RETURN and self.state in ("menu", "over"):
                    self.reset_game()
                    self.state = "playing"
                elif event.key == pygame.K_p:
                    if self.state == "playing":
                        self.state = "paused"
                    elif self.state == "paused":
                        self.state = "playing"

    # ---------- 2. update ----------
    def update(self):
        if self.state != "playing":
            return

        self.player.update(pygame.key.get_pressed())
        self.spawn_objects()

        for obj in self.objects[:]:          # [:] = loop over a copy
            obj.update()
            if obj.rect.colliderect(self.player.rect):
                self.handle_catch(obj)
                self.objects.remove(obj)
            elif obj.is_off_screen():
                # Missed fruit costs a life; missed bombs are fine
                if obj.kind == "fruit":
                    self.lose_life()
                self.objects.remove(obj)

    def spawn_objects(self):
        """Create a new fruit/bomb whenever enough time has passed."""
        now = pygame.time.get_ticks()
        if now - self.last_spawn >= self.spawn_delay:
            kind = "bomb" if random.random() < BOMB_CHANCE else "fruit"
            speed = FALL_SPEED_BASE + self.level   # faster each level
            self.objects.append(Falling(kind, speed))
            self.last_spawn = now

    def handle_catch(self, obj):
        if obj.kind == "fruit":
            self.score += POINTS_PER_FRUIT * self.level
            self.caught_this_level += 1
            self.sounds["catch"].play()
            if self.caught_this_level >= FRUITS_PER_LEVEL:
                self.level_up()
        else:
            self.sounds["bomb"].play()
            self.lose_life()

    def level_up(self):
        self.level += 1
        self.caught_this_level = 0
        self.spawn_delay = max(300, self.spawn_delay - 100)   # spawn faster
        self.player.speed = PLAYER_SPEED_BASE + self.level    # basket keeps pace
        self.sounds["level"].play()

    def lose_life(self):
        self.lives -= 1
        if self.lives <= 0:
            self.game_over()

    def game_over(self):
        self.state = "over"
        self.sounds["over"].play()
        if self.score > self.high_score:
            self.high_score = self.score
            self.save_high_score()

    # ---------- 3. draw ----------
    def draw(self):
        self.screen.fill(SKY)
        pygame.draw.rect(self.screen, GRASS, (0, HEIGHT - 20, WIDTH, 20))

        if self.state == "menu":
            self.draw_center("FRUIT CATCHER", -60, self.big_font, BLACK)
            self.draw_center("Catch fruit, dodge bombs!", 0)
            self.draw_center("Arrow keys / A-D to move  |  P to pause", 35)
            self.draw_center("Press ENTER to start", 85, color=RED)
        else:
            self.player.draw(self.screen)
            for obj in self.objects:
                obj.draw(self.screen)
            self.draw_hud()
            if self.state == "paused":
                self.draw_center("PAUSED", -20, self.big_font, BLACK)
            elif self.state == "over":
                self.draw_center("GAME OVER", -50, self.big_font, RED)
                self.draw_center(f"Final score: {self.score}", 10)
                self.draw_center("Press ENTER to play again", 50)

        pygame.display.flip()

    def draw_hud(self):
        """Score, level, lives, and high score at the top."""
        self.screen.blit(self.font.render(f"Score: {self.score}", True, BLACK), (10, 8))
        self.screen.blit(self.font.render(f"Level: {self.level}", True, BLACK), (10, 38))
        best = self.font.render(f"Best: {self.high_score}", True, BLACK)
        self.screen.blit(best, (WIDTH - best.get_width() - 10, 8))
        for i in range(self.lives):                      # hearts as red circles
            pygame.draw.circle(self.screen, RED, (WIDTH - 25 - i * 30, 52), 11)

    def draw_center(self, text, y_offset, font=None, color=BLACK):
        """Draw text centered on screen, shifted up/down by y_offset."""
        img = (font or self.font).render(text, True, color)
        rect = img.get_rect(center=(WIDTH // 2, HEIGHT // 2 + y_offset))
        self.screen.blit(img, rect)

    def quit(self):
        pygame.quit()
        sys.exit()


# ----------------------------------------------------------------------
# Program entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    Game().run()
