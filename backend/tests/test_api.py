import pytest
from app.core.security import get_password_hash, verify_password, create_access_token, decode_access_token
from app.services.export import export_service
from app.models.models import NoteOutput

def test_security_utilities():
    password = "secretpassword123"
    hashed = get_password_hash(password)
    
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False

    subject = "testuser@example.com"
    token = create_access_token(subject=subject)
    decoded = decode_access_token(token)
    
    assert decoded == subject

def test_export_markdown_assembly():
    mock_notes = NoteOutput(
        summary_exec="Mock Executive Summary",
        summary_detailed="Mock Detailed Summary",
        revision_notes="Mock Revision notes",
        takeaways="* Takeaway 1\n* Takeaway 2",
        glossary="Term: Definition",
        flashcards=[{"question": "Q1", "answer": "A1"}],
        mcqs=[{"question": "Q1", "options": ["A", "B"], "answer": "A", "explanation": "Why A"}],
        mindmap="graph TD\n  A --> B"
    )

    md = export_service.generate_markdown(mock_notes, "Test Lecture")
    
    assert "# Test Lecture - Study Notes" in md
    assert "## Executive Summary" in md
    assert "Mock Executive Summary" in md
    assert "## Detailed Lecture Notes" in md
    assert "Mock Detailed Summary" in md
    assert "## Multiple Choice Quiz" in md
    assert "Correct Answer: A" in md

def test_export_docx_buffer():
    mock_notes = NoteOutput(
        summary_exec="Mock Executive Summary",
        summary_detailed="Mock Detailed Summary",
        revision_notes="Mock Revision notes",
        takeaways="* Takeaway 1\n* Takeaway 2",
        glossary="Term: Definition",
        flashcards=[{"question": "Q1", "answer": "A1"}],
        mcqs=[{"question": "Q1", "options": ["A", "B"], "answer": "A", "explanation": "Why A"}],
        mindmap="graph TD\n  A --> B"
    )

    docx_bytes = export_service.generate_docx(mock_notes, "Test Lecture")
    
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 0

def test_export_pdf_buffer():
    mock_notes = NoteOutput(
        summary_exec="Mock Executive Summary",
        summary_detailed="Mock Detailed Summary",
        revision_notes="Mock Revision notes",
        takeaways="* Takeaway 1\n* Takeaway 2",
        glossary="Term: Definition",
        flashcards=[{"question": "Q1", "answer": "A1"}],
        mcqs=[{"question": "Q1", "options": ["A", "B"], "answer": "A", "explanation": "Why A"}],
        mindmap="graph TD\n  A --> B"
    )

    pdf_bytes = export_service.generate_pdf(mock_notes, "Test Lecture")
    
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
