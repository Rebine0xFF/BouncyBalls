import pygame
import math
import colorsys
import random
import time
import os


# Largeur de l’ouverture du cercle (en degrés)
GAP_ANGLE_DEGREES = 30

# Vitesse de rotation du cercle (en degrés par frame)
ROT_SPEED_DEGREES = 0.7

# Chemins vers vos fichiers de rebond (tous au format WAV)
BOUNCE_SOUND_PATHS = [
    r"C:\Users\hrobi\Desktop\BouncyBalls\sounds\bounce1.wav",
    r"C:\Users\hrobi\Desktop\BouncyBalls\sounds\bounce2.wav",
    r"C:\Users\hrobi\Desktop\BouncyBalls\sounds\bounce3.wav",
    r"C:\Users\hrobi\Desktop\BouncyBalls\sounds\bounce4.wav",
    r"C:\Users\hrobi\Desktop\BouncyBalls\sounds\bounce5.wav",
    r"C:\Users\hrobi\Desktop\BouncyBalls\sounds\bounce6.wav"
]

# Cooldown entre deux lectures du son de rebond (en millisecondes)
BOUNCE_COOLDOWN_MS = 100



ENABLE_BALL_COLLISIONS = True



# ------------------------------------------------

# --- Initialisation Pygame (graphique + son) ---
pygame.init()
pygame.mixer.init()

# Chargement des 6 sons de rebond dans une liste
bounce_sounds = []
for path in BOUNCE_SOUND_PATHS:
    snd = pygame.mixer.Sound(path)
    snd.set_volume(0.5)
    bounce_sounds.append(snd)

# Variable globale pour gérer le cooldown
last_bounce_time = 0

# --- Configuration graphique ---
WIDTH, HEIGHT = 1920, 1920
FPS = 100
screen     = pygame.display.set_mode((WIDTH, HEIGHT))
trail_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
clock      = pygame.time.Clock()
running    = True

# --- Constantes physiques & visuelles ---
GRAVITY        = 0.3
HUE_SPEED      = 0.002
GHOST_ALPHA    = 50
INNER_VAL      = 0.7
OUTER_VAL      = 1
SATURATION     = 0.9
TIME_SCALE     = 0.3
MAX_TIME_SCALE = 1.6
START_VX, START_VY = 19, 23

TIME_ACCEL_FACTOR = 1
SIZE_UP_FACTOR    = 0

SPRING_K    = 0.1
DAMPING     = 0.85
SHOCK_FORCE = 0

particles = []




# Dossier où se trouvent les frames (dézippées)
DANCER_FOLDER = r"C:\Users\hrobi\Desktop\BouncyBalls\dancer_assets\animation_frames"

# Vitesse (en secondes) entre chaque frame de danse
DANCE_FRAME_DELAY = 0.05  # correspond au “delay-0.05s” dans le nom, mais on peut ajuster

# Charger toutes les images du dossier, triées par nom
dance_frames = []
DANCER_SCALE = 1.2

for filename in sorted(os.listdir(DANCER_FOLDER)):
    if filename.startswith("frame_") and filename.endswith(".png"):
        img = pygame.image.load(os.path.join(DANCER_FOLDER, filename)).convert_alpha()
        w, h = img.get_size()
        scaled_img = pygame.transform.smoothscale(img, (int(w * DANCER_SCALE), int(h * DANCER_SCALE)))
        dance_frames.append(scaled_img)

# Index courant de la frame (float pour interpolation)
dance_index = 0.0

# Temps du dernier changement de frame
last_dance_update = pygame.time.get_ticks()

# Charger la musique de danse
pygame.mixer.music.load(r"C:\Users\hrobi\Desktop\BouncyBalls\dancer_assets\dance_music.mp3")




