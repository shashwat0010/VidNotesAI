import pytest
import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.cleaner import cleaner_service, PipelineCleaner

def test_transcript_overlap_and_stutter_removal():
    """Test merging overlapping subtitle cues, removing stutters and verbal fillers."""
    raw_segments = [
        {"text": "uh welcome to this lecture on on SQL window functions.", "start": 0.0, "duration": 5.0},
        {"text": "SQL window functions and what I can say as row number.", "start": 4.0, "duration": 5.0},
        {"text": "row number right now I will use rank also also for this.", "start": 8.5, "duration": 6.0},
        {"text": "rank also for this and dense rank.", "start": 14.0, "duration": 4.0},
    ]

    cleaned = cleaner_service.clean_transcript_segments(raw_segments, target_chunk_duration=10.0)
    
    assert len(cleaned) > 0
    full_text = " ".join([c["text"] for c in cleaned])
    
    # Assert fillers removed
    assert "uh " not in full_text.lower()
    # Assert stutter duplicates collapsed
    assert "on on" not in full_text
    assert "also also" not in full_text
    # Assert overlaps between cues resolved without repeated phrases
    assert "and what I can say as row number" in full_text
    assert "right now I will use rank also for this" in full_text
    assert "and dense rank" in full_text
    assert "SQL window functions" in full_text

def test_gibberish_and_broken_fragment_filtering():
    """Test detection and exclusion of nonsensical ASR/OCR loops and noise."""
    assert cleaner_service.is_gibberish_or_broken("") is True
    assert cleaner_service.is_gibberish_or_broken("   ") is True
    assert cleaner_service.is_gibberish_or_broken(".") is True
    assert cleaner_service.is_gibberish_or_broken("§¶¥æ ø¿??!!") is True
    assert cleaner_service.is_gibberish_or_broken("row row row row row row") is True
    assert cleaner_service.is_gibberish_or_broken("aaaaaaaaaaaa") is True
    
    # Valid text and code should not be flagged as gibberish
    assert cleaner_service.is_gibberish_or_broken("SELECT ROW_NUMBER() OVER (ORDER BY hire_date)") is False
    assert cleaner_service.is_gibberish_or_broken("In this session we discuss PySpark dataframe partitioning.") is False

def test_ocr_normalization_and_duplicate_detection():
    """Test OCR cleanup (removing line numbers, typos) and detecting duplicate slide OCR."""
    raw_ocr_1 = """
    294 SELECT employee_id,
    295 ROH_MUMBER() OVER (ORDER BY salary DESC) as rnk
    296 FROM employees;
    """
    
    cleaned_ocr_1 = cleaner_service.clean_ocr_text(raw_ocr_1)
    assert "294" not in cleaned_ocr_1
    assert "ROW_NUMBER()" in cleaned_ocr_1
    assert "SELECT" in cleaned_ocr_1

    # Identical slide captured at next timestamp
    raw_ocr_2 = """
    294 SELECT employee_id,
    295 ROW_NUMBER() OVER (ORDER BY salary DESC) as rnk
    296 FROM employees;
    """
    cleaned_ocr_2 = cleaner_service.clean_ocr_text(raw_ocr_2)
    
    # Duplicate detector should flag ocr_2 as duplicate of ocr_1
    is_dup = cleaner_service.is_duplicate_ocr(cleaned_ocr_2, [cleaned_ocr_1])
    assert is_dup is True

    # New distinct slide
    ocr_3 = "SELECT department_id, AVG(salary) FROM employees GROUP BY department_id;"
    is_not_dup = cleaner_service.is_duplicate_ocr(ocr_3, [cleaned_ocr_1])
    assert is_not_dup is False

