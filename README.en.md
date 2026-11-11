# Windows Touchpad Gestures

[Русский](README.md) | **English**

A tiny background app for Windows 10/11 with a Precision Touchpad:

- **Three-finger swipe down minimizes the active window right away**, even a fullscreen one. The built-in Windows gesture first takes the window out of fullscreen and only then minimizes it.
- **One finger up/down along the right edge of the touchpad changes the volume.** The standard Windows volume indicator is shown, and the cursor stays still meanwhile.

A single Python file with no third-party libraries (only `ctypes`).

## Requirements

- Windows 10 or 11 with a Precision Touchpad
- Python 3.10+ ([python.org](https://www.python.org/downloads/) or the Microsoft Store)

## Setup

1. Download the repository (Code → Download ZIP) and unpack it to any folder.
2. Assign the gesture: **Settings → Bluetooth & devices → Touchpad → Advanced gestures → "Swipe down with three fingers" → Custom shortcut** → press `Ctrl+Alt+Shift+M`.
3. Add the app to startup and launch it:
   ```powershell
   powershell -ExecutionPolicy Bypass -File install_autostart.ps1
   ```

The edge volume control works even without step 2.

## Testing and tuning

```powershell
py touchpad_gestures.pyw --debug     # prints finger coordinates and edge state
py touchpad_gestures.pyw --selftest  # checks the edge logic
```

At the top of `touchpad_gestures.pyw`:
- `EDGE_X = 0.93`: the fraction of the touchpad width where the volume zone starts;
- `STEP_Y = 0.05`: how much of the touchpad height you slide for one volume step (2%).

## Uninstall

Delete the "Жесты тачпада" shortcut from the startup folder (`Win+R` → `shell:startup`) and end the `pythonw.exe` process in Task Manager. Set the gesture in Settings back to its default.

## Limitations

- Games in exclusive fullscreen mode may not minimize cleanly.
- Windows running as administrator won't be minimized unless the app itself runs as administrator.
- Windows only.

## License

[MIT](LICENSE)
