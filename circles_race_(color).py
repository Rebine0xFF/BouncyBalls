import pygame
import pygame.midi
import math
import colorsys
import random
import pretty_midi
import time
from collections import deque

# --- Initialisation Pygame et son ---
pygame.init()
pygame.mixer.init()  # pour les effets sonores
font_ball = pygame.font.SysFont("calibri", 45, bold=True)
font_ui = pygame.font.SysFont("Ebrima", 50, bold=True)
time_left_text = pygame.font.SysFont("Ebrima", 33)
pygame.midi.init()

# Chargement sons d'effet
yes_sound = pygame.mixer.Sound(r"C:\Users\hrobi\Desktop\BouncyBalls\sounds\yes.mp3")
no_sound  = pygame.mixer.Sound(r"C:\Users\hrobi\Desktop\BouncyBalls\sounds\no.mp3")
# régler un volume inférieur à la musique MIDI
yes_sound.set_volume(0.04)
no_sound.set_volume(0.04)

# Chargement MIDI
midi_data = pretty_midi.PrettyMIDI(r"C:\Users\hrobi\Desktop\BouncyBalls\music\Tetris1.mid")
instruments = midi_data.instruments
all_notes = []
for chan, inst in enumerate(instruments):
    for note in inst.notes:
        note.start = round(note.start, 3)
        all_notes.append((note.start, note.pitch, note.velocity, chan))
all_notes.sort(key=lambda x: (x[0], x[1]))

# Initialisation de la sortie MIDI
midi_output = pygame.midi.Output(pygame.midi.get_default_output_id())
for chan, inst in enumerate(instruments):
    midi_output.set_instrument(inst.program, chan)
note_index = 0

# Configuration graphique
WIDTH, HEIGHT = 1080, 1920
FPS = 100
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
running = True
start_time = pygame.time.get_ticks() / 1000

# Constantes
GAME_DURATION = 29
GRAVITY        = 0.4
HUE_SPEED      = 0.002
SATURATION     = 0.9
INNER_VAL      = 0.7
OUTER_VAL      = 1
TIME_SCALE     = 0.35
START_VX, START_VY = 20, 15
ROTATION_SPEED = 0.01
ARC_COUNT      = 156
ARC_WIDTH      = 9
ARC_SPACING    = 25
GAP_SHIFT      = 0.1
GAP_WIDTH      = math.pi/2.5
MAX_VIEW_RADIUS = math.hypot(WIDTH/2, HEIGHT/2) + ARC_WIDTH
BASE_MIN_RADIUS = 200
SHRINK_FACTOR = 0.01
MAX_SHRINK = 5.0

# Couleurs UI
COLOR_YES = (67, 160, 71)
COLOR_NO = (142, 36, 170)
COLOR_TEXT = (255, 255, 255)

# Couleurs des arcs
def generate_neighborhood(rgb, n, hue_spread=20, sat_spread=0.2, val_spread=0.2):
    """
    Pour une couleur RGB, génère n variantes en :
     - décalant la teinte de ±hue_spread degrés
     - modifiant saturation ±sat_spread
     - modifiant valeur (luminosité) ±val_spread
    """
    r, g, b = [v/255 for v in rgb]
    h0, l0, s0 = colorsys.rgb_to_hls(r, g, b)
    variants = []
    for _ in range(n):
        # hue en radians normalisé [0,1]
        dh = random.uniform(-hue_spread, hue_spread) / 360
        h = (h0 + dh) % 1.0
        # saturation et luminosité
        s = min(1, max(0, s0 + random.uniform(-sat_spread, sat_spread)))
        l = min(1, max(0, l0 + random.uniform(-val_spread, val_spread)))
        nr, ng, nb = colorsys.hls_to_rgb(h, l, s)
        variants.append((int(nr*255), int(ng*255), int(nb*255)))
    return variants

# Génère 15 variantes autour de chaque base
vars_yes = generate_neighborhood(COLOR_YES, n=15, hue_spread=30, sat_spread=0.3, val_spread=0.3)
vars_no  = generate_neighborhood(COLOR_NO,  n=15, hue_spread=30, sat_spread=0.3, val_spread=0.3)

# On assemble la palette en incluant les bases
raw_palette = [COLOR_YES, COLOR_NO] + vars_yes + vars_no

