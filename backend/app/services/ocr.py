import os
from typing import Optional
import easyocr
import numpy as np
from PIL import Image

class OCRService:
    def __init__(self):
        self.reader = None

    def _load_reader(self):
        if self.reader is None:
            print("Initializing EasyOCR reader...")
            # We initialize EasyOCR with English language.
            # You can add other languages if needed.
            # gpu=False to run on CPU by default in standard Docker container
            self.reader = easyocr.Reader(['en'], gpu=False)
            print("EasyOCR reader initialized.")

    def extract_text(self, image_path: str) -> str:
        """
        Runs EasyOCR on an image and returns the combined text.
        """
        if not os.path.exists(image_path):
            return ""

        try:
            self._load_reader()
            
            # Read text
            results = self.reader.readtext(image_path)
            
            # Combine text results
            # results is a list of tuples: (bounding box, text, confidence)
            extracted_lines = []
            for result in results:
                text = result[1]
                extracted_lines.append(text)
                
            return "\n".join(extracted_lines)
        except Exception as e:
            print(f"OCR failed for {image_path}: {e}")
            return ""

ocr_service = OCRService()
