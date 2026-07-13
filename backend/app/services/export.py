import io
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.models.models import NoteOutput

class ExportService:
    @staticmethod
    def generate_markdown(note: NoteOutput, title: str) -> str:
        md = []
        md.append(f"# {title} - Study Notes")
        md.append("\n## Executive Summary\n")
        md.append(note.summary_exec)
        
        md.append("\n## Detailed Lecture Notes\n")
        md.append(note.summary_detailed)
        
        md.append("\n## Revision & Review Checklist\n")
        md.append(note.revision_notes)
        
        md.append("\n## Key Takeaways\n")
        md.append(note.takeaways)
        
        md.append("\n## Glossary of Terms\n")
        md.append(note.glossary)
        
        md.append("\n## Flashcards\n")
        for idx, card in enumerate(note.flashcards, 1):
            md.append(f"**Q{idx}:** {card.get('question')}")
            md.append(f"**A{idx}:** {card.get('answer')}\n")
            
        md.append("\n## Multiple Choice Quiz\n")
        for idx, mcq in enumerate(note.mcqs, 1):
            md.append(f"**Question {idx}:** {mcq.get('question')}")
            for opt in mcq.get('options', []):
                md.append(f"- {opt}")
            md.append(f"\n*Correct Answer: {mcq.get('answer')}*")
            md.append(f"*Explanation: {mcq.get('explanation')}*\n")

        md.append("\n## Mermaid Mind Map\n")
        md.append("```mermaid")
        md.append(note.mindmap)
        md.append("```")

        return "\n".join(md)

    @staticmethod
    def generate_docx(note: NoteOutput, title: str, keyframes: list = None) -> bytes:
        import io
        import re
        import requests
        from docx import Document
        from docx.shared import Inches, Pt, RGBColor

        doc = Document()
        
        # Add basic document configurations
        sections = doc.sections
        for section in sections:
            section.top_margin = Inches(1)
            section.bottom_margin = Inches(1)
            section.left_margin = Inches(1)
            section.right_margin = Inches(1)

        # Base style configuration
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Arial'
        font.size = Pt(11)

        # Title
        t = doc.add_heading(level=0)
        run = t.add_run(f"{title} - Study Notes")
        run.font.size = Pt(24)
        run.font.color.rgb = RGBColor(31, 41, 55)

        # Setup keyframes map
        MINIO_BASE = "http://minio:9000"
        kf_url_map = {}
        if keyframes:
            for kf in keyframes:
                url = kf.s3_url if hasattr(kf, 's3_url') else kf.get('s3_url') if isinstance(kf, dict) else None
                if url:
                    kf_url_map[url] = f"{MINIO_BASE}{url}"

        def _fetch_img_stream(url: str):
            try:
                resp = requests.get(url, timeout=8)
                resp.raise_for_status()
                return io.BytesIO(resp.content)
            except Exception as e:
                print(f"[DOCX] Image fetch failed {url}: {e}")
                return None

        def _parse_md_docx(text: str):
            if not isinstance(text, str):
                return
            lines = text.splitlines()
            for line in lines:
                l_str = line.strip()
                if not l_str:
                    continue

                # Check images
                img_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
                matches = list(re.finditer(img_pattern, l_str))
                if matches:
                    last_idx = 0
                    for match in matches:
                        start_pos, end_pos = match.span()
                        txt = l_str[last_idx:start_pos].strip()
                        if txt:
                            doc.add_paragraph(txt)
                        
                        caption_text = match.group(1)
                        img_url = match.group(2)
                        fetch_url = kf_url_map.get(img_url, f"{MINIO_BASE}{img_url}" if img_url.startswith('/') else None)
                        if fetch_url:
                            stream = _fetch_img_stream(fetch_url)
                            if stream:
                                try:
                                    doc.add_picture(stream, width=Inches(4.5))
                                    if caption_text:
                                        cap_p = doc.add_paragraph()
                                        cap_run = cap_p.add_run(caption_text)
                                        cap_run.italic = True
                                        cap_run.font.size = Pt(9)
                                except Exception as e:
                                    print(f"[DOCX] Add picture failed: {e}")
                        last_idx = end_pos
                    txt_after = l_str[last_idx:].strip()
                    if txt_after:
                        doc.add_paragraph(txt_after)
                    continue

                # Headings
                if l_str.startswith("### "):
                    p = doc.add_heading(l_str[4:], level=3)
                    p.style.font.color.rgb = RGBColor(55, 65, 81)
                elif l_str.startswith("## "):
                    p = doc.add_heading(l_str[3:], level=2)
                    p.style.font.color.rgb = RGBColor(31, 41, 55)
                elif l_str.startswith("# "):
                    p = doc.add_heading(l_str[2:], level=1)
                    p.style.font.color.rgb = RGBColor(30, 64, 175)
                elif l_str.startswith("- ") or l_str.startswith("* "):
                    doc.add_paragraph(l_str[2:], style='List Bullet')
                elif re.match(r'^\d+\.\s+(.+)', l_str):
                    match = re.match(r'^\d+\.\s+(.+)', l_str)
                    doc.add_paragraph(match.group(1), style='List Number')
                else:
                    doc.add_paragraph(l_str)

        # Executive Summary
        doc.add_heading("Executive Summary", level=1)
        _parse_md_docx(note.summary_exec)

        # Detailed summary
        doc.add_heading("Detailed Lecture Notes", level=1)
        _parse_md_docx(note.summary_detailed)

        # Revision Guide
        doc.add_heading("Revision Guide", level=1)
        _parse_md_docx(note.revision_notes)

        # Takeaways
        doc.add_heading("Key Takeaways", level=1)
        _parse_md_docx(note.takeaways)

        # Glossary
        doc.add_heading("Glossary of Terms", level=1)
        _parse_md_docx(note.glossary)

        # Flashcards
        if note.flashcards:
            doc.add_heading("Flashcards", level=1)
            for idx, card in enumerate(note.flashcards, 1):
                p = doc.add_paragraph()
                p.add_run(f"Q{idx}: ").bold = True
                p.add_run(f"{card.get('question')}\n")
                p.add_run(f"A{idx}: ").bold = True
                p.add_run(f"{card.get('answer')}")

        # Quiz
        if note.mcqs:
            doc.add_heading("Multiple Choice Quiz", level=1)
            for idx, mcq in enumerate(note.mcqs, 1):
                p = doc.add_paragraph()
                p.add_run(f"Question {idx}: ").bold = True
                p.add_run(f"{mcq.get('question')}\n")
                for o in mcq.get('options', []):
                    p.add_run(f"  [ ] {o}\n")
                p.add_run("Correct Answer: ").bold = True
                p.add_run(f"{mcq.get('answer')}\n")
                p.add_run("Explanation: ").italic = True
                p.add_run(f"{mcq.get('explanation')}")

        # Save to buffer
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        return file_stream.getvalue()


    @staticmethod
    def generate_pdf(note: NoteOutput, title: str, keyframes: list = None) -> bytes:
        import re
        import requests
        from reportlab.platypus import Image as RLImage
        from reportlab.lib.units import inch

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=60,
            leftMargin=60,
            topMargin=60,
            bottomMargin=60
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'DocTitle', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=22, leading=28,
            textColor=colors.HexColor('#111827'), spaceAfter=20
        )
        h1_style = ParagraphStyle(
            'H1', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=16, leading=20,
            textColor=colors.HexColor('#1e40af'),
            spaceBefore=18, spaceAfter=8, keepWithNext=True
        )
        h2_style = ParagraphStyle(
            'H2', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=13, leading=17,
            textColor=colors.HexColor('#1f2937'),
            spaceBefore=12, spaceAfter=6, keepWithNext=True
        )
        h3_style = ParagraphStyle(
            'H3', parent=styles['Normal'],
            fontName='Helvetica-BoldOblique', fontSize=11, leading=15,
            textColor=colors.HexColor('#374151'),
            spaceBefore=8, spaceAfter=4, keepWithNext=True
        )
        body_style = ParagraphStyle(
            'Body', parent=styles['Normal'],
            fontName='Helvetica', fontSize=10, leading=15,
            textColor=colors.HexColor('#374151'), spaceAfter=4
        )
        bullet_style = ParagraphStyle(
            'Bullet', parent=body_style,
            leftIndent=18, bulletIndent=6, spaceAfter=3
        )
        caption_style = ParagraphStyle(
            'Caption', parent=styles['Normal'],
            fontName='Helvetica-Oblique', fontSize=8, leading=10,
            textColor=colors.HexColor('#6b7280'),
            alignment=1, spaceAfter=8  # centered
        )

        # Build a quick lookup: url path → local MinIO fetch URL
        MINIO_BASE = "http://minio:9000"
        kf_url_map = {}
        if keyframes:
            for kf in keyframes:
                url = kf.s3_url  # e.g. /vidnotes-storage/keyframes/.../frame_0001.jpg
                kf_url_map[url] = f"{MINIO_BASE}{url}"

        def _inline_md(text: str) -> str:
            """Convert inline markdown (**bold**, *italic*, `code`) to ReportLab HTML."""
            # Escape XML special chars first (except already-added tags)
            text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', text)
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
            text = re.sub(r'`(.+?)`', r'<font name="Courier">\1</font>', text)
            return text

        def _fetch_image(url: str):
            """Fetch image bytes from MinIO and return an RLImage or None."""
            try:
                resp = requests.get(url, timeout=8)
                resp.raise_for_status()
                img_buf = io.BytesIO(resp.content)
                img = RLImage(img_buf, width=4.5 * inch, height=2.8 * inch, kind='proportional')
                return img
            except Exception as e:
                print(f"[PDF] Could not fetch image {url}: {e}")
                return None

        def _safe_str(value) -> str:
            """Convert any value (str, dict, list) to a clean string."""
            if isinstance(value, str):
                return value
            if isinstance(value, (dict, list)):
                import json as _json
                try:
                    # Try to convert structured data to readable text
                    if isinstance(value, list):
                        parts = []
                        for item in value:
                            if isinstance(item, dict):
                                parts.append(', '.join(f"{k}: {v}" for k, v in item.items()))
                            else:
                                parts.append(str(item))
                        return '\n'.join(parts)
                    elif isinstance(value, dict):
                        return '\n'.join(f"**{k}**: {v}" for k, v in value.items())
                except Exception:
                    pass
                return _json.dumps(value, indent=2)
            return str(value) if value else ""

        def _parse_markdown(text: str, story: list):
            """Parse markdown text line-by-line and append PDF elements to story."""
            text = _safe_str(text)
            # Handle inline image refs before line processing
            lines = text.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i]

                # Image: ![caption](url)
                img_match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line.strip())
                if img_match:
                    caption_text = img_match.group(1)
                    img_url = img_match.group(2)
                    # Map relative URL to internal MinIO URL
                    fetch_url = kf_url_map.get(img_url, f"{MINIO_BASE}{img_url}" if img_url.startswith('/') else None)
                    if fetch_url:
                        img = _fetch_image(fetch_url)
                        if img:
                            story.append(Spacer(1, 6))
                            story.append(img)
                            if caption_text:
                                story.append(Paragraph(caption_text, caption_style))
                            story.append(Spacer(1, 6))
                    i += 1
                    continue

                # H1: # Heading
                if re.match(r'^#\s+(.+)', line):
                    text_content = re.match(r'^#\s+(.+)', line).group(1)
                    story.append(Paragraph(_inline_md(text_content), h2_style))
                    i += 1
                    continue

                # H2: ## Heading
                if re.match(r'^##\s+(.+)', line):
                    text_content = re.match(r'^##\s+(.+)', line).group(1)
                    story.append(Paragraph(_inline_md(text_content), h2_style))
                    i += 1
                    continue

                # H3: ### Heading
                if re.match(r'^###\s+(.+)', line):
                    text_content = re.match(r'^###\s+(.+)', line).group(1)
                    story.append(Paragraph(_inline_md(text_content), h3_style))
                    i += 1
                    continue

                # Horizontal rule: ---
                if re.match(r'^---+\s*$', line.strip()):
                    story.append(Spacer(1, 4))
                    i += 1
                    continue

                # Bullet: - item or * item
                if re.match(r'^[\-\*]\s+(.+)', line):
                    text_content = re.match(r'^[\-\*]\s+(.+)', line).group(1)
                    story.append(Paragraph(f"• {_inline_md(text_content)}", bullet_style))
                    i += 1
                    continue

                # Numbered list: 1. item
                num_match = re.match(r'^(\d+)\.\s+(.+)', line)
                if num_match:
                    num = num_match.group(1)
                    text_content = num_match.group(2)
                    story.append(Paragraph(f"{num}. {_inline_md(text_content)}", bullet_style))
                    i += 1
                    continue

                # Empty line → small spacer
                if not line.strip():
                    story.append(Spacer(1, 5))
                    i += 1
                    continue

                # Normal paragraph
                story.append(Paragraph(_inline_md(line), body_style))
                i += 1

        story = []

        # ── Title ──────────────────────────────────────────────────────────────
        story.append(Paragraph(f"{title}", title_style))
        story.append(Paragraph("Study Notes", ParagraphStyle('Sub', parent=body_style,
            fontName='Helvetica-Oblique', fontSize=11, textColor=colors.HexColor('#6b7280'), spaceAfter=20)))
        story.append(Spacer(1, 12))

        # ── Executive Summary ──────────────────────────────────────────────────
        story.append(Paragraph("Executive Summary", h1_style))
        _parse_markdown(note.summary_exec, story)
        story.append(Spacer(1, 10))

        # ── Detailed Lecture Notes (with inline slide images) ──────────────────
        story.append(Paragraph("Detailed Lecture Notes", h1_style))
        _parse_markdown(note.summary_detailed, story)
        story.append(Spacer(1, 10))

        # ── Revision Guide ─────────────────────────────────────────────────────
        story.append(Paragraph("Revision Guide", h1_style))
        _parse_markdown(note.revision_notes, story)
        story.append(Spacer(1, 10))

        # ── Key Takeaways ──────────────────────────────────────────────────────
        story.append(Paragraph("Key Takeaways", h1_style))
        _parse_markdown(note.takeaways, story)
        story.append(Spacer(1, 10))

        # ── Glossary ───────────────────────────────────────────────────────────
        story.append(Paragraph("Glossary of Terms", h1_style))
        _parse_markdown(note.glossary, story)
        story.append(Spacer(1, 10))

        # ── Flashcards ─────────────────────────────────────────────────────────
        if note.flashcards:
            story.append(Paragraph("Flashcards", h1_style))
            for idx, card in enumerate(note.flashcards, 1):
                q = _inline_md(str(card.get('question', '')))
                a = _inline_md(str(card.get('answer', '')))
                story.append(Paragraph(f"<b>Q{idx}:</b> {q}", body_style))
                story.append(Paragraph(f"<b>A{idx}:</b> {a}", body_style))
                story.append(Spacer(1, 6))

        # ── Quiz ───────────────────────────────────────────────────────────────
        if note.mcqs:
            story.append(Spacer(1, 10))
            story.append(Paragraph("Multiple Choice Quiz", h1_style))
            for idx, mcq in enumerate(note.mcqs, 1):
                q = _inline_md(str(mcq.get('question', '')))
                story.append(Paragraph(f"<b>Question {idx}:</b> {q}", body_style))
                for opt in mcq.get('options', []):
                    story.append(Paragraph(f"&nbsp;&nbsp;○&nbsp;{_inline_md(str(opt))}", bullet_style))
                ans = _inline_md(str(mcq.get('answer', '')))
                exp = _inline_md(str(mcq.get('explanation', '')))
                story.append(Paragraph(f"<i>✓ Correct: {ans}</i>", body_style))
                story.append(Paragraph(f"<i>Explanation: {exp}</i>", body_style))
                story.append(Spacer(1, 8))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()


export_service = ExportService()
