#!/usr/bin/env python3
"""Carrom — a two player carrom board game written with Python + Tkinter.

Follows the device/OS colour scheme by default and ships with hand tuned
light and dark palettes (Appearance: Auto / Light / Dark).

Controls
    Click the baseline (or drag the striker, or use <- / ->)  place the striker
    Drag from the striker and release                         shoot (slingshot)
    N new game      T toggle appearance      Esc cancel aim
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

from physics import (BLACK, COIN, QUEEN, STRIKER, WHITE, Board, Disc,
                     all_at_rest, free_spot, step)
from theming import PALETTES, apply_ttk_theme, detect_system_theme

FRAME_MS = 16
SUBSTEPS = 4
MAX_SHOT_SPEED = 1750.0     # px/s at full power
MIN_SHOT_SPEED = 120.0
SIDE_NAMES = {WHITE: "White", BLACK: "Black"}
QUEEN_BONUS = 3
BOARD_MIN = 460


class CarromGame(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, style="App.TFrame", padding=14)
        self.master.title("Carrom")
        self.master.minsize(880, 660)

        self.style = ttk.Style(master)
        self.theme_mode = tk.StringVar(value="Auto")
        self.palette = PALETTES[detect_system_theme()]

        self.board = Board(560)
        self.discs: list[Disc] = []
        self.striker: Disc | None = None

        self.scores = [0, 0]
        self.player = 0                      # 0 -> WHITE, 1 -> BLACK
        self.sides = (WHITE, BLACK)
        self.queen_pending: int | None = None
        self.queen_owner: int | None = None
        self.state = "aim"                   # aim | sim | over
        self.status = "White to break."
        self.shot_potted: list[Disc] = []

        self.drag_from: tuple[float, float] | None = None
        self.placing = False
        self.hover: tuple[float, float] | None = None

        self._build_ui()
        self.apply_palette()
        self.new_game()
        self.after(FRAME_MS, self._tick)
        self.after(2000, self._poll_system_theme)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        self.pack(fill="both", expand=True)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, style="App.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="Carrom", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        self.status_label = ttk.Label(header, text=self.status, style="Status.TLabel")
        self.status_label.grid(row=0, column=1, sticky="w", padx=16)

        ttk.Label(header, text="Appearance", style="App.TLabel").grid(row=0, column=2, padx=(0, 6))
        self.theme_menu = ttk.OptionMenu(
            header, self.theme_mode, "Auto", "Auto", "Light", "Dark",
            command=lambda _=None: self.apply_palette(),
        )
        self.theme_menu.configure(style="App.TMenubutton", width=6)
        self.theme_menu.grid(row=0, column=3)
        ttk.Button(header, text="New game", style="App.TButton",
                   command=self.new_game).grid(row=0, column=4, padx=(10, 0))

        self.board_holder = ttk.Frame(self, style="App.TFrame")
        self.board_holder.grid(row=1, column=0, sticky="nsew")
        self.board_holder.columnconfigure(0, weight=1)
        self.board_holder.rowconfigure(0, weight=1)
        self.board_holder.bind("<Configure>", self._on_resize)

        self.canvas = tk.Canvas(self.board_holder, width=self.board.size,
                                height=self.board.size, highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Motion>", self._on_hover)

        self.panel = self._build_panel()
        self.panel.grid(row=1, column=1, sticky="ns", padx=(14, 0))

        root = self.master
        root.bind("<Left>", lambda e: self._nudge_striker(-12))
        root.bind("<Right>", lambda e: self._nudge_striker(12))
        root.bind("<Escape>", lambda e: self._cancel_aim())
        root.bind("n", lambda e: self.new_game())
        root.bind("N", lambda e: self.new_game())
        root.bind("t", lambda e: self._cycle_theme())
        root.bind("T", lambda e: self._cycle_theme())

    def _build_panel(self) -> ttk.Frame:
        panel = ttk.Frame(self, style="Panel.TFrame", padding=16, width=250)
        panel.grid_propagate(False)

        self.player_cards = []
        for idx, side in enumerate(self.sides):
            card = ttk.Frame(panel, style="Panel.TFrame")
            card.pack(fill="x", pady=(0, 14))
            name = ttk.Label(card, text=f"Player {idx + 1} · {SIDE_NAMES[side]}",
                             style="Panel.TLabel")
            name.pack(anchor="w")
            score = ttk.Label(card, text="0", style="Score.TLabel")
            score.pack(anchor="w")
            info = ttk.Label(card, text="0 / 9 coins", style="Muted.TLabel")
            info.pack(anchor="w")
            turn = ttk.Label(card, text="", style="Turn.TLabel")
            turn.pack(anchor="w")
            self.player_cards.append((score, info, turn))

        ttk.Separator(panel, orient="horizontal", style="App.TSeparator").pack(fill="x", pady=8)

        self.queen_label = ttk.Label(panel, text="Queen: on board", style="Panel.TLabel")
        self.queen_label.pack(anchor="w", pady=(6, 10))

        self.power_canvas = tk.Canvas(panel, height=14, highlightthickness=0, bd=0)
        self.power_canvas.pack(fill="x", pady=(0, 6))
        ttk.Label(panel, text="Shot power", style="Muted.TLabel").pack(anchor="w")

        ttk.Separator(panel, orient="horizontal", style="App.TSeparator").pack(fill="x", pady=12)

        help_text = (
            "• Drag from the striker and release to shoot.\n"
            "• Click the baseline or use ← → to reposition.\n"
            "• Pot your colour to score and shoot again.\n"
            "• Pot the queen, then cover it with one of your\n"
            "   coins for +3 — otherwise it returns.\n"
            "• Potting the striker costs a point and returns\n"
            "   one of your coins to the board."
        )
        ttk.Label(panel, text=help_text, style="Muted.TLabel", justify="left").pack(anchor="w")
        return panel

    # ------------------------------------------------------------- theming

    def resolved_theme(self) -> str:
        mode = self.theme_mode.get()
        if mode == "Light":
            return "light"
        if mode == "Dark":
            return "dark"
        return detect_system_theme()

    def apply_palette(self) -> None:
        self.palette = PALETTES[self.resolved_theme()]
        apply_ttk_theme(self.master, self.style, self.palette)
        self.canvas.configure(background=self.palette.app_bg)
        self.power_canvas.configure(background=self.palette.panel_bg)
        self._draw_static()
        self._refresh_panel()

    def _cycle_theme(self) -> None:
        order = ["Auto", "Light", "Dark"]
        self.theme_mode.set(order[(order.index(self.theme_mode.get()) + 1) % 3])
        self.apply_palette()

    def _poll_system_theme(self) -> None:
        if self.theme_mode.get() == "Auto":
            wanted = PALETTES[detect_system_theme()]
            if wanted.name != self.palette.name:
                self.apply_palette()
        self.after(2000, self._poll_system_theme)

    # ---------------------------------------------------------- game setup

    def new_game(self) -> None:
        self.scores = [0, 0]
        self.player = 0
        self.queen_pending = None
        self.queen_owner = None
        self.state = "aim"
        self.shot_potted = []
        self.drag_from = None
        self._layout_pieces()
        self.status = "Player 1 (White) to break."
        self._refresh_panel()

    def _layout_pieces(self) -> None:
        b = self.board
        cx, cy = b.centre
        r = b.coin_r
        self.discs = [Disc(cx, cy, r, QUEEN, mass=1.0)]

        for i in range(6):
            ang = math.pi / 2 + i * math.pi / 3
            self.discs.append(Disc(cx + math.cos(ang) * 2 * r, cy + math.sin(ang) * 2 * r,
                                   r, COIN, WHITE if i % 2 == 0 else BLACK))
        for i in range(12):
            ang = math.pi / 2 + i * math.pi / 6
            self.discs.append(Disc(cx + math.cos(ang) * 4 * r, cy + math.sin(ang) * 4 * r,
                                   r, COIN, WHITE if i % 2 == 0 else BLACK))

        self.striker = Disc(cx, b.baseline_y(bottom=True), b.striker_r, STRIKER, mass=1.55)
        self.discs.append(self.striker)
        self._park_striker()

    def _park_striker(self) -> None:
        """Place the striker on the current shooter's baseline."""
        s = self.striker
        assert s is not None
        s.potted = False
        s.pocket_anim = 0.0
        s.stop()
        lo, hi = self.board.baseline_x_range()
        s.x = min(max(s.x, lo), hi)
        s.y = self.board.baseline_y(bottom=self.player == 0)
        self._unstick_striker()

    def _unstick_striker(self) -> None:
        s = self.striker
        assert s is not None
        lo, hi = self.board.baseline_x_range()
        for offset in range(0, int(hi - lo) + 1, 4):
            for x in {min(hi, s.x + offset), max(lo, s.x - offset)}:
                if not any(d is not s and not d.potted
                           and math.hypot(x - d.x, s.y - d.y) < s.r + d.r + 0.5
                           for d in self.discs):
                    s.x = x
                    return

    def _own_side(self, player: int) -> str:
        return self.sides[player]

    def _potted_count(self, player: int) -> int:
        side = self._own_side(player)
        return sum(1 for d in self.discs if d.kind == COIN and d.side == side and d.potted)

    # ------------------------------------------------------------- input

    def _on_resize(self, event) -> None:
        size = max(BOARD_MIN, min(event.width, event.height))
        if abs(size - self.board.size) < 2:
            return
        self.canvas.configure(width=size, height=size)
        old = self.board
        scale = size / old.size
        self.board = Board(size)
        for d in self.discs:
            d.x = (d.x - old.size / 2) * scale + size / 2
            d.y = (d.y - old.size / 2) * scale + size / 2
            d.r = self.board.striker_r if d.kind == STRIKER else self.board.coin_r
        if self.state == "aim":
            self._park_striker()
        self._draw_static()

    def _on_hover(self, event) -> None:
        self.hover = (event.x, event.y)

    def _on_press(self, event) -> None:
        if self.state != "aim" or self.striker is None:
            return
        s = self.striker
        if math.hypot(event.x - s.x, event.y - s.y) <= s.r * 1.6:
            self.drag_from = (event.x, event.y)
            self.placing = False
            return
        if abs(event.y - s.y) <= s.r * 2.4:
            self.placing = True
            self._move_striker_to(event.x)

    def _on_drag(self, event) -> None:
        if self.state != "aim":
            return
        self.hover = (event.x, event.y)
        if self.placing:
            self._move_striker_to(event.x)
        elif self.drag_from is not None:
            self.drag_from = (event.x, event.y)

    def _on_release(self, event) -> None:
        if self.state != "aim":
            return
        if self.placing:
            self.placing = False
            return
        if self.drag_from is None or self.striker is None:
            return
        s = self.striker
        dx = s.x - event.x
        dy = s.y - event.y
        pull = math.hypot(dx, dy)
        self.drag_from = None
        if pull < s.r * 0.6:
            return
        power = min(pull / self._max_pull(), 1.0)
        speed = MIN_SHOT_SPEED + power * (MAX_SHOT_SPEED - MIN_SHOT_SPEED)
        s.vx = dx / pull * speed
        s.vy = dy / pull * speed
        self.shot_potted = []
        self.state = "sim"
        self.status = "…"
        self._refresh_panel()

    def _max_pull(self) -> float:
        return self.board.play * 0.42

    def _move_striker_to(self, x: float) -> None:
        lo, hi = self.board.baseline_x_range()
        self.striker.x = min(max(x, lo), hi)
        self._unstick_striker()

    def _nudge_striker(self, dx: float) -> None:
        if self.state == "aim" and self.striker is not None:
            self._move_striker_to(self.striker.x + dx)

    def _cancel_aim(self) -> None:
        self.drag_from = None
        self.placing = False

    # -------------------------------------------------------------- loop

    def _tick(self) -> None:
        if self.state == "sim":
            dt = (FRAME_MS / 1000.0) / SUBSTEPS
            for _ in range(SUBSTEPS):
                self.shot_potted.extend(step(self.discs, self.board, dt))
            if all_at_rest(self.discs):
                self._end_shot()

        for d in self.discs:
            if d.pocket_anim > 0:
                d.pocket_anim = max(0.0, d.pocket_anim - 0.08)

        self._draw_dynamic()
        self.after(FRAME_MS, self._tick)

    # ------------------------------------------------------------- rules

    def _end_shot(self) -> None:
        player = self.player
        side = self._own_side(player)
        opponent = 1 - player

        striker_potted = any(d.kind == STRIKER for d in self.shot_potted)
        own = [d for d in self.shot_potted if d.kind == COIN and d.side == side]
        opp = [d for d in self.shot_potted if d.kind == COIN and d.side != side]
        queen = next((d for d in self.shot_potted if d.kind == QUEEN), None)

        messages: list[str] = []
        keep_turn = False

        if striker_potted:
            self.scores[player] = max(0, self.scores[player] - 1)
            messages.append("Striker potted — 1 point penalty.")
            returned = self._return_own_coin(player)
            if returned:
                messages.append("A coin returns to the board.")
            if self.queen_pending == player:
                self._return_queen()
                self.queen_pending = None
                messages.append("Queen returns to the centre.")
        else:
            if own:
                self.scores[player] += len(own)
                messages.append(f"Potted {len(own)} {SIDE_NAMES[side].lower()} "
                                f"coin{'s' if len(own) > 1 else ''}.")
                keep_turn = True
            if opp:
                self.scores[opponent] += len(opp)
                messages.append(f"{len(opp)} {SIDE_NAMES[self._own_side(opponent)].lower()} "
                                f"coin{'s' if len(opp) > 1 else ''} went to Player {opponent + 1}.")

            if queen is not None:
                if own:
                    self._claim_queen(player)
                    messages.append(f"Queen covered! +{QUEEN_BONUS}.")
                else:
                    self.queen_pending = player
                    messages.append("Queen potted — cover it with your next coin.")
                keep_turn = True
            elif self.queen_pending == player:
                if own:
                    self._claim_queen(player)
                    messages.append(f"Queen covered! +{QUEEN_BONUS}.")
                else:
                    self._return_queen()
                    self.queen_pending = None
                    messages.append("Queen uncovered — back to the centre.")

        self.shot_potted = []

        winner = self._check_winner()
        if winner is not None:
            self.state = "over"
            self.status = (f"Player {winner + 1} ({SIDE_NAMES[self._own_side(winner)]}) wins "
                           f"{self.scores[winner]}–{self.scores[1 - winner]}! Press N for a new game.")
            self._refresh_panel()
            return

        if not keep_turn or striker_potted:
            self.player = opponent
        self.state = "aim"
        self._park_striker()

        turn_text = (f"Player {self.player + 1} "
                     f"({SIDE_NAMES[self._own_side(self.player)]}) to play.")
        self.status = " ".join(messages + [turn_text]) if messages else turn_text
        self._refresh_panel()

    def _claim_queen(self, player: int) -> None:
        if self.queen_owner is None:
            self.queen_owner = player
            self.scores[player] += QUEEN_BONUS
        self.queen_pending = None

    def _return_queen(self) -> None:
        queen = next(d for d in self.discs if d.kind == QUEEN)
        queen.potted = False
        queen.pocket_anim = 0.0
        queen.stop()
        queen.x, queen.y = free_spot(self.discs, self.board, queen.r, *self.board.centre)

    def _return_own_coin(self, player: int) -> bool:
        side = self._own_side(player)
        coin = next((d for d in self.discs if d.kind == COIN and d.side == side and d.potted), None)
        if coin is None:
            return False
        coin.potted = False
        coin.pocket_anim = 0.0
        coin.stop()
        coin.x, coin.y = free_spot(self.discs, self.board, coin.r, *self.board.centre)
        return True

    def _check_winner(self) -> int | None:
        for player in (0, 1):
            if self._potted_count(player) == 9 and self.queen_pending != player:
                return player
        return None

    # ------------------------------------------------------------ drawing

    def _draw_static(self) -> None:
        c, p, b = self.canvas, self.palette, self.board
        c.delete("static")
        size = b.size
        c.create_rectangle(0, 0, size, size, fill=p.frame_outer, outline="", tags="static")
        c.create_rectangle(6, 6, size - 6, size - 6, fill=p.frame_inner, outline="", tags="static")
        c.create_rectangle(b.left - 4, b.top - 4, b.right + 4, b.bottom + 4,
                           fill=p.board_shade, outline="", tags="static")
        c.create_rectangle(b.left, b.top, b.right, b.bottom,
                           fill=p.board, outline=p.board_line, width=1, tags="static")

        # Decorative border frame inside the playing surface.
        pad = b.play * 0.055
        c.create_rectangle(b.left + pad, b.top + pad, b.right - pad, b.bottom - pad,
                           outline=p.board_line, width=1, tags="static")

        # Base lines with their end circles.
        for bottom in (True, False):
            y = b.baseline_y(bottom)
            lo, hi = b.baseline_x_range()
            c.create_line(lo, y, hi, y, fill=p.board_line, width=3, tags="static")
            c.create_line(lo, y - 6, hi, y - 6, fill=p.board_line, width=1, tags="static")
            c.create_line(lo, y + 6, hi, y + 6, fill=p.board_line, width=1, tags="static")
            for x in (lo, hi):
                rr = b.play * 0.022
                c.create_oval(x - rr, y - rr, x + rr, y + rr,
                              outline=p.board_line, width=2, tags="static")
        for bottom in (True, False):
            x_line = b.left + b.base_inset if bottom else b.right - b.base_inset
            lo, hi = b.baseline_x_range()
            c.create_line(x_line, lo, x_line, hi, fill=p.board_line, width=3, tags="static")
            c.create_line(x_line - 6, lo, x_line - 6, hi, fill=p.board_line, width=1, tags="static")
            c.create_line(x_line + 6, lo, x_line + 6, hi, fill=p.board_line, width=1, tags="static")

        cx, cy = b.centre
        c.create_oval(cx - b.centre_r, cy - b.centre_r, cx + b.centre_r, cy + b.centre_r,
                      outline=p.board_line, width=2, tags="static")
        inner = b.centre_r * 0.33
        c.create_oval(cx - inner, cy - inner, cx + inner, cy + inner,
                      outline=p.board_line, width=1, tags="static")

        # Corner arrows pointing at the pockets.
        d = b.play * 0.12
        for sx, sy, ox, oy in ((1, 1, b.left, b.top), (-1, 1, b.right, b.top),
                               (1, -1, b.left, b.bottom), (-1, -1, b.right, b.bottom)):
            x0 = ox + sx * (b.pocket_r * 1.9)
            y0 = oy + sy * (b.pocket_r * 1.9)
            c.create_line(x0, y0, x0 + sx * d, y0 + sy * d,
                          fill=p.board_line, width=2, tags="static")

        for px, py in b.pockets:
            r = b.pocket_r
            c.create_oval(px - r - 3, py - r - 3, px + r + 3, py + r + 3,
                          fill=p.pocket_rim, outline="", tags="static")
            c.create_oval(px - r, py - r, px + r, py + r,
                          fill=p.pocket, outline="", tags="static")

    def _disc_colors(self, d: Disc) -> tuple[str, str]:
        p = self.palette
        if d.kind == STRIKER:
            return p.striker, p.striker_edge
        if d.kind == QUEEN:
            return p.queen, p.queen_edge
        if d.side == WHITE:
            return p.coin_light, p.coin_light_edge
        return p.coin_dark, p.coin_dark_edge

    def _draw_dynamic(self) -> None:
        c, p = self.canvas, self.palette
        c.delete("dyn")

        for d in self.discs:
            if d.potted and d.pocket_anim <= 0:
                continue
            scale = d.pocket_anim if d.potted else 1.0
            r = d.r * scale
            if r < 1:
                continue
            fill, edge = self._disc_colors(d)
            c.create_oval(d.x - r + 2, d.y - r + 3, d.x + r + 2, d.y + r + 3,
                          fill=p.board_shade, outline="", tags="dyn")
            c.create_oval(d.x - r, d.y - r, d.x + r, d.y + r,
                          fill=fill, outline=edge, width=2, tags="dyn")
            ring = r * 0.55
            c.create_oval(d.x - ring, d.y - ring, d.x + ring, d.y + ring,
                          outline=edge, width=1, tags="dyn")
            gloss = r * 0.34
            c.create_oval(d.x - gloss - r * 0.25, d.y - gloss - r * 0.3,
                          d.x + gloss - r * 0.25, d.y + gloss - r * 0.3,
                          fill=self._lighten(fill), outline="", tags="dyn")

        if self.state == "aim":
            self._draw_aim()

        if self.state == "over":
            b = self.board
            c.create_rectangle(b.left, b.centre[1] - 42, b.right, b.centre[1] + 42,
                               fill=p.panel_bg, outline=p.accent, width=2, tags="dyn")
            c.create_text(b.centre[0], b.centre[1], text=self.status.split("!")[0] + "!",
                          fill=p.text, font=("Helvetica", 16, "bold"), tags="dyn")

        self._draw_power()

    def _draw_aim(self) -> None:
        c, p = self.canvas, self.palette
        s = self.striker
        if s is None:
            return
        halo = s.r * 1.45
        c.create_oval(s.x - halo, s.y - halo, s.x + halo, s.y + halo,
                      outline=p.accent, width=2, dash=(4, 4), tags="dyn")

        target = self.drag_from or self.hover
        if target is None:
            return
        dx, dy = s.x - target[0], s.y - target[1]
        dist = math.hypot(dx, dy)
        if dist < 1:
            return
        ux, uy = dx / dist, dy / dist
        length = min(self.board.play * 0.55, self._ray_to_cushion(s, ux, uy))
        if length < s.r:
            return
        c.create_line(s.x, s.y, s.x + ux * length, s.y + uy * length,
                      fill=p.aim_line, width=2, dash=(7, 6), tags="dyn")
        c.create_line(s.x + ux * length, s.y + uy * length,
                      s.x + ux * (length - 12) - uy * 7, s.y + uy * (length - 12) + ux * 7,
                      fill=p.aim_line, width=2, tags="dyn")
        c.create_line(s.x + ux * length, s.y + uy * length,
                      s.x + ux * (length - 12) + uy * 7, s.y + uy * (length - 12) - ux * 7,
                      fill=p.aim_line, width=2, tags="dyn")

        if self.drag_from is not None:
            c.create_line(s.x, s.y, target[0], target[1],
                          fill=p.power_high, width=2, tags="dyn")

    def _ray_to_cushion(self, s: Disc, ux: float, uy: float) -> float:
        """Distance from the striker to the cushion along the aiming direction."""
        b = self.board
        best = float("inf")
        if ux > 1e-6:
            best = min(best, (b.right - s.r - s.x) / ux)
        elif ux < -1e-6:
            best = min(best, (b.left + s.r - s.x) / ux)
        if uy > 1e-6:
            best = min(best, (b.bottom - s.r - s.y) / uy)
        elif uy < -1e-6:
            best = min(best, (b.top + s.r - s.y) / uy)
        return max(best, 0.0)

    def _draw_power(self) -> None:
        pc, p = self.power_canvas, self.palette
        pc.delete("all")
        w = max(pc.winfo_width(), 1)
        h = pc.winfo_height()
        pc.create_rectangle(0, 3, w, h - 3, fill=p.button_bg, outline="")
        power = 0.0
        if self.state == "aim" and self.drag_from is not None and self.striker is not None:
            pull = math.hypot(self.striker.x - self.drag_from[0],
                              self.striker.y - self.drag_from[1])
            power = min(pull / self._max_pull(), 1.0)
        if power > 0:
            color = p.power_high if power > 0.66 else p.power_low
            pc.create_rectangle(0, 3, w * power, h - 3, fill=color, outline="")

    @staticmethod
    def _lighten(hex_color: str, amount: float = 0.22) -> str:
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        r = int(r + (255 - r) * amount)
        g = int(g + (255 - g) * amount)
        b = int(b + (255 - b) * amount)
        return f"#{r:02x}{g:02x}{b:02x}"

    # ------------------------------------------------------------- panel

    def _refresh_panel(self) -> None:
        self.status_label.configure(text=self.status)
        for idx, (score, info, turn) in enumerate(self.player_cards):
            score.configure(text=str(self.scores[idx]))
            info.configure(text=f"{self._potted_count(idx)} / 9 coins")
            active = idx == self.player and self.state != "over"
            turn.configure(text="● your turn" if active else " ")

        queen = next((d for d in self.discs if d.kind == QUEEN), None)
        if self.queen_owner is not None:
            text = f"Queen: Player {self.queen_owner + 1} (+{QUEEN_BONUS})"
        elif self.queen_pending is not None:
            text = f"Queen: pending cover by P{self.queen_pending + 1}"
        elif queen is not None and queen.potted:
            text = "Queen: off board"
        else:
            text = "Queen: on board"
        self.queen_label.configure(text=text)


def main() -> None:
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.25)
    except tk.TclError:
        pass
    CarromGame(root)
    root.geometry("980x720")
    root.mainloop()


if __name__ == "__main__":
    main()
