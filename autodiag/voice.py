import speech_recognition as sr
import threading
import tempfile
import os
import time
import logging

logger = logging.getLogger("synthai.voice")

tts_lock = threading.Lock()

# ВИПРАВЛЕНО: pygame ініціалізується лінивo, лише при першому виклику speak()
_pygame_initialized = False
_pygame_lock = threading.Lock()


def _init_pygame():
    global _pygame_initialized
    with _pygame_lock:
        if not _pygame_initialized:
            try:
                import pygame
                pygame.mixer.init()
                _pygame_initialized = True
            except Exception as e:
                logger.error(f"pygame init error: {e}")


recognizer = sr.Recognizer()
recognizer.energy_threshold = 300
recognizer.dynamic_energy_threshold = True
recognizer.pause_threshold = 1.5


def speak(text):
    with tts_lock:
        try:
            import asyncio
            import edge_tts

            _init_pygame()
            import pygame

            clean = text.replace("*", "").replace("#", "").replace("\n", " ").strip()
            clean = clean.replace("IRIS", "Айріс")
            clean = clean.replace("SynthAI", "Синт ЕІ")
            clean = clean.replace("OBD", "ОБД")
            clean = clean.replace("AI", "АІ")
            clean = clean[:800]

            async def generate():
                communicate = edge_tts.Communicate(clean, "uk-UA-PolinaNeural", rate="+10%")
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                await communicate.save(tmp.name)
                return tmp.name

            path = asyncio.run(generate())
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
            os.unlink(path)
        except Exception as e:
            logger.error(f"TTS error: {e}")


def listen(online: bool = True):
    """
    Розпізнає мову з мікрофону.
    При online=True використовує Google STT.
    При online=False або помилці мережі — повертає None (faster-whisper можна підключити тут).
    """
    try:
        with sr.Microphone(sample_rate=44100) as source:
            logger.info("Калібрую мікрофон...")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            logger.info("Слухаю...")
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=15)

        logger.info("Розпізнаю...")

        if online:
            try:
                text = recognizer.recognize_google(audio, language="uk-UA")
                logger.info(f"Розпізнано (Google): {text}")
                return text
            except sr.RequestError as e:
                logger.warning(f"Google STT недоступний (офлайн?): {e}")
                # Тут можна підключити faster-whisper як офлайн-fallback:
                # return _recognize_whisper(audio)
                return None
        else:
            # Офлайн: використати faster-whisper (якщо потрібно — розкоментуйте нижче)
            # return _recognize_whisper(audio)
            logger.info("Офлайн-режим: голос недоступний без faster-whisper")
            return None

    except sr.WaitTimeoutError:
        logger.info("Час очікування вичерпано")
        return None
    except sr.UnknownValueError:
        logger.info("Не вдалось розпізнати мову")
        return None
    except Exception as e:
        logger.error(f"STT error: {e}")
        return None


# Приклад офлайн-розпізнавання через faster-whisper (розкоментуйте при потребі):
# def _recognize_whisper(audio):
#     try:
#         from faster_whisper import WhisperModel
#         model = WhisperModel("small", device="cpu", compute_type="int8")
#         wav_data = audio.get_wav_data()
#         import io, soundfile as sf
#         audio_array, _ = sf.read(io.BytesIO(wav_data))
#         segments, _ = model.transcribe(audio_array, language="uk")
#         text = " ".join(s.text for s in segments).strip()
#         print(f"Розпізнано (Whisper): {text}")
#         return text if text else None
#     except Exception as e:
#         print(f"Whisper error: {e}")
#         return None
