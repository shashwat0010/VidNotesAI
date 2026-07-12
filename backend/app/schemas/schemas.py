from pydantic import BaseModel, EmailStr, HttpUrl
from typing import List, Optional, Any
from datetime import datetime

# Auth Schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    oauth_provider: str
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class TokenData(BaseModel):
    email: Optional[str] = None


# Folder Schemas
class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None

class FolderResponse(BaseModel):
    id: int
    name: str
    parent_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# Video Schemas
class VideoCreate(BaseModel):
    url: Optional[str] = None
    folder_id: Optional[int] = None

class VideoResponse(BaseModel):
    id: str
    title: str
    url: Optional[str]
    status: str
    error_message: Optional[str]
    duration: Optional[float]
    size: Optional[int]
    folder_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# Transcript Schemas
class TranscriptSegmentResponse(BaseModel):
    id: int
    start_time: float
    end_time: float
    text: str

    class Config:
        from_attributes = True


# Keyframe Schemas
class KeyframeResponse(BaseModel):
    id: int
    timestamp: float
    s3_url: str
    ocr_text: Optional[str]
    vision_description: Optional[str]

    class Config:
        from_attributes = True


# Notes & AI Outputs
class Flashcard(BaseModel):
    question: str
    answer: str

class MCQ(BaseModel):
    question: str
    options: List[str]
    answer: str
    explanation: str

class NoteOutputResponse(BaseModel):
    video_id: str
    summary_exec: str
    summary_detailed: str
    revision_notes: str
    takeaways: str
    glossary: str
    flashcards: List[Flashcard]
    mcqs: List[MCQ]
    mindmap: str
    created_at: datetime

    class Config:
        from_attributes = True


# Chat Schemas
class ChatMessageCreate(BaseModel):
    content: str

class Citation(BaseModel):
    text: str
    start_time: float
    end_time: float

class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    citations: Optional[List[Citation]]
    created_at: datetime

    class Config:
        from_attributes = True
        
class SearchResultResponse(BaseModel):
    text: str
    start_time: float
    end_time: float
    score: float
