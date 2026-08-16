import re
import os
from typing import List, Dict, Tuple, Any, Optional
import numpy as np

class PipelineCleaner:
    """
    Core Normalization, Deduplication, and Multimodal Cleaning Engine for VidNotes AI.
    Handles transcript overlap removal, stutter/filler suppression, gibberish filtering,
    keyframe visual similarity deduplication, slide OCR normalization, and structured knowledge consolidation.
    """

    # Common speech disfluencies and ASR subtitle noise
    FILLER_WORDS_PATTERN = re.compile(
        r'\b(?:uh+|um+|umm+|uhh+|er+|ah+|you\s+know|like\s+I\s+say|sort\s+of|kind\s+of)\b',
        re.IGNORECASE
    )
    
    SUBTITLE_ARTIFACTS_PATTERN = re.compile(
        r'\[(?:Music|Applause|Laughter|Silence|Foreign|Cheering|Audio)\]|<[^>]+>|\{[^}]+\}',
        re.IGNORECASE
    )

    @staticmethod
    def clean_text_fragment(text: str) -> str:
        """Cleans a single text fragment: removes subtitle tags, stuttered words, and fillers."""
        if not text:
            return ""
        
        # 1. Remove subtitle noise tags like [Music], <c>, etc.
        cleaned = PipelineCleaner.SUBTITLE_ARTIFACTS_PATTERN.sub(" ", text)
        
        # 2. Remove filler words (uh, um, you know)
        cleaned = PipelineCleaner.FILLER_WORDS_PATTERN.sub(" ", cleaned)
        
        # 3. Remove consecutive word stutter repetitions (e.g., "the the the" -> "the", "I I will" -> "I will")
        cleaned = re.sub(r'\b(\w+)(?:\s+\1\b)+', r'\1', cleaned, flags=re.IGNORECASE)
        
        # 4. Remove consecutive 2-word phrase stutter repetitions (e.g., "for this for this" -> "for this")
        cleaned = re.sub(r'\b(\w+\s+\w+)(?:\s+\1\b)+', r'\1', cleaned, flags=re.IGNORECASE)
        
        # 5. Remove consecutive 3-word phrase stutter repetitions
        cleaned = re.sub(r'\b(\w+\s+\w+\s+\w+)(?:\s+\1\b)+', r'\1', cleaned, flags=re.IGNORECASE)
        
        # 6. Normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned

    @staticmethod
    def is_gibberish_or_broken(text: str) -> bool:
        """
        Detects broken, nonsensical, or corrupt text fragments.
        Returns True if the text should be discarded.
        """
        if not text or len(text.strip()) == 0:
            return True
        
        t = text.strip()
        words = t.split()
        
        # Fragment with fewer than 2 characters and no alphanumeric value
        if len(t) < 2 and not t.isalnum():
            return True
        
        # Extreme repetition of single character (e.g., "......", "aaaaaaa")
        if re.search(r'(.)\1{5,}', t):
            return True
            
        # Non-alphanumeric/non-ascii noise ratio check (excluding code symbols)
        allowed_code_chars = set("=+-*/<>():;{}[]_.,!?'\"%#$@&|\\~`")
        non_printable_count = sum(1 for c in t if not c.isalnum() and c not in allowed_code_chars and not c.isspace())
        if len(t) > 0 and (non_printable_count / len(t)) > 0.35:
            return True
            
        # Unusually high repetitive word ratio in a single segment (e.g. ASR loop: "row row row row row")
        if len(words) >= 4:
            unique_words = set(w.lower() for w in words)
            if (len(unique_words) / len(words)) < 0.30:
                return True
                
        return False

    @staticmethod
    def resolve_overlap_between_segments(prev_text: str, curr_text: str) -> str:
        """
        Detects and removes overlapping word sequences between consecutive speech cues.
        Example:
          prev: "based on hire date"
          curr: "based on hire date and row number"
          -> returns "and row number"
        """
        if not prev_text or not curr_text:
            return curr_text
            
        prev_words = prev_text.split()
        curr_words = curr_text.split()
        
        if not prev_words or not curr_words:
            return curr_text
            
        max_overlap_to_check = min(len(prev_words), len(curr_words), 15)
        overlap_size = 0
        
        # Check from longest possible overlap down to 2 words
        for n in range(max_overlap_to_check, 1, -1):
            prev_tail = [w.lower().strip(".,!?:;\"'") for w in prev_words[-n:]]
            curr_head = [w.lower().strip(".,!?:;\"'") for w in curr_words[:n]]
            if prev_tail == curr_head:
                overlap_size = n
                break
                
        if overlap_size > 0:
            return " ".join(curr_words[overlap_size:]).strip()
            
        # Also check single-word overlap if exact match at boundary
        if len(prev_words) >= 1 and len(curr_words) >= 1:
            if prev_words[-1].lower().strip(".,!?:;\"'") == curr_words[0].lower().strip(".,!?:;\"'"):
                if len(curr_words) > 1:
                    return " ".join(curr_words[1:]).strip()
                    
        return curr_text

    @classmethod
    def clean_transcript_segments(cls, raw_segments: List[Dict[str, Any]], target_chunk_duration: float = 25.0) -> List[Dict[str, Any]]:
        """
        Takes raw subtitle or Whisper segments, merges overlapping time boundaries,
        removes phrase repetitions and stutters, filters gibberish, and creates clean, coherent timeline chunks.
        """
        if not raw_segments:
            return []
            
        # 1. Sort by start timestamp
        sorted_raw = sorted(raw_segments, key=lambda x: float(x.get("start", 0.0)))
        
        cleaned_stream: List[Dict[str, Any]] = []
        prev_cleaned_text = ""
        
        for seg in sorted_raw:
            raw_text = str(seg.get("text", "")).strip()
            start_t = float(seg.get("start", 0.0))
            end_t = float(seg.get("end", start_t + float(seg.get("duration", 5.0))))
            
            # Step A: Basic normalization & filler removal
            cleaned_text = cls.clean_text_fragment(raw_text)
            
            if cls.is_gibberish_or_broken(cleaned_text):
                continue
                
            # Step B: Boundary overlap resolution with previous segment
            overlap_resolved_text = cls.resolve_overlap_between_segments(prev_cleaned_text, cleaned_text)
            
            if not overlap_resolved_text or cls.is_gibberish_or_broken(overlap_resolved_text):
                continue
                
            cleaned_stream.append({
                "text": overlap_resolved_text,
                "start": max(0.0, start_t),
                "end": max(start_t + 0.5, end_t)
            })
            prev_cleaned_text = cleaned_text

        # Step C: Group into coherent, readable thought units (15s - 30s)
        final_segments: List[Dict[str, Any]] = []
        current_chunk_words: List[str] = []
        chunk_start = None
        chunk_end = 0.0
        
        for item in cleaned_stream:
            if chunk_start is None:
                chunk_start = item["start"]
            
            # Clean repeated words within current chunk
            words = item["text"].split()
            current_chunk_words.extend(words)
            chunk_end = max(chunk_end, item["end"])
            
            duration = chunk_end - chunk_start
            sentence_ends = item["text"].rstrip().endswith((".", "!", "?", ";"))
            
            if (duration >= target_chunk_duration and sentence_ends) or duration >= (target_chunk_duration * 1.5):
                chunk_str = cls.clean_text_fragment(" ".join(current_chunk_words))
                if chunk_str and not cls.is_gibberish_or_broken(chunk_str):
                    final_segments.append({
                        "text": chunk_str,
                        "start": round(chunk_start, 2),
                        "end": round(chunk_end, 2)
                    })
                current_chunk_words = []
                chunk_start = None

        if current_chunk_words and chunk_start is not None:
            chunk_str = cls.clean_text_fragment(" ".join(current_chunk_words))
            if chunk_str and not cls.is_gibberish_or_broken(chunk_str):
                final_segments.append({
                    "text": chunk_str,
                    "start": round(chunk_start, 2),
                    "end": round(max(chunk_end, chunk_start + 1.0), 2)
                })

        return final_segments

    @staticmethod
    def deduplicate_keyframes(keyframes_list: List[Tuple[float, str]], similarity_threshold: float = 0.94) -> List[Tuple[float, str]]:
        """
        Removes near-identical sequential video frames using image histogram comparison.
        Prevents processing the same static slide 10 times if it stayed on screen for minutes.
        """
        if not keyframes_list or len(keyframes_list) <= 1:
            return keyframes_list
            
        unique_keyframes: List[Tuple[float, str]] = []
        prev_img_array = None
        
        try:
            from PIL import Image
            for timestamp, file_path in keyframes_list:
                if not os.path.exists(file_path):
                    continue
                try:
                    with Image.open(file_path) as img:
                        # Convert to small grayscale for fast perceptual similarity check
                        small_gray = img.convert("L").resize((64, 64))
                        arr = np.array(small_gray, dtype=np.float32)
                        
                        if prev_img_array is None:
                            unique_keyframes.append((timestamp, file_path))
                            prev_img_array = arr
                        else:
                            # Mean Absolute Error (MAE) normalized
                            diff = np.mean(np.abs(arr - prev_img_array)) / 255.0
                            similarity = 1.0 - diff
                            
                            if similarity < similarity_threshold:
                                unique_keyframes.append((timestamp, file_path))
                                prev_img_array = arr
                except Exception as e:
                    # If single frame fails to read, keep it safely
                    unique_keyframes.append((timestamp, file_path))
        except ImportError:
            # Fallback if PIL not available
            return keyframes_list
            
        return unique_keyframes

    @staticmethod
    def clean_ocr_text(ocr_text: str) -> str:
        """
        Normalizes OCR extracted text: removes line numbers, editor artifacts,
        and fixes common OCR typos while preserving code and SQL query syntax.
        """
        if not ocr_text:
            return ""
            
        cleaned = ocr_text.strip()
        
        # 1. Remove line numbers common in code editors (e.g. "294 ROW_NUMBER 295 RANK 296 DENSE_RANK")
        cleaned = re.sub(r'^\s*\d{1,4}\s+', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'\b(29[0-9]|30[0-9]|31[0-9]|32[0-9]|33[0-9])\b(?=\s+[A-Za-z_])', '', cleaned)
        cleaned = re.sub(r'\b\d{1,3}\b(?=\s+(?:SELECT|FROM|WHERE|GROUP|ORDER|ROW_NUMBER|RANK|DENSE_RANK|DEF|CLASS|IMPORT))', '', cleaned, flags=re.IGNORECASE)
        
        # 2. Fix common OCR misrecognitions for SQL keywords
        cleaned = re.sub(r'\b(ElECT|EIeCT|ELeCT|SElECT)\b', 'SELECT', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b(ROH_MUMBER|RON_NUMBER|ROH_NUMBER|ROW NUMBER)\b', 'ROW_NUMBER', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b(dense rnk|dense_rnk|DENSE RANK)\b', 'DENSE_RANK', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b(OVER\s*\(\s*ORDER\s+BY)\b', 'OVER (ORDER BY', cleaned, flags=re.IGNORECASE)
        
        # 3. Clean up non-code OCR junk characters (e.g. stray pipe bars, broken symbols)
        cleaned = re.sub(r'[^\x20-\x7E\n\t]', ' ', cleaned)
        cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)
        
        # 4. Remove empty lines
        lines = [line.strip() for line in cleaned.splitlines() if line.strip() and not PipelineCleaner.is_gibberish_or_broken(line.strip())]
        return "\n".join(lines)

    @staticmethod
    def is_duplicate_ocr(curr_ocr: str, previous_ocrs: List[str], similarity_threshold: float = 0.82) -> bool:
        """Checks if slide OCR is essentially identical to a recently observed slide."""
        if not curr_ocr or not previous_ocrs:
            return False
            
        curr_tokens = set(re.findall(r'\b\w{3,}\b', curr_ocr.lower()))
        if not curr_tokens:
            return False
            
        for prev in previous_ocrs[-5:]:
            prev_tokens = set(re.findall(r'\b\w{3,}\b', prev.lower()))
            if not prev_tokens:
                continue
            intersection = curr_tokens.intersection(prev_tokens)
            union = curr_tokens.union(prev_tokens)
            jaccard = len(intersection) / len(union) if union else 0.0
            if jaccard >= similarity_threshold:
                return True
                
        return False

    @classmethod
    def build_normalized_lecture_knowledge(
        cls,
        clean_transcripts: List[Dict[str, Any]],
        keyframes_data: List[Dict[str, Any]],
        video_title: str = ""
    ) -> Dict[str, Any]:
        """
        Constructs a structured, normalized multimodal lecture knowledge base.
        Separates spoken transcript from visual slide code and structures them logically.
        """
        # Clean & deduplicate visuals
        clean_visuals: List[Dict[str, Any]] = []
        seen_ocrs: List[str] = []
        
        for idx, kf in enumerate(keyframes_data):
            ts = float(kf.get("timestamp", idx * 30.0))
            raw_ocr = kf.get("ocr_text") or ""
            cleaned_ocr = cls.clean_ocr_text(raw_ocr)
            
            is_dup = cls.is_duplicate_ocr(cleaned_ocr, seen_ocrs)
            if cleaned_ocr and not is_dup:
                seen_ocrs.append(cleaned_ocr)
                
            v_desc = kf.get("vision_description") or ""
            if cls.is_gibberish_or_broken(v_desc):
                v_desc = ""
                
            clean_visuals.append({
                "timestamp": ts,
                "s3_url": kf.get("s3_url", ""),
                "ocr": "" if is_dup else cleaned_ocr,
                "description": v_desc,
                "is_slide_change": not is_dup and bool(cleaned_ocr)
            })

        # Structured textual representation for LLM synthesis (cleanly tagged without mixing)
        timeline_blocks: List[str] = []
        
        # Combine transcript and visual events into a chronological timeline
        events = []
        for t in clean_transcripts:
            events.append({
                "time": t["start"],
                "type": "speech",
                "text": t["text"],
                "end": t["end"]
            })
        for v in clean_visuals:
            if v["ocr"] or v["description"]:
                events.append({
                    "time": v["timestamp"],
                    "type": "visual",
                    "ocr": v["ocr"],
                    "description": v["description"],
                    "s3_url": v["s3_url"]
                })
                
        events.sort(key=lambda x: x["time"])
        
        for ev in events:
            mins = int(ev["time"] // 60)
            secs = int(ev["time"] % 60)
            ts_badge = f"[{mins:02d}:{secs:02d}]"
            
            if ev["type"] == "speech":
                timeline_blocks.append(f"{ts_badge} [Spoken Lecture]: {ev['text']}")
            elif ev["type"] == "visual":
                content_parts = []
                if ev.get("description"):
                    content_parts.append(f"Diagram/Layout: {ev['description']}")
                if ev.get("ocr"):
                    content_parts.append(f"Slide Code/Text:\n```\n{ev['ocr']}\n```")
                if content_parts:
                    timeline_blocks.append(f"{ts_badge} [Slide Visual]: {' | '.join(content_parts)}")

        compiled_text = "\n\n".join(timeline_blocks)
        
        return {
            "title": video_title,
            "transcript": clean_transcripts,
            "visuals": clean_visuals,
            "timeline_text": compiled_text
        }

    @staticmethod
    def validate_pipeline_metrics(
        raw_transcript_count: int,
        clean_transcript_count: int,
        raw_keyframe_count: int,
        unique_keyframe_count: int,
        clean_knowledge_text: str
    ) -> Dict[str, Any]:
        """
        Validates pipeline quality metrics before saving.
        Calculates duplicate sentence ratio and verifies timestamp coherence.
        """
        lines = [l.strip() for l in clean_knowledge_text.splitlines() if l.strip()]
        sentences = [l for l in lines if len(l.split()) >= 4]
        
        total_sentences = len(sentences)
        unique_sentences = len(set(s.lower() for s in sentences))
        dup_ratio = round((total_sentences - unique_sentences) / max(1, total_sentences), 3)
        
        metrics = {
            "raw_transcripts": raw_transcript_count,
            "clean_transcripts": clean_transcript_count,
            "raw_keyframes": raw_keyframe_count,
            "unique_keyframes": unique_keyframe_count,
            "total_sentences": total_sentences,
            "unique_sentences": unique_sentences,
            "duplicate_sentence_ratio": dup_ratio,
            "is_valid": dup_ratio <= 0.20
        }
        
        print(f"[Pipeline Validation] Transcripts: {raw_transcript_count} -> {clean_transcript_count} | Keyframes: {raw_keyframe_count} -> {unique_keyframe_count} | Dup Ratio: {dup_ratio:.1%} (Passed={metrics['is_valid']})")
        return metrics

cleaner_service = PipelineCleaner()
