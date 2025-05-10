from PyQt6.QtCore import QObject, pyqtSlot, QThread
from PyQt6.QtWidgets import QDialog
import mido
import time
import threading

class MIDIListener:
    
    def deviceListUpdated(self, devices):
        pass
    
    def midiEvent(self, msg):
        pass
    
    def notifyDeviceRemoved(self, removed_device):
        pass
    
    def automaticDeviceSwitch(self, new_device):
        pass

class MIDIDeviceMonitor:
    
    def __init__(self, window: MIDIListener):
        self.window = window
        self.connected_device = None
        self.midi_input = None
        self.midi_listener_thread = None
        self.devices = self.get_available_devices()
        self.window.deviceListUpdated(self.devices)
        
         
    def start(self):
        self.monitor_thread = QThread()
        worker = MIDIDeviceMonitorWorker(self)
        worker.moveToThread(self.monitor_thread)
        self.monitor_thread.started.connect(worker.run)
        self.monitor_thread.start()
        
        
    def connect_to_device(self, device_name):
        """Connect to a specific MIDI input device and start listening."""
        if device_name in self.get_available_devices():
            self.disconnect_device()  # Close any existing connection
            self.connected_device = device_name
            self.midi_input = mido.open_input(device_name)
            print(f"Connected to MIDI device: {device_name}")

            # Start listening thread
            self.midi_listener_thread = threading.Thread(target=self.listen_for_midi_events, daemon=True)
            self.midi_listener_thread.start()
        else:
            print(f"Error: {device_name} not found.")

    def disconnect_device(self):
        """Disconnect from the currently connected MIDI device."""
        if self.midi_input:
            self.midi_input.close()
            print(f"Disconnected from MIDI device: {self.connected_device}")
        self.connected_device = None
        self.midi_input = None

    def select_first_available_device(self):
        """Automatically connect to the first available MIDI input device if none is connected."""
        devices = self.get_available_devices()
        # remove the thru port
        
        if devices:
            first_device = next(iter(devices))
            self.connect_to_device(first_device)
    
    def get_available_devices(self):
        """Retrieve available MIDI input devices."""
        return set(mido.get_input_names())
    
    def listen_for_midi_events(self):
        for msg in self.midi_input:
            self.window.midiEvent(msg)
    
    def run(self):
        
        while True:
            devices = self.get_available_devices()
            new_devices = devices - self.devices
            removed_devices = self.devices - devices
            
            if new_devices:
                print("New devices:", new_devices)
                self.devices = devices
                self.window.deviceListUpdated(devices)

                if self.connected_device is None:
                    response = self.window.automaticDeviceSwitch(new_devices.pop())
                    if response == QDialog.DialogCode.Accepted:
                        self.select_first_available_device()
                
            if removed_devices:
                print("Removed devices:", removed_devices)
                self.devices = devices
                
                self.window.deviceListUpdated(devices)
                
                if self.connected_device in removed_devices:
                    self.disconnect_device()
                    self.window.notifyDeviceRemoved(self.connected_device)
                
            time.sleep(1)
    