import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Response, BackgroundTasks
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
    background_tasks: BackgroundTasks,
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

    # Generate a user-scoped unique video ID so multiple users can process the same YouTube URL independently
    unique_video_id = f"{youtube_id}_{current_user.id}"

    # Check if already processed for this user
    result = await db.execute(select(Video).filter(Video.id == unique_video_id, Video.user_id == current_user.id))
    video = result.scalars().first()
    if video:
        # Re-trigger processing if previously stuck in pending or failed
        if video.status in ("pending", "failed"):
            video.status = "pending"
            await db.commit()
            background_tasks.add_task(process_video_pipeline, video.id, current_user.id)
            try:
                process_video_pipeline.delay(video.id, current_user.id)
            except Exception as e:
                print(f"Celery queue notice: {e}")
        return video

    # Initialize immediately with instant title & processing status (< 20ms)
    initial_title = f"YouTube Video ({youtube_id})"

    # Create new Video with status='processing' immediately
    new_video = Video(
        id=unique_video_id,
        title=initial_title,
        url=url,
        status="processing",
        user_id=current_user.id,
        folder_id=folder_id
    )
    db.add(new_video)
    await db.commit()
    await db.refresh(new_video)

    # Trigger processing pipeline immediately via FastAPI BackgroundTasks & Celery
    background_tasks.add_task(process_video_pipeline, new_video.id, current_user.id)
    try:
        process_video_pipeline.delay(new_video.id, current_user.id)
    except Exception as celery_err:
        print(f"Celery queue notice: {celery_err}")
    
    return new_video

@router.post("/upload", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    background_tasks: BackgroundTasks,
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
    await db.commit()
    await db.refresh(new_video)

    # Trigger processing pipeline
    background_tasks.add_task(process_video_pipeline, new_video.id, current_user.id)
    try:
        process_video_pipeline.delay(new_video.id, current_user.id)
    except Exception as celery_err:
        print(f"Celery queue notice: {celery_err}")

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

@router.get("/media/{key:path}")
async def get_media_proxy(key: str):
    """
    Authenticated proxy to serve S3 keyframe images directly to browser.
    """
    local_path = os.path.join(s3_service.uploads_base, key)
    if os.path.exists(local_path):
        with open(local_path, "rb") as f:
            content = f.read()
        return Response(content=content, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})

    # Fetch from S3
    if s3_service.s3:
        try:
            s3_obj = s3_service.s3.get_object(Bucket=s3_service.bucket, Key=key)
            content = s3_obj["Body"].read()
            # Save locally for caching
            try:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(content)
            except Exception:
                pass
            return Response(content=content, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
        except Exception as e:
            print(f"S3 fetch error for key {key}: {e}")

    raise HTTPException(status_code=404, detail="Media file not found")

@router.get("/{video_id}/transcript", response_model=List[TranscriptSegmentResponse])
async def get_transcript(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
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

    import re
    from urllib.parse import quote

    # Sanitize title for HTTP latin-1 headers (ASCII safe filename + UTF-8 filename*)
    clean_title = re.sub(r'[^\w\s-]', '', video.title).strip().replace(' ', '_') or "notes"
    
    from app.models.models import Keyframe
    kf_res = await db.execute(
        select(Keyframe).filter(Keyframe.video_id == video_id).order_by(Keyframe.timestamp.asc())
    )
    keyframes = kf_res.scalars().all()

    if format_type.lower() == "markdown":
        content = export_service.generate_markdown(note, video.title, keyframes)
        utf8_filename = quote(f"{video.title}_notes.md")
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{clean_title}_notes.md"; filename*=UTF-8\'\'{utf8_filename}'}
        )
    elif format_type.lower() == "docx":
        content = export_service.generate_docx(note, video.title, keyframes)
        utf8_filename = quote(f"{video.title}_notes.docx")
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{clean_title}_notes.docx"; filename*=UTF-8\'\'{utf8_filename}'}
        )
    elif format_type.lower() == "pdf":
        from app.models.models import Keyframe
        kf_res = await db.execute(
            select(Keyframe).filter(Keyframe.video_id == video_id).order_by(Keyframe.timestamp.asc())
        )
        keyframes = kf_res.scalars().all()
        content = export_service.generate_pdf(note, video.title, keyframes)
        utf8_filename = quote(f"{video.title}_notes.pdf")
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{clean_title}_notes.pdf"; filename*=UTF-8\'\'{utf8_filename}'}
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
        consolidated_elements.append(f"[{int(seg.start_time // 60):02d}:{int(seg.start_time % 60):02d}] (Transcript): {seg.text}")

    for kf in keyframes:
        time_str = f"[{int(kf.timestamp // 60):02d}:{int(kf.timestamp % 60):02d}]"
        if kf.vision_description:
            consolidated_elements.append(f"{time_str} (Visual Screen Layout): {kf.vision_description}")
        if kf.ocr_text:
            consolidated_elements.append(f"{time_str} (Visual Text/OCR): {kf.ocr_text}")

    return "\n".join(consolidated_elements)


def _is_placeholder_flashcards(flashcards: list) -> bool:
    if not flashcards:
        return True
    # Check if flashcards match generic rule-based fallback
    return any("The concepts discussed in the video transcript" in str(f.get("answer", "")) for f in flashcards)


def _is_placeholder_quiz(mcqs: list) -> bool:
    if not mcqs or len(mcqs) <= 2:
        return True
    # Check if quiz matches generic rule-based fallback
    return any("pgvector embeddings" in str(m.get("question", "")) or "pgvector embeddings" in str(m.get("answer", "")) for m in mcqs)


