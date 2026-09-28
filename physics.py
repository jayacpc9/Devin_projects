"""Simple 2D disc physics for the carrom board: friction, walls, pockets, collisions."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

COIN = "coin"
QUEEN = "queen"
STRIKER = "striker"

WHITE = "white"
BLACK = "black"

LINEAR_DAMPING = 1.9      # per second, exponential velocity decay (cloth friction)
WALL_RESTITUTION = 0.74
DISC_RESTITUTION = 0.95
SLEEP_SPEED = 4.0         # px/s below which a disc is considered at rest


@dataclass
class Disc:
    x: float
    y: float
    r: float
    kind: str                 # COIN | QUEEN | STRIKER
    side: str = ""            # WHITE | BLACK for coins, "" otherwise
    mass: float = 1.0
    vx: float = 0.0
    vy: float = 0.0
    potted: bool = False
    pocket_anim: float = 0.0  # 1 -> 0 shrink animation when potted
    _id: int = field(default=0)

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    def stop(self) -> None:
        self.vx = self.vy = 0.0


class Board:
    """Geometry of the playing surface."""

    def __init__(self, size: int):
        self.size = size
        self.margin = round(size * 0.085)          # wooden frame width
        self.left = self.margin
        self.top = self.margin
        self.right = size - self.margin
        self.bottom = size - self.margin
        self.play = self.right - self.left

        self.coin_r = self.play * 0.0248
        self.striker_r = self.play * 0.0315
        self.pocket_r = self.play * 0.0405
        inset = self.pocket_r * 0.82
        self.pockets = [
            (self.left + inset, self.top + inset),
            (self.right - inset, self.top + inset),
            (self.left + inset, self.bottom - inset),
            (self.right - inset, self.bottom - inset),
        ]
        self.base_inset = self.play * 0.135         # distance of baseline from the edge
        self.base_pad = self.play * 0.175           # how far the baseline stops from corners
        self.centre = (size / 2.0, size / 2.0)
        self.centre_r = self.play * 0.128

    def baseline_y(self, bottom: bool) -> float:
        return self.bottom - self.base_inset if bottom else self.top + self.base_inset

    def baseline_x_range(self) -> tuple[float, float]:
        return self.left + self.base_pad, self.right - self.base_pad


def resolve_pair(a: Disc, b: Disc) -> bool:
    """Elastic collision between two discs. Returns True if they were touching."""
    dx = b.x - a.x
    dy = b.y - a.y
    dist_sq = dx * dx + dy * dy
    min_dist = a.r + b.r
    if dist_sq >= min_dist * min_dist or dist_sq == 0.0:
        return False

    dist = math.sqrt(dist_sq)
    nx, ny = dx / dist, dy / dist

    # Positional correction so discs never sink into each other.
    overlap = min_dist - dist
    total = a.mass + b.mass
    a.x -= nx * overlap * (b.mass / total)
    a.y -= ny * overlap * (b.mass / total)
    b.x += nx * overlap * (a.mass / total)
    b.y += ny * overlap * (a.mass / total)

    rvx = b.vx - a.vx
    rvy = b.vy - a.vy
    vel_along_normal = rvx * nx + rvy * ny
    if vel_along_normal > 0:
        return True

    j = -(1.0 + DISC_RESTITUTION) * vel_along_normal / (1.0 / a.mass + 1.0 / b.mass)
    ix, iy = j * nx, j * ny
    a.vx -= ix / a.mass
    a.vy -= iy / a.mass
    b.vx += ix / b.mass
    b.vy += iy / b.mass
    return True


def step(discs: list[Disc], board: Board, dt: float) -> list[Disc]:
    """Advance the simulation by dt seconds. Returns discs potted during this step."""
    decay = math.exp(-LINEAR_DAMPING * dt)
    potted: list[Disc] = []

    for d in discs:
        if d.potted:
            continue
        d.x += d.vx * dt
        d.y += d.vy * dt
        d.vx *= decay
        d.vy *= decay
        if d.speed < SLEEP_SPEED:
            d.stop()

        if d.x - d.r < board.left:
            d.x = board.left + d.r
            d.vx = -d.vx * WALL_RESTITUTION
        elif d.x + d.r > board.right:
            d.x = board.right - d.r
            d.vx = -d.vx * WALL_RESTITUTION
        if d.y - d.r < board.top:
            d.y = board.top + d.r
            d.vy = -d.vy * WALL_RESTITUTION
        elif d.y + d.r > board.bottom:
            d.y = board.bottom - d.r
            d.vy = -d.vy * WALL_RESTITUTION

    live = [d for d in discs if not d.potted]
    for i in range(len(live)):
        for j in range(i + 1, len(live)):
            resolve_pair(live[i], live[j])

    for d in live:
        for px, py in board.pockets:
            if math.hypot(d.x - px, d.y - py) < board.pocket_r - d.r * 0.25:
                d.potted = True
                d.pocket_anim = 1.0
                d.stop()
                d.x, d.y = px, py
                potted.append(d)
                break

    return potted


def all_at_rest(discs: list[Disc]) -> bool:
    return all(d.potted or d.speed == 0.0 for d in discs)


def free_spot(discs: list[Disc], board: Board, radius: float,
              cx: float, cy: float) -> tuple[float, float]:
    """Find an empty position near (cx, cy) to place a returned coin."""
    for ring in range(0, 14):
        step_r = ring * radius * 1.1
        points = 1 if ring == 0 else ring * 8
        for k in range(points):
            ang = 2 * math.pi * k / points
            x = cx + math.cos(ang) * step_r
            y = cy + math.sin(ang) * step_r
            if not (board.left + radius <= x <= board.right - radius):
                continue
            if not (board.top + radius <= y <= board.bottom - radius):
                continue
            if any(math.hypot(x - px, y - py) < board.pocket_r + radius
                   for px, py in board.pockets):
                continue
            if any(not d.potted and math.hypot(x - d.x, y - d.y) < radius + d.r + 1.0
                   for d in discs):
                continue
            return x, y
    return cx, cy
