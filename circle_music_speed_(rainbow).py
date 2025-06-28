import pygame
import pygame.midi
import math
import colorsys
import random
import pretty_midi
import time

# --- Initialisation Pygame ---
pygame.init()
pygame.midi.init()


midi_data = pretty_midi.PrettyMIDI(r"C:\Users\hrobi\Desktop\BouncyBalls\music\Aria_math2.mid")
instruments = midi_data.instruments
all_notes = []
for chan, inst in enumerate(instruments):
    for note in inst.notes:
        note.start = round(note.start, 3)
        # on stocke aussi le canal (ici, l'index du track)
        all_notes.append((note.start, note.pitch, note.velocity, chan))
# tri par instant, puis par pitch
all_notes.sort(key=lambda x: (x[0], x[1]))

# --- Initialisation de la sortie MIDI ---
midi_output = pygame.midi.Output(pygame.midi.get_default_output_id())

# Pour chaque instrument, on envoie son program change sur son canal
for chan, inst in enumerate(instruments):
    midi_output.set_instrument(inst.program, chan)

note_index = 0


# --- Configuration graphique ---
WIDTH, HEIGHT = 1080, 1920
FPS = 100
screen    = pygame.display.set_mode((WIDTH, HEIGHT))
trail_surf= pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
clock     = pygame.time.Clock()
running   = True

# --- Constantes physiques & visuelles ---
GRAVITY     = 0.3
HUE_SPEED   = 0.002
GHOST_ALPHA = 100
INNER_VAL   = 0.7
OUTER_VAL   = 1
SATURATION  = 0.9
TIME_SCALE  = 0.3
MAX_TIME_SCALE = 1.6
START_VX, START_VY = 15, 9

TIME_ACCEL_FACTOR = 1.017
SIZE_UP_FACTOR = 1.5

SPRING_K    = 0.1
DAMPING     = 0.85
SHOCK_FORCE = 0

particles = []



class OuterCircle:
    def __init__(self, x, y, radius, width=4):
        # position de repos
        self.base_x, self.base_y = x, y
        # position courante (commence à la position de repos)
        self.x, self.y = x, y
        self.radius = radius
        self.width  = width

        # vélocité initiale
        self.vx, self.vy = 0.0, 0.0

        # HSV pour la couleur
        self.hue, self.sat, self.val = 0.0, 1.0, 1.0
        self.color = self.hsv_to_rgb()

    def hsv_to_rgb(self):
        r, g, b = colorsys.hsv_to_rgb(self.hue, self.sat, self.val)
        return (int(r*255), int(g*255), int(b*255))

    def shock(self, nx, ny):
        """Projette le cercle dans la direction du vecteur normal (nx,ny)."""
        self.vx += nx * SHOCK_FORCE
        self.vy += ny * SHOCK_FORCE

    def update(self):
        # animation de la couleur
        self.hue = (self.hue + HUE_SPEED) % 1.0
        self.color = self.hsv_to_rgb()

        # ressort vers la position de repos
        dx = self.base_x - self.x
        dy = self.base_y - self.y
        self.vx += dx * SPRING_K
        self.vy += dy * SPRING_K

        # amortissement
        self.vx *= DAMPING
        self.vy *= DAMPING

        # mise à jour de la position
        self.x += self.vx
        self.y += self.vy

    def draw(self, surf):
        pygame.draw.circle(surf, self.color,
                           (int(self.x), int(self.y)),
                           self.radius,
                           self.width)

class Particle:
    def __init__(self, x, y, vx, vy, hue):
        self.x, self.y = x, y
        self.vx = vx + random.uniform(-4, 4)
        self.vy = vy + random.uniform(-4, 4)
        self.hue = hue
        self.life = random.randint(40, 80)
        self.w = random.randint(4, 8)
        self.h = random.randint(2, 6)

    def update(self):
        self.vy += GRAVITY
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    def draw(self, surf):
        r, g, b = colorsys.hsv_to_rgb(self.hue, SATURATION, OUTER_VAL)
        color = (int(r*255), int(g*255), int(b*255))
        rect = pygame.Rect(int(self.x - self.w/2),
                           int(self.y - self.h/2),
                           self.w, self.h)
        pygame.draw.rect(surf, color, rect)

    def is_dead(self):
        return self.life <= 0