@router.get("/{video_id}/flashcards")
@router.get("/{video_id}/notes/flashcards")
async def get_on_demand_flashcards(
    video_id: str,
    regenerate: bool = False,
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

    # Check if already generated and NOT placeholder
    if note.flashcards and not _is_placeholder_flashcards(note.flashcards) and not regenerate:
        return note.flashcards

    # Generate on-demand
    knowledge = await _get_compiled_knowledge(video_id, db)
    flashcards = llm_service.generate_flashcards(knowledge[:12000])
    
    # Save back to database
    note.flashcards = flashcards
    await db.commit()
    return flashcards


@router.get("/{video_id}/quiz")
@router.get("/{video_id}/notes/quiz")
async def get_on_demand_quiz(
    video_id: str,
    regenerate: bool = False,
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

    # Check if already generated and NOT placeholder
    if note.mcqs and not _is_placeholder_quiz(note.mcqs) and not regenerate:
        return note.mcqs

    # Generate on-demand
    knowledge = await _get_compiled_knowledge(video_id, db)
    mcqs = llm_service.generate_quiz(knowledge[:12000])
    
    # Save back to database
    note.mcqs = mcqs
    await db.commit()
    return mcqs


@router.get("/{video_id}/mindmap")
@router.get("/{video_id}/notes/mindmap")
async def get_on_demand_mindmap(
    video_id: str,
    regenerate: bool = False,
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

    # Check if already generated and clean
    if note.mindmap and not regenerate:
        is_corrupt = "thinking process" in note.mindmap.lower() or "here's a" in note.mindmap.lower() or ("-->" not in note.mindmap and "---" not in note.mindmap)
        if not is_corrupt:
            return {"mindmap": note.mindmap}

    # Generate on-demand
    knowledge = await _get_compiled_knowledge(video_id, db)
    mindmap = llm_service.generate_mindmap(knowledge[:12000])
    
    # Save back to database
    note.mindmap = mindmap
    await db.commit()
    return {"mindmap": mindmap}


@router.post("/{video_id}/notes/regenerate", response_model=NoteOutputResponse)
async def regenerate_notes(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    v_res = await db.execute(select(Video).filter(Video.id == video_id, Video.user_id == current_user.id))
    if not v_res.scalars().first():
        raise HTTPException(status_code=404, detail="Video workspace not found")

    knowledge = await _get_compiled_knowledge(video_id, db)
    kf_res = await db.execute(select(Keyframe).filter(Keyframe.video_id == video_id).order_by(Keyframe.timestamp.asc()))
    kfs = kf_res.scalars().all()
    keyframes_data = [{
        "timestamp": kf.timestamp,
        "s3_url": kf.s3_url,
        "vision_description": kf.vision_description,
        "ocr_text": kf.ocr_text
    } for kf in kfs]
    pkg = llm_service.generate_notes_package(knowledge[:12000], keyframes=keyframes_data)

    takeaways_raw = pkg.get("takeaways", "")
    if isinstance(takeaways_raw, list):
        takeaways_str = "\n".join(f"- {item}" for item in takeaways_raw)
    elif isinstance(takeaways_raw, dict):
        takeaways_str = "\n".join(f"- **{k}**: {v}" for k, v in takeaways_raw.items())
    else:
        takeaways_str = str(takeaways_raw)

    glossary_raw = pkg.get("glossary", "")
    if isinstance(glossary_raw, dict):
        glossary_str = "\n".join(f"- **{k}**: {v}" for k, v in glossary_raw.items())
    elif isinstance(glossary_raw, list):
        glossary_str = "\n".join(f"- {item}" for item in glossary_raw)
    else:
        glossary_str = str(glossary_raw)

    revision_raw = pkg.get("revision_notes", "")
    if isinstance(revision_raw, dict):
        revision_str = "\n\n".join(f"### {k.replace('_', ' ').title()}\n{v}" for k, v in revision_raw.items())
    elif isinstance(revision_raw, list):
        revision_str = "\n".join(f"- {item}" for item in revision_raw)
    else:
        revision_str = str(revision_raw)

    note_res = await db.execute(select(NoteOutput).filter(NoteOutput.video_id == video_id))
    note = note_res.scalars().first()
    if not note:
        note = NoteOutput(video_id=video_id)
        db.add(note)

    note.summary_exec = pkg.get("summary_exec", "")
    note.summary_detailed = pkg.get("summary_detailed", "")
    note.revision_notes = revision_str
    note.takeaways = takeaways_str
    note.glossary = glossary_str
    await db.commit()
    await db.refresh(note)
    return note


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Find video
    v_res = await db.execute(select(Video).filter(Video.id == video_id))
    video = v_res.scalars().first()
    if not video:
        raise HTTPException(status_code=404, detail="Video record not found")

    from app.models.models import ChunkEmbedding, ChatMessage
    from sqlalchemy import delete as sql_delete

    # Cascade delete associated records
    await db.execute(sql_delete(NoteOutput).where(NoteOutput.video_id == video_id))
    await db.execute(sql_delete(TranscriptSegment).where(TranscriptSegment.video_id == video_id))
    await db.execute(sql_delete(Keyframe).where(Keyframe.video_id == video_id))
    await db.execute(sql_delete(ChunkEmbedding).where(ChunkEmbedding.video_id == video_id))
    await db.execute(sql_delete(ChatMessage).where(ChatMessage.video_id == video_id))
    await db.execute(sql_delete(Video).where(Video.id == video_id))
    await db.commit()

    # Clean up local keyframe images
    import shutil
    uploads_kf_dir = os.path.join(s3_service.uploads_base, "keyframes", video_id)
    if os.path.exists(uploads_kf_dir):
        shutil.rmtree(uploads_kf_dir, ignore_errors=True)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


