from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.core.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True) # Null for pure OAuth users
    oauth_provider = Column(String(50), default="email") # email, google, github
    oauth_id = Column(String(255), unique=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    videos = relationship("Video", back_populates="user", cascade="all, delete-orphan")
    folders = relationship("Folder", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")


class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="folders")
    subfolders = relationship("Folder", cascade="all, delete-orphan")
    videos = relationship("Video", back_populates="folder")


class Video(Base):
    __tablename__ = "videos"

    id = Column(String(50), primary_key=True, index=True) # UUID or YouTube ID
    title = Column(String(255), nullable=False)
    url = Column(Text, nullable=True)  # YouTube URL if present
    file_path = Column(Text, nullable=True)  # S3 bucket object key
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    duration = Column(Float, nullable=True)  # in seconds
    size = Column(Integer, nullable=True)  # in bytes
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    folder_id = Column(Integer, ForeignKey("folders.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="videos")
    folder = relationship("Folder", back_populates="videos")
    transcript_segments = relationship("TranscriptSegment", back_populates="video", cascade="all, delete-orphan")
    keyframes = relationship("Keyframe", back_populates="video", cascade="all, delete-orphan")
    note_output = relationship("NoteOutput", back_populates="video", uselist=False, cascade="all, delete-orphan")
    embeddings = relationship("ChunkEmbedding", back_populates="video", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="video", cascade="all, delete-orphan")


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String(50), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    start_time = Column(Float, nullable=False)  # seconds
    end_time = Column(Float, nullable=False)    # seconds

    video = relationship("Video", back_populates="transcript_segments")


class Keyframe(Base):
    __tablename__ = "keyframes"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String(50), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(Float, nullable=False)  # seconds
    s3_url = Column(Text, nullable=False)      # URL path to storage
    ocr_text = Column(Text, nullable=True)
    vision_description = Column(Text, nullable=True)

    video = relationship("Video", back_populates="keyframes")


class NoteOutput(Base):
    __tablename__ = "note_outputs"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String(50), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, unique=True)
    summary_exec = Column(Text, nullable=False)
    summary_detailed = Column(Text, nullable=False)
    revision_notes = Column(Text, nullable=False)
    takeaways = Column(Text, nullable=False)
    glossary = Column(Text, nullable=False)
    flashcards = Column(JSON, nullable=False)  # JSON List of {question, answer}
    mcqs = Column(JSON, nullable=False)        # JSON List of {question, options: List[str], answer: str, explanation: str}
    mindmap = Column(Text, nullable=False)      # Mermaid syntax string
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="note_output")


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String(50), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    embedding = Column(Vector(1536), nullable=False)  # 1536 dimensions vector (OpenAI text-embedding-3-small standard)

    video = relationship("Video", back_populates="embeddings")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String(50), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user or assistant
    content = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True)    # JSON List of {text: str, start_time: float, end_time: float}
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="chat_messages")
    user = relationship("User", back_populates="chat_messages")