class OuterCircle:
    def __init__(self, x, y, radius, width=4):
        self.base_x, self.base_y = x, y
        self.x, self.y = x, y
        self.radius = radius
        self.width  = width
        self.vx, self.vy = 0.0, 0.0
        self.hue, self.sat, self.val = 0.0, 1.0, 1.0
        self.color = self.hsv_to_rgb()

        self.gap_angle    = math.radians(GAP_ANGLE_DEGREES)
        self.angle_offset = 0.0
        self.rot_speed    = math.radians(ROT_SPEED_DEGREES)

    def hsv_to_rgb(self):
        r, g, b = colorsys.hsv_to_rgb(self.hue, self.sat, self.val)
        return (int(r * 255), int(g * 255), int(b * 255))

    def shock(self, nx, ny):
        self.vx += nx * SHOCK_FORCE
        self.vy += ny * SHOCK_FORCE

    def update(self):
        # Animation de la couleur
        self.hue = (self.hue + HUE_SPEED) % 1.0
        self.color = self.hsv_to_rgb()

        # Ressort vers la position de repos
        dx = self.base_x - self.x
        dy = self.base_y - self.y
        self.vx += dx * SPRING_K
        self.vy += dy * SPRING_K

        # Amortissement
        self.vx *= DAMPING
        self.vy *= DAMPING

        # Mise à jour de la position
        self.x += self.vx
        self.y += self.vy

        # Rotation continue
        self.angle_offset = (self.angle_offset + self.rot_speed) % (2 * math.pi)

    def draw(self, surf):
        rect = pygame.Rect(
            int(self.x - self.radius),
            int(self.y - self.radius),
            int(2 * self.radius),
            int(2 * self.radius)
        )

        gap_center = self.angle_offset % (2 * math.pi)
        half_gap   = self.gap_angle / 2
        gap_start  = (gap_center - half_gap + 2 * math.pi) % (2 * math.pi)
        gap_end    = (gap_center + half_gap) % (2 * math.pi)

        if gap_start < gap_end:
            # Dessine tout sauf l’arc [gap_start→gap_end]
            pygame.draw.arc(surf, self.color, rect, gap_end, 2 * math.pi, self.width)
            pygame.draw.arc(surf, self.color, rect, 0, gap_start, self.width)
        else:
            # Si l’arc solide franchit 2π→0
            pygame.draw.arc(surf, self.color, rect, gap_end, gap_start, self.width)


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
        color = (int(r * 255), int(g * 255), int(b * 255))
        rect = pygame.Rect(
            int(self.x - self.w / 2),
            int(self.y - self.h / 2),
            self.w, self.h
        )
        pygame.draw.rect(surf, color, rect)

    def is_dead(self):
        return self.life <= 0


