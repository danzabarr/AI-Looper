import json
import midigpt
import os
import mido

def generate_task(queue, piece, status):
    midi_input = "midi/input.mid"
    ckpt = "midigpt_workspace/MIDI-GPT/models/EXPRESSIVE_ENCODER_RES_1920_12_GIGAMIDI_CKPT_150K.pt"
    midi_dest = "midi/output.mid"

    e = midigpt.ExpressiveEncoder()
    midi_json_input = json.loads(e.midi_to_json(midi_input))

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
          'ckpt': ckpt,
          'sampling_seed': -1,
          'mask_top_k': 0
        }

    param = json.dumps(parami)
    callbacks = midigpt.CallbackManager()
    max_attempts = 3

    midi_str = midigpt.sample_multi_step(piece, status, param, max_attempts, callbacks)[0]
    midi_json = json.loads(midi_str)

    e.json_to_midi(midi_str, midi_dest)

    queue.put("done")