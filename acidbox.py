import sys, random, json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QListWidget,
    QFileDialog, QComboBox, QSpinBox, QMessageBox, QCheckBox, QSlider
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPainter
import mido

SCALES = {
    "acid":         [0, 2, 4, 7, 8, 9],
    "major":        [0, 2, 4, 5, 7, 9, 11],
    "minor":        [0, 2, 3, 5, 7, 8, 10],
    "harm minor":   [0, 2, 3, 5, 7, 8, 11],
    "mel minor":    [0, 2, 3, 5, 7, 9, 11],
    "dorian":       [0, 2, 3, 5, 7, 9, 10],
    "phrygian":     [0, 1, 3, 5, 7, 8, 10],
    "lydian":       [0, 2, 4, 6, 7, 9, 11],
    "mixolydian":   [0, 2, 4, 5, 7, 9, 10],
    "locrian":      [0, 1, 3, 5, 6, 8, 10],
    "chromatic":    list(range(12)),
    "blues":        [0, 3, 5, 6, 7, 10],
    "pentatonic m": [0, 3, 5, 7, 10],
    "pentatonic M": [0, 2, 4, 7, 9]
}
SCALE_NAMES = list(SCALES.keys())
ROOT_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
ROOT2MIDI = {note: midi for midi, note in enumerate(ROOT_NOTES)}
PATTERN_LEN = 16

def root_note_to_midi(root_note, octave=3):
    return ROOT2MIDI[root_note] + 12 * octave

class PatternStep:
    def __init__(self, note_idx=None, accent=False, slide=False, velocity=80):
        self.note_idx = note_idx
        self.accent = accent
        self.slide = slide
        self.velocity = velocity
    def as_dict(self):
        return {'note_idx': self.note_idx, 'accent': self.accent, 'slide': self.slide, 'velocity': self.velocity}
    @staticmethod
    def from_dict(d):
        return PatternStep(d.get('note_idx',None), d.get('accent',False), d.get('slide',False), d.get('velocity',80))

class Pattern:
    def __init__(self, name="Pattern", scale="acid", root="C", octave=3, steps=None, transpose=0, swing=50):
        self.name = name
        self.scale = scale
        self.root = root
        self.octave = octave
        self.transpose = transpose
        self.swing = swing
        if steps:
            self.steps = steps
        else:
            self.steps = [PatternStep() for _ in range(PATTERN_LEN)]
    def as_dict(self):
        return {
            'name': self.name,
            'scale': self.scale,
            'root': self.root,
            'octave': self.octave,
            'transpose': self.transpose,
            'swing': self.swing,
            'steps': [s.as_dict() for s in self.steps]
        }
    @staticmethod
    def from_dict(d):
        return Pattern(
            name=d.get('name',"Pattern"),
            scale=d.get('scale',"acid"),
            root=d.get('root',"C"),
            octave=d.get('octave',3),
            transpose=d.get('transpose',0),
            swing=d.get('swing',50),
            steps=[PatternStep.from_dict(s) for s in d['steps']]
        )
    def randomize(self, wide=None, vel_min=80, vel_max=120, rand_accent=False, rand_slide=False,
                  rand_swing=False, swing_value=50, density=12, rand_density=False, rand_velocity=False, rand_notes=True):
        intervals = SCALES.get(self.scale, SCALES["acid"])
        maxidx = (wide if wide is not None else len(intervals)) - 1
        actual_density = random.randint(1, PATTERN_LEN) if rand_density else density
        if rand_notes:
            note_steps = random.sample(range(PATTERN_LEN), actual_density)
        for i, s in enumerate(self.steps):
            if rand_notes:
                if i in note_steps:
                    s.note_idx = random.randint(0, maxidx)
                else:
                    s.note_idx = None
            s.accent = random.random() < 0.22 if rand_accent else False
            s.slide = random.random() < 0.12 if rand_slide else False
            s.velocity = random.randint(vel_min, vel_max) if rand_velocity else vel_min
        self.fix_note_indices()
        if rand_swing:
            self.swing = random.randint(40, 75)
        else:
            self.swing = swing_value
    def transpose_pattern(self, n):
        self.transpose += n
    def fix_note_indices(self):
        intervals = SCALES.get(self.scale, SCALES["acid"])
        maxidx = len(intervals) - 1
        for s in self.steps:
            if s.note_idx is not None and (s.note_idx > maxidx or s.note_idx < 0):
                s.note_idx = None
    def midi_notes(self):
        intervals = SCALES.get(self.scale, SCALES["acid"])
        midi_base = root_note_to_midi(self.root, self.octave) + self.transpose
        out = []
        maxidx = len(intervals) - 1
        for s in self.steps:
            if s.note_idx is not None and 0 <= s.note_idx <= maxidx:
                out.append(midi_base + intervals[s.note_idx])
            else:
                out.append(None)
        return out
    def shift_left(self):
        self.steps = self.steps[1:] + self.steps[:1]
    def shift_right(self):
        self.steps = self.steps[-1:] + self.steps[:-1]

