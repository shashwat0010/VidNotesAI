import os
from typing import List, Dict, Any
from app.core.config import settings

class WhisperService:
    def __init__(self):
        self.model = None

    def _load_model(self):
        if self.model is None:
            from faster_whisper import WhisperModel
            print(f"Loading Whisper model: {settings.WHISPER_MODEL} on {settings.WHISPER_DEVICE}...")
            self.model = WhisperModel(
                settings.WHISPER_MODEL,
                device=settings.WHISPER_DEVICE,
                compute_type=settings.WHISPER_COMPUTE_TYPE
            )
            print("Whisper model loaded successfully.")

    def transcribe(self, audio_path: str) -> List[Dict[str, Any]]:
        """
        Transcribes an audio file.
        Returns a list of segment dicts: [{"text": str, "start": float, "end": float}]
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        try:
            self._load_model()
            segments, info = self.model.transcribe(audio_path, beam_size=5)
            results = []
            for segment in segments:
                results.append({
                    "text": segment.text.strip(),
                    "start": round(segment.start, 2),
                    "end": round(segment.end, 2)
                })
            return results
        except Exception as err:
            print(f"[Whisper Notice] Transcription execution notice: {err}")
            return []

whisper_service = WhisperService()
