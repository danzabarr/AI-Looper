import sys, os
from looper import *
from device_manager import MIDIDeviceMonitor
from gui import MainWindow
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QThread, pyqtSlot, pyqtSignal, QObject, QTimer

"""
class LooperWorker(QObject):
    updated = pyqtSignal()

    def __init__(self, looper):
        super().__init__()
        self.looper = looper

    @pyqtSlot()
    def run(self):
        self.looper.run()
"""

class MIDIDeviceMonitorWorker(QObject):
    
    def __init__(self, monitor):
        super().__init__()
        self.monitor = monitor
        
    @pyqtSlot()
    def run(self):
        self.monitor.run()

if __name__ == "__main__":

    looper = Looper(bpm=120, beats=16, track_count=8)
    #looper_thread = QThread()
    #looper_worker = LooperWorker(looper)
    #looper_worker.moveToThread(looper_thread)ex
    #looper_thread.started.connect(looper_worker.run)
    #looper_thread.start()

    qtapp = QApplication(sys.argv)
    win = MainWindow(looper)

    timer = QTimer()
    timer.timeout.connect(looper.update)  # looper.update should be non-blocking
    timer.start(16)  # ~60Hz
    
    monitor = MIDIDeviceMonitor(win)
    monitor_thread = QThread()
    monitor_worker = MIDIDeviceMonitorWorker(monitor)
    monitor_worker.moveToThread(monitor_thread)
    monitor_thread.started.connect(monitor_worker.run)
    monitor_thread.start()
    
    monitor.select_first_available_device()
    win.connectDeviceMonitor(monitor)    
    
    #looper.loadMIDI(mido.MidiFile('midi/export_2.mid'))
    
    win.show()
    sys.exit(qtapp.exec())
    
    looper_thread.join()
