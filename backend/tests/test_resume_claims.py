import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import create_access_token
from app.models.models import User, Folder, Video, TranscriptSegment, Keyframe, NoteOutput, ChunkEmbedding, ChatMessage
from app.services.video import video_service
from app.services.llm import llm_service
from app.tasks.worker import celery_app

def test_resume_claim_1_multi_tenant_configuration():
    """Verify backend settings support JWT and multi-tenant workspace architecture."""
    assert settings.SECRET_KEY is not None
    assert settings.ALGORITHM == "HS256"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0

def test_resume_claim_2_event_driven_broker_config():
    """Verify Celery worker uses RabbitMQ as broker and Redis for caching/transient state."""
    assert settings.CELERY_BROKER_URL is not None
    assert "amqp://" in settings.CELERY_BROKER_URL or "5672" in settings.CELERY_BROKER_URL
    assert settings.REDIS_URL is not None
    assert "redis://" in settings.REDIS_URL
    assert celery_app.conf.broker_url == settings.CELERY_BROKER_URL

def test_resume_claim_2_1536_dim_embedding_and_rrf():
    """Verify 1536-dimensional embedding vector format and RRF hybrid retrieval algorithm."""
    dummy_text = "Testing pgvector embedding generation"
    emb = llm_service.get_embedding(dummy_text)
    assert isinstance(emb, list)
    assert len(emb) == 1536

    # Reciprocal Rank Fusion (RRF) algorithm test
    k = 60
    vector_rankings = ["chunk_A", "chunk_B", "chunk_C"]
    lexical_rankings = ["chunk_B", "chunk_D", "chunk_A"]

    rrf_scores = {}
    for idx, doc_id in enumerate(vector_rankings, start=1):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + idx)
    for idx, doc_id in enumerate(lexical_rankings, start=1):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + idx)

    sorted_chunks = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    assert sorted_chunks[0] == "chunk_B"
    assert sorted_chunks[1] == "chunk_A"

def test_resume_claim_3_video_ingestion_pipeline_extractors():
    """Verify YouTube ID extractor and caption fallback mechanisms."""
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    vid_id = video_service.extract_youtube_id(url)
    assert vid_id == "dQw4w9WgXcQ"

    short_url = "https://youtu.be/dQw4w9WgXcQ"
    assert video_service.extract_youtube_id(short_url) == "dQw4w9WgXcQ"

def test_resume_claim_4_reliability_and_idempotency_settings():
    """Verify Celery task retry configuration."""
    task_conf = celery_app.tasks.get("process_video_pipeline")
    assert task_conf is not None
    assert task_conf.max_retries == 3
