import pygame
import pygame.midi
import math
import colorsys
import random
import pretty_midi
import time
from collections import deque

# --- Initialisation Pygame et MIDI ---
pygame.init()
pygame.midi.init()

# --- Chargement MIDI ---
midi_data = pretty_midi.PrettyMIDI(r"C:\Users\hrobi\Desktop\BouncyBalls\music\Spectre_NCS.mid")
instruments = midi_data.instruments
all_notes = []
for chan, inst in enumerate(instruments):
    for note in inst.notes:
        all_notes.append((round(note.start,3), note.pitch, note.velocity, chan))
all_notes.sort(key=lambda x:(x[0],x[1]))
midi_out = pygame.midi.Output(pygame.midi.get_default_output_id())
for chan,inst in enumerate(instruments):
    midi_out.set_instrument(inst.program, chan)
note_index = 0

# --- Config graphique ---
WIDTH, HEIGHT = 1080, 1920
FPS = 100
HUE_SPEED = 0.002
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

# --- Constantes ---
GRAVITY = 0.3
TIME_SCALE = 0.4
BASE_VX, BASE_VY = -8, 7
DELTA_VX, DELTA_VY = 0, 0   # par exemple : on ajoute +2 en x et +1 en y à chaque balle
SPAWN_X_MIN, SPAWN_X_MAX = WIDTH * 0.2, WIDTH * 0.6
SPAWN_Y_MIN, SPAWN_Y_MAX = HEIGHT * 0.2, HEIGHT * 0.4
FREEZE_DELAY = 3.0  # secondes avant qu’une balle se fige
BALL_RADIUS = 30

CIRCLE_GAP_CENTER = math.pi / 1.2    # angle central de l’ouverture
CIRCLE_GAP_WIDTH  = math.pi / 4    # largeur de l’ouverture



def get_spawn_position():
    x = random.uniform(SPAWN_X_MIN, SPAWN_X_MAX)
    y = random.uniform(SPAWN_Y_MIN, SPAWN_Y_MAX)
    return x, y


# --- Classes ---
class OuterCircle:
    def __init__(self, x, y, radius, width=6):
        self.x, self.y, self.radius, self.width = x, y, radius, width
        self.hue = 0.0
        # calcul de l’ouverture
        self.gap_center = CIRCLE_GAP_CENTER
        self.gap_width  = CIRCLE_GAP_WIDTH
        self.compute_gap()

    def compute_gap(self):
        self.gap_start = (self.gap_center - self.gap_width/2) % (2*math.pi)
        self.gap_end   = (self.gap_center + self.gap_width/2) % (2*math.pi)

    def update(self):
        self.hue = (self.hue + HUE_SPEED) % 1.0

    def draw(self, surf):
        r, g, b = colorsys.hsv_to_rgb(self.hue, 1.0, 1.0)
        color = (int(r*255), int(g*255), int(b*255))
        rect = pygame.Rect(self.x-self.radius, self.y-self.radius,
                           2*self.radius, 2*self.radius)
        # on dessine l’arc en deux segments hors de l’ouverture
        if self.gap_start < self.gap_end:
            pygame.draw.arc(surf, color, rect, self.gap_end, 2*math.pi, self.width)
            pygame.draw.arc(surf, color, rect, 0, self.gap_start, self.width)
        else:
            pygame.draw.arc(surf, color, rect, self.gap_end, self.gap_start, self.width)



