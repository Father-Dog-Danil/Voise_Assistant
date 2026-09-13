
import sys
import os
import tempfile
import torch
import soundfile as sf
from TTS.api import TTS

speaker_wav = sys.argv[1]

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"DEVICE:{device}", flush=True)

tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
print("READY", flush=True)

for line in sys.stdin:
    text = line.strip()
    if not text:
        continue
    
    if text == "EXIT":
        break
    
    try:
        audio = tts.tts(text=text, speaker_wav=speaker_wav, language="ru", speed=1.0)
        
        # Временный файл
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        
        sf.write(tmp_path, audio, 24000)
        print(f"DONE:{tmp_path}", flush=True)
    except Exception as e:
        print(f"ERROR:{e}", flush=True)