class AcidGridWidget(QWidget):
    def __init__(self, pattern, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(176)
        self.setMinimumWidth(650)
        self.pattern = pattern
        self.active_step = -1
        self.selected_step = None
        self.dragging = False
        self.drag_start = None
        self.copied_step = None
        self.parent_gui = None

    def get_scale_notes(self):
        intervals = SCALES.get(self.pattern.scale, SCALES["acid"])
        root = ROOT2MIDI[self.pattern.root]
        notes = []
        for i in intervals:
            absnote = (root + i) % 12
            notes.append(ROOT_NOTES[absnote])
        return notes

    def paintEvent(self, event):
        qp = QPainter(self)
        width = self.width()
        height = self.height()
        scale_notes = self.get_scale_notes()
        nrows = len(scale_notes)
        grid_left = 36
        grid_top = 24
        grid_width = width - grid_left - 8
        grid_height = height - grid_top - 10
        step_w = grid_width / PATTERN_LEN
        note_h = grid_height / nrows if nrows else 1

        # Čísla kroků nad gridem
        qp.setPen(QColor(170, 170, 170))
        for i in range(PATTERN_LEN):
            x = int(grid_left + i * step_w)
            qp.drawText(int(x + step_w // 2 - 6), 16, str(i+1))

        # Popisky not vlevo
        midi_base = root_note_to_midi(self.pattern.root, self.pattern.octave) + self.pattern.transpose
        intervals = SCALES.get(self.pattern.scale, SCALES["acid"])
        midi_notes = [midi_base + i for i in intervals]
        note_labels = []
        for midi_num in midi_notes:
            note_labels.append(ROOT_NOTES[midi_num % 12] + str(midi_num // 12))

        for j in range(nrows):
            note_idx = nrows - 1 - j
            rect_y = int(grid_top + j * note_h + note_h / 2 + 6)
            qp.setPen(QColor(200, 200, 200))
            qp.drawText(5, int(rect_y), note_labels[note_idx])

        # Grid samotný
        for i in range(PATTERN_LEN):
            for j in range(nrows):
                note_idx = nrows - 1 - j
                rect_x = int(grid_left + i * step_w)
                rect_y = int(grid_top + j * note_h)
                w = int(step_w) - 2
                h = int(note_h) - 2
                step = self.pattern.steps[i]
                velocity = getattr(step, "velocity", 80)
                base_val = int(160 + (velocity-80)/47*60) if step.note_idx == note_idx else 40
                if step.note_idx == note_idx:
                    color = QColor(base_val, base_val, 200) if not step.accent else QColor(255, 220, 70)
                    if step.slide:
                        color = QColor(60, 220, 220)
                elif step.note_idx is None:
                    color = QColor(45, 45, 45)
                elif step.note_idx is not None and (step.note_idx < 0 or step.note_idx >= nrows):
                    color = QColor(180, 50, 50)
                else:
                    color = QColor(40, 40, 40)
                if i == self.active_step:
                    color = QColor(255, 100, 100)
                if self.selected_step == i and step.note_idx == note_idx:
                    color = QColor(255, 255, 180)
                qp.fillRect(int(rect_x), int(rect_y), w, h, color)
                qp.setPen(QColor(50, 50, 50))
                qp.drawRect(int(rect_x), int(rect_y), w, h)
                if step.note_idx == note_idx:
                    qp.setPen(QColor(100,100,100))
                    qp.drawText(int(rect_x+6), int(rect_y+14), str(velocity))
        qp.end()

    # ... ostatní metody AcidGridWidget jsou beze změny (viz předchozí verze)

    def mousePressEvent(self, event):
        width = self.width()
        height = self.height()
        grid_left = 36
        grid_top = 24
        grid_width = width - grid_left - 8
        grid_height = height - grid_top - 10
        scale_notes = self.get_scale_notes()
        nrows = len(scale_notes)
        step_w = grid_width / PATTERN_LEN
        note_h = grid_height / nrows if nrows else 1
        x, y = event.x() - grid_left, event.y() - grid_top
        col = int(x // step_w)
        row = int(y // note_h)
        note_idx = nrows - 1 - row
        if 0 <= col < PATTERN_LEN and 0 <= note_idx < nrows:
            step = self.pattern.steps[col]
            self.selected_step = col
            if event.button() == Qt.LeftButton:
                if step.note_idx is not None and step.note_idx == note_idx:
                    self.dragging = True
                    self.drag_start = (col, note_idx)
                else:
                    if self.parent_gui: self.parent_gui.save_undo()
                    step.note_idx = note_idx
                if event.modifiers() & Qt.ShiftModifier:
                    if self.parent_gui: self.parent_gui.save_undo()
                    step.accent = not step.accent
            elif event.button() == Qt.RightButton:
                if self.parent_gui: self.parent_gui.save_undo()
                step.slide = not step.slide
            self.update()

    def mouseMoveEvent(self, event):
        width = self.width()
        height = self.height()
        grid_left = 36
        grid_top = 24
        grid_width = width - grid_left - 8
        grid_height = height - grid_top - 10
        scale_notes = self.get_scale_notes()
        nrows = len(scale_notes)
        step_w = grid_width / PATTERN_LEN
        note_h = grid_height / nrows if nrows else 1
        x, y = event.x() - grid_left, event.y() - grid_top
        col = int(x // step_w)
        row = int(y // note_h)
        note_idx = nrows - 1 - row
        if not self.dragging or self.drag_start is None:
            return
        orig_col, orig_note_idx = self.drag_start
        if 0 <= col < PATTERN_LEN and 0 <= note_idx < nrows and col == orig_col:
            step = self.pattern.steps[orig_col]
            if step.note_idx is not None:
                if self.parent_gui: self.parent_gui.save_undo()
                step.note_idx = note_idx
                self.selected_step = orig_col
                self.update()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.drag_start = None

    def mouseDoubleClickEvent(self, event):
        width = self.width()
        height = self.height()
        grid_left = 36
        grid_top = 24
        grid_width = width - grid_left - 8
        grid_height = height - grid_top - 10
        scale_notes = self.get_scale_notes()
        nrows = len(scale_notes)
        step_w = grid_width / PATTERN_LEN
        note_h = grid_height / nrows if nrows else 1
        x, y = event.x() - grid_left, event.y() - grid_top
        col = int(x // step_w)
        row = int(y // note_h)
        note_idx = nrows - 1 - row
        if 0 <= col < PATTERN_LEN and 0 <= note_idx < nrows:
            step = self.pattern.steps[col]
            if self.parent_gui: self.parent_gui.save_undo()
            if step.note_idx == note_idx:
                step.note_idx = None
            else:
                step.note_idx = note_idx
            self.selected_step = col
            self.update()

    def wheelEvent(self, event):
        width = self.width()
        height = self.height()
        grid_left = 36
        grid_top = 24
        grid_width = width - grid_left - 8
        grid_height = height - grid_top - 10
        nrows = len(self.get_scale_notes())
        step_w = grid_width / PATTERN_LEN
        note_h = grid_height / nrows if nrows else 1
        x, y = event.x() - grid_left, event.y() - grid_top
        col = int(x // step_w)
        row = int(y // note_h)
        note_idx = nrows - 1 - row
        if 0 <= col < PATTERN_LEN and 0 <= note_idx < nrows:
            step = self.pattern.steps[col]
            if step.note_idx == note_idx:
                if self.parent_gui: self.parent_gui.save_undo()
                delta = event.angleDelta().y() // 120
                if event.modifiers() & Qt.ControlModifier:
                    delta *= 8
                else:
                    delta *= 2
                v = max(1, min(127, step.velocity + delta))
                step.velocity = v
                self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_C and (event.modifiers() & Qt.ControlModifier) and self.selected_step is not None:
            s = self.pattern.steps[self.selected_step]
            self.copied_step = PatternStep(s.note_idx, s.accent, s.slide, s.velocity)
        elif event.key() == Qt.Key_V and (event.modifiers() & Qt.ControlModifier) and self.selected_step is not None and self.copied_step:
            if self.parent_gui: self.parent_gui.save_undo()
            self.pattern.steps[self.selected_step] = PatternStep(
                self.copied_step.note_idx,
                self.copied_step.accent,
                self.copied_step.slide,
                self.copied_step.velocity
            )
            self.update()
        elif event.key() == Qt.Key_Delete and self.selected_step is not None:
            if self.parent_gui: self.parent_gui.save_undo()
            self.pattern.steps[self.selected_step].note_idx = None
            self.update()

    def set_active_step(self, idx):
        self.active_step = idx
        self.update()

    def randomize(self, wide=None, vel_min=80, vel_max=120, rand_accent=False, rand_slide=False,
                  rand_swing=False, swing_value=50, density=12, rand_density=False, rand_velocity=False, rand_notes=True):
        self.pattern.randomize(wide=wide, vel_min=vel_min, vel_max=vel_max,
                              rand_accent=rand_accent, rand_slide=rand_slide,
                              rand_swing=rand_swing, swing_value=swing_value,
                              density=density, rand_density=rand_density, rand_velocity=rand_velocity, rand_notes=rand_notes)
        self.update()

class AcidBoxGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AcidBox - Acid Grid Sequencer")
        self.patterns = [Pattern(name="Pattern 1")]
        self.chain = [0]
        self.active_idx = 0
        self.is_playing = False
        self.outport = None
        self.midi_chan = 0
        self.tempo = 120
        self.random_wide = len(SCALES["acid"])
        self.random_vel_min = 100
        self.random_vel_max = 127
        self.random_notes = True
        self.random_velocity = True
        self.random_swing = True
        self.random_density = True
        self.random_slide = False
        self.random_accent = False
        self.swing = 50
        self.density = 12
        self.undo_stack = []
        self.max_undo = 30
        self.setMinimumHeight(345)  # Minimalizovaná výška hlavního okna
        self.setMaximumHeight(420)
        self.build_ui()
        self.update_ui()

    def build_ui(self):
        layout = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(QLabel("Patterns:"))
        self.pattern_list = QListWidget()
        self.pattern_list.addItem("Pattern 1")
        self.pattern_list.currentRowChanged.connect(self.switch_pattern)
        left.addWidget(self.pattern_list, 1)
        ph = QHBoxLayout()
        btn_new = QPushButton("Add")
        btn_new.clicked.connect(self.add_pattern)
        ph.addWidget(btn_new)
        btn_del = QPushButton("Del")
        btn_del.clicked.connect(self.del_pattern)
        ph.addWidget(btn_del)
        left.addLayout(ph)
        left.addWidget(QLabel("Chain:"))
        self.chain_list = QListWidget()
        self.refresh_chain_list()
        left.addWidget(self.chain_list, 1)
        ch = QHBoxLayout()
        btn_chain_add = QPushButton("+")
        btn_chain_add.clicked.connect(self.chain_add)
        ch.addWidget(btn_chain_add)
        btn_chain_del = QPushButton("-")
        btn_chain_del.clicked.connect(self.chain_del)
        ch.addWidget(btn_chain_del)
        left.addLayout(ch)
        left.setStretchFactor(self.pattern_list, 1)
        left.setStretchFactor(self.chain_list, 1)
        layout.addLayout(left)
        self.grid = AcidGridWidget(self.patterns[self.active_idx])
        self.grid.parent_gui = self
        grid_and_buttons = QVBoxLayout()
        grid_and_buttons.addWidget(self.grid)
        h_shift = QHBoxLayout()
        btn_step_left = QPushButton("◀")
        btn_step_left.clicked.connect(self.rotate_left)
        h_shift.addWidget(btn_step_left)
        btn_step_right = QPushButton("▶")
        btn_step_right.clicked.connect(self.rotate_right)
        h_shift.addWidget(btn_step_right)
        btn_undo = QPushButton("⟲")
        btn_undo.setToolTip("Undo (Ctrl+Z)")
        btn_undo.clicked.connect(self.undo)
        h_shift.addWidget(btn_undo)
        h_shift.addStretch()
        grid_and_buttons.addLayout(h_shift)
        layout.addLayout(grid_and_buttons)
        right = QVBoxLayout()
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("MIDI Port:"))
        self.midi_combo = QComboBox()
        self.midi_combo.addItems(mido.get_output_names())
        h1.addWidget(self.midi_combo)
        right.addLayout(h1)
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("Ch:"))
        self.channel_spin = QSpinBox()
        self.channel_spin.setRange(1, 16)
        self.channel_spin.setValue(1)
        h2.addWidget(self.channel_spin)
        h2.addWidget(QLabel("Tempo:"))
        self.tempo_spin = QSpinBox()
        self.tempo_spin.setRange(60, 200)
        self.tempo_spin.setValue(125)
        h2.addWidget(self.tempo_spin)
        right.addLayout(h2)
        h3 = QHBoxLayout()
        h3.addWidget(QLabel("Scale:"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(SCALE_NAMES)
        self.scale_combo.currentTextChanged.connect(self.change_scale)
        h3.addWidget(self.scale_combo)
        h3.addWidget(QLabel("Root:"))
        self.root_combo = QComboBox()
        self.root_combo.addItems(ROOT_NOTES)
        self.root_combo.currentTextChanged.connect(self.change_root)
        h3.addWidget(self.root_combo)
        self.octave_spin = QSpinBox()
        self.octave_spin.setRange(1, 6)
        self.octave_spin.setValue(3)
        self.octave_spin.valueChanged.connect(self.change_octave)
        h3.addWidget(QLabel("Octave:"))
        h3.addWidget(self.octave_spin)
        right.addLayout(h3)
        ht = QHBoxLayout()
        btn_trp_up = QPushButton("+")
        btn_trp_up.clicked.connect(lambda: self.transpose(1))
        btn_trp_down = QPushButton("-")
        btn_trp_down.clicked.connect(lambda: self.transpose(-1))
        ht.addWidget(QLabel("Transpose:"))
        ht.addWidget(btn_trp_down)
        ht.addWidget(btn_trp_up)
        self.transpose_label = QLabel("0")
        ht.addWidget(self.transpose_label)
        right.addLayout(ht)
        hswing = QHBoxLayout()
        hswing.addWidget(QLabel("Swing:"))
        self.swing_slider = QSlider(Qt.Horizontal)
        self.swing_slider.setRange(0, 100)
        self.swing_slider.setValue(50)
        self.swing_slider.setFixedWidth(80)
        self.swing_slider.valueChanged.connect(self.set_swing)
        hswing.addWidget(self.swing_slider)
        self.swing_label = QLabel("50%")
        hswing.addWidget(self.swing_label)
        self.cb_rand_swing = QCheckBox("Randomize Swing")
        self.cb_rand_swing.setChecked(True)
        self.cb_rand_swing.stateChanged.connect(lambda state: setattr(self, "random_swing", bool(state)))
        hswing.addWidget(self.cb_rand_swing)
        right.addLayout(hswing)
        hdens = QHBoxLayout()
        hdens.addWidget(QLabel("Density:"))
        self.density_spin = QSpinBox()
        self.density_spin.setRange(1, 16)
        self.density_spin.setValue(12)
        self.density_spin.valueChanged.connect(self.set_density)
        hdens.addWidget(self.density_spin)
        self.cb_rand_density = QCheckBox("Randomize Density")
        self.cb_rand_density.setChecked(True)
        self.cb_rand_density.stateChanged.connect(lambda state: setattr(self, "random_density", bool(state)))
        hdens.addWidget(self.cb_rand_density)
        right.addLayout(hdens)
        hcb = QHBoxLayout()
        self.cb_accent = QCheckBox("Randomize Accent")
        self.cb_accent.setChecked(False)
        self.cb_accent.stateChanged.connect(lambda state: setattr(self, "random_accent", bool(state)))
        hcb.addWidget(self.cb_accent)
        self.cb_slide = QCheckBox("Randomize Glide")
        self.cb_slide.setChecked(False)
        self.cb_slide.stateChanged.connect(lambda state: setattr(self, "random_slide", bool(state)))
        hcb.addWidget(self.cb_slide)
        self.cb_rand_notes = QCheckBox("Randomize Notes")
        self.cb_rand_notes.setChecked(True)
        self.cb_rand_notes.stateChanged.connect(lambda state: setattr(self, "random_notes", bool(state)))
        hcb.addWidget(self.cb_rand_notes)
        right.addLayout(hcb)
        hv = QHBoxLayout()
        hv.addWidget(QLabel("Wide:"))
        self.wide_spin = QSpinBox()
        self.wide_spin.setRange(1, 12)
        self.wide_spin.setValue(len(SCALES["acid"]))
        self.wide_spin.valueChanged.connect(self.set_wide)
        hv.addWidget(self.wide_spin)
        hv.addWidget(QLabel("Velocity:"))
        self.vel_min_spin = QSpinBox()
        self.vel_min_spin.setRange(1, 126)
        self.vel_min_spin.setValue(100)
        self.vel_min_spin.setFixedWidth(44)
        self.vel_min_spin.valueChanged.connect(self.set_vel_min)
        hv.addWidget(self.vel_min_spin)
        hv.addWidget(QLabel("–"))
        self.vel_max_spin = QSpinBox()
        self.vel_max_spin.setRange(2, 127)
        self.vel_max_spin.setValue(127)
        self.vel_max_spin.setFixedWidth(44)
        self.vel_max_spin.valueChanged.connect(self.set_vel_max)
        hv.addWidget(self.vel_max_spin)
        self.cb_rand_velocity = QCheckBox("Randomize Velocity")
        self.cb_rand_velocity.setChecked(True)
        self.cb_rand_velocity.stateChanged.connect(self.set_rand_velocity)
        hv.addWidget(self.cb_rand_velocity)
        right.addLayout(hv)
        hc = QHBoxLayout()
        self.btn_random = QPushButton("Randomize")
        self.btn_random.clicked.connect(self.randomize_pattern)
        hc.addWidget(self.btn_random)
        self.btn_play = QPushButton("Play")
        self.btn_play.clicked.connect(self.toggle_play)
        hc.addWidget(self.btn_play)
        right.addLayout(hc)
        he = QHBoxLayout()
        self.btn_export = QPushButton("Export MIDI")
        self.btn_export.clicked.connect(self.export_midi)
        he.addWidget(self.btn_export)
        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self.save_pattern)
        he.addWidget(self.btn_save)
        self.btn_load = QPushButton("Load")
        self.btn_load.clicked.connect(self.load_pattern)
        he.addWidget(self.btn_load)
        right.addLayout(he)
        layout.addLayout(right)
        self.setLayout(layout)
        self.timer = QTimer()
        self.timer.timeout.connect(self.play_step)
        self.play_pat_idx = 0
        self.play_step_idx = 0

    # ... Všechny metody GUI jsou beze změn (viz minulé verze)

    def set_wide(self, v): self.random_wide = v
    def set_vel_min(self, v):
        self.random_vel_min = v
        if self.vel_max_spin.value() < v:
            self.vel_max_spin.setValue(v+1)
    def set_vel_max(self, v):
        self.random_vel_max = v
        if self.vel_min_spin.value() > v:
            self.vel_min_spin.setValue(v-1)
    def set_rand_velocity(self, state): self.random_velocity = bool(state)
    def set_swing(self, v):
        self.swing = v
        self.swing_label.setText(f"{v}%")
    def set_density(self, v): self.density = v

    def save_undo(self):
        if len(self.undo_stack) >= self.max_undo:
            self.undo_stack.pop(0)
        snapshot = json.dumps({
            "patterns": [p.as_dict() for p in self.patterns],
            "chain": list(self.chain),
            "active_idx": self.active_idx
        })
        self.undo_stack.append(snapshot)

    def undo(self):
        if self.undo_stack:
            snapshot = self.undo_stack.pop()
            data = json.loads(snapshot)
            self.patterns = [Pattern.from_dict(p) for p in data["patterns"]]
            self.chain = data.get("chain", [0])
            self.active_idx = data.get("active_idx", 0)
            self.pattern_list.clear()
            for p in self.patterns:
                self.pattern_list.addItem(p.name)
            self.refresh_chain_list()
            self.pattern_list.setCurrentRow(self.active_idx)
            self.grid.pattern = self.patterns[self.active_idx]
            self.grid.update()
            self.update_ui()

    def add_pattern(self):
        self.save_undo()
        n = len(self.patterns)+1
        p = Pattern(name=f"Pattern {n}", scale=self.scale_combo.currentText(), root=self.root_combo.currentText(), octave=self.octave_spin.value())
        p.randomize(wide=self.random_wide, vel_min=self.random_vel_min, vel_max=self.random_vel_max)
        self.patterns.append(p)
        self.pattern_list.addItem(f"Pattern {n}")

    def del_pattern(self):
        self.save_undo()
        idx = self.active_idx
        if len(self.patterns) <= 1:
            QMessageBox.warning(self, "Nelze smazat", "Musí zůstat aspoň jeden pattern.")
            return
        self.patterns.pop(idx)
        self.pattern_list.takeItem(idx)
        if idx >= len(self.patterns): idx = len(self.patterns)-1
        self.active_idx = idx
        self.pattern_list.setCurrentRow(idx)
        self.update_ui()
        self.refresh_chain_list()

    def switch_pattern(self, idx):
        if idx < 0 or idx >= len(self.patterns): return
        self.active_idx = idx
        self.grid.pattern = self.patterns[self.active_idx]
        self.grid.update()
        self.update_ui()

    def chain_add(self):
        self.save_undo()
        idx = self.pattern_list.currentRow()
        self.chain.append(idx)
        self.refresh_chain_list()

    def chain_del(self):
        self.save_undo()
        row = self.chain_list.currentRow()
        if row >= 0 and len(self.chain) > 1:
            self.chain.pop(row)
            self.refresh_chain_list()

    def refresh_chain_list(self):
        self.chain_list.clear()
        for idx in self.chain:
            if idx < len(self.patterns):
                self.chain_list.addItem(self.patterns[idx].name)
            else:
                self.chain_list.addItem("X")

    def change_scale(self, scale):
        self.patterns[self.active_idx].scale = scale
        self.patterns[self.active_idx].fix_note_indices()
        nnotes = len(SCALES[scale])
        self.wide_spin.setMaximum(nnotes)
        self.grid.update()

    def change_root(self, note):
        self.patterns[self.active_idx].root = note
        self.grid.update()

    def change_octave(self, octv):
        self.patterns[self.active_idx].octave = octv

    def transpose(self, amount):
        self.save_undo()
        self.patterns[self.active_idx].transpose_pattern(amount)
        self.update_ui()
        self.grid.update()

    def update_ui(self):
        pat = self.patterns[self.active_idx]
        self.scale_combo.setCurrentText(pat.scale)
        self.root_combo.setCurrentText(pat.root)
        self.octave_spin.setValue(pat.octave)
        self.transpose_label.setText(str(pat.transpose))
        self.swing_slider.setValue(pat.swing)
        self.swing_label.setText(f"{pat.swing}%")
        self.density_spin.setValue(self.density)
        self.wide_spin.setMaximum(len(SCALES[pat.scale]))
        self.refresh_chain_list()

    def rotate_left(self):
        self.save_undo()
        self.patterns[self.active_idx].shift_left()
        self.grid.update()

    def rotate_right(self):
        self.save_undo()
        self.patterns[self.active_idx].shift_right()
        self.grid.update()

    def randomize_pattern(self):
        self.save_undo()
        wide = self.wide_spin.value()
        vel_min = self.vel_min_spin.value()
        vel_max = self.vel_max_spin.value()
        pat = self.patterns[self.active_idx]
        if self.random_notes:
            pat.randomize(
                wide=wide,
                vel_min=vel_min,
                vel_max=vel_max,
                rand_accent=self.random_accent,
                rand_slide=self.random_slide,
                rand_swing=self.random_swing,
                swing_value=self.swing,
                density=self.density,
                rand_density=self.random_density,
                rand_velocity=self.random_velocity,
                rand_notes=True
            )
        else:
            for s in pat.steps:
                if self.random_accent:
                    s.accent = random.random() < 0.22
                if self.random_slide:
                    s.slide = random.random() < 0.12
                if self.random_velocity:
                    s.velocity = random.randint(vel_min, vel_max)
                else:
                    s.velocity = vel_min
            if self.random_swing:
                pat.swing = random.randint(40, 75)
            else:
                pat.swing = self.swing
        self.swing_slider.setValue(pat.swing)
        self.swing_label.setText(f"{pat.swing}%")
        self.density_spin.setValue(self.density)
        self.grid.update()

    def toggle_play(self):
        if self.is_playing:
            self.is_playing = False
            self.timer.stop()
            self.btn_play.setText("Play")
            QTimer.singleShot(15, self.safe_close_port)
            self.grid.set_active_step(-1)
        else:
            self.outport = mido.open_output(self.midi_combo.currentText())
            self.midi_chan = self.channel_spin.value() - 1
            self.tempo = self.tempo_spin.value()
            self.play_pat_idx = 0
            self.play_step_idx = 0
            self.btn_play.setText("Stop")
            self.is_playing = True
            self.timer.start(int(60000 / (self.tempo * 4)))
            for p in self.patterns:
                for s in p.midi_notes():
                    if s is not None:
                        self.outport.send(mido.Message('note_off', note=s, velocity=0, channel=self.midi_chan))

    def safe_close_port(self):
        if self.outport:
            self.outport.close()
            self.outport = None

    def play_step(self):
        if not self.is_playing: return
        pat_idx = self.chain[self.play_pat_idx % len(self.chain)]
        if pat_idx >= len(self.patterns): return
        pat = self.patterns[pat_idx]
        step = pat.steps[self.play_step_idx]
        notes = pat.midi_notes()
        note = notes[self.play_step_idx]
        velocity = getattr(step, "velocity", 80)
        swing = getattr(pat, "swing", 50)
        base_time = int(60000 / (self.tempo_spin.value() * 4))
        if self.play_step_idx % 2 == 1:
            swing_ratio = (swing-50)/50.0
            step_time = int(base_time * (1 + 0.5 * swing_ratio))
        else:
            swing_ratio = (swing-50)/50.0
            step_time = int(base_time * (1 - 0.5 * swing_ratio))
        if note is not None:
            vel = velocity
            self.outport.send(mido.Message('note_on', note=note, velocity=vel, channel=self.midi_chan))
        self.grid.set_active_step(self.play_step_idx)
        if note is not None and not step.slide:
            QTimer.singleShot(int(step_time * 0.7), lambda n=note: self.safe_note_off(n))
        self.play_step_idx += 1
        if self.play_step_idx >= PATTERN_LEN:
            self.play_step_idx = 0
            self.play_pat_idx += 1
            if self.play_pat_idx >= len(self.chain):
                self.play_pat_idx = 0
        self.timer.start(step_time)

    def safe_note_off(self, n):
        if self.is_playing and self.outport:
            self.outport.send(mido.Message('note_off', note=n, velocity=0, channel=self.midi_chan))

    def save_pattern(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Save Patterns", "", "Pattern JSON (*.json)")
        if not fname: return
        data = [p.as_dict() for p in self.patterns]
        with open(fname, "w") as f:
            json.dump({"patterns": data, "chain": self.chain}, f, indent=2)

    def load_pattern(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Load Patterns", "", "Pattern JSON (*.json)")
        if not fname: return
        with open(fname) as f:
            obj = json.load(f)
        self.patterns = [Pattern.from_dict(p) for p in obj.get("patterns",[])]
        self.chain = obj.get("chain", [0])
        for pat in self.patterns:
            pat.fix_note_indices()
        self.pattern_list.clear()
        for p in self.patterns:
            self.pattern_list.addItem(p.name)
        self.active_idx = 0
        self.pattern_list.setCurrentRow(0)
        self.refresh_chain_list()
        self.grid.pattern = self.patterns[self.active_idx]
        self.grid.update()
        self.update_ui()

    def export_midi(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Export MIDI", "", "MIDI files (*.mid)")
        if not fname: return
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)
        chan = self.channel_spin.value()-1
        for pat_idx in self.chain:
            pat = self.patterns[pat_idx]
            notes = pat.midi_notes()
            for idx, s in enumerate(pat.steps):
                note = notes[idx]
                vel = getattr(s, "velocity", 80)
                if note is not None:
                    track.append(mido.Message('note_on', note=note, velocity=vel, time=0, channel=chan))
                    track.append(mido.Message('note_off', note=note, velocity=0, time=120, channel=chan))
        mid.save(fname)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = AcidBoxGUI()
    win.show()
    sys.exit(app.exec_())