# On enlève les doublons
palette = list(dict.fromkeys(raw_palette))

# On mélange et on limite à 20 couleurs pour rester maniable
random.shuffle(palette)
PALETTE = palette[:20]

particles = []

# Fonctions utilitaires
def draw_translucent_rect(surf, rect, color, alpha=128, border_radius=0):
    tmp = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    pygame.draw.rect(tmp, (*color, alpha), tmp.get_rect(), border_radius=border_radius)
    surf.blit(tmp, rect.topleft)

# Gestion collisions
def handle_collisions(balls):
    if len(balls) != 2:
        return
    b1, b2 = balls
    dx = b2.x - b1.x
    dy = b2.y - b1.y
    dist = math.hypot(dx, dy)
    min_dist = b1.radius + b2.radius
    if dist < min_dist and dist != 0:
        overlap = (min_dist - dist) / 2
        nx = dx / dist
        ny = dy / dist
        b1.x -= nx * overlap
        b1.y -= ny * overlap
        b2.x += nx * overlap
        b2.y += ny * overlap

        dvx = b2.xspeed - b1.xspeed
        dvy = b2.yspeed - b1.yspeed
        v_dot_n = dvx * nx + dvy * ny
        if v_dot_n < 0:
            impulse = 2 * v_dot_n / 2
            b1.xspeed += impulse * nx
            b1.yspeed += impulse * ny
            b2.xspeed -= impulse * nx
            b2.yspeed -= impulse * ny
            cx = (b1.x + b2.x) / 2
            cy = (b1.y + b2.y) / 2
            for _ in range(25):
                angle = random.uniform(0, 2 * math.pi)
                speed = random.uniform(1, 3)
                vx = math.cos(angle) * speed
                vy = math.sin(angle) * speed
                particles.append(Particle(cx, cy, vx, vy, hue=0, color_mode="white"))

# Gestion arcs & particules
def update_and_handle_arcs(arcs, balls, particles):
    remaining = []
    for arc in arcs:
        destroyed_by = None
        for ball in balls:
            if arc.ball_exits(ball):
                destroyed_by = ball
                break
        if destroyed_by:
            # jouer effet sonore selon la balle
            if destroyed_by.label == "Yes":
                yes_sound.play()
            else:
                no_sound.play()
            destroyed_by.destroyed += 1
            hue = arc.hue
            for _ in range(50):
                angle = random.random() * 2 * math.pi
                px = arc.cx + math.cos(angle) * arc.radius
                py = arc.cy + math.sin(angle) * arc.radius
                vx = math.cos(angle) * random.uniform(1, 4)
                vy = math.sin(angle) * random.uniform(1, 4)
                particles.append(Particle(px, py, vx, vy, hue))
        else:
            remaining.append(arc)
    return remaining


def update_particles(particles):
    for p in particles:
        p.update()
    particles[:] = [p for p in particles if not p.is_dead()]


def shrink_arcs(arcs):
    if not arcs:
        return
    current_min = min(arc.radius for arc in arcs)
    delta = (current_min - BASE_MIN_RADIUS) * SHRINK_FACTOR
    delta = max(0.0, min(delta, MAX_SHRINK))
    for arc in arcs:
        arc.radius -= delta

# Dessin principal
def draw_game(screen, arcs, particles, balls):
    screen.fill((10, 10, 10))
    for arc in arcs:
        if arc.radius - arc.width/2 <= MAX_VIEW_RADIUS:
            arc.draw(screen)
    for p in particles:
        p.draw(screen)
    for ball in balls:
        ball.draw(screen)