class Ball:
    def __init__(self, x, y, radius, vx, vy):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.radius = radius
        self.spawn_time = time.time()
        self.frozen = False
        self.current_chord = []
        self.trail = deque(maxlen=4)
        self.fill_color = (100, 200, 250)
        self.border_color = (255, 255, 255)

    def update(self, outer, others):
        global note_index
        EPS = 1e-3
        now = time.time()
        if not self.frozen:

            # Synchroniser la couleur de la balle avec celle du cercle
            r, g, b = colorsys.hsv_to_rgb(outer.hue, 1.0, 1.0)
            self.fill_color = (int(r*255), int(g*255), int(b*255))

            # gravité et mouvement
            self.vy += GRAVITY
            self.x += self.vx * TIME_SCALE
            self.y += self.vy * TIME_SCALE
            self.trail.append((self.x,self.y))

            # collision avec le cercle
            dx, dy = self.x - outer.x, self.y - outer.y
            dist = math.hypot(dx, dy)
            min_dist = outer.radius - self.radius
            if dist >= min_dist:
                dy_screen = outer.y - self.y
                angle = math.atan2(dy_screen, dx) % (2 * math.pi)

                # test si l'angle est DANS l'ouverture
                if outer.gap_start < outer.gap_end:
                    in_gap = outer.gap_start <= angle <= outer.gap_end
                else:
                    # cas où l'ouverture est à cheval sur 0
                    in_gap = angle >= outer.gap_start or angle <= outer.gap_end

                if not in_gap:
                    # rebond : projection normale
                    nx, ny = dx / dist, dy / dist
                    # repositionnement
                    self.x = outer.x + nx * min_dist
                    self.y = outer.y + ny * min_dist
                    # réflexion du vecteur vitesse
                    v_dot_n = self.vx * nx + self.vy * ny
                    self.vx -= 2 * v_dot_n * nx
                    self.vy -= 2 * v_dot_n * ny

                    # jouer l'accord MIDI
                    for p, v, c in self.current_chord:
                        midi_out.note_off(p, v, c)
                    if note_index < len(all_notes):
                        t0 = all_notes[note_index][0]
                        chord = []
                        while note_index < len(all_notes) and abs(all_notes[note_index][0] - t0) < EPS:
                            _, pitch, vel, chan = all_notes[note_index]
                            chord.append((pitch, vel, chan))
                            note_index += 1
                        for p, v, c in chord:
                            midi_out.note_on(p, v, c)
                        self.current_chord = chord

                        
            # collision avec autres balles figées
            for other in others:
                if other is not self:
                    dx, dy = self.x-other.x, self.y-other.y
                    d = math.hypot(dx,dy)
                    if d < self.radius+other.radius and d>0:
                        nx, ny = dx/d, dy/d
                        overlap = (self.radius+other.radius - d)/2
                        self.x += nx*overlap
                        self.y += ny*overlap
                        # réflection élastique (other étant figé, échange de vitesse partiel)
                        v_dot_n = self.vx*nx + self.vy*ny
                        self.vx -= 2*v_dot_n*nx
                        self.vy -= 2*v_dot_n*ny

                        # --- jouer une note MIDI ---
                        for p,v,c in self.current_chord:
                            midi_out.note_off(p,v,c)
                        if note_index < len(all_notes):
                            t0 = all_notes[note_index][0]
                            chord = []
                            while note_index < len(all_notes) and abs(all_notes[note_index][0]-t0)<EPS:
                                _, pitch, vel, chan = all_notes[note_index]
                                chord.append((pitch,vel,chan))
                                note_index += 1
                            for p,v,c in chord:
                                midi_out.note_on(p,v,c)
                            self.current_chord = chord

            # figer après délai
            if now - self.spawn_time >= FREEZE_DELAY:
                self.frozen = True


    def draw(self, surf):
        # traînée (outline semi-transparent)
        for idx, (tx, ty) in enumerate(self.trail):
            alpha = int(255 * (idx / len(self.trail)))
            s = pygame.Surface((self.radius*2, self.radius*2), pygame.SRCALPHA)
            pygame.draw.circle(
                s,
                (*self.border_color, alpha),
                (self.radius, self.radius),
                self.radius
            )
            surf.blit(s, (tx-self.radius, ty-self.radius))

        # balle principale (remplissage + contour)
        color = self.fill_color
        center = (int(self.x), int(self.y))
        # d’abord le contour (largeur 4), puis le remplissage
        pygame.draw.circle(surf, self.border_color, center, self.radius, width=4)
        pygame.draw.circle(surf, color, center, self.radius-4)

# --- Initialisation objets ---
outer = OuterCircle(WIDTH/2, HEIGHT/2, 500)
balls = []
n = len(balls)
vx = BASE_VX + n * DELTA_VX
vy = BASE_VY + n * DELTA_VY
sx, sy = get_spawn_position()
balls.append(Ball(sx, sy, BALL_RADIUS, vx, vy))

# --- Boucle principale ---
running = True
while running:
    for evt in pygame.event.get():
        if evt.type == pygame.QUIT:
            running = False

    # si la dernière balle est figée, on en crée une nouvelle
    if balls[-1].frozen:
        n = len(balls)
        vx = BASE_VX + n * DELTA_VX
        vy = BASE_VY + n * DELTA_VY
        sx, sy = get_spawn_position()
        balls.append(Ball(sx, sy, BALL_RADIUS, vx, vy))

    # MAJ
    outer.update()
    for b in balls:
        b.update(outer, balls)

    # Rendu
    screen.fill((30,30,30))
    outer.draw(screen)
    for b in balls:
        b.draw(screen)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
