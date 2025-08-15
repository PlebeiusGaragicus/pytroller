import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple

import pygame

# Shared colors
BG_COLOR = (10, 10, 10)
FG_COLOR = (220, 220, 220)
ACCENT = (100, 180, 255)
YELLOW = (240, 210, 70)
GREEN = (80, 200, 120)
RED = (240, 90, 90)
PURPLE = (180, 100, 220)


@dataclass
class Star:
    x: float
    y: float
    layer: float  # 0.6..1.4


@dataclass
class Laser:
    x: float
    y: float
    vx: float
    vy: float
    color: Tuple[int, int, int]
    friendly: bool
    w: int = 14
    h: int = 3

    def update(self, dt: float):
        self.x += self.vx * dt
        self.y += self.vy * dt

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - self.w / 2), int(self.y - self.h / 2), self.w, self.h)


@dataclass
class Shard:
    x: float
    y: float
    vx: float
    vy: float
    ttl: float = 6.0
    value: float = 10.0

    def update(self, dt: float):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= (1.0 - 0.4 * dt)
        self.vy *= (1.0 - 0.4 * dt)
        self.ttl -= dt

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - 4), int(self.y - 4), 8, 8)


@dataclass
class Enemy:
    kind: str  # 'asteroid' | 'blob' | 'red' | 'snake'
    x: float
    y: float
    vx: float
    vy: float
    hp: float
    t: float = 0.0
    data: dict = field(default_factory=dict)

    def rect(self) -> pygame.Rect:
        if self.kind == "red":
            s = 24
            return pygame.Rect(int(self.x - s / 2), int(self.y - s / 2), s, s)
        r = self.data.get("r", 18)
        return pygame.Rect(int(self.x - r), int(self.y - r), r * 2, r * 2)


