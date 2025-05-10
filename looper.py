import os, sys, random, time, json, threading

import mido
import fluidsynth

sys.path.append("midigpt_workspace/MIDI-GPT/python_lib")
import midigpt
from multiprocessing import Process, Queue

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QThread
#sys.path.append(os.path.dirname(os.getcwd()) + "/python_lib")

from midi import ( Track, Note, ControlChange, is_empty_track, append_to_file )
from synth import DefaultSynth
from metronome import Metronome

class Looper:
    
    def __init__(self, bpm, beats, track_count):
        
        self.bpm = bpm
        self.beats = beats
        self.loops = 0
        
        self.playhead_position_beats = 0    # just used for emitting beat events
        self.elapsed_beats = 0
        self.last_time = None
        
        self.playing = False
        self.metronome_active = False
        self.metronome = Metronome("audio/Metronomes/Perc_MetronomeQuartz_lo.wav", "audio/Metronomes/Perc_MetronomeQuartz_hi.wav")
        self.recording = False
        
        self.transpose = 0
        self.tracks = [None] * track_count
        
        self.mutes = [False] * track_count
        self.solos = [False] * track_count
        self.volumes = [127] * track_count
        self.quantise = [0] * track_count
        self.synth = DefaultSynth()
        self.active_track = -1
        
        self.on_active_track_change = None
        self.on_track_change = None
        self.on_playhead_position_change = None
        self.on_beat = None
        self.on_loop = None
        
        self.setActiveTrack(0)
        
        self.queue = None
        #self.generate_thread = None
        self.generate_ready = False
        self.piece = None
        self.status = None
    
    def start(self):
        #self.last_beats = (time.time() / 60 * self.bpm) % self.beats
        self.last_time = time.time()
        self.playing = True
        
    def pause(self):
        self.playing = False
        for i in range(len(self.tracks)):
            self.synth.all_notes_off(i)

    def startRecording(self):
        self.recording = True
        
    def stopRecording(self):
        self.recording = False
    
    def is_playing(self):
        return self.playing

    def playhead_position(self):
        return self.elapsed_beats % self.beats

    def trackCount(self):
        return len(self.tracks)
        
    def activeTrack(self):

        if self.active_track < 0:
            return None
                
        if self.active_track >= len(self.tracks):
            return None
        
        return self.tracks[self.active_track]
        
    def setActiveTrack(self, track_number):
        print("Setting active track", track_number)
        if track_number >= len(self.tracks):
            return
        if track_number < 0:
            track_number = -1
        
        self.active_track = track_number
        if self.on_active_track_change:
            track = self.tracks[track_number] if track_number >= 0 else None
            self.on_active_track_change(track, track_number)
      
    def setSynth(self, track_number, sfid):
        self.synth.program_select(track_number, sfid, 0, 0)
        
    def setQuantise(self, track_number, fraction):
        if track_number < 0:
            return
        if track_number >= len(self.tracks):
            return
        
        print(f"Setting quantise for track {track_number} to {fraction}")
        self.quantise[track_number] = fraction
        
    def updateVolumes(self):
        solo_count = sum(self.solos)
        for i in range(len(self.solos)):
            volume = 0
            if self.solos[i] or solo_count == 0:
                volume = self.volumes[i]
            if self.mutes[i]:
                volume = 0
            self.synth.cc(i, 7, volume)
    
    def mute(self, track_number):
        self.mutes[track_number] = not self.mutes[track_number]
        self.updateVolumes()
    
    def solo(self, track_number):
        self.solos[track_number] = not self.solos[track_number]
        self.updateVolumes()
            
    def setVolume(self, track_number, volume):
        self.volumes[track_number] = volume
        self.updateVolumes()
    
    def addEmptyTrack(self, track_number):
        self.tracks[track_number] = Track(None)
        self.on_track_change(self.tracks[track_number], track_number)
        return self.tracks[track_number]
    
    def loadMIDI(self, midi):
        ticks_per_beat = midi.ticks_per_beat
        index = 0
        print("Loading MIDI file")
        print("Ticks per beat:", ticks_per_beat)
        print("Track count:", len(midi.tracks))
        for i in range(len(midi.tracks)):
            track = midi.tracks[i]
            
            if len(track) == 0:
                continue
            
            print(f"Loading track #{index}: {track.name}")
            
            if is_empty_track(track):
                self.tracks[index] = None
            else:
                self.tracks[index] = Track(track, ticks_per_beat)

            self.on_track_change(self.tracks[index], index)
            index += 1
            
            print(f"Loaded track {track.name} \n")
            
            if index >= len(self.tracks):
                break
            
    def loadTrack(self, midi, track_index):
        ticks_per_beat = midi.ticks_per_beat
        index = 0
        print("Loading MIDI file")
        print("Ticks per beat:", ticks_per_beat)
        print("Track count:", len(midi.tracks))
        for i in range(len(midi.tracks)):
            track = midi.tracks[i]
            
            if len(track) == 0:
                continue
            
            
            if i == track_index:
                print(f"Loading track #{index}: {track.name}")
                if is_empty_track(track):
                    self.tracks[index] = None
                else:
                    self.tracks[index] = Track(track, ticks_per_beat)

                self.on_track_change(self.tracks[index], index)
                print(f"Loaded track {track.name} \n")
            
            index += 1
            
            if index >= len(self.tracks):
                break
    
    def load(self, midi, track_number):
        track = midi.tracks[0]
        ticks_per_beat = midi.ticks_per_beat
        self.tracks[track_number] = Track(track, ticks_per_beat)
        self.on_track_change(self.tracks[track_number], track_number)
    
    def export(self, filename):
        print("Exporting to", filename)
        
        midi_file = mido.MidiFile()
        midi_file.ticks_per_beat = 480
        for i, track in enumerate(self.tracks):
            
            midi_track = mido.MidiTrack()
            midi_track.name = f"Track {i}"
            
            if track is None or is_empty_track(track.midi_track):
                print(f"Exporting empty track {i}")
                
                #midi_track.append(mido.Message("note_on", note=60, velocity=1, time=0))
                #midi_track.append(mido.Message("note_off", note=60, velocity=0, time=1))

            else:
                # convert the track to 480 ticks per beat
                print(f"Exporting track {i}")
                
                for msg in track.midi_track:
                    
                    
                    beats = msg.time / track.ticks_per_beat
                    if beats > self.beats:
                        print(f"Breaking at {beats} beats")
                        break
                    
                    ticks = int(beats * midi_file.ticks_per_beat)
                    midi_track.append(msg.copy(time=ticks))
            
                # add a dummy note to the track

            midi_file.tracks.append(midi_track)
            
        print("Exported MIDI file:")
        print(f"Track count: {len(midi_file.tracks)}")
            
        midi_file.save(filename)
       
    def start_generation(self):
        
        midi_input = "midi/input.mid"
        self.export(midi_input)

        e = midigpt.ExpressiveEncoder()
        m2j = None
        try:
            m2j = e.midi_to_json(midi_input)

        except RuntimeError:
            print("Error converting MIDI to JSON")
            return            
        
        midi_json_input = json.loads(m2j)
        
        bars = 8
        
        # add back in the empty tracks
        for index in range(len(midi_json_input['tracks'])):
            
            bars = len(midi_json_input['tracks'][index]['bars'])
            print(f"Track {index} has {bars} bars")
        
        # add back in the empty tracks
        for index in range(len(self.tracks)):
            if self.tracks[index] is None or is_empty_track(self.tracks[index].midi_track):
                print(f"Adding empty track {index}")
                midi_json_input['tracks'].insert(index, {
                    'instrument': 0,
                    'track_type': 10,
                    'bars': [{'events': [], 'ts_numerator': 4, 'ts_denominator': 4} for _ in range(bars)]
                })
                
        
        num_tracks = len(midi_json_input['tracks'])
        print(f"Number of tracks: {num_tracks}")
        
        valid_status = {
            'tracks': []
        }
        
        track_id = 0
        active_track_id = -1
        
        for index in range(len(self.tracks)):
        
            active_track = index == self.active_track
            empty_track = self.tracks[index] == None or is_empty_track(self.tracks[index].midi_track)
            #empty_track = False
            print(f"Assembling track {index}, active: {active_track}, empty: {empty_track}")

               
            if active_track:
                
                active_track_id = track_id
                
                valid_status['tracks'].append({
                    'track_id': active_track_id,
                    'temperature': 0.5,
                    'instrument': 'no_drums',
                    'density': 10,
                    'track_type': 10, #STANDARD_TRACK
                    'ignore': False,
                    'selected_bars': [True] * bars,
                    'min_polyphony_q': 'POLYPHONY_ANY',
                    'max_polyphony_q': 'POLYPHONY_ANY',
                    'autoregressive': False,
                    'polyphony_hard_limit': 9
                })
                
                track_id += 1
                
            elif empty_track:
            
                valid_status['tracks'].append({
                    'track_id': track_id,
                    'temperature': 0.5,
                    'instrument': 'no_drums',
                    'density': 10,
                    'track_type': 10,
                    'ignore': True,
                    'selected_bars': [False] * bars,
                    'min_polyphony_q': 'POLYPHONY_ANY',
                    'max_polyphony_q': 'POLYPHONY_ANY',
                    'autoregressive': False,
                    'polyphony_hard_limit': 9
                })
                
                track_id += 1
            
            else:
                
                valid_status['tracks'].append({
                    'track_id': track_id,
                    'temperature': 0.5,
                    'instrument': 'no_drums',
                    'density': 10,
                    'track_type': 10,
                    'ignore': False,
                    'selected_bars': [False] * bars,
                    'min_polyphony_q': 'POLYPHONY_ANY',
                    'max_polyphony_q': 'POLYPHONY_ANY',
                    'autoregressive': False,
                    'polyphony_hard_limit': 9
                })
                
                track_id += 1

        parami={
          'tracks_per_step': 1, 
          'bars_per_step': 1, 
          'model_dim': 4, 
          'percentage': 100, 
          'batch_size': 1, 
          'temperature': 1.0, 
          'max_steps': 200, 
          'polyphony_hard_limit': 6, 
          'shuffle': True, 
          'verbose': False, 
          'ckpt': "midigpt_workspace/MIDI-GPT/models/EXPRESSIVE_ENCODER_RES_1920_12_GIGAMIDI_CKPT_150K.pt",
          'sampling_seed': -1,
          'mask_top_k': 0
        }

        piece = json.dumps(midi_json_input)
        status = json.dumps(valid_status)
        param = json.dumps(parami)

        return piece, status, param
       
    def delete(self, track_number):
        if len(self.tracks) <= track_number:
            return
        
        self.tracks[track_number] = None
        self.on_track_change(None, track_number)
    
    def play_button_pressed(self, event=None):
        
        if self.last_time is None or not self.is_playing():
            self.start()

        else:
            self.pause()
    
    def reset_playhead_button_pressed(self, event=None):
        
        current_beats = ((time.time() / 60) * self.bpm) % self.beats
        
        self.playhead_position_beats = 0
        
        #self.last_beats = current_beats % self.beats
        self.last_time = time.time()
        self.elapsed_beats = 0
        
        self.on_playhead_position_change(0)
        self.loops = 0
        
        for i in range(len(self.tracks)):
            self.synth.all_notes_off(i)
        
    def record_button_pressed(self, event=None):
        
        if self.recording:
            self.stopRecording()
        else:
            self.startRecording()
    
    def metronome_button_pressed(self, event=None):
        self.metronome_active = not self.metronome_active
    
    def OLDgenerate_button_pressed(self, event=None):
        print("Generate button pressed")
        pass
    
    def update(self):
        
        if self.queue and not self.queue.empty():
            result = self.queue.get()
            self.timer.stop()
            self.gen_process.join()

            if result == "error":
                print("Generation failed")
            else:
                print(f"Generation finished: {result}")
                midi_file = mido.MidiFile(result)
                self.loadTrack(midi_file, self.active_track)
        
        if self.generate_ready:
            self.generate_ready = False
            self.generate_thread = None
            self.piece = None
            self.status = None
            
            midi_dest = "midi/generated.mid"
            
            midi_file = mido.MidiFile(midi_dest)
            #self.loadMIDI(midi_file)
            self.loadTrack(midi_file, self.active_track)

        current_time = time.time()
        
        if not self.is_playing():
            self.last_time = current_time
        
        else:
        
            delta = current_time - self.last_time
            delta_beats = delta / 60 * self.bpm
            self.elapsed_beats += delta_beats
            self.last_time = current_time
            
            looped = self.elapsed_beats >= self.beats
            self.elapsed_beats %= self.beats

            if self.on_playhead_position_change:
                self.on_playhead_position_change(self.playhead_position())
                
            if self.on_beat and int(self.playhead_position()) != int(self.playhead_position_beats):
                self.on_beat(self.playhead_position())
                if self.metronome_active:
                    if int(self.playhead_position()) % 4 == 0:
                        self.metronome.clock()
                    else:
                        self.metronome.click()
                    
            self.playhead_position_beats = self.playhead_position()
            
            if self.on_loop and looped:
                self.on_loop(self.loops)
                self.loops += 1

            for track_index in range(len(self.tracks)):
                
                if self.tracks[track_index] is None:
                    continue
                
                track = self.tracks[track_index].midi_track
                ticks_per_beat = self.tracks[track_index].ticks_per_beat
                
                if self.synth is None:
                    continue
                
                if self.mutes[track_index]:
                    continue
                
                if not self.solos[track_index] and any(self.solos):
                    continue
            
                update_start = self.elapsed_beats - delta_beats
                update_end = self.elapsed_beats
                
                acc_ticks = 0
                
                for msg in track:
                    
                    acc_ticks += msg.time
                    abs_beats = (acc_ticks / ticks_per_beat)# % self.beats

                    # quantisation = self.quantise[track_index]
                    #if quantisation != 0:
                    #    abs_beats = round(abs_beats * quantisation) / quantisation
                    # round the abs_beats to the nearest fraction of a beat
                    # e.g. if the fraction is 4, and the abs_beats is 3.24, it will be rounded to 3.25
                    
                    
                    #print(f"Abs beats: {abs_beats}, last beats: {self.last_beats}, current beats: {current_beats}, playhead: {self.playhead_position()}")
                    
                    # if the absolute time in beats is between the last time and the current time, play the note
                    if abs_beats >= update_start and abs_beats < update_end:
                        
                        if msg.type == "note_on":
                            self.synth.noteon(track_index, msg.note, msg.velocity)
                            
                        elif msg.type == "note_off":
                            self.synth.noteoff(track_index, msg.note)
                            
                        elif msg.type == "pitchwheel":
                            self.synth.pitch_bend(track_index, msg.pitch)
                            
                        elif msg.type == "control_change":
                            self.synth.cc(track_index, msg.control, msg.value)
                            
                    if abs_beats > update_end:
                        break
  
    def handleMidiEvent(self, msg):
        
        if msg.type == "note_on" or msg.type == "note_off":
            msg.note += self.transpose
        
        print(msg)

        self.inputMonitoring(msg)
        self.inputRecording(msg)
        
    def inputRecording(self, msg):

        if self.active_track < 0:
            return
        
        if self.active_track >= len(self.tracks):
            return
        
        if not self.is_playing():
            return
        
        if not self.recording:
            return
        
        active_track = self.activeTrack()
        if msg.type == "note_on" or msg.type == "note_off":
            
            if active_track is None:
                active_track = self.addEmptyTrack(self.active_track)
            
            midi_track = active_track.midi_track
            ticks_per_beat = active_track.ticks_per_beat
            
            ticks = int((self.elapsed_beats * ticks_per_beat) % (self.beats * ticks_per_beat))
            
            midi = append_to_file(midi_track, msg, ticks)
            
            self.tracks[self.active_track] = Track(midi_track)
            
            self.on_track_change(self.tracks[self.active_track], self.active_track)
        
    def inputMonitoring(self, msg):
        # Input monitoring when the key is pressed
        if self.synth is None:
            return
        
        if self.active_track < 0:
            return
        
        if self.active_track >= len(self.tracks):
            return
        
        
        if msg.type == "note_on":
            self.synth.noteon(self.active_track, msg.note, msg.velocity)
            print(f"Note on: {msg.note}, velocity: {msg.velocity}")
        
        elif msg.type == "note_off":
            self.synth.noteoff(self.active_track, msg.note)
            
        elif msg.type == "pitchwheel":
            self.synth.pitch_bend(self.active_track, msg.pitch)
            
        elif msg.type == "control_change":
            self.synth.cc(self.active_track, msg.control, msg.value)

    def run(self):
        while True:
            self.update()
            time.sleep(0.0001)      
  