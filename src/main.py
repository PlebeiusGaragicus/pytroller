import sys
import time
import math
from collections import deque
from typing import Dict, Set, Tuple

import pygame
from .game import Game


WIDTH, HEIGHT = 800, 600
BG_COLOR = (10, 10, 10)
FG_COLOR = (220, 220, 220)
ACCENT = (100, 180, 255)
ERROR = (255, 120, 120)
LOG_MAX = 300
LINE_SPACING = 2
TITLE = "Pytroller: USB Arcade Controller Debug"


# Button and axis mapping based on BUTTONS.md capture
# Buttons
#  - Start: 9
#  - Menu (quit): 8
#  - Left trigger: 4
#  - Right trigger: 5
#  - Face buttons: Right (blue)=0, Left (green)=1, Up (yellow)=2, Down (red)=3
BUTTON_MAP = {
    "start": 9,
    "menu": 8,
    "trigger_left": 4,
    "trigger_right": 5,
    "action_right": 0,
    "action_left": 1,
    "action_up": 2,
    "action_down": 3,
}

# Axes mapping observed from logs:
#  - Axis 0: Left is +1.0, Right is -1.0
#  - Axis 1: Up is +1.0, Down is -1.0
AXIS_X = 0
AXIS_Y = 1
AXIS_LEFT_POSITIVE = True
AXIS_UP_POSITIVE = True
AXIS_THRESH = 0.50

# Face button colors
BLUE = (70, 140, 255)
GREEN = (80, 200, 120)
YELLOW = (240, 210, 70)
RED = (240, 90, 90)
DIM = (60, 60, 60)


class JoystickManager:
    def __init__(self, log_fn):
        self.joysticks: Dict[int, pygame.joystick.Joystick] = {}
        self.log = log_fn

    def rescan(self):
        """Rescan currently connected joysticks without restarting the SDL subsystem."""
        seen: Set[int] = set()
        try:
            count = pygame.joystick.get_count()
        except Exception as e:
            self.log(f"[ERR] joystick get_count failed: {e}")
            count = 0
        for i in range(count):
            try:
                joy = pygame.joystick.Joystick(i)
                if not joy.get_init():
                    joy.init()
                iid = joy.get_instance_id()
                seen.add(iid)
                if iid not in self.joysticks:
                    self.joysticks[iid] = joy
                    self.log(f"[ADD] idx={i} iid={iid} name='{joy.get_name()}' axes={joy.get_numaxes()} hats={joy.get_numhats()} buttons={joy.get_numbuttons()}")
            except Exception as e:
                self.log(f"[ERR] Failed to init joystick index {i}: {e}")
        # Remove stale devices
        for iid in list(self.joysticks.keys()):
            if iid not in seen:
                self.remove_device(iid)
        if not self.joysticks:
            self.log("[INFO] No joysticks found. Plug one in and press R to rescan.")

    def add_device(self, device_index: int):
        try:
            joy = pygame.joystick.Joystick(device_index)
            joy.init()
            iid = joy.get_instance_id()
            self.joysticks[iid] = joy
            self.log(f"[ADD] idx={device_index} iid={iid} name='{joy.get_name()}' axes={joy.get_numaxes()} hats={joy.get_numhats()} buttons={joy.get_numbuttons()}")
        except Exception as e:
            self.log(f"[ERR] add_device failed: {e}")

    def remove_device(self, instance_id: int):
        joy = self.joysticks.pop(instance_id, None)
        if joy is not None:
            name = joy.get_name()
            try:
                joy.quit()
            except Exception:
                pass
            self.log(f"[REM] iid={instance_id} name='{name}'")
        else:
            self.log(f"[WARN] remove_device: unknown iid={instance_id}")

    def summary_lines(self):
        lines = [f"Joysticks: {len(self.joysticks)} connected"]
        for iid, joy in sorted(self.joysticks.items()):
            lines.append(f"- iid={iid} name='{joy.get_name()}' axes={joy.get_numaxes()} hats={joy.get_numhats()} buttons={joy.get_numbuttons()}")
        return lines


