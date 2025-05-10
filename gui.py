from PyQt6.QtWidgets import (
    QApplication, QWidget, 
    QVBoxLayout, QHBoxLayout, QGridLayout,  
    QPushButton, QComboBox, QLabel, QSlider, QSpinBox,
    QDialog, QDialogButtonBox, QFileDialog,
    QGraphicsView, QGraphicsScene, 
    QGraphicsRectItem, QGraphicsItem,QStackedLayout
)

from PyQt6.QtGui import (
    QPainter, QColor, QIcon, QPen, QBrush, 
    QPaintEvent, QResizeEvent
)

from PyQt6.QtCore import (
    Qt, QThread, QObject, QEvent,
    pyqtSlot, pyqtSignal
)

from device_manager import MIDIListener
from looper import Looper
from timeline import Timeline
from midi import ( Track, Note, ControlChange, quantise )
from generate import generate_task

import mido
import os
import sys
import time
import json
from multiprocessing import Process, Queue
import midigpt

class TopBar(QHBoxLayout):
    def __init__(self, buttons):
        super().__init__()

        self.addStretch()
        for button in buttons:
            self.addWidget(button)
        self.addStretch()

class TrackControls(QWidget):
    def __init__(self, track_number):
        super().__init__()

        layout = QGridLayout()
        
        self.setLayout(layout)

        # outline border
        self.soundfont_select = QComboBox()
        self.select_button = QPushButton(f"Track {track_number}")
        self.mute_button = QPushButton(QIcon.fromTheme("audio-volume-muted"), "")
        self.solo_button = QPushButton(QIcon.fromTheme("audio-volume-high"), "")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 127)
        self.volume_slider.setValue(127)
        self.volume_slider.setMinimumWidth(120)
        
        for check_button in (self.mute_button, self.solo_button):
            check_button.setCheckable(True)
            check_button.setChecked(False)
            check_button.setFixedSize(30, 30)
        
        # set border to label border
        layout.addWidget(self.soundfont_select, 0, 0, 1, 1, Qt.AlignmentFlag.AlignCenter)
        # this button is removed because the entire layout needs to be clickable
        #self.addWidget(self.select_button, 0, 0, 1, 1, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.mute_button, 0, 1, 1, 1, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.solo_button, 0, 2, 1, 1, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.volume_slider, 0, 3, 1, 1, Qt.AlignmentFlag.AlignCenter)
        
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 0)
        layout.setColumnStretch(2, 0)     
        layout.setColumnStretch(3, 1)       
        
        layout.setRowStretch(0, 1) 
        
        self.onMouseButtonPress = None
        self.installEventFilter(self)
        
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            self.onMouseButtonPress()
            return True
        return False

    def soundFontListUpdated(self, soundfonts):
        selected = self.soundfont_select.currentText()
        self.soundfont_select.clear()
        self.soundfont_select.addItems(soundfonts)
        self.soundfont_select.setCurrentText(selected)
    
    def setSoundFont(self, soundfont):
        pass
        
class MIDIControls(QWidget):
    def __init__(self):
        super().__init__()
        
        self.delete_button = QPushButton(QIcon.fromTheme("edit-delete"), "")
        self.record_button = QPushButton(QIcon.fromTheme("media-record"), "")
        self.load_button = QPushButton(QIcon.fromTheme("document-open"), "")
        self.save_button = QPushButton(QIcon.fromTheme("document-save"), "")
        self.generate_button = QPushButton(QIcon.fromTheme("document-new"), "")
        self.quantise_select = QComboBox()
        self.quantise_label = QLabel("Quantise:")
        self.quantise_select.addItem("Off", 0)
        
        self.quantise_select.addItem("4/1", 0.25)
        self.quantise_select.addItem("2/1", 0.5)
        self.quantise_select.addItem("1/1", 1)
        self.quantise_select.addItem("1/2", 2)
        self.quantise_select.addItem("1/4", 4)
        self.quantise_select.addItem("1/8", 8)
        self.quantise_select.addItem("1/16", 16)
        self.quantise_select.addItem("1/32", 32)
        for button in (self.delete_button, self.record_button, self.load_button, self.save_button, self.generate_button):
            button.setFixedSize(30, 30)
            
        layout = QGridLayout()
        self.setLayout(layout)
        
        
        layout.addWidget(self.delete_button, 0, 0, 1, 1, Qt.AlignmentFlag.AlignCenter)
        #self.addWidget(self.record_button, 0, 1, 1, 1, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.load_button, 0, 2, 1, 1, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.save_button, 0, 3, 1, 1, Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.quantise_label, 0, 4, 1, 1, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.quantise_select, 0, 4, 1, 1, Qt.AlignmentFlag.AlignCenter)    
        #self.addWidget(self.generate_button, 0, 4, 1, 1, Qt.AlignmentFlag.AlignCenter)
        
        #self.setRowStretch(1, 1)
        self.onMouseButtonPress = None
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            if self.onMouseButtonPress:
                self.onMouseButtonPress()
            return True
        return False
    
