import pytest
import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.cleaner import cleaner_service, PipelineCleaner
from app.services.llm import llm_service

def test_generic_transcript_overlap_and_stutter_removal():
    """
    Verifies that subtitle cues with arbitrary subject matter (e.g. astrophysics / biology)
    have stutters, fillers, and boundary overlaps removed cleanly.
    """
    raw_segments = [
        {"text": "um welcome to this lecture on on quantum entanglement and spin states.", "start": 0.0, "duration": 5.0},
        {"text": "quantum entanglement and spin states where two particles become linked.", "start": 4.0, "duration": 5.0},
        {"text": "where two particles become linked uhh measuring one instantly sets the other.", "start": 8.5, "duration": 6.0},
        {"text": "measuring one instantly sets the other across arbitrary distances.", "start": 14.0, "duration": 4.0},
    ]

    cleaned = cleaner_service.clean_transcript_segments(raw_segments, target_chunk_duration=12.0)
    
    assert len(cleaned) > 0
    full_text = " ".join([c["text"] for c in cleaned])
    
    # Assert generic fillers (um, uhh) removed
    import re
    assert not re.search(r'\bum\b', full_text.lower())
    assert not re.search(r'\buhh\b', full_text.lower())
    # Assert single-word and phrase stutters collapsed
    assert "on on" not in full_text
    # Assert boundary overlaps resolved cleanly without duplicate clauses
    assert full_text.count("quantum entanglement and spin states") == 1
    assert full_text.count("where two particles become linked") == 1
    assert full_text.count("measuring one instantly sets the other") == 1
    assert "across arbitrary distances" in full_text

def test_generic_gibberish_and_corrupt_filtering():
    """
    Tests detection of synthetic corrupted text fragments, noisy OCR artifacts, and degenerate ASR loops.
    """
    # Empty and whitespace
    assert cleaner_service.is_gibberish_or_broken("") is True
    assert cleaner_service.is_gibberish_or_broken("   \n\t") is True
    
    # Single punctuation / symbol noise
    assert cleaner_service.is_gibberish_or_broken("~") is True
    assert cleaner_service.is_gibberish_or_broken("...") is True
    assert cleaner_service.is_gibberish_or_broken("§¶¥æ ø¿??!!") is True
    
    # High-density noise symbol lines (typical corrupted OCR)
    assert cleaner_service.is_gibberish_or_broken("~VERLOAD 14Jf4 dor ttee") is True
    assert cleaner_service.is_gibberish_or_broken("^^^^^\\\\\\||||||||") is True
    
    # Repetitive ASR loop degeneracy
    assert cleaner_service.is_gibberish_or_broken("loop loop loop loop loop loop") is True
    assert cleaner_service.is_gibberish_or_broken("token token token token token") is True
    
    # Consonant cluster corruption
    assert cleaner_service.is_gibberish_or_broken("bdfghjklmnpq") is True

    # Valid domain-independent sentences and code should NOT be flagged as gibberish
    assert cleaner_service.is_gibberish_or_broken("Mitochondria generate ATP through oxidative phosphorylation.") is False
    assert cleaner_service.is_gibberish_or_broken("function calculateMetrics(records: Array<DataPoint>): SummaryStats {") is False
    assert cleaner_service.is_gibberish_or_broken("The judicial review doctrine safeguards constitutional supremacy.") is False

def test_generic_ocr_cleaning_and_duplicate_suppression():
    """
    Tests generic OCR cleaning (stripping arbitrary line numbers, removing symbol junk)
    and token-level duplicate detection on distinct domains.
    """
    raw_ocr_1 = """
    10: def compute_gradient(weights, inputs):
    11:     predictions = np.dot(inputs, weights)
    12:     loss = np.mean((predictions - targets) ** 2)
    13:     return 2 * np.dot(inputs.T, (predictions - targets)) / len(inputs)
    """
    
    cleaned_ocr_1 = cleaner_service.clean_ocr_text(raw_ocr_1)
    assert "10:" not in cleaned_ocr_1
    assert "11:" not in cleaned_ocr_1
    assert "compute_gradient" in cleaned_ocr_1
    assert "predictions" in cleaned_ocr_1

    # Identical slide with slightly shifted timestamps / minor formatting differences
    raw_ocr_2 = """
    10 def compute_gradient(weights, inputs):
    11 predictions = np.dot(inputs, weights)
    12 loss = np.mean((predictions - targets) ** 2)
    13 return 2 * np.dot(inputs.T, (predictions - targets)) / len(inputs)
    """
    cleaned_ocr_2 = cleaner_service.clean_ocr_text(raw_ocr_2)
    
    # Duplicate detector should flag ocr_2 as duplicate of ocr_1
    is_dup = cleaner_service.is_duplicate_ocr(cleaned_ocr_2, [cleaned_ocr_1])
    assert is_dup is True

    # Brand new distinct slide on a different topic
    ocr_3 = """
    class NeuralNetwork(nn.Module):
        def __init__(self, input_dim, hidden_dim):
            super().__init__()
            self.fc1 = nn.Linear(input_dim, hidden_dim)
    """
    cleaned_ocr_3 = cleaner_service.clean_ocr_text(ocr_3)
    is_not_dup = cleaner_service.is_duplicate_ocr(cleaned_ocr_3, [cleaned_ocr_1])
    assert is_not_dup is False

