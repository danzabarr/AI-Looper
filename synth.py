import os
import fluidsynth

class DefaultSynth(fluidsynth.Synth):
    
    def __init__(self, default_dir="soundfonts", default_ext=".sf2"):
        super().__init__()
        self.default_dir = default_dir
        self.default_ext = default_ext
        self.start(driver='alsa')
        self.sfids = {}       
        
        self.loadAllFonts(self.default_dir)
         
        for i in range(16):
            self.assignDefaultSoundFont(i)
            
    def loadAllFonts(self, dir):
        for root, dirs, files in os.walk(dir):
            for file in files:
                path = os.path.join(root, file)
                # remove the directory prefix
                path = path[len(dir) + 1:]
                if path.endswith(self.default_ext):
                    self.loadSoundFont(path)
                    
    def loadSoundFont(self, path):
        without_ext = path[:-len(self.default_ext)]
        lookup = self.sfids.get(without_ext)
        if lookup is not None:
            return lookup
        sfid = self.sfload(os.path.join(self.default_dir, path))
        if sfid == -1:
            return None
        self.sfids[without_ext] = sfid
        print(f"Loaded soundfont {path} with sfid {sfid}")
        return sfid
    
    def listLoadedSoundFonts(self):
        return self.sfids.keys()
    
    def assignDefaultSoundFont(self, track_number):
        if len(self.sfids) == 0:
            print("No soundfonts loaded")
            return
        path = next(iter(self.sfids))# + self.default_ext
        self.assignSoundFont(track_number, path)
    
    def assignSoundFont(self, track_number, path):
        path += self.default_ext
        sfid = self.loadSoundFont(path)
        if sfid is None:
            return
        self.program_select(track_number, sfid, 0, 0)
        print(f"Assigned soundfont {path} to track {track_number}")