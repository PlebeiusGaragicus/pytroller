# pytroller
Minimal Pygame-based USB arcade controller debug app with a built-in mini space shooter demo.

## Features
- Detects hot-plug joysticks (USB gamepads/arcade sticks).
- Logs buttons, axes, and hat/D-pad events to the console.
- Built-in demo game (space shooter):
  - Player triangle, scrolling starfield, enemies (asteroids, green blobs, red shooters, purple snakes).
  - Yellow (Up) shoots. Green (Left) boosts speed (uses energy). Blue (Right) shields (uses energy).
  - Enemies drop energy shards to recharge.
- Keys: ESC quit, R rescan devices, C clear log (console continues to show live logs).

## Setup
1) Ensure your venv is activated.
2) Install dependencies:

```
pip install -r requirements.txt
```

## Run

```
python -m src.main
```

A window titled "Pytroller: USB Arcade Controller Debug" will open with the demo game.

## Usage notes
- Plug in your controller before starting, or press R to rescan after plugging in.
- The header shows connected devices, with axes/hats/buttons counts.
- 4-way sticks may report as a single hat (D-pad) or as X/Y axes, depending on the controller/driver. Current mapping follows the captured logs.
- Debug lines continue printing to the terminal; the window shows the live game.

### Mapping (from BUTTONS.md capture)
- Start: button 9
- Menu (quit): button 8
- Left trigger: button 4
- Right trigger: button 5
- Face buttons: Right(blue)=0, Left(green)=1, Up(yellow)=2, Down(red)=3
- Axes: X=0 (Left=+1.0, Right=-1.0), Y=1 (Up=+1.0, Down=-1.0)

If your device differs, adjust these constants in `src/main.py`:
- `BUTTON_MAP` for button indices
- `AXIS_X`, `AXIS_Y`, `AXIS_LEFT_POSITIVE`, `AXIS_UP_POSITIVE`, and `AXIS_THRESH`

### Demo controls (keyboard fallback)
- Move: Arrow keys
- Shoot: Space (maps to Yellow/Up face button)
- Boost: Shift (maps to Green/Left face button)
- Shield: Ctrl (maps to Blue/Right face button)

## Troubleshooting (macOS)
- If no devices are detected, try unplugging/replugging then press R.
- Some controllers expose multiple interfaces; try different USB ports or a powered hub.
- Ensure you are launching with the venv's Python (prints in the log on startup).

## Roadmap
- Deadzone and 4-way gating helpers.
- Button mapping profiles and saving.
- Optional full-screen display and overlay widgets.