def test_generic_pipeline_quality_metrics():
    """
    Verifies computation of generic quality metrics (n-gram repetition rate,
    sentence similarity, chunk overlap).
    """
    # N-gram repetition rate test
    repetitive_text = "the model converges the model converges the model converges the model converges"
    rep_rate = cleaner_service.compute_ngram_repetition_rate(repetitive_text, n=3)
    assert rep_rate > 0.50

    clean_text = "The quick brown fox jumps over the lazy dog in the tranquil forest."
    clean_rep_rate = cleaner_service.compute_ngram_repetition_rate(clean_text, n=3)
    assert clean_rep_rate == 0.0

    # Sentence similarity test
    s1 = "Distributed ledgers guarantee Byzantine fault tolerance across nodes."
    s2 = "Distributed ledgers provide Byzantine fault tolerance across validator nodes."
    sim = cleaner_service.compute_sentence_similarity(s1, s2)
    assert sim >= 0.70

    # Chunk overlap test
    c1 = "We begin by analyzing the neural network architecture"
    c2 = "neural network architecture and the forward propagation step."
    overlap = cleaner_service.compute_chunk_overlap_ratio(c1, c2)
    assert overlap >= 0.50

def test_deterministic_notes_sanitizer():
    """
    Verifies that the deterministic safety pass purges OCR noise, fake code blocks,
    and debugging labels from generated notes packages.
    """
    drafted_notes = {
        "summary_exec": "This lecture explores cellular respiration.\n**Visual Breakdown:** Diagram of mitochondria.",
        "summary_detailed": (
            "### Lecture Overview\n\n"
            "![Slide at 01:00](http://example.com/s1.jpg)\n\n"
            "**Code / Slide Content:**\n```sql\n~VERLOAD 14Jf4 dor ttee\n```\n\n"
            "```python\ndef calculate_atp(glucose_moles):\n    return glucose_moles * 32\n```\n"
        ),
        "revision_notes": "- [ ] Review executive summary.\n- [ ] Master the electron transport chain mechanism.",
        "takeaways": "1. Core principles demonstrated in lecture.\n2. Glycolysis yields 2 net ATP per glucose molecule.",
        "glossary": "- **ATP**: Adenosine triphosphate energy currency."
    }

    sanitized = llm_service._deterministic_sanitize_notes_dict(drafted_notes)

    # 1. Debug labels stripped
    assert "Code / Slide Content" not in sanitized["summary_detailed"]
    assert "Visual Breakdown" not in sanitized["summary_exec"]

    # 2. Corrupt code block purged
    assert "~VERLOAD" not in sanitized["summary_detailed"]
    assert "14Jf4" not in sanitized["summary_detailed"]

    # 3. Authentic code preserved
    assert "def calculate_atp" in sanitized["summary_detailed"]

    # 4. Generic boilerplate lines purged
    assert "Review executive summary" not in sanitized["revision_notes"]
    assert "Core principles demonstrated in lecture" not in sanitized["takeaways"]
    assert "Glycolysis yields 2 net ATP" in sanitized["takeaways"]

def test_genuine_code_validation_and_corrupt_code_purging():
    """
    Explicitly tests rejection of corrupt OCR code fragments (e.g. 'Ren44\n7solInier...')
    and verifies that only 100% syntactically valid code blocks are preserved.
    """
    corrupt_ocr_1 = "Ren44\n7solInier\nwth Drahon (SCLie nln"
    corrupt_ocr_2 = "EfaL\n7solInier\nwth Dahon (SCLie enen"
    
    assert cleaner_service.is_gibberish_or_broken(corrupt_ocr_1) is True
    assert cleaner_service.is_gibberish_or_broken(corrupt_ocr_2) is True
    assert cleaner_service.is_genuine_code(corrupt_ocr_1) is False
    assert cleaner_service.is_genuine_code(corrupt_ocr_2) is False

    valid_sql = "SELECT employee_id, salary FROM employees WHERE salary > 50000 ORDER BY salary DESC;"
    valid_python = "def compute_loss(y_true, y_pred):\n    return np.mean((y_true - y_pred) ** 2)"
    
    assert cleaner_service.is_genuine_code(valid_sql) is True
    assert cleaner_service.is_genuine_code(valid_python) is True

    # Notes with corrupted code blocks must be completely stripped of the code blocks
    draft_notes = {
        "summary_exec": "Python data science lecture.",
        "summary_detailed": (
            "#### Slide at 10:30\n\n"
            "```\nRen44\n7solInier\nwth Drahon (SCLie nln\n```\n\n"
            "#### Slide at 11:30\n\n"
            "```\nEfaL\n7solInier\nwth Dahon (SCLie enen\n```\n\n"
            "#### Valid Code Slide\n\n"
            "```python\ndef calculate_metrics(data):\n    return sum(data) / len(data)\n```\n"
        )
    }

    sanitized = llm_service._deterministic_sanitize_notes_dict(draft_notes)
    
    assert "Ren44" not in sanitized["summary_detailed"]
    assert "7solInier" not in sanitized["summary_detailed"]
    assert "EfaL" not in sanitized["summary_detailed"]
    assert "wth Drahon" not in sanitized["summary_detailed"]
    assert "def calculate_metrics" in sanitized["summary_detailed"]
