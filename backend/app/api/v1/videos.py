import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.db import get_db
from app.api.v1.auth import get_current_user
from app.models.models import User, Video, Folder, TranscriptSegment, Keyframe, NoteOutput
from app.schemas.schemas import VideoResponse, NoteOutputResponse, TranscriptSegmentResponse, KeyframeResponse
from app.services.video import video_service
from app.services.s3 import s3_service
from app.services.export import export_service
from app.services.llm import llm_service
from app.tasks.worker import process_video_pipeline

router = APIRouter()

@router.get("/", response_model=List[VideoResponse])
async def list_videos(
    folder_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Video).filter(Video.user_id == current_user.id)
    if folder_id is not None:
        query = query.filter(Video.folder_id == folder_id)
    
    result = await db.execute(query.order_by(Video.created_at.desc()))
    return result.scalars().all()

@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Video).filter(Video.id == video_id, Video.user_id == current_user.id)
    )
    video = result.scalars().first()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video record not found"
        )
    return video

@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Video).filter(Video.id == video_id, Video.user_id == current_user.id)
    )
    video = result.scalars().first()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video record not found or unauthorized access"
        )
    
    # We can delete S3 object asynchronously or immediately
    if video.file_path:
        try:
            s3_service.s3.delete_object(Bucket=s3_service.bucket, Key=video.file_path)
        except Exception as s3_err:
            print(f"Error removing video file from S3: {s3_err}")
            
    await db.delete(video)
    return None

@router.post("/youtube", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def process_youtube(
    url: str = Form(...),
    folder_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    youtube_id = video_service.extract_youtube_id(url)
    if not youtube_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid YouTube URL syntax"
        )

    # Check if folder exists and belongs to user
    if folder_id:
        f_res = await db.execute(select(Folder).filter(Folder.id == folder_id, Folder.user_id == current_user.id))
        if not f_res.scalars().first():
            raise HTTPException(status_code=404, detail="Selected folder not found")

    # Check if already processed
    result = await db.execute(select(Video).filter(Video.id == youtube_id, Video.user_id == current_user.id))
    video = result.scalars().first()
    if video:
        return video

    # Create new Video
    new_video = Video(
        id=youtube_id,
        title="Processing YouTube Video...",
        url=url,
        status="pending",
        user_id=current_user.id,
        folder_id=folder_id
    )
    db.add(new_video)
    await db.flush()

    # Trigger Celery background pipeline
    process_video_pipeline.delay(new_video.id, current_user.id)
    
    return new_video

@router.post("/upload", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    folder_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if folder exists
    if folder_id:
        f_res = await db.execute(select(Folder).filter(Folder.id == folder_id, Folder.user_id == current_user.id))
        if not f_res.scalars().first():
            raise HTTPException(status_code=404, detail="Selected folder not found")

    # Save to local temp workspace
    video_id = uuid.uuid4().hex
    file_ext = os.path.splitext(file.filename)[1]
    
    temp_local_path = os.path.join(settings.UPLOAD_DIR, f"{video_id}{file_ext}")
    
    # Read/Write file chunks
    size = 0
    with open(temp_local_path, "wb") as buffer:
        while True:
            chunk = await file.read(1024 * 1024)  # 1MB chunks
            if not chunk:
                break
            size += len(chunk)
            if size > settings.MAX_UPLOAD_SIZE:
                os.remove(temp_local_path)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Upload exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE / (1024*1024)}MB"
                )
            buffer.write(chunk)

    # Upload to S3/MinIO
    s3_key = f"uploads/{current_user.id}/{video_id}{file_ext}"
    s3_service.upload_file(temp_local_path, s3_key, content_type=file.content_type)
    
    # Clean up local temporary file after S3 upload is complete
    if os.path.exists(temp_local_path):
        os.remove(temp_local_path)

    # Create Video record
    new_video = Video(
        id=video_id,
        title=file.filename,
        file_path=s3_key,
        size=size,
        status="pending",
        user_id=current_user.id,
        folder_id=folder_id
    )
    db.add(new_video)
    await db.flush()

    # Trigger Celery worker process
    process_video_pipeline.delay(new_video.id, current_user.id)

    return new_video

@router.get("/{video_id}/notes", response_model=NoteOutputResponse)
async def get_notes(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify owner
    v_res = await db.execute(select(Video).filter(Video.id == video_id, Video.user_id == current_user.id))
    video = v_res.scalars().first()
    if not video:
        raise HTTPException(status_code=404, detail="Video workspace not found")

    result = await db.execute(
        select(NoteOutput).filter(NoteOutput.video_id == video_id)
    )
    note = result.scalars().first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notes have not finished generating for this video."
        )
    return note

