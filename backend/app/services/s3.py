import os
import shutil
import boto3
from botocore.client import Config
from app.core.config import settings

class S3Service:
    def __init__(self):
        self.bucket = settings.S3_BUCKET_NAME
        self._s3_client = None
        self._minio_available = None  # None = untested, True = reachable, False = offline
        self.uploads_base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
        os.makedirs(self.uploads_base, exist_ok=True)

    @property
    def s3(self):
        if self._s3_client is None:
            endpoint = settings.S3_ENDPOINT_URL.strip() if settings.S3_ENDPOINT_URL and settings.S3_ENDPOINT_URL.strip() else None
            try:
                self._s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_REGION,
                    endpoint_url=endpoint,
                    config=Config(signature_version="s3v4", connect_timeout=1.5, read_timeout=3)
                )
            except Exception as e:
                print(f"[Storage S3 Notice] S3 Client init notice: {e}")
        return self._s3_client

    def _save_local(self, local_path: str, s3_key: str) -> str:
        """Saves file directly to local uploads directory (fast disk fallback)."""
        target_file_path = os.path.join(self.uploads_base, s3_key)
        os.makedirs(os.path.dirname(target_file_path), exist_ok=True)
        shutil.copy2(local_path, target_file_path)
        return f"/uploads/{s3_key}"

    def upload_file(self, local_path: str, s3_key: str, content_type: str = "binary/octet-stream") -> str:
        # Always maintain local copy for fast export PDF/DOCX building
        self._save_local(local_path, s3_key)

        if not self.s3:
            return f"/uploads/{s3_key}"

        try:
            self.s3.upload_file(
                local_path,
                self.bucket,
                s3_key,
                ExtraArgs={"ContentType": content_type}
            )
            self._minio_available = True
            print(f"[Storage] Successfully uploaded keyframe to S3 bucket '{self.bucket}': {s3_key}")
            if settings.S3_ENDPOINT_URL and settings.S3_ENDPOINT_URL.strip():
                return f"/{self.bucket}/{s3_key}"
            else:
                return f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
        except Exception as err:
            if self._minio_available is not False:
                print(f"[Storage] S3 cloud upload notice: {err} (using local disk storage)")
                self._minio_available = False
            return f"/uploads/{s3_key}"

    def download_file(self, s3_key: str, local_path: str):
        # Check local disk first
        local_stored = os.path.join(self.uploads_base, s3_key)
        if os.path.exists(local_stored):
            shutil.copy2(local_stored, local_path)
            return

        if self.s3 and self._minio_available is not False:
            try:
                self.s3.download_file(self.bucket, s3_key, local_path)
                return
            except Exception as e:
                print(f"[Storage] S3 download notice: {e}")

    def get_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        if self._minio_available is False or not self.s3:
            return f"/uploads/{s3_key}"
        try:
            return self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": s3_key},
                ExpiresIn=expiration
            )
        except Exception:
            return f"/uploads/{s3_key}"

s3_service = S3Service()