class AutomaticDeviceSwitchDialog(QDialog):
    def __init__(self, new_device):
        super().__init__()
        
        self.setWindowTitle("Device Change")
        self.setModal(True)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"Switch to new device: {new_device}?"))
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
        self.setLayout(layout)

def is_empty_track(track):
    
    for msg in track:

        if msg.type == "note_on" or msg.type == "note_off":
            return False
        
        #if not msg.is_meta:
        #    return False
        
    print("---Empty track---")
    for msg in track:
        print(msg)
        
    print("---End of empty track---")
    
    return True

class MainWindow(QWidget, MIDIListener):
    def __init__(self, looper):
        super().__init__()
        
        self.looper = looper

        self.setWindowTitle("AI Looper v1.0")
        self.setMinimumSize(800, 600)

        root_layout = QVBoxLayout(self)  # Full vertical layout
        bottom_layout = QHBoxLayout()
        left_bar = QVBoxLayout()
        right_bar = QVBoxLayout()


        # --- Top Bar ---
        self.playpause_button = QPushButton(QIcon.fromTheme("media-playback-start"), "")
        self.playpause_button.clicked.connect(looper.play_button_pressed)
        
        self.restart_button = QPushButton(QIcon.fromTheme("media-seek-backward"), "")
        self.restart_button.clicked.connect(looper.reset_playhead_button_pressed)
        
        self.loop_button = QPushButton(QIcon.fromTheme("media-playlist-repeat"), "")
        # self.loop_button.clicked.connect(looper.loop_button_pressed)
        
        self.metronome_button = QPushButton(QIcon.fromTheme("alarm-symbolic"), "")
        self.metronome_button.clicked.connect(looper.metronome_button_pressed)
        
        self.record_button = QPushButton(QIcon.fromTheme("media-record"), "")
        self.record_button.clicked.connect(looper.record_button_pressed)
        
        self.import_button = QPushButton(QIcon.fromTheme("document-open"), "")
        self.import_button.clicked.connect(lambda: self.importSongDialog())
        
        self.export_button = QPushButton(QIcon.fromTheme("document-save-as"), "")
        self.export_button.clicked.connect(lambda: self.exportSongDialog())
        
        self.generate_button = QPushButton("Generate")
        #self.generate_button.clicked.connect(looper.generate_button_pressed)
        self.generate_button.clicked.connect(self.start_generate)
        
        
        self.device_chooser = QComboBox()
        self.device_chooser.addItem("No MIDI Device")
        
        self.transpose = QSpinBox()
        self.transpose.setRange(-12, 12)
        self.transpose.setValue(0)
        self.transpose.valueChanged.connect(lambda value: setattr(looper, "transpose", value))
        
        for button in (self.playpause_button, self.metronome_button, self.record_button, self.loop_button):
            button.setCheckable(True)
        
        top_bar = TopBar([
            self.restart_button,
            self.playpause_button, 
            self.metronome_button,
            self.record_button,
            self.device_chooser,
            self.transpose,
            self.import_button,
            self.export_button,
            self.generate_button 
        ])
        root_layout.addLayout(top_bar)
        
        root_layout.setContentsMargins(5, 5, 5, 5)
        top_bar.setContentsMargins(0, 5, 0, 5)
        left_bar.setContentsMargins(0, 0, 0, 0)
        right_bar.setContentsMargins(0, 0, 0, 0)
        
        # --- Bottom Section ---
        
        self.track_controls = [
            TrackControls(i) for i in range(self.looper.trackCount())
        ]
        
        for index, track_control in enumerate(self.track_controls):
            track_control.onMouseButtonPress = lambda i=index: self.looper.setActiveTrack(i)
            
            track_control.select_button.clicked.connect(
                lambda _, i=index: self.looper.setActiveTrack(i)
            )
            track_control.mute_button.clicked.connect(
                lambda _, i=index: self.looper.mute(i)
            )
            track_control.solo_button.clicked.connect(
                lambda _, i=index: self.looper.solo(i)
            )
            track_control.volume_slider.valueChanged.connect(
                lambda value, i=index: self.looper.setVolume(i, value)
            )
            track_control.soundfont_select.addItems(looper.synth.listLoadedSoundFonts())
            track_control.soundfont_select.currentIndexChanged.connect(
                lambda _, i=index, t=track_control: self.looper.synth.assignSoundFont(i, t.soundfont_select.currentText())
            )

        self.activeHighlight = QWidget(self)
        self.activeHighlight.setStyleSheet("background-color: rgba(255, 255, 255, 0.1);")# border: 2px solid rgba(255, 0, 0, 255);")
        
        for track_control in self.track_controls:
            left_bar.addWidget(track_control)
        
        
        bottom_layout.addLayout(left_bar)
        
        # Canvas parent container
        
        beats = looper.beats
        track_count = looper.trackCount()
        
        self.timeline = Timeline(beats, track_count)
        self.playhead = QWidget(self.timeline.viewport())
        self.playhead.setStyleSheet("background-color: red;")
        self.playhead.setFixedWidth(2)
        self.playhead.setFixedHeight(self.timeline.height())
        
        bottom_layout.addWidget(self.timeline, stretch=1)

        # Right Sidebar 
        
        self.midi_controls = [
            MIDIControls() for index in range(looper.trackCount())
        ]
        
        for index, midi_control in enumerate(self.midi_controls):
            midi_control.onMouseButtonPress = lambda i=index: self.looper.setActiveTrack(i)
            midi_control.delete_button.clicked.connect(
                lambda _, i=index: self.looper.delete(i)
            )
            midi_control.load_button.clicked.connect(
                lambda _, i=index: self.openFileDialog(i)
            )
            midi_control.save_button.clicked.connect(
                lambda _, i=index: self.saveFileDialog(i)
            )
            midi_control.quantise_select.currentIndexChanged.connect(
                lambda _, i=index,c=midi_control: self.selectQuantisation(i, c.quantise_select.currentData())
            )
        
        for midi_control in self.midi_controls:
            right_bar.addWidget(midi_control)
         
        bottom_layout.addLayout(right_bar)


        root_layout.addLayout(bottom_layout)

        # set stacking to top
        #self.activeHighlight.raise_()
        
        looper.on_playhead_position_change = self.looper_on_playhead_position_change
        looper.on_beat = self.looper_on_beat
        looper.on_loop = self.looper_on_loop
        looper.on_track_change = self.looper_on_track_change
        looper.on_active_track_change = self.looper_on_active_track_change
        
        self.gen_process = None
        self.queue = None
        self.times = []
        
    def connectDeviceMonitor(self, monitor):
        self.device_chooser.currentIndexChanged.connect(lambda index: monitor.connect_to_device(self.device_chooser.currentText()))
    
    @pyqtSlot()
    def start_generate(self):
        if self.gen_process is not None and self.gen_process.is_alive():
            return

        print("Starting generation")

        self.queue = Queue()
        self.gen_process = Process(target=generate_task, args=(self.queue, self.looper))
        self.gen_process.start()
        
        self.timer = self.startTimer(50)  # Check every 0.5s
        self.start_time = time.time()

    def timerEvent(self, event):
        #print("Timer event")
        if self.queue and not self.queue.empty():
            result = self.queue.get()
            if result == "done":
                self.generate_complete()
                #self.looper_worker.on_generate_complete()
                self.killTimer(self.timer)

    def generate_complete(self):
        print("Generate complete!!")
        midi_path = "midi/output.mid"
        midi_file = mido.MidiFile(midi_path)
        self.looper.loadTrack(midi_file, self.looper.active_track)
        elapsed_time = time.time() - self.start_time
        self.times.append(elapsed_time)
        print(f"Generation took {elapsed_time:.2f} seconds")
        
        for t in self.times:
            print(t)
            
        print(f"Average time: {sum(self.times) / len(self.times):.2f} seconds")
    
    def soundFontListUpdated(self, soundfonts):
        for track_control in self.track_controls:
            track_control.soundFontListUpdated(soundfonts)
    
    def openFileDialog(self, track_number):
        default_dir = os.path.join(os.path.dirname(__file__), "midi")
        file_dialog = QFileDialog(self, "Open MIDI File", default_dir)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilter("MIDI Files (*.mid)")
        
        if file_dialog.exec():
            filenames = file_dialog.selectedFiles()
            filename = filenames[0]
            midi = mido.MidiFile(filename)
            self.looper.load(midi, track_number)
            
    def saveFileDialog(self, track_number):
        default_dir = os.path.join(os.path.dirname(__file__), "midi")
        file_dialog = QFileDialog(self, "Save MIDI File", default_dir)
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setNameFilter("MIDI Files (*.mid)")
        
        if file_dialog.exec():
            filenames = file_dialog.selectedFiles()
            filename = filenames[0]
            track = self.looper.tracks[track_number]
            midi = mido.MidiFile(ticks_per_beat=track.ticks_per_beat)
            midi.tracks.append(track.midi_track)
            quantisation = self.looper.quantise[track_number]
            if quantisation != 0:            
                midi = quantise(midi, quantisation)
            midi.save(filename)
                
    def importSongDialog(self):
        default_dir = os.path.join(os.path.dirname(__file__), "midi")
        file_dialog = QFileDialog(self, "Import MIDI Song", default_dir)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilter("MIDI Files (*.mid)")
        
        if file_dialog.exec():
            filenames = file_dialog.selectedFiles()
            filename = filenames[0]
            midi = mido.MidiFile(filename)
            self.looper.loadMIDI(midi)
            
    def exportSongDialog(self):
        default_dir = os.path.join(os.path.dirname(__file__), "midi")
        file_dialog = QFileDialog(self, "Export MIDI Song", default_dir)
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setNameFilter("MIDI Files (*.mid)")
        #file_dialog.setNameFilter("JSON Files (*.json)")
        
        if file_dialog.exec():
            filenames = file_dialog.selectedFiles()
            filename = filenames[0]
            self.looper.export(filename)
                
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.playhead.setFixedHeight(self.timeline.height())
        position = self.looper.playhead_position()
        x = int(position * self.timeline.width() / self.timeline.beats)
        self.playhead.move(x, 0)
        
        track_height = int(self.timeline.height() / self.looper.trackCount())
        self.activeHighlight.setFixedHeight(track_height)
        self.activeHighlight.setFixedWidth(self.width())
        self.activeHighlight.move(0, self.timeline.y() + self.looper.active_track * track_height)
        
    def looper_on_playhead_position_change(self, position):
        x = int(position * self.timeline.width() / self.timeline.beats)
        self.playhead.move(x, 0)
        
    def looper_on_beat(self, position):
        pass
        #if self.looper.metronome_active:
        #    if position == 0:
        #        self.looper.boop()
        #    else:
        #        self.looper.beep()
    
    def looper_on_loop(self, loops):
        pass
    
    def looper_on_track_change(self, track, track_number):
        print("Track", track_number, track)
        self.timeline.setTrack(track, track_number)
        self.timeline.viewport().update()
    
    def looper_on_active_track_change(self, track, track_number):
        
        self.timeline.setActiveTrack(track_number)
        track_height = int(self.timeline.height() / self.looper.trackCount())
        self.activeHighlight.setFixedHeight(track_height)
        self.activeHighlight.setFixedWidth(self.width())
        self.activeHighlight.move(0, self.timeline.y() + self.looper.active_track * track_height)
        
    def selectQuantisation(self, track_number, quantisation):
        
        self.looper.setQuantise(track_number, quantisation)
        self.timeline.tracks[track_number].quantisation = quantisation
        #self.timeline.setTrack(self.looper.tracks[track_number], track_number)
        self.timeline.viewport().update()
    
    def automaticDeviceSwitch(self, new_device):
        dialog = AutomaticDeviceSwitchDialog(new_device)
        
        return dialog.exec()
    
    def notifyDeviceRemoved(self, removed_device):
        pass
    
    def deviceListUpdated(self, devices):
        
        self.device_chooser.clear()
        if devices:
            self.device_chooser.addItems(devices)
        else:
            self.device_chooser.addItem("No MIDI Device")
        
        
    def midiEvent(self, msg):
        self.looper.handleMidiEvent(msg)
    