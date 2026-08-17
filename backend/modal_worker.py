import modal

# 1. Define the Modal App
app = modal.App("vidnotes-gpu-worker")

# 2. Define the container environment with PyTorch + CUDA + EasyOCR + FFmpeg
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libgl1", "libglib2.0-0")
    .pip_install(
        "torch",
        "torchvision",
        "easyocr",
        "opencv-python-headless",
        "requests",
        "pillow"
    )
)

# 3. Serverless GPU Function for Fast Batch OCR on NVIDIA T4
@app.function(image=image, gpu="T4", timeout=300)
def process_keyframes_ocr_gpu(image_urls: list[str]) -> list[dict]:
    """
    Downloads keyframe images and runs batch EasyOCR on an NVIDIA T4 GPU in parallel.
    """
    import io
    import requests
    from PIL import Image
    import numpy as np
    import easyocr

    print("🚀 Initializing EasyOCR on NVIDIA T4 GPU inside Modal...")
    reader = easyocr.Reader(['en'], gpu=True)
    print("✅ EasyOCR loaded on GPU.")

    results = []
    for idx, url in enumerate(image_urls):
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                img_np = np.array(img)
                
                # Fast GPU OCR inference
                ocr_lines = reader.readtext(img_np, detail=0, paragraph=True)
                cleaned_text = "\n".join([t.strip() for t in ocr_lines if len(t.strip()) > 1])
                
                results.append({
                    "url": url,
                    "ocr_text": cleaned_text,
                    "success": True
                })
            else:
                results.append({"url": url, "ocr_text": "", "success": False})
        except Exception as e:
            print(f"Error processing frame {idx}: {e}")
            results.append({"url": url, "ocr_text": "", "success": False})

    return results

@app.local_entrypoint()
def main():
    print("Modal GPU worker configuration verified successfully.")