@router.get("/{video_id}/transcript", response_model=List[TranscriptSegmentResponse])
async def get_transcript(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify owner
    v_res = await db.execute(select(Video).filter(Video.id == video_id, Video.user_id == current_user.id))
    if not v_res.scalars().first():
         raise HTTPException(status_code=404, detail="Video workspace not found")

    result = await db.execute(
        select(TranscriptSegment)
        .filter(TranscriptSegment.video_id == video_id)
        .order_by(TranscriptSegment.start_time.asc())
    )
    return result.scalars().all()

@router.get("/{video_id}/keyframes", response_model=List[KeyframeResponse])
async def get_keyframes(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify owner
    v_res = await db.execute(select(Video).filter(Video.id == video_id, Video.user_id == current_user.id))
    if not v_res.scalars().first():
         raise HTTPException(status_code=404, detail="Video workspace not found")

    result = await db.execute(
        select(Keyframe)
        .filter(Keyframe.video_id == video_id)
        .order_by(Keyframe.timestamp.asc())
    )
    return result.scalars().all()

@router.get("/{video_id}/export/{format_type}")
async def export_workspace_notes(
    video_id: str,
    format_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify owner
    v_res = await db.execute(select(Video).filter(Video.id == video_id, Video.user_id == current_user.id))
    video = v_res.scalars().first()
    if not video:
        raise HTTPException(status_code=404, detail="Video workspace not found")

    note_res = await db.execute(select(NoteOutput).filter(NoteOutput.video_id == video_id))
    note = note_res.scalars().first()
    if not note:
        raise HTTPException(status_code=400, detail="Notes are not processed yet.")

    title = video.title.replace(" ", "_")
    
    if format_type.lower() == "markdown":
        content = export_service.generate_markdown(note, video.title)
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={title}_notes.md"}
        )
    elif format_type.lower() == "docx":
        from app.models.models import Keyframe
        kf_res = await db.execute(
            select(Keyframe).filter(Keyframe.video_id == video_id).order_by(Keyframe.timestamp.asc())
        )
        keyframes = kf_res.scalars().all()
        content = export_service.generate_docx(note, video.title, keyframes)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={title}_notes.docx"}
        )
    elif format_type.lower() == "pdf":
        from app.models.models import Keyframe
        kf_res = await db.execute(
            select(Keyframe).filter(Keyframe.video_id == video_id).order_by(Keyframe.timestamp.asc())
        )
        keyframes = kf_res.scalars().all()
        content = export_service.generate_pdf(note, video.title, keyframes)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={title}_notes.pdf"}
        )
    else:
        raise HTTPException(status_code=400, detail="Supported export formats are 'markdown', 'docx', and 'pdf'.")


async def _get_compiled_knowledge(video_id: str, db: AsyncSession) -> str:
    t_res = await db.execute(
        select(TranscriptSegment)
        .filter(TranscriptSegment.video_id == video_id)
        .order_by(TranscriptSegment.start_time.asc())
    )
    segments = t_res.scalars().all()

    k_res = await db.execute(
        select(Keyframe)
        .filter(Keyframe.video_id == video_id)
        .order_by(Keyframe.timestamp.asc())
    )
    keyframes = k_res.scalars().all()

    consolidated_elements = []
    for seg in segments:
        consolidated_elements.append({
            "time": seg.start_time,
            "type": "transcript",
            "content": seg.text
        })
    for kf in keyframes:
        content = f"[Slide/Visual Analysis]: {kf.vision_description or ''} [Text found in frame]: {kf.ocr_text or ''}"
        consolidated_elements.append({
            "time": kf.timestamp,
            "type": "keyframe",
            "content": content
        })

    consolidated_elements.sort(key=lambda x: x["time"])

    full_timeline_text = []
    for el in consolidated_elements:
        mins = int(el["time"] // 60)
        secs = int(el["time"] % 60)
        timestamp_str = f"[{mins:02d}:{secs:02d}]"
        if el["type"] == "transcript":
            full_timeline_text.append(f"{timestamp_str} (Transcript): {el['content']}")
        else:
            full_timeline_text.append(f"{timestamp_str} (Slide/Visual): {el['content']}")
            
    return "\n".join(full_timeline_text)


@router.get("/{video_id}/notes/flashcards")
async def get_on_demand_flashcards(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify owner
    v_res = await db.execute(select(Video).filter(Video.id == video_id, Video.user_id == current_user.id))
    if not v_res.scalars().first():
        raise HTTPException(status_code=404, detail="Video workspace not found")

    note_res = await db.execute(select(NoteOutput).filter(NoteOutput.video_id == video_id))
    note = note_res.scalars().first()
    if not note:
        raise HTTPException(status_code=400, detail="Executive summary and notes have not generated yet.")

    # Check if already generated (not empty list)
    if note.flashcards:
        return note.flashcards

    # Generate on-demand
    knowledge = await _get_compiled_knowledge(video_id, db)
    flashcards = llm_service.generate_flashcards(knowledge[:12000])
    
    # Save back to database
    note.flashcards = flashcards
    await db.commit()
    return flashcards


@router.get("/{video_id}/notes/quiz")
async def get_on_demand_quiz(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify owner
    v_res = await db.execute(select(Video).filter(Video.id == video_id, Video.user_id == current_user.id))
    if not v_res.scalars().first():
        raise HTTPException(status_code=404, detail="Video workspace not found")

    note_res = await db.execute(select(NoteOutput).filter(NoteOutput.video_id == video_id))
    note = note_res.scalars().first()
    if not note:
        raise HTTPException(status_code=400, detail="Executive summary and notes have not generated yet.")

    # Check if already generated
    if note.mcqs:
        return note.mcqs

    # Generate on-demand
    knowledge = await _get_compiled_knowledge(video_id, db)
    mcqs = llm_service.generate_quiz(knowledge[:12000])
    
    # Save back to database
    note.mcqs = mcqs
    await db.commit()
    return mcqs


@router.get("/{video_id}/notes/mindmap")
async def get_on_demand_mindmap(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify owner
    v_res = await db.execute(select(Video).filter(Video.id == video_id, Video.user_id == current_user.id))
    if not v_res.scalars().first():
        raise HTTPException(status_code=404, detail="Video workspace not found")

    note_res = await db.execute(select(NoteOutput).filter(NoteOutput.video_id == video_id))
    note = note_res.scalars().first()
    if not note:
        raise HTTPException(status_code=400, detail="Executive summary and notes have not generated yet.")

    # Check if already generated
    if note.mindmap:
        return {"mindmap": note.mindmap}

    # Generate on-demand
    knowledge = await _get_compiled_knowledge(video_id, db)
    mindmap = llm_service.generate_mindmap(knowledge[:12000])
    
    # Save back to database
    note.mindmap = mindmap
    await db.commit()
    return {"mindmap": mindmap}