class VisualUI:
    def __init__(self):
        # Stick area (left)
        self.stick_cx = 200
        self.stick_cy = HEIGHT // 2
        self.stick_outer = 80
        self.stick_inner = 36

        # Action cluster (right)
        self.base_x = WIDTH - 200
        self.base_y = HEIGHT // 2
        self.offset = 50
        self.radius = 22

        # Triggers and sys buttons
        self.trig_w, self.trig_h = 70, 18
        self.trig_y = self.base_y - 110
        self.start_x = self.base_x - 40
        self.menu_x = self.base_x + 10
        self.sys_y = self.base_y + 110

    def _axis_dirs(self, axes: Dict[int, float]) -> Tuple[bool, bool, bool, bool]:
        x = float(axes.get(AXIS_X, 0.0))
        y = float(axes.get(AXIS_Y, 0.0))

        left = x >= AXIS_THRESH if AXIS_LEFT_POSITIVE else x <= -AXIS_THRESH
        right = x <= -AXIS_THRESH if AXIS_LEFT_POSITIVE else x >= AXIS_THRESH
        up = y >= AXIS_THRESH if AXIS_UP_POSITIVE else y <= -AXIS_THRESH
        down = y <= -AXIS_THRESH if AXIS_UP_POSITIVE else y >= AXIS_THRESH
        return left, right, up, down

    def _draw_stick(self, screen: pygame.Surface, left: bool, right: bool, up: bool, down: bool):
        # Background circle
        pygame.draw.circle(screen, (30, 30, 30), (self.stick_cx, self.stick_cy), self.stick_outer, 0)
        pygame.draw.circle(screen, (70, 70, 70), (self.stick_cx, self.stick_cy), self.stick_outer, 2)

        # Direction triangles
        def tri(points, active):
            col = ACCENT if active else (80, 80, 80)
            pygame.draw.polygon(screen, col, points)
            pygame.draw.polygon(screen, (20, 20, 20), points, 2)

        size_long = 44
        size_short = 26
        # Up
        tri([(self.stick_cx, self.stick_cy - self.stick_outer + 8),
             (self.stick_cx - size_short, self.stick_cy - size_short),
             (self.stick_cx + size_short, self.stick_cy - size_short)], up)
        # Down
        tri([(self.stick_cx, self.stick_cy + self.stick_outer - 8),
             (self.stick_cx - size_short, self.stick_cy + size_short),
             (self.stick_cx + size_short, self.stick_cy + size_short)], down)
        # Left
        tri([(self.stick_cx - self.stick_outer + 8, self.stick_cy),
             (self.stick_cx - size_short, self.stick_cy - size_short),
             (self.stick_cx - size_short, self.stick_cy + size_short)], left)
        # Right
        tri([(self.stick_cx + self.stick_outer - 8, self.stick_cy),
             (self.stick_cx + size_short, self.stick_cy - size_short),
             (self.stick_cx + size_short, self.stick_cy + size_short)], right)

        # Center
        pygame.draw.circle(screen, (120, 120, 120), (self.stick_cx, self.stick_cy), self.stick_inner, 0)
        pygame.draw.circle(screen, (20, 20, 20), (self.stick_cx, self.stick_cy), self.stick_inner, 2)

    def _draw_face_buttons(self, screen: pygame.Surface, pressed: Set[int], font: pygame.font.Font):
        x, y, d, r = self.base_x, self.base_y, self.offset, self.radius

        def draw_btn(cx, cy, color, idx, label):
            active = idx in pressed
            fill = color if active else (40, 40, 40)
            pygame.draw.circle(screen, fill, (cx, cy), r)
            pygame.draw.circle(screen, color, (cx, cy), r, 3)
            lab = font.render(label, True, FG_COLOR)
            screen.blit(lab, (cx - lab.get_width() // 2, cy - lab.get_height() // 2))

        # Diamond layout: Right, Left, Up, Down
        draw_btn(x + d, y, BLUE, BUTTON_MAP["action_right"], "R")
        draw_btn(x - d, y, GREEN, BUTTON_MAP["action_left"], "L")
        draw_btn(x, y - d, YELLOW, BUTTON_MAP["action_up"], "U")
        draw_btn(x, y + d, RED, BUTTON_MAP["action_down"], "D")

    def _draw_triggers_and_sys(self, screen: pygame.Surface, pressed: Set[int], font: pygame.font.Font):
        # Triggers
        lt_idx = BUTTON_MAP["trigger_left"]
        rt_idx = BUTTON_MAP["trigger_right"]
        lt_rect = pygame.Rect(self.base_x - 120, self.trig_y, self.trig_w, self.trig_h)
        rt_rect = pygame.Rect(self.base_x + 50, self.trig_y, self.trig_w, self.trig_h)
        pygame.draw.rect(screen, (40, 40, 40), lt_rect)
        pygame.draw.rect(screen, (40, 40, 40), rt_rect)
        pygame.draw.rect(screen, GREEN if lt_idx in pressed else (80, 80, 80), lt_rect, 3)
        pygame.draw.rect(screen, BLUE if rt_idx in pressed else (80, 80, 80), rt_rect, 3)
        lt_lab = font.render("LT", True, FG_COLOR)
        rt_lab = font.render("RT", True, FG_COLOR)
        screen.blit(lt_lab, (lt_rect.centerx - lt_lab.get_width() // 2, lt_rect.centery - lt_lab.get_height() // 2))
        screen.blit(rt_lab, (rt_rect.centerx - rt_lab.get_width() // 2, rt_rect.centery - rt_lab.get_height() // 2))

        # Start/Menu
        start_idx = BUTTON_MAP["start"]
        menu_idx = BUTTON_MAP["menu"]
        sx = self.start_x
        mx = self.menu_x
        wy, h = self.sys_y, 18
        start_rect = pygame.Rect(sx, wy, 44, h)
        menu_rect = pygame.Rect(mx, wy, 44, h)
        pygame.draw.rect(screen, (40, 40, 40), start_rect)
        pygame.draw.rect(screen, (40, 40, 40), menu_rect)
        pygame.draw.rect(screen, ACCENT if start_idx in pressed else (80, 80, 80), start_rect, 3)
        pygame.draw.rect(screen, ACCENT if menu_idx in pressed else (80, 80, 80), menu_rect, 3)
        s_lab = font.render("START", True, FG_COLOR)
        m_lab = font.render("MENU", True, FG_COLOR)
        screen.blit(s_lab, (start_rect.centerx - s_lab.get_width() // 2, start_rect.centery - s_lab.get_height() // 2))
        screen.blit(m_lab, (menu_rect.centerx - m_lab.get_width() // 2, menu_rect.centery - m_lab.get_height() // 2))

    def draw(self, screen: pygame.Surface, font: pygame.font.Font, pressed: Set[int], axes: Dict[int, float]):
        left, right, up, down = self._axis_dirs(axes)
        self._draw_stick(screen, left, right, up, down)
        self._draw_face_buttons(screen, pressed, font)
        self._draw_triggers_and_sys(screen, pressed, font)


def main():
    pygame.init()
    pygame.joystick.init()

    flags = 0  # windowed
    screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    pygame.display.set_caption(TITLE)

    # Font setup
    try:
        font = pygame.font.SysFont("Menlo", 16)
        if font is None:
            raise ValueError("Menlo not available")
    except Exception:
        font = pygame.font.SysFont("monospace", 16)

    clock = pygame.time.Clock()

    log_lines = deque(maxlen=LOG_MAX)

    def log(msg: str):
        timestamp = time.strftime("%H:%M:%S")
        line = f"{timestamp} | {msg}"
        print(line)
        log_lines.append(line)

    jm = JoystickManager(log)
    jm.rescan()

    # Input state (per joystick instance id)
    pressed_by_iid: Dict[int, Set[int]] = {}
    axis_by_iid: Dict[int, Dict[int, float]] = {}

    def ensure_state(iid: int):
        if iid not in pressed_by_iid:
            pressed_by_iid[iid] = set()
        if iid not in axis_by_iid:
            axis_by_iid[iid] = {}

    ui = VisualUI()
    game = Game(WIDTH, HEIGHT, log)

    last_auto_rescan = 0.0

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    log("[KEY] R - rescan")
                    jm.rescan()
                elif event.key == pygame.K_c:
                    log("[KEY] C - clear log")
                    log_lines.clear()

            # Hotplug events
            elif event.type == pygame.JOYDEVICEADDED:
                # event.device_index is the device index to open
                idx = getattr(event, "device_index", None)
                log(f"[EVT] JOYDEVICEADDED idx={idx}")
                if idx is not None:
                    jm.add_device(idx)
            elif event.type == pygame.JOYDEVICEREMOVED:
                iid = getattr(event, "instance_id", None)
                log(f"[EVT] JOYDEVICEREMOVED iid={iid}")
                if iid is not None:
                    jm.remove_device(iid)
                    pressed_by_iid.pop(iid, None)
                    axis_by_iid.pop(iid, None)

            # Input events
            elif event.type == pygame.JOYBUTTONDOWN:
                iid = event.instance_id
                ensure_state(iid)
                pressed_by_iid[iid].add(event.button)
                log(f"[BTN] iid={event.instance_id} btn={event.button} DOWN")
            elif event.type == pygame.JOYBUTTONUP:
                iid = event.instance_id
                ensure_state(iid)
                pressed_by_iid[iid].discard(event.button)
                log(f"[BTN] iid={event.instance_id} btn={event.button} UP")
            elif event.type == pygame.JOYAXISMOTION:
                # Axis value in [-1.0, 1.0]
                iid = event.instance_id
                ensure_state(iid)
                axis_by_iid[iid][event.axis] = float(event.value)
                log(f"[AXS] iid={event.instance_id} axis={event.axis} val={event.value:.3f}")
            elif event.type == pygame.JOYHATMOTION:
                log(f"[HAT] iid={event.instance_id} hat={event.hat} val={event.value}")

        # Auto-rescan occasionally if nothing connected (avoid SDL restart churn)
        if not jm.joysticks and time.time() - last_auto_rescan > 10.0:
            last_auto_rescan = time.time()
            jm.rescan()

        # Inputs from joystick/keyboard
        active_iid = next(iter(sorted(jm.joysticks.keys())), None)
        pressed = pressed_by_iid.get(active_iid, set()) if active_iid is not None else set()
        axes = axis_by_iid.get(active_iid, {}) if active_iid is not None else {}
        ax = float(axes.get(AXIS_X, 0.0))
        ay = float(axes.get(AXIS_Y, 0.0))
        # Convert to screen dx,dy (right/down positive)
        mx = -ax if AXIS_LEFT_POSITIVE else ax
        my = -ay if AXIS_UP_POSITIVE else ay
        # Deadzone and normalize
        if abs(mx) < 0.20:
            mx = 0.0
        if abs(my) < 0.20:
            my = 0.0
        L = math.hypot(mx, my)
        if L > 1.0:
            mx /= L
            my /= L

        keys = pygame.key.get_pressed()
        kx = (1 if keys[pygame.K_RIGHT] else 0) - (1 if keys[pygame.K_LEFT] else 0)
        ky = (1 if keys[pygame.K_DOWN] else 0) - (1 if keys[pygame.K_UP] else 0)
        if kx != 0 or ky != 0:
            mx, my = float(kx), float(ky)
            L = math.hypot(mx, my)
            if L > 0:
                mx /= L
                my /= L

        shoot = (BUTTON_MAP["action_up"] in pressed) or keys[pygame.K_SPACE]
        boost = (BUTTON_MAP["action_left"] in pressed) or keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        shield = (BUTTON_MAP["action_right"] in pressed) or keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]

        # Update game world
        game.update(dt, mx, my, shoot, boost, shield)

        # Render
        screen.fill(BG_COLOR)
        game.draw(screen, font)

        # Header overlay
        y = 8
        def blit_text(text, color=FG_COLOR):
            nonlocal y
            surf = font.render(text, True, color)
            screen.blit(surf, (10, y))
            y += surf.get_height() + LINE_SPACING

        blit_text(TITLE, ACCENT)
        blit_text("Keys: ESC quit | R rescan | C clear log | Arrows move | Space shoot | Shift boost | Ctrl shield")
        for line in jm.summary_lines():
            blit_text(line)

        pygame.display.flip()

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
