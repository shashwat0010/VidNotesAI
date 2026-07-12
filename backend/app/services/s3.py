import boto3
from botocore.client import Config
from app.core.config import settings

class S3Service:
    def __init__(self):
        # Configure client for MinIO/S3
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL,
            config=Config(signature_version="s3v4")
        )
        self.bucket = settings.S3_BUCKET_NAME
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        try:
            self.s3.head_bucket(Bucket=self.bucket)
        except Exception:
            try:
                # If local or region configuration
                if settings.S3_ENDPOINT_URL:
                    self.s3.create_bucket(Bucket=self.bucket)
                else:
                    self.s3.create_bucket(
                        Bucket=self.bucket,
                        CreateBucketConfiguration={"LocationConstraint": settings.AWS_REGION}
                    )
            except Exception as e:
                print(f"Error creating bucket (it may already exist): {e}")

    def upload_file(self, local_path: str, s3_key: str, content_type: str = "binary/octet-stream") -> str:
        self.s3.upload_file(
            local_path,
            self.bucket,
            s3_key,
            ExtraArgs={"ContentType": content_type}
        )
        # Generate the access URL
        if settings.S3_ENDPOINT_URL:
            # Return a path routed through Nginx (/vidnotes-storage/...) so the
            # browser fetches images via Nginx (port 80) which proxies to minio:9000.
            # Returning localhost:9000 would bypass Nginx and fail in the browser.
            return f"/{self.bucket}/{s3_key}"
        else:
            return f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"

    def download_file(self, s3_key: str, local_path: str):
        self.s3.download_file(self.bucket, s3_key, local_path)

    def get_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": s3_key},
            ExpiresIn=expiration
        )

s3_service = S3Service()