class Ball:
    def __init__(self, x, y, radius):
        self.time_scale = TIME_SCALE  # valeur de départ
        self.x, self.y = x, y
        self.radius = radius
        self.xspeed, self.yspeed = START_VX, START_VY
        self.hue = 0.0
        self.prev_x = x
        self.prev_y = y
        self.current_note = None


    def update(self, outer):
        global particles, note_index, midi_output
        EPS = 1e-3
        
        self.prev_x, self.prev_y = self.x, self.y
        # gravité + déplacement
        self.yspeed += GRAVITY #* TIME_SCALE
        self.x += self.xspeed * self.time_scale
        self.y += self.yspeed * self.time_scale

        # collision avec outer circle
        dx = self.x - outer.x
        dy = self.y - outer.y
        dist = math.hypot(dx, dy)
        min_dist = outer.radius - self.radius

        if dist >= min_dist:
            # enregistrer la vitesse pré-réflexion
            prev_vx, prev_vy = self.xspeed, self.yspeed

            # normale au point de contact
            nx, ny = dx/dist, dy/dist
            # recaler sur la circonférence
            self.x = outer.x + nx*min_dist
            self.y = outer.y + ny*min_dist

            # réflexion de la vitesse
            v_dot_n = self.xspeed*nx + self.yspeed*ny
            self.xspeed -= 2 * v_dot_n * nx
            self.yspeed -= 2 * v_dot_n * ny

            # Augmente only time_scale
            self.time_scale = min(self.time_scale * TIME_ACCEL_FACTOR, MAX_TIME_SCALE)

            # taille s’agrandit toujours
            self.radius += SIZE_UP_FACTOR

            # --- EFFET DE CHOC ---
            outer.shock(nx, ny)

            # particules
            for _ in range(30):
                particles.append(Particle(
                    self.x, self.y,
                    prev_vx * 0.3, prev_vy * 0.3,
                    self.hue
                ))

            # --- MUSIQUE : jouer l'accord enregistré à cet index ---
            if note_index < len(all_notes):
                # 1) collecter toutes les notes du même début
                start_time = all_notes[note_index][0]
                chord = []
                while note_index < len(all_notes) and abs(all_notes[note_index][0] - start_time) < EPS:
                    _, pitch, velocity, chan = all_notes[note_index]
                    chord.append((pitch, velocity, chan))
                    note_index += 1

                # 2) couper l'accord précédent
                if hasattr(self, 'current_chord'):
                    for p, v, c in self.current_chord:
                        midi_output.note_off(p, v, c)

                # 3) jouer l'accord *avec* le canal de chaque note
                self.current_chord = []
                for pitch, velocity, chan in chord:
                    midi_output.note_on(pitch, velocity, chan)
                    self.current_chord.append((pitch, velocity, chan))



        # animation de la teinte de la balle
        self.hue = (self.hue + HUE_SPEED) % 1.0

    def draw(self, surf):
        r1, g1, b1 = colorsys.hsv_to_rgb(self.hue, SATURATION, INNER_VAL)
        fill_color    = (int(r1*255), int(g1*255), int(b1*255))
        r2, g2, b2 = colorsys.hsv_to_rgb(self.hue, SATURATION, OUTER_VAL)
        outline_color = (int(r2*255), int(g2*255), int(b2*255))

        N = 4  # nombre de ghosts intermédiaires
        for i in range(1, N+1):
            t = i / (N+1)
            xg = self.prev_x + (self.x - self.prev_x) * t
            yg = self.prev_y + (self.y - self.prev_y) * t
            # ghost plein noir
            pygame.draw.circle(
                trail_surf,
                (0, 0, 0, GHOST_ALPHA),
                (int(xg), int(yg)),
                self.radius
            )
            # ghost contour coloré
            pygame.draw.circle(
                trail_surf,
                (*outline_color, GHOST_ALPHA),
                (int(xg), int(yg)),
                self.radius,
                width=1
            )

        # 2) on dessine **sur l’écran** la balle pleine et opaque
        pygame.draw.circle(surf, fill_color,
                           (int(self.x), int(self.y)), self.radius)

# --- Initialisation des objets ---
outer = OuterCircle(WIDTH//2, HEIGHT//2, 500, width=6)
ball  = Ball(WIDTH//2.4, HEIGHT//2.3, 18)

# --- Boucle principale ---
while running:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

    # mise à jour
    outer.update()
    ball.update(outer)
    for p in particles:
        p.update()
    particles = [p for p in particles if not p.is_dead()]

    # rendu
    screen.fill((0, 0, 0))
    screen.blit(trail_surf, (0, 0))

    outer.draw(screen)
    for p in particles:
        p.draw(screen)
    ball.draw(screen)

    pygame.display.flip()

    clock.tick(FPS)

pygame.quit()