# UI
def draw_ui(screen, font_ui, balls, time_left):
    box_w, box_h, spacing = 200, 70, 40
    center_y = HEIGHT//2 - 550
    yes_r = pygame.Rect(WIDTH//2 - box_w - spacing//2, center_y, box_w, box_h)
    no_r  = pygame.Rect(WIDTH//2 + spacing//2, center_y, box_w, box_h)
    time_r = pygame.Rect((WIDTH-270)//2, center_y+box_h+15, 270, 55)
    draw_translucent_rect(screen, yes_r, COLOR_YES, alpha=128, border_radius=5)
    draw_translucent_rect(screen, no_r,  COLOR_NO,  alpha=128, border_radius=5)
    draw_translucent_rect(screen, time_r,(255,255,255),alpha=200,border_radius=5)
    yes_t = font_ui.render(f"Yes: {balls[0].destroyed}", True, COLOR_TEXT)
    no_t  = font_ui.render(f"No:  {balls[1].destroyed}", True, COLOR_TEXT)
    time_t= time_left_text.render(f"Time Left: {time_left:.1f}s", True, "black")
    screen.blit(yes_t, yes_t.get_rect(center=yes_r.center))
    screen.blit(no_t,  no_t.get_rect(center=no_r.center))
    screen.blit(time_t,time_t.get_rect(center=time_r.center))

# Classes
class OuterArc:
    def __init__(self, x, y, radius, width=ARC_WIDTH, gap_center=0, gap_width=GAP_WIDTH):
        self.cx, self.cy, self.radius, self.width = x, y, radius, width
        self.gap_center, self.gap_width = gap_center, gap_width
        self.compute_gap()
        # palette
        self.c1, self.c2 = random.sample(PALETTE, 2)
        self.cycle_time = random.uniform(2.0, 5.0)
        self.phase = random.uniform(0, 2*math.pi)
        # on initialise hue pour les particules
        self.hue = 0.0

    def compute_gap(self):
        self.gap_start = (self.gap_center - self.gap_width/2) % (2*math.pi)
        self.gap_end   = (self.gap_center + self.gap_width/2) % (2*math.pi)

    def update(self):
        # rotation du gap
        self.gap_center = (self.gap_center + ROTATION_SPEED) % (2*math.pi)
        self.compute_gap()
        # mise à jour de la teinte pour les particules
        t = pygame.time.get_ticks() / 1000.0
        # facteur [0,1] sinusoïdal
        f = (math.sin((2*math.pi/self.cycle_time)*t + self.phase) + 1) / 2
        self.hue = f
        # (on ne stocke pas la couleur ici mais on la calcule à la volée dans draw)

    def current_color(self):
        """Renvoie la couleur RGB interpolée pour le dessin."""
        # f = self.hue tel que mis à jour plus haut
        r = int(self.c1[0] * (1-self.hue) + self.c2[0] * self.hue)
        g = int(self.c1[1] * (1-self.hue) + self.c2[1] * self.hue)
        b = int(self.c1[2] * (1-self.hue) + self.c2[2] * self.hue)
        return (r, g, b)

    def draw(self, surf):
        c = self.current_color()
        r = pygame.Rect(self.cx-self.radius, self.cy-self.radius, 2*self.radius, 2*self.radius)
        if self.gap_start < self.gap_end:
            pygame.draw.arc(surf, c, r, self.gap_end, 2*math.pi, self.width)
            pygame.draw.arc(surf, c, r, 0, self.gap_start, self.width)
        else:
            pygame.draw.arc(surf, c, r, self.gap_end, self.gap_start, self.width)

    def ball_exits(self, ball):
        dx, dy = ball.x-self.cx, ball.y-self.cy
        dist = math.hypot(dx, dy)
        if dist > self.radius - ball.radius:
            ang = (math.atan2(-dy, dx) + 2*math.pi) % (2*math.pi)
            if self.gap_start < self.gap_end:
                return self.gap_start <= ang <= self.gap_end
            return ang >= self.gap_start or ang <= self.gap_end
        return False

class Ball:
    def __init__(self, x, y, radius, border_color, label):
        self.x, self.y = x, y
        self.radius = radius
        self.xspeed, self.yspeed = START_VX, START_VY
        self.time_scale = TIME_SCALE
        self.border_color, self.label = border_color, label
        self.destroyed = 0
        self.current_chord = []
        self.last_note_time = 0.0
        self.note_cooldown = 0.1
        self.trail = deque(maxlen=9)
    def update(self, arcs):
        global note_index
        EPS = 1e-3
        self.yspeed += GRAVITY
        self.x += self.xspeed*self.time_scale
        self.y += self.yspeed*self.time_scale
        self.trail.append((self.x,self.y))
        for arc in sorted(arcs,key=lambda a:-a.radius):
            if arc.radius-arc.width/2>MAX_VIEW_RADIUS: continue
            dx,dy = self.x-arc.cx, self.y-arc.cy
            dist=math.hypot(dx,dy)
            if dist>=arc.radius-self.radius:
                ang=(math.atan2(-dy,dx)+2*math.pi)%(2*math.pi)
                in_gap=((arc.gap_start<arc.gap_end and arc.gap_start<=ang<=arc.gap_end) or
                        (arc.gap_start>=arc.gap_end and (ang>=arc.gap_start or ang<=arc.gap_end)))
                if not in_gap:
                    nx,ny=dx/dist,dy/dist
                    self.x=arc.cx+nx*(arc.radius-self.radius)
                    self.y=arc.cy+ny*(arc.radius-self.radius)
                    v_dot_n=self.xspeed*nx+self.yspeed*ny
                    self.xspeed-=2*v_dot_n*nx
                    self.yspeed-=2*v_dot_n*ny
                    if abs(v_dot_n)<3:
                        self.xspeed+=nx*10; self.yspeed+=ny*10
                    now=time.time()
                    if now-self.last_note_time>=self.note_cooldown:
                        for p,v,c in self.current_chord: midi_output.note_off(p,v,c)
                        if note_index<len(all_notes):
                            t0=all_notes[note_index][0]
                            chord=[]
                            while note_index<len(all_notes) and abs(all_notes[note_index][0]-t0)<EPS:
                                _,pitch,vel,chan=all_notes[note_index]
                                chord.append((pitch,vel,chan)); note_index+=1
                            for p,v,c in chord: midi_output.note_on(p,v,c)
                            self.current_chord=chord; self.last_note_time=now
                    break
    def draw(self, surf):
        for idx,(tx,ty) in enumerate(self.trail):
            alpha=int(255*(idx/len(self.trail)))
            s=pygame.Surface((self.radius*2,self.radius*2),pygame.SRCALPHA)
            pygame.draw.circle(s,(*self.border_color,alpha),(self.radius,self.radius),self.radius)
            surf.blit(s,(tx-self.radius,ty-self.radius))
        pygame.draw.circle(surf,(0,0,0),(int(self.x),int(self.y)),self.radius)
        pygame.draw.circle(surf,self.border_color,(int(self.x),int(self.y)),self.radius,5)
        ls=font_ball.render(self.label,True,"white")
        surf.blit(ls,ls.get_rect(center=(int(self.x),int(self.y))))

class Particle:
    def __init__(self, x, y, vx, vy, hue, color_mode="hue"):
        self.x, self.y, self.vx, self.vy = x, y, vx+random.uniform(-3,3), vy+random.uniform(-3,3)
        self.hue, self.color_mode = hue, color_mode
        self.life = random.randint(15,30) if color_mode=="white" else random.randint(30,60)
        self.size = random.randint(2,4) if color_mode=="white" else random.randint(3,6)
    def update(self):
        self.vy+=GRAVITY; self.x+=self.vx; self.y+=self.vy; self.life-=1
    def draw(self,surf):
        clr=(255,255,255) if self.color_mode=="white" else tuple(int(c*255) for c in colorsys.hsv_to_rgb(self.hue,SATURATION,OUTER_VAL))
        pygame.draw.circle(surf,clr,(int(self.x),int(self.y)),self.size)
    def is_dead(self): return self.life<=0

# Création arcs et balles
arcs=[]; cx,cy=WIDTH/2,HEIGHT/2
for i in range(ARC_COUNT):
    arcs.append(OuterArc(cx,cy,BASE_MIN_RADIUS+i*(ARC_WIDTH+ARC_SPACING),gap_center=GAP_SHIFT*i))
balls=[Ball(cx-150,cy-200,50,COLOR_YES,"Yes"), Ball(cx+100,cy-200,50,COLOR_NO,"No")]

# Boucle principale
while running:
    for e in pygame.event.get():
        if e.type==pygame.QUIT: running=False
    for arc in arcs: arc.update()
    for ball in balls: ball.update(arcs)
    handle_collisions(balls)
    arcs = update_and_handle_arcs(arcs, balls, particles)
    update_particles(particles)
    shrink_arcs(arcs)
    elapsed = pygame.time.get_ticks()/1000 - start_time
    time_left = max(0.0, GAME_DURATION - elapsed)
    draw_game(screen, arcs, particles, balls)
    draw_ui(screen, font_ui, balls, time_left)
    pygame.display.flip()
    clock.tick(FPS)
pygame.quit()