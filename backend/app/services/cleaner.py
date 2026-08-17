import re
import os
import math
from typing import List, Dict, Tuple, Any, Optional
import numpy as np

class PipelineCleaner:
    """
    Core Content-Independent Normalization, Deduplication, and Multimodal Quality Engine for VidNotes AI.
    Works for any YouTube video and any subject without hardcoded keywords, topics, or static replacements.
    """

    # Generic speech disfluencies and subtitle artifact patterns (content-agnostic)
    FILLER_WORDS_PATTERN = re.compile(
        r'\b(?:uh+|um+|umm+|uhh+|er+|ah+|eh+)\b',
        re.IGNORECASE
    )
    
    SUBTITLE_ARTIFACTS_PATTERN = re.compile(
        r'\[[A-Za-z0-9\s_-]+\]|<[^>]+>|\{[^}]+\}',
        re.IGNORECASE
    )

    @staticmethod
    def clean_text_fragment(text: str) -> str:
        """
        Cleans a single text fragment using content-independent structural rules:
        removes subtitle markers, vocal disfluencies, stutter loops, and whitespace anomalies.
        """
        if not text or not isinstance(text, str):
            return ""
        
        # 1. Remove bracketed subtitle noise tags like [Music], [Applause], <c>, etc.
        cleaned = PipelineCleaner.SUBTITLE_ARTIFACTS_PATTERN.sub(" ", text)
        
        # 2. Remove universal phoneme filler disfluencies (uh, um, er, ah)
        cleaned = PipelineCleaner.FILLER_WORDS_PATTERN.sub(" ", cleaned)
        
        # 3. Remove consecutive word stutter repetitions (e.g. "the the the" -> "the")
        cleaned = re.sub(r'\b(\w+)(?:\s+\1\b)+', r'\1', cleaned, flags=re.IGNORECASE)
        
        # 4. Remove consecutive 2-word phrase stutter repetitions (e.g. "to do to do" -> "to do")
        cleaned = re.sub(r'\b(\w+\s+\w+)(?:\s+\1\b)+', r'\1', cleaned, flags=re.IGNORECASE)
        
        # 5. Remove consecutive 3-word phrase stutter repetitions
        cleaned = re.sub(r'\b(\w+\s+\w+\s+\w+)(?:\s+\1\b)+', r'\1', cleaned, flags=re.IGNORECASE)
        
        # 6. Remove consecutive 4-word phrase stutter repetitions
        cleaned = re.sub(r'\b(\w+\s+\w+\s+\w+\s+\w+)(?:\s+\1\b)+', r'\1', cleaned, flags=re.IGNORECASE)

        # 7. Normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned

    @staticmethod
    def is_gibberish_or_broken(text: str) -> bool:
        """
        Generic content-independent classifier for corrupted, nonsensical, or fragmented text.
        Evaluates character entropy, noise ratios, lexical repetition, and malformed sequences.
        """
        if not text or not isinstance(text, str):
            return True
        
        t = text.strip()
        if len(t) == 0:
            return True
        
        # If no alphanumeric characters exist at all (e.g. "...", "---", "~!@#")
        if not any(c.isalnum() for c in t):
            return True

        # Fragment with fewer than 2 alphanumeric characters
        alpha_count = sum(1 for c in t if c.isalnum())
        if alpha_count < 2:
            return True
        
        # Extreme repetition of single character (e.g. "......", "aaaaaaa", "------")
        if re.search(r'(.)\1{4,}', t):
            return True
            
        # Non-alphanumeric noise ratio check (allowing standard punctuation and code symbols)
        allowed_chars = set("=+-*/<>():;{}[]_.,!?'\"%#$@&|\\~`^")
        non_printable_count = sum(1 for c in t if not c.isalnum() and c not in allowed_chars and not c.isspace())
        if len(t) > 0 and (non_printable_count / len(t)) > 0.25:
            return True
            
        # High unprintable / corrupt symbol ratio (e.g. "~`|^\\_")
        symbol_count = sum(1 for c in t if c in "~`|^\\_")
        if len(t) > 0 and (symbol_count / len(t)) > 0.08:
            return True

        words = t.split()
        if len(words) >= 4:
            unique_words = set(w.lower() for w in words)
            if (len(unique_words) / len(words)) < 0.35:
                return True
                
        # Consonant cluster anomaly: words with 6+ consonants and no vowels (excluding digit strings)
        vowels = set("aeiouyAEIOUY")
        for w in words:
            if w.isalpha() and len(w) >= 6:
                vowel_count = sum(1 for char in w if char in vowels)
                if vowel_count == 0:
                    return True
            # Mixed irregular digit-letter token noise (e.g. "14Jf4", "3x9kPZ")
            if re.search(r'^\d+[A-Za-z]+\d+[A-Za-z]*$', w) or re.search(r'^[A-Za-z]+\d+[A-Za-z]+\d+', w):
                return True

        return False

    @staticmethod
    def resolve_overlap_between_segments(prev_text: str, curr_text: str) -> str:
        """
        Detects and removes overlapping word sequences between consecutive speech cues.
        Operates generically across any language/vocabulary without hardcoded tokens.
        """
        if not prev_text or not curr_text:
            return curr_text or ""
            
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
            resolved_text = cls.resolve_overlap_between_segments(prev_cleaned_text, cleaned_text)
            if not resolved_text or cls.is_gibberish_or_broken(resolved_text):
                continue
                
            # Step C: Exact duplicate suppression
            if prev_cleaned_text and resolved_text.lower() == prev_cleaned_text.lower():
                continue
                
            cleaned_stream.append({
                "start": start_t,
                "end": max(end_t, start_t + 1.0),
                "text": resolved_text
            })
            prev_cleaned_text = resolved_text

        # Step D: Chronological chunking into unified conceptual windows (e.g. 20-30s blocks)
        if not cleaned_stream:
            return []

        consolidated_chunks: List[Dict[str, Any]] = []
        curr_chunk_texts: List[str] = []
        curr_chunk_start: float = cleaned_stream[0]["start"]
        curr_chunk_end: float = cleaned_stream[0]["end"]

        for item in cleaned_stream:
            # If current block duration exceeds target window and has full sentence end, seal chunk
            duration = item["end"] - curr_chunk_start
            text_str = item["text"]
            
            if duration >= target_chunk_duration and (curr_chunk_texts and curr_chunk_texts[-1].endswith(('.', '!', '?'))):
                merged_body = " ".join(curr_chunk_texts)
                # Final pass on merged body to remove any residual intra-chunk stutter
                merged_body = cls.clean_text_fragment(merged_body)
                if merged_body:
                    consolidated_chunks.append({
                        "start": round(curr_chunk_start, 2),
                        "end": round(curr_chunk_end, 2),
                        "text": merged_body
                    })
                curr_chunk_texts = [text_str]
                curr_chunk_start = item["start"]
                curr_chunk_end = item["end"]
            else:
                curr_chunk_texts.append(text_str)
                curr_chunk_end = max(curr_chunk_end, item["end"])

        if curr_chunk_texts:
            merged_body = cls.clean_text_fragment(" ".join(curr_chunk_texts))
            if merged_body:
                consolidated_chunks.append({
                    "start": round(curr_chunk_start, 2),
                    "end": round(curr_chunk_end, 2),
                    "text": merged_body
                })

        return consolidated_chunks

    @staticmethod
    def clean_ocr_text(ocr_text: str) -> str:
        """
        Generic, content-agnostic OCR cleaner:
        1. Strips editor line numbers (e.g. '1 ', '10:', '294 ') at the beginning of code/text lines.
        2. Strips non-printable ASCII noise and stray isolated symbols.
        3. Filters corrupt/gibberish lines using generic entropy checks.
        4. Preserves authentic code, symbols, indentations, and formulas without hardcoding vocabulary.
        """
        if not ocr_text or not isinstance(ocr_text, str):
            return ""
            
        cleaned = ocr_text.strip()
        
        # 1. Remove generic line numbers common in slide code editors (e.g. "1: ", "294 ", "12. ")
        cleaned = re.sub(r'^\s*\d{1,4}\s*[:|.)]\s*', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'^\s*\d{1,4}\s+(?=[A-Za-z_])', '', cleaned, flags=re.MULTILINE)
        
        # 2. Clean up non-printable and non-standard noise characters
        cleaned = re.sub(r'[^\x20-\x7E\n\t]', ' ', cleaned)
        cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)
        
        # 3. Filter lines: drop isolated noise symbols or corrupted lines
        clean_lines = []
        for line in cleaned.splitlines():
            l_str = line.strip()
            if not l_str:
                continue
            # Drop lines with only 1-2 non-alphanumeric noise chars (e.g. "~", "|", "-")
            if len(l_str) <= 2 and not l_str.isalnum():
                continue
            if PipelineCleaner.is_gibberish_or_broken(l_str):
                continue
            clean_lines.append(l_str)
            
        return "\n".join(clean_lines)

    @staticmethod
    def is_duplicate_ocr(curr_ocr: str, previous_ocrs: List[str], similarity_threshold: float = 0.82) -> bool:
        """
        Generic token-level Jaccard similarity check for duplicate OCR across frames.
        """
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
        clean_transcripts: List[Dict[str, Any]] = None,
        keyframes_data: List[Dict[str, Any]] = None,
        video_title: str = "",
        transcript_segments: List[Dict[str, Any]] = None,
        keyframes: List[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Constructs a structured, normalized multimodal lecture knowledge base.
        Separates spoken transcript from visual slide code and structures them chronologically.
        Accepts flexible parameter names (clean_transcripts/transcript_segments, keyframes_data/keyframes).
        """
        resolved_transcripts = clean_transcripts if clean_transcripts is not None else (transcript_segments or [])
        resolved_keyframes = keyframes_data if keyframes_data is not None else (keyframes or [])
        resolved_title = video_title or kwargs.get("title", "")

        clean_visuals: List[Dict[str, Any]] = []
        seen_ocrs: List[str] = []
        
        for idx, kf in enumerate(resolved_keyframes):
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
        for t in resolved_transcripts:
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
                    content_parts.append(f"Visual Breakdown: {ev['description']}")
                if ev.get("ocr"):
                    content_parts.append(f"Slide Content:\n```\n{ev['ocr']}\n```")
                if content_parts:
                    timeline_blocks.append(f"{ts_badge} [Slide Visual]: {' | '.join(content_parts)}")

        compiled_text = "\n\n".join(timeline_blocks)
        
        return {
            "title": resolved_title,
            "transcript": resolved_transcripts,
            "visuals": clean_visuals,
            "timeline_text": compiled_text
        }

    # -------------------------------------------------------------
    # Generic Pipeline Quality Metrics & Diagnostics
    # -------------------------------------------------------------

    @staticmethod
    def compute_ngram_repetition_rate(text: str, n: int = 3) -> float:
        """Calculates n-gram repetition ratio to detect looping ASR or degenerate outputs."""
        if not text or not isinstance(text, str):
            return 0.0
        words = text.lower().split()
        if len(words) < n:
            return 0.0
        ngrams = [tuple(words[i:i+n]) for i in range(len(words) - n + 1)]
        if not ngrams:
            return 0.0
        unique_ngrams = set(ngrams)
        return round(1.0 - (len(unique_ngrams) / len(ngrams)), 3)

    @staticmethod
    def compute_sentence_similarity(s1: str, s2: str) -> float:
        """Token-level Jaccard similarity between two sentences."""
        if not s1 or not s2:
            return 0.0
        tokens1 = set(re.findall(r'\b\w+\b', s1.lower()))
        tokens2 = set(re.findall(r'\b\w+\b', s2.lower()))
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        return round(len(intersection) / len(union), 3)

    @staticmethod
    def compute_chunk_overlap_ratio(chunk1_text: str, chunk2_text: str) -> float:
        """Evaluates boundary word overlap ratio between two consecutive chunks."""
        if not chunk1_text or not chunk2_text:
            return 0.0
        words1 = chunk1_text.split()
        words2 = chunk2_text.split()
        if not words1 or not words2:
            return 0.0
        tail = [w.lower().strip(".,!?:;\"'") for w in words1[-min(10, len(words1)):]]
        head = [w.lower().strip(".,!?:;\"'") for w in words2[:min(10, len(words2))]]
        overlap = set(tail).intersection(set(head))
        return round(len(overlap) / max(1, len(set(tail))), 3)

    @staticmethod
    def validate_pipeline_metrics(
        raw_transcript_count: int,
        clean_transcript_count: int,
        raw_keyframe_count: int,
        unique_keyframe_count: int,
        clean_knowledge_text: str
    ) -> Dict[str, Any]:
        """
        Validates pipeline quality metrics before synthesis.
        Tracks duplicate ratios, n-gram repetition rates, and content integrity.
        """
        lines = [l.strip() for l in clean_knowledge_text.splitlines() if l.strip()]
        sentences = [l for l in lines if len(l.split()) >= 4]
        
        total_sentences = len(sentences)
        unique_sentences = len(set(s.lower() for s in sentences))
        dup_ratio = round((total_sentences - unique_sentences) / max(1, total_sentences), 3)
        ngram_rep = PipelineCleaner.compute_ngram_repetition_rate(clean_knowledge_text, n=3)
        
        metrics = {
            "raw_transcripts": raw_transcript_count,
            "clean_transcripts": clean_transcript_count,
            "raw_keyframes": raw_keyframe_count,
            "unique_keyframes": unique_keyframe_count,
            "total_sentences": total_sentences,
            "unique_sentences": unique_sentences,
            "duplicate_sentence_ratio": dup_ratio,
            "ngram_repetition_rate": ngram_rep,
            "is_valid": dup_ratio <= 0.20 and ngram_rep <= 0.25
        }
        
        print(f"[Pipeline Validation] Transcripts: {raw_transcript_count} -> {clean_transcript_count} | Keyframes: {raw_keyframe_count} -> {unique_keyframe_count} | Dup Ratio: {dup_ratio:.1%} | N-Gram Rep: {ngram_rep:.1%} (Passed={metrics['is_valid']})")
        return metrics

cleaner_service = PipelineCleaner()
