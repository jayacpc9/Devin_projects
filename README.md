# Carrom (Python + Tkinter)

A two-player carrom board game with a small rigid-body physics engine, written with the
standard library only (`tkinter`). It follows the device/OS appearance and ships with
matching light and dark board themes.

## Run

```bash
python3 carrom.py
```

Requires Python 3.10+ with Tk (`sudo apt install python3-tk` on Debian/Ubuntu;
already bundled on Windows and macOS python.org builds).

## Theming

* **Auto** (default) reads the system colour scheme and re-checks it every 2 s, so the
  board flips themes live when the OS switches between light and dark.
  * Linux: `org.freedesktop.portal.Settings` (`org.freedesktop.appearance color-scheme`),
    falling back to `gsettings` GNOME keys.
  * macOS: `defaults read -g AppleInterfaceStyle`.
  * Windows: `HKCU\...\Themes\Personalize\AppsUseLightTheme`.
* **Light** / **Dark** override the detection from the *Appearance* menu (or press `T`).
* Both the board canvas and the ttk chrome (buttons, menus, labels, separators) are
  restyled from one `Palette` dataclass in `theming.py`.

## Controls

| Action | Input |
| --- | --- |
| Position the striker | Click/drag along your baseline, or `←` / `→` |
| Aim & shoot | Drag away from the striker and release (slingshot); power bar on the right |
| Cancel an aim | `Esc` |
| New game | `N` or the *New game* button |
| Toggle appearance | `T` |

## Rules implemented

* 19 pieces: 9 white, 9 black, 1 red queen, in the standard flower arrangement.
* Player 1 shoots white from the bottom baseline, Player 2 shoots black from the top.
* Potting one of your own coins scores 1 and you shoot again.
* Potting an opponent coin gives them the point and the turn passes.
* The queen must be *covered*: pot one of your own coins on the same or the next shot
  for +3, otherwise the queen returns to the centre.
* Potting the striker is a foul: −1 point, one of your potted coins returns to the
  board, and the turn passes.
* First player to pot all nine of their coins wins.

## Files

| File | Purpose |
| --- | --- |
| `carrom.py` | Tk UI, rendering, input, turn/scoring rules |
| `physics.py` | Board geometry, disc integration, friction, cushions, pockets, elastic collisions |
| `theming.py` | System theme detection, light/dark palettes, ttk styling |

The window is resizable — board geometry and piece positions scale with it.
