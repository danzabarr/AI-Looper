from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene

from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, 
    QPaintEvent
)

from midi import ( Track, Note, ControlChange )

import colorsys

def velocity_color(velocity):
    """
    Convert a MIDI velocity (0-127) into an RGB color using HSV.
    
    - 0 velocity = RED (0° hue)
    - 127 velocity = PURPLE (~275° hue)
    
    :param velocity: MIDI velocity (0-127)
    :return: Hex color string in "#RRGGBB" format
    """
    velocity_ratio = velocity / 127.0  # Normalize to 0-1
    hue = (1.0 - velocity_ratio) * 275 / 360  # Map to hue range (0° = Red, 275° = Purple)
    rgb = colorsys.hsv_to_rgb(hue, 1, 1)  # Convert HSV to RGB (max saturation & value)
    
    # Convert to 8-bit RGB and hex format
    r, g, b = [int(c * 255) for c in rgb]
    return f"#{r:02x}{g:02x}{b:02x}"

        
class Timeline(QGraphicsView):
    def __init__(self, beats=16, track_count=8):
        super().__init__()
        self.beats = beats
        self.playhead_position = 0
        self.active_track_index = 0
        self.tracks = [None] * track_count
        self.setScene(QGraphicsScene())
        self.recording = False
        #self.setBackgroundBrush(Qt.GlobalColor.clear)
        
    def paintEvent(self, event):
        
        qp = QPainter(self.viewport())
        qp.setPen(QPen(QColor(255, 255, 255, 20), 1))
        
        # draw vertical lines
        for i in range(0, self.beats + 1):
            x = int(i * self.width() / self.beats)
            qp.drawLine(x, 0, x, self.height())
            
        # draw notes
        height = self.height()
        track_height = height / len(self.tracks)

        track_index = 0
        for track in self.tracks:
            
            # draw a rectangle around the track
            
            if track_index == self.active_track_index:
                qp.setBrush(QBrush(QColor(255, 255, 255, 20)))
            else:
                qp.setBrush(QBrush(QColor(0, 0, 0, 0)))
                
            qp.drawRect(0, int(track_index * int(track_height)), self.width(), int(track_height))
                
            
            if track is None:
                track_index += 1
                continue
            
            highest_note = track.highest_note
            lowest_note = track.lowest_note - 1
            
            for note in track.notes:
                
                start = note.start
                
                if track.quantisation != 0:
                   start = round(note.start * track.quantisation) / track.quantisation
                
                x = int(start * self.width() / self.beats)
                y = int(track_index * track_height) + int((highest_note - note.pitch) / (highest_note - lowest_note) * track_height)
                width = int(note.duration * self.width() / self.beats)
                height = int(track_height / (highest_note - lowest_note))
                fill = QBrush(QColor(velocity_color(note.velocity)))
                qp.fillRect(x, y, width, height, fill)
                
            track_index += 1
                
        # draw control changes...
                
        # draw playhead
        #x = int(self.playhead_position * self.width() / self.beats)
        #qp.setPen(QPen(Qt.GlobalColor.red, 2))
        #qp.drawLine(x, 15, x, self.height())
    def setTrack(self, track, track_number):
        self.tracks[track_number] = track
    
    def setActiveTrack(self, track_index):
        self.active_track_index = track_index