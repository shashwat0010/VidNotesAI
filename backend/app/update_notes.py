from app.core.db import SessionLocal
from app.models.models import NoteOutput, TranscriptSegment, Keyframe
from app.services.llm import llm_service

def update_notes():
    db = SessionLocal()
    notes = db.query(NoteOutput).all()
    print(f"Found {len(notes)} note output records in database.")
    updated_count = 0
    for n in notes:
        if 'No LLM Configured' in str(n.summary_exec or ''):
            video_id = n.video_id
            segments = db.query(TranscriptSegment).filter(TranscriptSegment.video_id == video_id).order_by(TranscriptSegment.start_time).all()
            keyframes = db.query(Keyframe).filter(Keyframe.video_id == video_id).all()
            consolidated = [{'time': seg.start_time, 'type': 'transcript', 'content': seg.text} for seg in segments]
            for kf in keyframes:
                consolidated.append({'time': kf.timestamp, 'type': 'keyframe', 'content': kf.ocr_text or ''})
            consolidated.sort(key=lambda x: x['time'])
            
            lines = []
            for el in consolidated:
                mins = int(el['time'] // 60)
                secs = int(el['time'] % 60)
                lines.append(f"[{mins:02d}:{secs:02d}] ({el['type']}): {el['content']}")
            
            kb = "\n".join(lines)
            pkg = llm_service.generate_notes_package(kb[:12000])
            n.summary_exec = pkg.get('summary_exec', '')
            n.summary_detailed = pkg.get('summary_detailed', '')
            n.revision_notes = pkg.get('revision_notes', '')
            n.takeaways = str(pkg.get('takeaways', ''))
            n.glossary = str(pkg.get('glossary', ''))
            updated_count += 1
            
    db.commit()
    db.close()
    print(f"Successfully updated {updated_count} note output records.")

if __name__ == "__main__":
    update_notes()
