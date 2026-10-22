"""Small original procedural music beds, generated offline without sample files."""
import math
import struct
import wave

MUSIC_STYLES={"ambient":"温暖氛围","piano":"柔和琴音","light":"清亮节奏"}
RATE=22050


def make_music(path,duration,cancel=None,style="ambient"):
    if style not in MUSIC_STYLES:
        raise ValueError("请选择已有音乐风格")
    pad=[130.81,164.81,196.,261.63]
    chords=[(60,64,67),(57,60,64),(53,57,60),(55,59,62)]
    beat=60/(76 if style=="piano" else 100)
    def frequency(note):return 440*2**((note-69)/12)
    frequencies=[[frequency(note) for note in chord] for chord in chords]
    frames=round(duration*RATE)
    with wave.open(str(path),"wb") as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(RATE)
        for second in range(math.ceil(duration)):
            if cancel:cancel()
            buffer=bytearray()
            for i in range(min(RATE,frames-second*RATE)):
                t=second+i/RATE
                fade=max(0,min(1,t/1.5,(duration-t)/2))
                if style=="ambient":
                    value=sum(math.sin(2*math.pi*f*t)*(.7+.3*math.sin(t*.4+j)) for j,f in enumerate(pad))/4
                else:
                    chord=frequencies[int(t/(4*beat))%4]
                    step=beat if style=="piano" else beat/2
                    number=int(t/step);phase=t-number*step
                    note=chord[(0,1,2,1)[number%4]]*(1 if style=="piano" else 2)
                    decay=math.exp(-phase*(3.2 if style=="piano" else 6))
                    envelope=decay*(1-math.exp(-phase*90))
                    value=envelope*(math.sin(2*math.pi*note*phase)+.23*math.sin(4*math.pi*note*phase)+.08*math.sin(6*math.pi*note*phase))
                    bar_phase=t%(4*beat)
                    bass_envelope=(1-math.exp(-bar_phase*12))*math.exp(-bar_phase*.55)
                    value+=.24*bass_envelope*math.sin(2*math.pi*chord[0]/2*bar_phase)
                buffer.extend(struct.pack("<h",int(value*(3400 if style=="ambient" else 4200)*fade)))
            out.writeframes(buffer)
