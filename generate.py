import json
import midigpt
import os
import mido
from midi import is_empty_track

def generate_task(queue, looper):
    midi_input = "midi/input.mid"
    midi_dest = "midi/output.mid"

    e = midigpt.ExpressiveEncoder()
    m2j = None
    try:
        m2j = e.midi_to_json(midi_input)

    except RuntimeError:
        print("Error converting MIDI to JSON")
        return            
    
    midi_json_input = json.loads(m2j)
    #print("Exporting to", midi_input)
    
    midi_file = mido.MidiFile()
    midi_file.ticks_per_beat = 480
    for i, track in enumerate(looper.tracks):
        
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
                if beats > looper.beats:
                    print(f"Breaking at {beats} beats")
                    break
                
                ticks = int(beats * midi_file.ticks_per_beat)
                midi_track.append(msg.copy(time=ticks))
        
            # add a dummy note to the track

        midi_file.tracks.append(midi_track)
        
    print("Exported MIDI file:")
    print(f"Track count: {len(midi_file.tracks)}")
        
    midi_file.save(midi_input)

    bars = 8
    
    # add back in the empty tracks
    for index in range(len(midi_json_input['tracks'])):
        
        bars = len(midi_json_input['tracks'][index]['bars'])
        print(f"Track {index} has {bars} bars")
    
    # add back in the empty tracks
    for index in range(len(looper.tracks)):
        if looper.tracks[index] is None or is_empty_track(looper.tracks[index].midi_track):
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
    
    for index in range(len(looper.tracks)):
    
        active_track = index == looper.active_track
        empty_track = looper.tracks[index] == None or is_empty_track(looper.tracks[index].midi_track)
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

    callbacks = midigpt.CallbackManager()
    max_attempts = 3

    midi_str = midigpt.sample_multi_step(piece, status, param, max_attempts, callbacks)[0]
    midi_json = json.loads(midi_str)

    e.json_to_midi(midi_str, midi_dest)

    queue.put("done")
    