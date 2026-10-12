"""Optional offline Mandarin voice-over using an installed macOS voice."""
import math
import platform
import struct
import subprocess
import wave
from functools import lru_cache


class NarrationError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def available():
    if platform.system() != "Darwin":
        return False
    try:
        result = subprocess.run(["/usr/bin/say", "-v", "?"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0 and any(line.startswith("Tingting ") for line in result.stdout.splitlines())
    except (OSError, subprocess.SubprocessError):
        return False


def synthesize(text, destination, convert):
    source = destination.with_suffix(".txt")
    aiff = destination.with_suffix(".aiff")
    source.write_text(text, encoding="utf-8")
    try:
        result = subprocess.run(["/usr/bin/say", "-v", "Tingting", "-r", "210", "-f", str(source), "-o", str(aiff)],
                                capture_output=True, timeout=90)
        if result.returncode:
            raise NarrationError("本机中文配音失败，请检查系统的婷婷语音，或关闭配音后重试。")
        convert(["-i", str(aiff), "-ar", "22050", "-ac", "1", "-c:a", "pcm_s16le", str(destination)])
        with wave.open(str(destination), "rb") as audio:
            duration = audio.getnframes() / audio.getframerate()
            samples = audio.readframes(audio.getnframes())
        energy = sum(v[0] ** 2 for v in struct.iter_unpack("<h", samples))
        if duration < .15 or not samples or math.sqrt(energy / (len(samples) / 2)) < 5:
            raise NarrationError("本机语音未产生有效声音，请在系统设置中检查中文语音，或关闭配音后重试。")
        return duration
    except NarrationError:
        raise
    except (OSError, subprocess.SubprocessError, RuntimeError, wave.Error) as exc:
        raise NarrationError("中文配音暂时不可用，可关闭配音继续导出。") from exc
