import pyaudio
import wave
import threading

# audio/Metronomes/Perc_MetronomeQuartz_lo.wav
# audio/Metronomes/Perc_MetronomeQuartz_hi.wav


class Metronome:
    def __init__(self, click_path, clock_path):
        self.click_path = click_path
        self.clock_path = clock_path
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=44100, output=True)
        self.click_wave = wave.open(self.click_path, 'rb')
        self.clock_wave = wave.open(self.clock_path, 'rb')
    
    def play_wave(self, wav):
        wav.rewind()
        data = wav.readframes(1024)
        while data:
            self.stream.write(data)
            data = wav.readframes(1024)

    def click(self):
        threading.Thread(target=self.play_wave, args=(self.click_wave,), daemon=True).start()

    def clock(self):
        threading.Thread(target=self.play_wave, args=(self.clock_wave,), daemon=True).start()