class Ball:
    def __init__(self, x, y, radius):
        self.time_scale = TIME_SCALE
        self.x, self.y = x, y
        self.radius = radius
        self.xspeed, self.yspeed = START_VX, START_VY
        self.hue = 0.0
        self.prev_x = x
        self.prev_y = y
        # NOUVEL ATTRIBUT : la balle est active tant qu'elle ne sort pas par le gap
        self.exited = False
        self.ghost_trail = []  # Liste de tuples (x, y, timestamp)

    def update(self, outer):
        """
        Met à jour la position + collision.
        Si exited == True, on ignore toutes collisions (cercles et autres balles).
        Retourne True seulement la première fois que la balle traverse le gap.
        """
        global particles, last_bounce_time
        EPS = 1e-3

        # Si la balle est déjà sortie, on se contente de la faire bouger sans aucune collision
        if self.exited:
            # Gravité + translation
            self.yspeed += GRAVITY
            self.x += self.xspeed * self.time_scale
            self.y += self.yspeed * self.time_scale
            # Variation de teinte quand même
            self.hue = (self.hue + HUE_SPEED) % 1.0
            return False

        # --- Sinon, la balle est encore à l’intérieur du cercle ---
        self.prev_x, self.prev_y = self.x, self.y

        # Gravité + déplacement
        self.yspeed += GRAVITY
        self.x += self.xspeed * self.time_scale
        self.y += self.yspeed * self.time_scale

        # Collision avec le cercle
        dx_act = self.x - outer.x
        dy_act = self.y - outer.y
        dist_act = math.hypot(dx_act, dy_act)
        min_dist = outer.radius - self.radius

        dx_prev = self.prev_x - outer.x
        dy_prev = self.prev_y - outer.y
        dist_prev = math.hypot(dx_prev, dy_prev)

        if dist_act >= min_dist:
            # Calcul de l’angle corrigé pour Pygame (y vers le bas)
            ang = (math.atan2(-dy_act, dx_act) + 2 * math.pi) % (2 * math.pi)

            gap_center = outer.angle_offset % (2 * math.pi)
            half_gap   = outer.gap_angle / 2
            gap_start  = (gap_center - half_gap + 2 * math.pi) % (2 * math.pi)
            gap_end    = (gap_center + half_gap) % (2 * math.pi)

            if gap_start < gap_end:
                in_gap = (gap_start <= ang <= gap_end)
            else:
                in_gap = (ang >= gap_start or ang <= gap_end)

            # 1) SI la balle vient de passer de l’intérieur vers l’extérieur DANS le gap
            if dist_prev < min_dist and in_gap:
                # On marque la balle comme sortie et on laisse le main loop créer de nouvelles balles
                self.exited = True
                return True

            # 2) Sinon, collision « solide » → rebond + particules + son
            if not in_gap:
                prev_vx, prev_vy = self.xspeed, self.yspeed
                nx, ny = dx_act / dist_act, dy_act / dist_act

                # Recalage sur la circonférence
                self.x = outer.x + nx * min_dist
                self.y = outer.y + ny * min_dist

                # Réflexion de la vitesse
                v_dot_n = self.xspeed * nx + self.yspeed * ny
                self.xspeed -= 2 * v_dot_n * nx
                self.yspeed -= 2 * v_dot_n * ny

                self.time_scale = min(self.time_scale * TIME_ACCEL_FACTOR, MAX_TIME_SCALE)
                self.radius += SIZE_UP_FACTOR

                outer.shock(nx, ny)

                # Particules au point d’impact
                for _ in range(30):
                    particles.append(Particle(
                        self.x, self.y,
                        prev_vx * 0.3, prev_vy * 0.3,
                        self.hue
                    ))

                # Lecture aléatoire d’un son de rebond si le cooldown est écoulé
                now = pygame.time.get_ticks()
                if now - last_bounce_time >= BOUNCE_COOLDOWN_MS:
                    random.choice(bounce_sounds).play()
                    last_bounce_time = now

        # Ajout de la position actuelle à la trail avec timestamp
        self.ghost_trail.append((self.x, self.y, time.time()))
        # Nettoyage des ghosts trop vieux (> GHOST_LIFETIME)
        GHOST_LIFETIME = 0.3  # secondes
        now = time.time()
        self.ghost_trail = [(x, y, t) for (x, y, t) in self.ghost_trail if now - t < GHOST_LIFETIME]

        # Variation de teinte
        self.hue = (self.hue + HUE_SPEED) % 1.0
        return False

    def draw(self, surf):
        # On dessine les ghosts (le même code)
        r1, g1, b1 = colorsys.hsv_to_rgb(self.hue, SATURATION, INNER_VAL)
        fill_color = (int(r1 * 255), int(g1 * 255), int(b1 * 255))
        r2, g2, b2 = colorsys.hsv_to_rgb(self.hue, SATURATION, OUTER_VAL)
        outline_color = (int(r2 * 255), int(g2 * 255), int(b2 * 255))

        # Dessiner les ghosts avec alpha dégressif selon l'âge
        now = time.time()
        for xg, yg, t in self.ghost_trail:
            age = now - t
            if age > 0:
                alpha = int(GHOST_ALPHA * (1 - age / 0.3))
                if alpha < 0: alpha = 0
            else:
                alpha = GHOST_ALPHA
            pygame.draw.circle(
                trail_surf,
                (0, 0, 0, alpha),
                (int(xg), int(yg)),
                self.radius
            )
            pygame.draw.circle(
                trail_surf,
                (*outline_color, alpha),
                (int(xg), int(yg)),
                self.radius,
                width=1
            )

        pygame.draw.circle(surf, fill_color, (int(self.x), int(self.y)), self.radius)


