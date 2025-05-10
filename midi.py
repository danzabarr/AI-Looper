import mido

def convert_notes_to_abs_time(track):
    acc_ticks = 0
    for msg in track:
        acc_ticks += msg.time
        msg.time = acc_ticks
        #if msg.type == "end_of_track":
        #    break
        
    return track

def convert_notes_to_delta_time(track):
    prev_time = 0
    for msg in track:
        time = msg.time
        msg.time -= prev_time
        prev_time = time
        #if msg.type == "end_of_track":
        #    break
        
    return track

def append_to_file(track, msg, ticks):
    
    track = convert_notes_to_abs_time(track)
    print(track)
    msg.time = ticks
    track.append(msg)
    track.sort(key=lambda m: m.time)
    
    track = convert_notes_to_delta_time(track)
    print(track)
    print(f"Appended message at {ticks} ticks: {msg}")
    
    msg_count = 0
    for msg in track:
        msg_count += 1
        
    print("Message count", msg_count)
    
    return track
    
def quantise(midi, quantisation):
    
    ticks_per_beat = midi.ticks_per_beat
    track = midi.tracks[0]
    
    #print("Ticks per beat:", ticks_per_beat)

    #print("Original track:")
    #for msg in track:
    #    print(msg)
    
    abs_track = []
    acc_ticks = 0
    for msg in track:
        acc_ticks += msg.time
        msg_copy = msg.copy(time=acc_ticks)
        abs_track.append(msg_copy)
        #if msg.type == "end_of_track":
        #    break

    
    #print("Absolute track:")
    #for msg in abs_track:
    #    print(msg)
    
    notes_on = []
    
    quantised_messages = []
    
    for msg in abs_track:
        
        if msg.type == "note_on" and msg.velocity > 0:
            abs_beats = msg.time / ticks_per_beat
            quantised_start_abs_beats = round(abs_beats * quantisation) / quantisation
            quantised_start_abs_ticks = int(quantised_start_abs_beats * ticks_per_beat)
            quantised_messages.append(msg.copy(time=quantised_start_abs_ticks))
            notes_on.append(msg)
            
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            
            for note_on in notes_on:
                
                if note_on.note == msg.note:
                    start_abs_ticks = note_on.time
                    start_abs_beats = start_abs_ticks / ticks_per_beat
                    end_abs_ticks = msg.time
                    duration_abs_ticks = int(end_abs_ticks - start_abs_ticks)
                    quantised_start_abs_beats = round(start_abs_beats * quantisation) / quantisation
                    quantised_start_abs_ticks = int(quantised_start_abs_beats * ticks_per_beat)
                    quantised_end_abs_ticks = quantised_start_abs_ticks + duration_abs_ticks
                    quantised_messages.append(msg.copy(time=quantised_end_abs_ticks))
                    notes_on.remove(note_on)
                    break
                
        else:
            quantised_messages.append(msg)
            
    
    quantised_messages.sort(key=lambda x: x.time)
    
    #print("Quantised track:")
    prev_time = 0
    for msg in quantised_messages:
        time = msg.time
        msg.time -= prev_time
        prev_time = time
        #print(msg)
        
    quantised_track = mido.MidiTrack(quantised_messages)
    quantised_file = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    quantised_file.tracks.append(quantised_track)
    
    return quantised_file

def to_tokens(msg):
    tokens = []
    
    if msg.type == "note_on":
        #NOTE_ON_XXX
        tokens.append("NOTE_ON_" + str(msg.note))
        tokens.append("VELOCITY_" + str(msg.velocity))
        tokens.append("TIME_" + str(msg.time))
    
    elif msg.type == "note_off":
        #NOTE_OFF_XXX
        tokens.append("NOTE_OFF_" + str(msg.note))
        tokens.append("TIME_" + str(msg.time))
    
    elif msg.type == "control_change":
        tokens.append("CONTROL_CHANGE_" + str(msg.control))
        tokens.append("VALUE_" + str(msg.value))
        tokens.append("TIME_" + str(msg.time))
        
    return tokens
        
