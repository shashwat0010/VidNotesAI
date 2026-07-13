import os
import shutil
import uuid
import numpy as np
from celery import Celery
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.db import SessionLocal
from app.models.models import Video, TranscriptSegment, Keyframe, NoteOutput, ChunkEmbedding
from app.services.video import video_service
from app.services.s3 import s3_service
from app.services.whisper import whisper_service
from app.services.ocr import ocr_service
from app.services.llm import llm_service

# Initialize Celery
celery_app = Celery("tasks", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True
)

@celery_app.task(name="process_video_pipeline", bind=True, max_retries=1)
def process_video_pipeline(self, video_id: str, user_id: int):
    """
    Background processing pipeline. Downloads/loads file, generates transcript,
    extracts keyframes, OCRs slides, queries vision, indexes RAG database,
    and runs LLM notes generator.
    """
    db: Session = SessionLocal()
    
    # Track paths for clean up
    temp_dir = os.path.join(settings.UPLOAD_DIR, video_id)
    os.makedirs(temp_dir, exist_ok=True)
    
    local_video_path = None
    local_audio_path = None
    
    try:
        # 1. Update status to processing
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found in database.")
            
        video.status = "processing"
        db.commit()
        
        # 2. Retrieve video file
        if video.url:
            print(f"Downloading YouTube content for video ID: {video_id}")
            # Get metadata first
            meta = video_service.get_youtube_metadata(video.url)
            video.title = meta.get("title", video.title)
            video.duration = meta.get("duration", 0.0)
            db.commit()

            # Attempt to fetch captions first
            captions = video_service.fetch_youtube_captions(video_id)
            
            # Download video file locally (needed for keyframe extraction)
            raw_video_filename = f"video_{uuid.uuid4().hex}.mp4"
            local_video_path = os.path.join(temp_dir, raw_video_filename)
            video_service.download_youtube_video(video.url, local_video_path)
        else:
            print(f"Retrieving uploaded file from S3: {video.file_path}")
            # Uploaded file
            file_extension = os.path.splitext(video.file_path)[1]
            local_video_name = f"video_{uuid.uuid4().hex}{file_extension}"
            local_video_path = os.path.join(temp_dir, local_video_name)
            s3_service.download_file(video.file_path, local_video_path)
            
            # Determine duration
            video.duration = video_service.get_video_duration(local_video_path)
            db.commit()
            
            captions = None # Uploaded files never have pre-fetched YouTube captions

        # 3. Transcribe if no captions
        raw_segments = []
        if captions:
            print("Using YouTube pre-existing captions.")
            for cap in captions:
                start = cap["start"]
                duration = cap["duration"]
                raw_segments.append({
                    "text": cap["text"],
                    "start": start,
                    "end": start + duration
                })
        else:
            print("Captions missing. Performing audio extraction & Whisper transcription...")
            # Extract audio
            local_audio_path = os.path.join(temp_dir, f"audio_{uuid.uuid4().hex}.mp3")
            video_service.extract_audio_from_video(local_video_path, local_audio_path)
            
            # Run Whisper transcription
            transcription_results = whisper_service.transcribe(local_audio_path)
            for seg in transcription_results:
                raw_segments.append({
                    "text": seg["text"],
                    "start": seg["start"],
                    "end": seg["end"]
                })

        # Group transcript segments to avoid excessive 2-3 second timestamps
        segments_data = []
        if raw_segments:
            current_chunk = []
            chunk_start = None
            for seg in raw_segments:
                txt = seg["text"].strip()
                if not txt:
                    continue
                if chunk_start is None:
                    chunk_start = seg["start"]
                current_chunk.append(txt)
                chunk_end = seg["end"]
                
                # Check if group duration reaches at least 20 seconds
                if (chunk_end - chunk_start) >= 20.0:
                    segments_data.append({
                        "text": " ".join(current_chunk),
                        "start": chunk_start,
                        "end": chunk_end
                    })
                    current_chunk = []
                    chunk_start = None
            if current_chunk:
                segments_data.append({
                    "text": " ".join(current_chunk),
                    "start": chunk_start,
                    "end": chunk_end
                })

        # Save transcript segments to DB
        for seg in segments_data:
            db_seg = TranscriptSegment(
                video_id=video_id,
                text=seg["text"],
                start_time=seg["start"],
                end_time=seg["end"]
            )
            db.add(db_seg)
        db.commit()

        # 4. Extract keyframes and perform OCR + Vision
        print("Extracting keyframes...")
        frames_dir = os.path.join(temp_dir, "frames")
        
        # Dynamically set keyframe interval to prevent CPU OCR bottlenecks
        duration = video.duration or 0.0
        if duration < 180:        # Under 3 minutes
            interval = 30
        elif duration < 600:      # Under 10 minutes
            interval = 60
        else:                     # Long videos
            interval = 120
            
        keyframes_list = video_service.extract_keyframes(local_video_path, frames_dir, interval_seconds=interval)

        
        keyframes_db_records = []
        for timestamp, local_frame_path in keyframes_list:
            # Upload keyframe image to S3/MinIO
            filename = os.path.basename(local_frame_path)
            s3_key = f"keyframes/{video_id}/{filename}"
            s3_url = s3_service.upload_file(local_frame_path, s3_key, content_type="image/jpeg")

            # OCR
            ocr_txt = ocr_service.extract_text(local_frame_path)
            ocr_txt = llm_service.clean_ocr_text(ocr_txt)
            
            # Vision analysis (LLM)
            vision_desc = llm_service.analyze_keyframe(local_frame_path, ocr_txt)

            db_kf = Keyframe(
                video_id=video_id,
                timestamp=timestamp,
                s3_url=s3_url,
                ocr_text=ocr_txt,
                vision_description=vision_desc
            )
            db.add(db_kf)
            keyframes_db_records.append(db_kf)
        db.commit()

        # 5. Consolidate knowledge base & Build RAG index
        print("Consolidating timeline knowledge base and chunking for pgvector...")
        # We merge transcripts and keyframe vision data by order of timestamp
        consolidated_elements = []
        
        for seg in segments_data:
            consolidated_elements.append({
                "time": seg["start"],
                "type": "transcript",
                "content": seg["text"],
                "end": seg["end"]
            })

        for kf in keyframes_db_records:
            content = f"[Slide/Visual Analysis]: {kf.vision_description or ''} [Text found in frame]: {kf.ocr_text or ''}"
            consolidated_elements.append({
                "time": kf.timestamp,
                "type": "keyframe",
                "content": content,
                "end": kf.timestamp + 5.0
            })

        # Sort by timestamp
        consolidated_elements.sort(key=lambda x: x["time"])

        # Create consolidated text representation for notes generation
        full_timeline_text = []
        for el in consolidated_elements:
            mins = int(el["time"] // 60)
            secs = int(el["time"] % 60)
            timestamp_str = f"[{mins:02d}:{secs:02d}]"
            
            if el["type"] == "transcript":
                full_timeline_text.append(f"{timestamp_str} (Transcript): {el['content']}")
            else:
                full_timeline_text.append(f"{timestamp_str} (Slide/Visual): {el['content']}")
                
        compiled_knowledge_base = "\n".join(full_timeline_text)

        # Chunk the compiled knowledge base for pgvector embedding indexing.
        # We group elements into chunks of ~5-10 adjacent lines, or text chunks of 800 characters.
        # Let's chunk the text into sliding windows.
        chunk_size = 1000
        overlap = 200
        
        # Simple text chunker keeping track of timestamps
        # We walk through elements, build text segments, compute embeddings
        current_chunk_text = []
        current_chunk_len = 0
        chunk_start_time = 0.0
        
        for item in consolidated_elements:
            item_text = item["content"]
            if not current_chunk_text:
                chunk_start_time = item["time"]
                
            current_chunk_text.append(item_text)
            current_chunk_len += len(item_text)
            
            if current_chunk_len >= chunk_size:
                combined_text = " ".join(current_chunk_text)
                emb = llm_service.get_embedding(combined_text)
                
                db_emb = ChunkEmbedding(
                    video_id=video_id,
                    text=combined_text,
                    start_time=chunk_start_time,
                    end_time=item["end"],
                    embedding=emb
                )
                db.add(db_emb)
                
                # Slide the window (overlap: keep last 2 items)
                current_chunk_text = current_chunk_text[-2:] if len(current_chunk_text) > 2 else []
                current_chunk_len = sum(len(x) for x in current_chunk_text)
                chunk_start_time = item["time"]

        # Handle last chunk if any text remains
        if current_chunk_text:
            combined_text = " ".join(current_chunk_text)
            emb = llm_service.get_embedding(combined_text)
            db_emb = ChunkEmbedding(
                video_id=video_id,
                text=combined_text,
                start_time=chunk_start_time,
                end_time=video.duration or chunk_start_time + 10.0,
                embedding=emb
            )
            db.add(db_emb)
        db.commit()

        # Build keyframes mapping data for inline markdown embedding
        keyframes_data = []
        for kf in keyframes_db_records:
            keyframes_data.append({
                "timestamp": kf.timestamp,
                "s3_url": kf.s3_url
            })

        # 6. Generate AI Study Materials package
        print("Invoking LLM for notes package generation...")
        notes_package = llm_service.generate_notes_package(compiled_knowledge_base[:12000], keyframes=keyframes_data) # Cap text to stay within tokens limit if huge
        
        # Format takeaways (Text column)
        takeaways_raw = notes_package.get("takeaways", "")
        if isinstance(takeaways_raw, list):
            takeaways_str = "\n".join(f"- {item}" for item in takeaways_raw)
        elif isinstance(takeaways_raw, dict):
            takeaways_str = "\n".join(f"- **{k}**: {v}" for k, v in takeaways_raw.items())
        else:
            takeaways_str = str(takeaways_raw) or "Error generating takeaways."

        # Format glossary (Text column)
        glossary_raw = notes_package.get("glossary", "")
        if isinstance(glossary_raw, dict):
            glossary_str = "\n".join(f"- **{k}**: {v}" for k, v in glossary_raw.items())
        elif isinstance(glossary_raw, list):
            glossary_str = "\n".join(f"- {item}" for item in glossary_raw)
        else:
            glossary_str = str(glossary_raw) or "Error generating glossary."

        # Format revision_notes (Text column)
        revision_raw = notes_package.get("revision_notes", "")
        if isinstance(revision_raw, dict):
            revision_str = "\n\n".join(f"### {k.replace('_', ' ').title()}\n{v}" for k, v in revision_raw.items())
        elif isinstance(revision_raw, list):
            revision_str = "\n".join(f"- {item}" for item in revision_raw)
        else:
            revision_str = str(revision_raw) or "Error generating revision notes."

        # Bypassing initial expensive outputs; generated dynamically on-demand!
        flashcards_data = []
        mcqs_data = []
        mindmap_data = ""

        db_notes = NoteOutput(
            video_id=video_id,
            summary_exec=notes_package.get("summary_exec", "Error generating executive summary."),
            summary_detailed=notes_package.get("summary_detailed", "Error generating detailed notes."),
            revision_notes=revision_str,
            takeaways=takeaways_str,
            glossary=glossary_str,
            flashcards=flashcards_data,
            mcqs=mcqs_data,
            mindmap=mindmap_data
        )
        db.add(db_notes)
        
        # Complete
        video.status = "completed"
        video.error_message = None
        db.commit()

        print(f"Video {video_id} processed successfully.")

    except Exception as e:
        print(f"Error executing processing pipeline for video {video_id}: {str(e)}")
        # Update database with failure status
        db.rollback()
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.status = "failed"
            video.error_message = str(e)
            db.commit()
            
    finally:
        db.close()
        # Clean up temp folder contents to optimize storage
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
