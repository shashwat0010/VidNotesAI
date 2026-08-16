import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.services.s3 import s3_service

def sync_local_images_to_s3():
    uploads_dir = s3_service.uploads_base
    print(f"=== VidNotes AI AWS S3 Uploader ===")
    print(f"Target Bucket: {settings.S3_BUCKET_NAME}")
    print(f"Region: {settings.AWS_REGION}")
    print(f"Access Key ID: {settings.AWS_ACCESS_KEY_ID[:4]}***" if settings.AWS_ACCESS_KEY_ID else "No Access Key set!")
    
    if not settings.AWS_ACCESS_KEY_ID or settings.AWS_ACCESS_KEY_ID == "minioadmin":
        print("\n[!] Please set your real AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env first!")
        return

    if not s3_service.s3:
        print("\n[!] Could not initialize S3 client. Check credentials.")
        return

    uploaded_count = 0
    for root, _, files in os.walk(uploads_dir):
        for f in files:
            if f.endswith(('.jpg', '.jpeg', '.png', '.mp4', '.mp3')):
                local_path = os.path.join(root, f)
                rel_path = os.path.relpath(local_path, uploads_dir).replace('\\', '/')
                try:
                    s3_service.s3.upload_file(
                        local_path,
                        settings.S3_BUCKET_NAME,
                        rel_path,
                        ExtraArgs={"ContentType": "image/jpeg" if f.endswith('.jpg') else "binary/octet-stream"}
                    )
                    print(f"Uploaded: s3://{settings.S3_BUCKET_NAME}/{rel_path}")
                    uploaded_count += 1
                except Exception as e:
                    print(f"Failed to upload {rel_path}: {e}")

    print(f"\n[OK] Sync completed. Uploaded {uploaded_count} files to s3://{settings.S3_BUCKET_NAME}/")

if __name__ == "__main__":
    sync_local_images_to_s3()