def test_normalized_multimodal_knowledge_construction():
    """Test structured knowledge base schema separating spoken lecture from slide visuals."""
    clean_transcripts = [
        {"text": "Let us examine the differences between ROW_NUMBER and RANK.", "start": 0.0, "end": 15.0}
    ]
    keyframes = [
        {
            "timestamp": 15.0,
            "s3_url": "https://example.com/slide1.jpg",
            "ocr_text": "SELECT ROW_NUMBER() OVER (ORDER BY salary) FROM emp;",
            "vision_description": "SQL query demonstrating ROW_NUMBER window syntax."
        }
    ]

    knowledge = cleaner_service.build_normalized_lecture_knowledge(
        clean_transcripts=clean_transcripts,
        keyframes_data=keyframes,
        video_title="SQL Window Functions"
    )

    assert "transcript" in knowledge
    assert "visuals" in knowledge
    assert "timeline_text" in knowledge
    assert "[Spoken Lecture]:" in knowledge["timeline_text"]
    assert "[Slide Visual]:" in knowledge["timeline_text"]
    assert "Visual Breakdown" not in knowledge["timeline_text"]
    assert "Code / Slide Content" not in knowledge["timeline_text"]

def test_pipeline_quality_validation():
    """Test duplicate sentence ratio calculation and validation checks."""
    text = (
        "[00:00] [Spoken Lecture]: In this lecture we study SQL window functions.\n"
        "[00:30] [Spoken Lecture]: ROW_NUMBER assigns a unique sequence number to every row.\n"
        "[01:00] [Spoken Lecture]: RANK handles ties by skipping positions in the ordered partition.\n"
        "[01:30] [Spoken Lecture]: DENSE_RANK assigns consecutive numbers without gaps."
    )

    metrics = cleaner_service.validate_pipeline_metrics(
        raw_transcript_count=20,
        clean_transcript_count=4,
        raw_keyframe_count=8,
        unique_keyframe_count=3,
        clean_knowledge_text=text
    )

    assert metrics["is_valid"] is True
    assert metrics["duplicate_sentence_ratio"] == 0.0
    assert metrics["clean_transcripts"] == 4

def test_retry_idempotency_clear_stages():
    """Test that retry clear_existing_stages deletes prior records before recreating."""
    from app.tasks.worker import clear_existing_stages
    from app.core.db import sync_engine
    from app.models.models import Video, TranscriptSegment, Keyframe, NoteOutput, ChunkEmbedding
    from sqlalchemy.orm import Session

    with Session(sync_engine) as session:
        # Create dummy video if not exists
        dummy_id = "test_idempotency_video_001"
        v = session.query(Video).filter_by(id=dummy_id).first()
        if not v:
            v = Video(id=dummy_id, user_id=1, title="Test Idempotency Video", status="processing")
            session.add(v)
            session.commit()

        # Add dummy segments
        session.add(TranscriptSegment(video_id=dummy_id, text="Dummy segment 1", start_time=0.0, end_time=10.0))
        session.add(Keyframe(video_id=dummy_id, timestamp=0.0, s3_url="http://dummy/1.jpg"))
        session.commit()

        assert session.query(TranscriptSegment).filter_by(video_id=dummy_id).count() >= 1

        # Execute clear_existing_stages
        clear_existing_stages(session, dummy_id)

        # Verify all records for this video are cleanly cleared
        assert session.query(TranscriptSegment).filter_by(video_id=dummy_id).count() == 0
        assert session.query(Keyframe).filter_by(video_id=dummy_id).count() == 0
        assert session.query(ChunkEmbedding).filter_by(video_id=dummy_id).count() == 0
        assert session.query(NoteOutput).filter_by(video_id=dummy_id).count() == 0

        # Clean up dummy video
        session.delete(v)
        session.commit()

if __name__ == "__main__":
    print("Running Pipeline Unit Tests...")
    test_transcript_overlap_and_stutter_removal()
    print("[PASS] Transcript overlap & stutter removal test passed.")
    test_gibberish_and_broken_fragment_filtering()
    print("[PASS] Gibberish and broken fragment filtering test passed.")
    test_ocr_normalization_and_duplicate_detection()
    print("[PASS] OCR normalization & duplicate detection test passed.")
    test_normalized_multimodal_knowledge_construction()
    print("[PASS] Multimodal structured knowledge test passed.")
    test_pipeline_quality_validation()
    print("[PASS] Pipeline validation & duplicate ratio test passed.")
    test_retry_idempotency_clear_stages()
    print("[PASS] Retry idempotency clear stages test passed.")
    print("\nALL 6 PIPELINE TESTS PASSED SUCCESSFULLY!")