# --- Initialisation des objets ---
outer = OuterCircle(WIDTH // 2, HEIGHT // 2, 500, width=6)
balls = [Ball(WIDTH // 2.4, HEIGHT // 2.3, 18)]

INITIAL_SPEED = math.hypot(START_VX, START_VY)


def handle_ball_collisions(balls):
    """Détecte et gère les collisions élastiques entre toutes les paires de balles."""
    for i in range(len(balls)):
        for j in range(i + 1, len(balls)):
            b1 = balls[i]
            b2 = balls[j]
            # Si l’une des deux est déjà sortie, on ignore la collision
            if b1.exited or b2.exited:
                continue

            dx = b2.x - b1.x
            dy = b2.y - b1.y
            dist = math.hypot(dx, dy)
            if dist == 0:
                continue
            min_dist = b1.radius + b2.radius
            if dist < min_dist:
                # Séparation : on recule chaque balle d’une moitié du chevauchement
                overlap = 0.5 * (min_dist - dist)
                nx, ny = dx / dist, dy / dist
                b1.x -= nx * overlap
                b1.y -= ny * overlap
                b2.x += nx * overlap
                b2.y += ny * overlap

                # Composantes normale et tangentielle
                v1n = b1.xspeed * nx + b1.yspeed * ny
                v2n = b2.xspeed * nx + b2.yspeed * ny
                v1t = -b1.xspeed * ny + b1.yspeed * nx
                v2t = -b2.xspeed * ny + b2.yspeed * nx

                # Échange des composantes normales (masses égales)
                b1.xspeed = v2n * nx - v1t * ny
                b1.yspeed = v2n * ny + v1t * nx
                b2.xspeed = v1n * nx - v2t * ny
                b2.yspeed = v1n * ny + v2t * nx

                # Son de rebond balle-balle, si cooldown expiré
                now = pygame.time.get_ticks()
                if now - last_bounce_time >= BOUNCE_COOLDOWN_MS:
                    random.choice(bounce_sounds).play()
                    globals()['last_bounce_time'] = now



def balls_outside(balls):
    return any(b.exited for b in balls)

animation_active = False


# --- Boucle principale ---
while running:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False


    outer.update()

    new_balls = []
    for b in balls:
        if b.update(outer):
            # Quand b.exited devient True, on fait apparaître deux nouvelles balles au centre
            offset = 30
            cx = WIDTH // 2
            cy = HEIGHT // 2

            b1 = Ball(cx - offset, cy, 18)
            θ1 = random.uniform(0, 2 * math.pi)
            b1.xspeed = INITIAL_SPEED * math.cos(θ1)
            b1.yspeed = INITIAL_SPEED * math.sin(θ1)

            b2 = Ball(cx + offset, cy, 18)
            θ2 = random.uniform(0, 2 * math.pi)
            b2.xspeed = INITIAL_SPEED * math.cos(θ2)
            b2.yspeed = INITIAL_SPEED * math.sin(θ2)

            new_balls.extend([b1, b2])

    balls.extend(new_balls)

    # Gérer les collisions balle-balle (en ignorant toute balle pour laquelle exited == True)
    if ENABLE_BALL_COLLISIONS:
        handle_ball_collisions(balls)

    # Filtrer les balles sorties de l’écran
    survivors = []
    for b in balls:
        if not (
            b.x + b.radius < 0 or
            b.x - b.radius > WIDTH or
            b.y + b.radius < 0 or
            b.y - b.radius > HEIGHT
        ):
            survivors.append(b)
    balls = survivors

    # Mettre à jour les particules
    for p in particles:
        p.update()
    particles = [p for p in particles if not p.is_dead()]




    # ─── GESTION DE L’ANIMATION DU DANSEUR ───

    if balls_outside(balls):
        # Si la musique n'est pas déjà lancée, on la démarre en boucle
        if not pygame.mixer.music.get_busy():
            pygame.mixer.music.play(-1)

        # On calcule si on doit passer à la frame suivante
        now = pygame.time.get_ticks()
        if now - last_dance_update > DANCE_FRAME_DELAY * 1000:
            dance_index = (dance_index + 1) % len(dance_frames)
            last_dance_update = now

    else:
        # Plus aucune balle à l'extérieur : on arrête musique et on fige l'animation
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        dance_index = 0.0  # on retourne à la frame 0 ou à celle qu’on souhaite
        # (on pourrait aussi décider de ne pas réinitialiser si on veut reprendre au même point)





    # Rendu
    screen.fill((0, 0, 0))
    screen.blit(trail_surf, (0, 0))

    outer.draw(screen)

    for p in particles:
        p.draw(screen)



# 2) Dessiner le frame courant du danseur, au centre de l’écran
    if balls_outside(balls):
        # convert dance_index en int
        frame_img = dance_frames[int(dance_index)]
        rect = frame_img.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        screen.blit(frame_img, rect)



    for b in balls:
        b.draw(screen)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
