import os
from typing import Optional

class OCRService:
    def __init__(self):
        self.reader = None

    def _load_reader(self):
        if self.reader is None:
            import easyocr
            import torch
            has_gpu = torch.cuda.is_available()
            device_str = f"GPU ({torch.cuda.get_device_name(0)})" if has_gpu else "CPU"
            print(f"Initializing EasyOCR reader on {device_str}...")
            self.reader = easyocr.Reader(['en'], gpu=has_gpu)
            print(f"EasyOCR reader initialized on {device_str}.")

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

    def extract_batch_gpu_modal(self, image_urls: list[str]) -> Optional[list[dict]]:
        """
        Invokes deployed Modal serverless NVIDIA T4 GPU function to process all keyframes in parallel.
        Returns list of {'url': ..., 'ocr_text': ..., 'success': True} or None if Modal is unavailable.
        """
        if not image_urls:
            return []
        try:
            import modal
            print(f"⚡ Dispatching {len(image_urls)} keyframes to Modal Serverless GPU (NVIDIA T4)...")
            f = modal.Function.from_name("vidnotes-gpu-worker", "process_keyframes_ocr_gpu")
            gpu_results = f.remote(image_urls)
            print(f"✅ Received {len(gpu_results)} GPU OCR outputs from Modal.")
            return gpu_results
        except Exception as e:
            print(f"[Modal GPU Notice] Modal serverless invocation skipped ({e}). Falling back to local OCR engine.")
            return None

ocr_service = OCRService()