def to_dict(midi):
    data = []
    
    for track in midi.tracks:
        track_data = []
        for msg in track:
            msg_data = {}
            
            if msg.type == "note_on":
                msg_data["type"] = "note_on"
                msg_data["note"] = msg.note
                msg_data["velocity"] = msg.velocity
                msg_data["time"] = msg.time
                
            elif msg.type == "note_off":
                msg_data["type"] = "note_off"
                msg_data["note"] = msg.note
                msg_data["time"] = msg.time
                
            elif msg.type == "control_change":
                msg_data["type"] = "control_change"
                msg_data["control"] = msg.control
                msg_data["value"] = msg.value
                msg_data["time"] = msg.time
                
            else:
                continue
            
            track_data.append(msg_data)
        data.append(track_data)
        
    return data        

def is_empty_track(track):
    for msg in track:

        if msg.type == "note_on" or msg.type == "note_off":
            return False
        
        #if not msg.is_meta:
        #    return False
        
    #print("---Empty track---")
    #for msg in track:
    #    print(msg)
        
    #print("---End of empty track---")
    
    return True

class Note:
    
    def __init__(self, start, duration, pitch, velocity):
        self.start = start
        self.duration = duration
        self.pitch = pitch
        self.velocity = velocity
        
class ControlChange:
    pass
        
class Track:
    
    def __init__(self, midi_track=mido.MidiTrack(), ticks_per_beat=480, quantisation=0):
        
        if midi_track is None:
            midi_track = mido.MidiTrack()
        
        self.midi_track = midi_track
        self.ticks_per_beat = ticks_per_beat
        #self.track_count = len(midi.tracks)
        #self.track = None
        self.quantisation = quantisation
        self.notes = []
        self.control_changes = []
        self.end_of_track = None
        self.notes_on = []
        
        print("Reading track")
        print("Ticks per beat:", self.ticks_per_beat)
        
        delta_time = 0
        if midi_track is not None:
            for msg in midi_track:
                delta_time += msg.time
                abs_time = delta_time / self.ticks_per_beat
                
                if msg.is_meta:
                    
                    if msg.type == "end_of_track":
                        self.end_of_track = abs_time
                        
                    if msg.type != "lyrics":
                        print(msg)
                    
                elif msg.type == "note_on" and msg.velocity > 0:
                    
                    #print("Note on:", msg.note, msg.velocity, abs_time)
                    #if abs_time > length:
                    #    print("Note on after end of track", abs_time, length)
                    #    continue
                    
                    
                    self.notes_on.append(Note(abs_time, None, msg.note, msg.velocity))
                    
                elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                        
                    for note in self.notes_on:

                        if note.pitch == msg.note:
                            note.duration = abs_time - note.start
                            if self.quantisation != 0:
                                note.start = round(note.start * self.quantisation) / self.quantisation
                            self.notes.append(note)
                            self.notes_on.remove(note)
                            break
                        
                elif msg.type == "control_change":
                        
                    self.control_changes.append
                    (
                        {
                            "control": msg.control, 
                            "value": msg.value, 
                            "time": msg.time, 
                            "abs_time": abs_time
                        }
                    )
            
            print("Remaining notes on:", len(self.notes_on))
        # add any remaining notes that are still on
        #for note in self.notes_on:
        #    print("Adding note:", note)
        #    note.duration = length - note.start
        #    self.notes.append(note)
                
        self.lowest_note = 0
        self.highest_note = 127
        
        if self.notes:
            self.lowest_note = min(note.pitch for note in self.notes)
            self.highest_note = max(note.pitch for note in self.notes)
        
        range = self.highest_note - self.lowest_note
        
        if range < 12:
            self.lowest_note -= 12 - range
            self.highest_note += 12 - range
        
        print("Number of notes:", len(self.notes))
        print("Highest note:", self.highest_note)
        print("Lowest note:", self.lowest_note)    
        print("End of track:", self.end_of_track)
        