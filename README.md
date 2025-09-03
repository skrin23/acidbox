**AcidBox** is a onefile open-source MIDI sequencer inspired by the Sting2 written in Python.  
It generates and edits acid-style patterns with **accent, glide, swing, density, velocity** and supports live editing during playback.  

---

## ✨ Features
- All in one file
- 16-step sequencer with graphical grid editor
- Random pattern generation with options:
  - Accent / Glide
  - Swing (0–100%)
  - Density (number of notes per pattern)
  - Velocity range
- Per-step velocity control (mouse wheel)
- Live editing while playing
- Pattern management (add, delete, chain, save/load JSON)
- Undo (patterns and chains)
- Transpose and pattern shifting (left/right)
- MIDI export to `.mid`
- ALSA MIDI routing for connecting to external synths

---

## 🛠 Installation (Debian/Ubuntu)

```bash
sudo apt install python3 python3-pyqt5 python3-mido python3-rtmidi
```
###  Run the Sequencer

```bash
python3 acidbox.py
```

## 🎛️ Usage

### 🖱️ Grid interaction
- Action	Effect
- Double-click step cell	Toggle note on/off
- Drag vertically	Move note pitch
- Scroll mouse wheel	Change velocity (of selected step)
- Shift + click	Toggle Accent
- Right click	Toggle Glide
- Top row	Step numbers (1–16)
- Left column	Real note names (based on scale)

### 🎚️ Controls
- Velocity Range: Minimum / Maximum velocity for randomization
- Wide: How many notes from the scale are used (starting from bottom)
- Transpose: Shift pattern notes up/down
- Randomization Checkboxes:
- Randomize Notes
- Randomize Velocity
- Randomize Accent
- Randomize Glide
- Randomize Swing
- Randomize Density

### 🧩 Pattern & Chain
- Add / Delete patterns
- Edit pattern name, root, scale, octave
- Transpose up/down
- Shift pattern left/right
- Chain patterns in sequence
- Undo last change (including chain and pattern structure)

### 🎵 Playback & Export
- Select MIDI output port
- Channel and tempo settings
- Play / Stop button
- Export full chain to .mid
- Save / Load pattern bank as .json

### 💾 File Formats
- JSON – for storing patterns and chains
- MIDI – standard MIDI file for use in any DAW or hardware

### 🎼 Supported Scales
Below is a list of musical scales (modes) used for pattern generation in AcidBox. Each scale is defined as a set of intervals (in semitones) from the root note.

| Scale Name       | Intervals (in semitones)   |
|------------------|----------------------------|
| `acid`           | 0, 2, 4, 7, 8, 9           |
| `major`          | 0, 2, 4, 5, 7, 9, 11       |
| `minor`          | 0, 2, 3, 5, 7, 8, 10       |
| `harm minor`     | 0, 2, 3, 5, 7, 8, 11       |
| `mel minor`      | 0, 2, 3, 5, 7, 9, 11       |
| `dorian`         | 0, 2, 3, 5, 7, 9, 10       |
| `phrygian`       | 0, 1, 3, 5, 7, 8, 10       |
| `lydian`         | 0, 2, 4, 6, 7, 9, 11       |
| `mixolydian`     | 0, 2, 4, 5, 7, 9, 10       |
| `locrian`        | 0, 1, 3, 5, 6, 8, 10       |
| `chromatic`      | 0–11 (all semitones)       |
| `blues`          | 0, 3, 5, 6, 7, 10          |
| `pentatonic M`   | 0, 2, 4, 7, 9              |
| `pentatonic m`   | 0, 3, 5, 7, 10             |
-------------------------------------------------

### 🧪 License
- MIT License. Use freely, modify, contribute, enjoy.

### 👤 Author
- Inspired, directed, edited and tested by SkrIN, written by ChatGPT.
---    
