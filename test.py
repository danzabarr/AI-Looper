from PyQt6.QtWidgets import QApplication, QPushButton, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
import sys
import time
import json
from multiprocessing import Process, Queue
import midigpt

class LooperWorker(QObject):
    update_gui = pyqtSignal(str)
    notify_generate_complete = pyqtSignal()

    @pyqtSlot()
    def run(self):
        counter = 0
        while True:
            time.sleep(1)  # Simulate synth update
            counter += 1
            self.update_gui.emit(str(counter))

    @pyqtSlot()
    def on_generate_complete(self):
        self.update_gui.emit("Generate complete")

def generate_task(queue):
    midi_input = "midi/export_2.mid"
    ckpt = "midigpt_workspace/MIDI-GPT/models/EXPRESSIVE_ENCODER_RES_1920_12_GIGAMIDI_CKPT_150K.pt"
    midi_dest = "midi/output.mid"
    
    e = midigpt.ExpressiveEncoder()
    midi_json_input = json.loads(e.midi_to_json(midi_input))

    valid_status = {
        'tracks': [
            {'track_id': i, 'temperature': 0.5, 'instrument': 'acoustic_grand_piano', 'density': 10,
             'track_type': 10, 'ignore': False, 'selected_bars': [i == 2]*4,
             'min_polyphony_q': 'POLYPHONY_ANY', 'max_polyphony_q': 'POLYPHONY_ANY',
             'autoregressive': False, 'polyphony_hard_limit': 9}
            for i in range(3)
        ]
    }

    parami = {
        'tracks_per_step': 1, 'bars_per_step': 1, 'model_dim': 4, 'percentage': 100,
        'batch_size': 1, 'temperature': 1.0, 'max_steps': 200,
        'polyphony_hard_limit': 6, 'shuffle': True, 'verbose': False,
        'ckpt': ckpt, 'sampling_seed': -1, 'mask_top_k': 0
    }

    piece = json.dumps(midi_json_input)
    status = json.dumps(valid_status)
    param = json.dumps(parami)
    callbacks = midigpt.CallbackManager()
    max_attempts = 3

    midi_str = midigpt.sample_multi_step(piece, status, param, max_attempts, callbacks)[0]
    midi_json = json.loads(midi_str)

    e.json_to_midi(midi_str, midi_dest)

    queue.put("done")

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.label = QLabel("Ready")
        self.button = QPushButton("Generate")
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.button)
        self.setLayout(layout)

        self.gen_process = None
        self.queue = None

        # Synth Thread
        self.looper_thread = QThread()
        self.looper_worker = LooperWorker()
        self.looper_worker.moveToThread(self.looper_thread)
        self.looper_thread.started.connect(self.looper_worker.run)
        self.looper_worker.update_gui.connect(self.update_label)
        self.looper_thread.start()

        # Generate Button
        self.button.clicked.connect(self.start_generate)

    @pyqtSlot()
    def start_generate(self):
        if self.gen_process is not None and self.gen_process.is_alive():
            return


        self.queue = Queue()
        self.gen_process = Process(target=generate_task, args=(self.queue,))
        self.gen_process.start()

        self.timer = self.startTimer(500)  # Check every 0.5s

    def timerEvent(self, event):
        print("Timer event")
        if self.queue and not self.queue.empty():
            result = self.queue.get()
            if result == "done":
                self.update_label("Generate complete")
                self.looper_worker.on_generate_complete()
                self.killTimer(self.timer)

    @pyqtSlot(str)
    def update_label(self, text):
        self.label.setText(text)
        print(text)

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.set_start_method("spawn")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