class Game:
    def __init__(self, width: int, height: int, log_fn=None):
        self.w, self.h = width, height
        self.log = log_fn or (lambda *_: None)

        # Player state
        self.px = width * 0.18
        self.py = height * 0.5
        self.base_speed = 220.0
        self.boost_mul = 2.0
        self.energy = 60.0
        self.energy_max = 120.0
        self.boost_active = False
        self.shield_active = False
        self.shoot_cd = 0.0
        self.score = 0

        # World
        self.stars: List[Star] = [
            Star(
                x=random.uniform(0, width),
                y=random.uniform(0, height),
                layer=random.choice([0.6, 0.8, 1.0, 1.2, 1.4]),
            )
            for _ in range(140)
        ]

        # Entities
        self.bullets: List[Laser] = []
        self.ebullets: List[Laser] = []
        self.enemies: List[Enemy] = []
        self.shards: List[Shard] = []
        self.spawn_t = 1.0

    # ---- Spawning / helpers ----
    def _fire_player(self):
        tip_x = self.px + 18
        tip_y = self.py
        self.bullets.append(Laser(tip_x, tip_y, 520.0, 0.0, YELLOW, True))

    def _spawn_enemy(self):
        y = random.uniform(40, self.h - 40)
        kind = random.choices(["asteroid", "blob", "red", "snake"], weights=[4, 3, 2, 1], k=1)[0]
        if kind == "asteroid":
            r = random.randint(12, 28)
            speed = random.uniform(80, 160)
            self.enemies.append(Enemy("asteroid", self.w + 40, y, -speed, 0.0, hp=1.0 + r / 10.0, data={"r": r}))
        elif kind == "blob":
            self.enemies.append(Enemy("blob", self.w + 40, y, -140.0, 0.0, hp=3.0))
        elif kind == "red":
            self.enemies.append(Enemy("red", self.w + 50, y, -120.0, 0.0, hp=4.0, data={"shoot_cd": random.uniform(0.6, 1.5)}))
        elif kind == "snake":
            segs = [(self.w + 60 + i * 16, y) for i in range(8)]
            self.enemies.append(Enemy("snake", self.w + 60, y, -130.0, 0.0, hp=6.0, data={"segs": segs, "phase": random.uniform(0, math.tau)}))

    def _enemy_die(self, e: Enemy):
        # Spawn energy shards
        n = random.randint(2, 5)
        for _ in range(n):
            ang = random.uniform(-0.6, 0.6)
            sp = random.uniform(80, 160)
            vx = -sp * math.cos(ang)
            vy = sp * math.sin(ang) * 0.5
            self.shards.append(Shard(e.x, e.y, vx, vy, ttl=random.uniform(3, 6), value=random.uniform(6, 12)))
        self.score += 1

    # ---- Update / Draw ----
    def update(self, dt: float, move_dx: float, move_dy: float, shoot: bool, boost: bool, shield: bool):
        # Energy drains
        self.boost_active = bool(boost and self.energy > 0.0)
        self.shield_active = bool(shield and self.energy > 0.0)
        drain = 0.0
        if self.boost_active:
            drain += 20.0 * dt
        if self.shield_active:
            drain += 28.0 * dt
        self.energy = max(0.0, self.energy - drain)

        # Movement
        speed = self.base_speed * (self.boost_mul if self.boost_active else 1.0)
        self.px = max(20, min(self.w - 20, self.px + move_dx * speed * dt))
        self.py = max(20, min(self.h - 20, self.py + move_dy * speed * dt))

        # Shooting
        self.shoot_cd = max(0.0, self.shoot_cd - dt)
        if shoot and self.shoot_cd <= 0.0:
            self._fire_player()
            self.shoot_cd = 0.18

        # Stars: parallax left; faster when moving right
        par = max(0.0, move_dx) * 60.0
        for s in self.stars:
            s.x -= (35.0 * s.layer + par * s.layer) * dt
            if s.x < -2:
                s.x = self.w + random.uniform(0, 60)
                s.y = random.uniform(0, self.h)

        # Bullets
        for b in self.bullets:
            b.update(dt)
        for b in self.ebullets:
            b.update(dt)
        self.bullets = [b for b in self.bullets if -40 <= b.x <= self.w + 80 and -40 <= b.y <= self.h + 40]
        self.ebullets = [b for b in self.ebullets if -80 <= b.x <= self.w + 40 and -40 <= b.y <= self.h + 40]

        # Enemies spawn/update
        self.spawn_t -= dt
        if self.spawn_t <= 0.0:
            self._spawn_enemy()
            self.spawn_t = random.uniform(0.6, 1.2)

        for e in self.enemies:
            e.t += dt
            if e.kind == "asteroid":
                e.x += e.vx * dt
            elif e.kind == "blob":
                e.x += e.vx * dt
                if random.random() < 0.1:
                    e.vy += random.uniform(-60, 60)
                e.vy *= (1.0 - 0.4 * dt)
                e.y += e.vy * dt
                e.y = max(20, min(self.h - 20, e.y))
            elif e.kind == "red":
                e.x += e.vx * dt
                e.data["shoot_cd"] = max(0.0, e.data.get("shoot_cd", 0.0) - dt)
                if e.data["shoot_cd"] <= 0.0:
                    dx = self.px - e.x
                    dy = self.py - e.y
                    L = math.hypot(dx, dy) or 1.0
                    sp = 280.0
                    self.ebullets.append(Laser(e.x - 16, e.y, sp * dx / L, sp * dy / L, RED, False))
                    e.data["shoot_cd"] = random.uniform(1.0, 1.8)
            elif e.kind == "snake":
                e.x += e.vx * dt
                segs: List[Tuple[float, float]] = e.data.get("segs", [])
                phase = e.data.get("phase", 0.0)
                phase += dt * 2.0
                e.data["phase"] = phase
                head_y = e.y + math.sin(phase + e.x * 0.02) * 40.0
                if segs:
                    segs[0] = (e.x, head_y)
                    for i in range(1, len(segs)):
                        px, py = segs[i - 1]
                        cx, cy = segs[i]
                        dx, dy = px - cx, py - cy
                        dist = math.hypot(dx, dy) or 1.0
                        step = min(100.0 * dt, dist)
                        segs[i] = (cx + dx / dist * step, cy + dy / dist * step)
                    e.y = head_y
                    e.data["segs"] = segs

        # Cull enemies
        self.enemies = [e for e in self.enemies if e.x > -80 and -80 < e.y < self.h + 80]

        # Collisions: player bullets vs enemies
        remaining_bullets: List[Laser] = []
        for b in self.bullets:
            hit = False
            for e in self.enemies:
                if e.kind == "asteroid":
                    r = e.data.get("r", 18)
                    dx, dy = b.x - e.x, b.y - e.y
                    if dx * dx + dy * dy <= (r + 4) ** 2:
                        e.hp -= 1.0
                        hit = True
                        break
                elif e.kind == "blob":
                    dx, dy = b.x - e.x, b.y - e.y
                    if dx * dx + dy * dy <= (18) ** 2:
                        e.hp -= 1.0
                        hit = True
                        break
                elif e.kind == "red":
                    if b.rect().colliderect(e.rect()):
                        e.hp -= 1.0
                        hit = True
                        break
                elif e.kind == "snake":
                    dx, dy = b.x - e.x, b.y - e.y
                    if dx * dx + dy * dy <= (16) ** 2:
                        e.hp -= 1.0
                        hit = True
                        break
            if not hit:
                remaining_bullets.append(b)
        self.bullets = remaining_bullets

        # Resolve dead enemies -> shards
        alive: List[Enemy] = []
        for e in self.enemies:
            if e.hp <= 0:
                self._enemy_die(e)
            else:
                alive.append(e)
        self.enemies = alive

        # Enemy bullets vs player
        prect = pygame.Rect(int(self.px - 12), int(self.py - 10), 24, 20)
        keep_e: List[Laser] = []
        for b in self.ebullets:
            if b.rect().colliderect(prect):
                if self.shield_active:
                    # absorbed
                    continue
                else:
                    self.energy = max(0.0, self.energy - 12.0)
                    continue
            keep_e.append(b)
        self.ebullets = keep_e

        # Shards update & collect
        new_shards: List[Shard] = []
        for s in self.shards:
            s.update(dt)
            if s.ttl <= 0:
                continue
            if prect.colliderect(s.rect()):
                self.energy = min(self.energy_max, self.energy + s.value)
                continue
            new_shards.append(s)
        self.shards = new_shards

    def draw(self, screen: pygame.Surface, font: pygame.font.Font):
        # Stars
        for s in self.stars:
            col = (140, 140, 140) if s.layer > 1.0 else (90, 90, 90)
            screen.fill(col, (int(s.x), int(s.y), 2, 2))

        # Player ship (triangle pointing right)
        p = (int(self.px + 14), int(self.py))
        q = (int(self.px - 10), int(self.py - 8))
        r = (int(self.px - 10), int(self.py + 8))
        pygame.draw.polygon(screen, ACCENT, [p, q, r])
        pygame.draw.polygon(screen, (20, 20, 20), [p, q, r], 2)

        # Shield
        if self.shield_active:
            pygame.draw.circle(screen, (120, 200, 255), (int(self.px), int(self.py)), 24, 2)

        # Bullets
        for b in self.bullets:
            pygame.draw.rect(screen, b.color, b.rect())
        for b in self.ebullets:
            pygame.draw.rect(screen, b.color, b.rect())

        # Enemies
        for e in self.enemies:
            if e.kind == "asteroid":
                r = e.data.get("r", 18)
                pygame.draw.circle(screen, (120, 120, 120), (int(e.x), int(e.y)), r)
                pygame.draw.circle(screen, (60, 60, 60), (int(e.x), int(e.y)), r, 2)
            elif e.kind == "blob":
                pygame.draw.circle(screen, (60, 220, 120), (int(e.x), int(e.y)), 16)
                pygame.draw.circle(screen, (30, 120, 70), (int(e.x), int(e.y)), 16, 2)
            elif e.kind == "red":
                s = 24
                rect = pygame.Rect(int(e.x - s / 2), int(e.y - s / 2), s, s)
                pygame.draw.rect(screen, (220, 80, 80), rect)
                pygame.draw.rect(screen, (120, 30, 30), rect, 2)
            elif e.kind == "snake":
                segs = e.data.get("segs", [])
                for i, (sx, sy) in enumerate(segs):
                    rr = max(6, 14 - i)
                    pygame.draw.circle(screen, PURPLE, (int(sx), int(sy)), rr)
                if segs:
                    pygame.draw.circle(screen, (90, 40, 120), (int(segs[0][0]), int(segs[0][1])), 14, 2)

        # Shards
        for s in self.shards:
            rect = s.rect()
            pygame.draw.rect(screen, (160, 220, 200), rect)

        # HUD: energy bar and score
        # Energy
        bar_w = 180
        pct = self.energy / self.energy_max if self.energy_max else 0
        x, y = 10, self.h - 30
        pygame.draw.rect(screen, (40, 40, 40), (x, y, bar_w, 12))
        pygame.draw.rect(screen, (60, 120, 200), (x, y, int(bar_w * pct), 12))
        pygame.draw.rect(screen, (20, 20, 20), (x, y, bar_w, 12), 2)
        label = font.render("Energy", True, FG_COLOR)
        screen.blit(label, (x, y - 18))

        # Score
        sc = font.render(f"Score: {self.score}", True, FG_COLOR)
        screen.blit(sc, (self.w - sc.get_width() - 12, 12))
