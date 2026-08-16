import os
from typing import Optional

class OCRService:
    def __init__(self):
        self.reader = None

    def _load_reader(self):
        if self.reader is None:
            import easyocr
            print("Initializing EasyOCR reader...")
            self.reader = easyocr.Reader(['en'], gpu=False)
            print("EasyOCR reader initialized.")

    def extract_text(self, image_path: str) -> str:
        """
        Runs fast EasyOCR on an image and returns the combined text.
        """
        if not os.path.exists(image_path):
            return ""

        try:
            self._load_reader()
            
            # Fast text extraction with detail=0 (returns strings directly without polygon computations)
            results = self.reader.readtext(image_path, detail=0, paragraph=True)
            if results:
                # Filter out pure noise lines
                cleaned = [t.strip() for t in results if len(t.strip()) > 1]
                return "\n".join(cleaned)
            return ""
        except Exception as e:
            print(f"[OCR Notice] OCR fast-read on {os.path.basename(image_path)}: {e}")
            return ""

ocr_service = OCRService()
