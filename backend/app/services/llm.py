import base64
import json
import os
from typing import List, Dict, Any, Optional
import httpx
from openai import OpenAI
from google import genai
from google.genai import types
from app.core.config import settings

try:
    from mistralai import Mistral
except ImportError:
    Mistral = None

class LLMService:
    def __init__(self):
        self._openai_client = None
        self._gemini_client = None
        self._mistral_client = None

    @property
    def openai_client(self) -> OpenAI:
        if self._openai_client is None and settings.OPENAI_API_KEY:
            self._openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai_client

    @property
    def gemini_client(self) -> genai.Client:
        if self._gemini_client is None and settings.GEMINI_API_KEY:
            self._gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._gemini_client

    @property
    def mistral_client(self) -> Optional[Any]:
        if self._mistral_client is None and settings.MISTRAL_API_KEY and Mistral is not None:
            self._mistral_client = Mistral(api_key=settings.MISTRAL_API_KEY)
        return self._mistral_client

    def is_configured(self) -> bool:
        return bool(settings.OPENAI_API_KEY or settings.GEMINI_API_KEY or settings.MISTRAL_API_KEY)

    def get_embedding(self, text: str) -> List[float]:
        """
        Generates 1536-dimensional vector embedding for the input text.
        If using Gemini (768d) or Mistral (1024d), we pad them with zeros 
        to maintain the 1536 dimension required by pgvector database schema.
        Retries automatically on 429 rate-limit errors with exponential backoff.
        """
        import time

        if not self.is_configured():
            # Mock embedding for testing / fallback (1536-dimensional zero vector)
            return [0.0] * 1536

        if settings.OPENAI_API_KEY:
            try:
                response = self.openai_client.embeddings.create(
                    input=[text.replace("\n", " ")],
                    model="text-embedding-3-small"
                )
                return response.data[0].embedding
            except Exception as e:
                print(f"OpenAI embedding failed: {e}")
                # Fallback to gemini or mistral if available
                if not settings.GEMINI_API_KEY and not settings.MISTRAL_API_KEY:
                    raise e

        if settings.GEMINI_API_KEY:
            try:
                # Gemini embedding
                response = self.gemini_client.models.embed_content(
                    model="text-embedding-004",
                    contents=text
                )
                embedding = response.embeddings[0].values
                # Pad Gemini 768 dimensions to 1536
                if len(embedding) < 1536:
                    embedding = list(embedding) + [0.0] * (1536 - len(embedding))
                return embedding[:1536]
            except Exception as e:
                print(f"Gemini embedding failed: {e}")
                if not settings.MISTRAL_API_KEY:
                    raise e

        if settings.MISTRAL_API_KEY and self.mistral_client:
            last_err = None
            for attempt in range(5):
                try:
                    response = self.mistral_client.embeddings.create(
                        model="mistral-embed",
                        inputs=[text]
                    )
                    embedding = response.data[0].embedding
                    # Pad Mistral 1024 dimensions to 1536
                    if len(embedding) < 1536:
                        embedding = list(embedding) + [0.0] * (1536 - len(embedding))
                    return embedding[:1536]
                except Exception as e:
                    last_err = e
                    err_str = str(e)
                    if "429" in err_str or "rate_limit" in err_str.lower() or "Rate limit" in err_str:
                        wait = 2 ** attempt  # 1s, 2s, 4s, 8s, 16s
                        print(f"[Embedding] Mistral 429 rate limit — retrying in {wait}s (attempt {attempt + 1}/5)...")
                        time.sleep(wait)
                    else:
                        print(f"Mistral embedding failed: {e}")
                        raise e
            print(f"Mistral embedding failed after 5 retries: {last_err}")
            raise last_err

        return [0.0] * 1536



    def analyze_keyframe(self, image_path: str, ocr_text: str) -> str:
        """
        Uses a vision model to analyze slides, diagrams, charts, code, UI, or whiteboards in a keyframe.
        """
        if not os.path.exists(image_path):
            return "No keyframe image available."

        if not self.is_configured():
            return f"Mock Vision Description: Keyframe analyze. OCR found: {ocr_text[:50]}"

        # Read image and convert to base64
        with open(image_path, "rb") as image_file:
            img_bytes = image_file.read()
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")

        prompt = f"""You are analyzing a slide/keyframe from a video lecture or presentation.
Here is the text extracted via raw OCR from this frame:
---
{ocr_text}
---
Please describe what is shown in this frame visually. Specifically point out:
1. Any diagrams, architectural flows, tables, math formulas, or charts, and explain what they represent.
2. Any code blocks, user interfaces, or sketches, and summarize their purpose.
3. Combine the OCR text and visual elements into a clear explanation of this screen's contents.
Keep it structured, analytical, and concise (under 250 words)."""

        if settings.OPENAI_API_KEY:
            try:
                response = self.openai_client.chat.completions.create(
                    model=settings.OPENAI_VISION_MODEL,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{img_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=400
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"OpenAI keyframe vision analysis failed: {e}")
                if not settings.GEMINI_API_KEY and not settings.MISTRAL_API_KEY:
                    return f"Vision analysis error: {e}. OCR raw: {ocr_text}"

        if settings.GEMINI_API_KEY:
            try:
                # Using Gemini API client
                response = self.gemini_client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=[
                        types.Part.from_bytes(
                            data=img_bytes,
                            mime_type="image/jpeg"
                        ),
                        prompt
                    ]
                )
                return response.text
            except Exception as e:
                print(f"Gemini keyframe vision analysis failed: {e}")
                if not settings.MISTRAL_API_KEY:
                    return f"Vision analysis error: {e}. OCR raw: {ocr_text}"

        if settings.MISTRAL_API_KEY:
            try:
                import httpx
                headers = {
                    "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": settings.MISTRAL_VISION_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": f"data:image/jpeg;base64,{img_base64}"
                                }
                            ]
                        }
                    ],
                    "max_tokens": 400
                }
                with httpx.Client(timeout=60.0) as client:
                    response = client.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload)
                    response.raise_for_status()
                    res_data = response.json()
                    return res_data["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"Mistral keyframe vision analysis failed: {e}")
                return f"Vision analysis error: {e}. OCR raw: {ocr_text}"


        return f"OCR extracted text: {ocr_text}"



    def clean_ocr_text(self, ocr_text: str) -> str:
        """
        Cleans up raw OCR text by using the LLM to remove noise, meaningless letters,
        and correct typos.
        """
        if not ocr_text or not ocr_text.strip():
            return ""
            
        if not self.is_configured():
            return ocr_text

        prompt = f"""You are an AI text post-processor. Clean up the following raw OCR text extracted from a lecture slide:
---
{ocr_text}
---
Instructions:
1. Correct obvious spelling mistakes and OCR typos.
2. Remove completely random characters, isolated letters (like single 'C', 'x', etc. unless they are variables in a clear mathematical equation), isolated numbers without context, and meaningless fragments.
3. Keep valid terms, proper nouns, complete words, code snippets, and sentences.
4. If the entire text consists only of random noise or gibberish, return absolutely nothing (empty output).
5. Output ONLY the cleaned text. Do not wrap it in markdown ticks or add any explanations."""

        try:
            if settings.MISTRAL_API_KEY and self.mistral_client:
                response = self.mistral_client.chat.complete(
                    model=settings.MISTRAL_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300,
                    temperature=0.0
                )
                return response.choices[0].message.content.strip()
            elif settings.OPENAI_API_KEY:
                response = self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300,
                    temperature=0.0
                )
                return response.choices[0].message.content.strip()
            elif settings.GEMINI_API_KEY:
                response = self.gemini_client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt
                )
                return response.text.strip()
        except Exception as e:
            print(f"Error cleaning OCR text via LLM: {e}")
            
        return ocr_text

    def generate_notes_package(self, consolidated_knowledge: str, keyframes: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Generates Executive summary, Detailed summary (with inline keyframe images), Revision notes, Key takeaways, Glossary.
        Returns a dictionary of generated contents.
        """
        system_prompt = "You are an elite academic tutor and technical analyst. Analyze the provided lecture transcript/OCR/vision log and generate the requested study outputs."
        
        keyframes_instruction = ""
        if keyframes:
            keyframes_list_str = "\n".join(
                f"- Timestamp: [{int(kf['timestamp']//60):02d}:{int(kf['timestamp']%60):02d}], Image URL: {kf['s3_url']}"
                for kf in keyframes
            )
            keyframes_instruction = f"""
We have extracted keyframe slide images from the video. Here is the list of available images with their exact S3 URLs:
{keyframes_list_str}

Please weave these images into the "summary_detailed" section. Whenever a topic is discussed that corresponds to a keyframe, insert the image inline using this exact Markdown syntax:
![Slide at MM:SS](image_url)
Do not invent any URLs; use only the exact URLs provided above.
"""

        prompt = f"""Review this compiled knowledge base of a video lecture (contains transcripts, slide text, and keyframe descriptions):
---
{consolidated_knowledge}
---
{keyframes_instruction}

Generate the following notes package structure as a SINGLE JSON object. It is crucial that the JSON is syntactically valid and matches this structure exactly:

{{
  "summary_exec": "A high-level executive summary (2-3 paragraphs) outlining the key themes and overall thesis of the video.",
  "summary_detailed": "A highly comprehensive detailed summary, formatted in Markdown, complete with subsections and detailed bullet points explaining every major topic discussed. Make sure to weave the keyframe slide images inline exactly where they belong using the ![Slide at MM:SS](image_url) syntax.",
  "revision_notes": "Student-focused study guides, tips, and step-by-step revision checklists based on the content.",
  "takeaways": "A bulleted list of 5-10 core key takeaways or actionable learnings.",
  "glossary": "A definition list of technical terms, acronyms, and jargon mentioned, structured as definitions."
}}

Provide ONLY the valid JSON structure. Do not wrap it in markdown ticks or prefix it in any way. Start with '{{' and end with '}}'."""

        default_response = {
            "summary_exec": "No LLM Configured. Please add API keys to configuration.",
            "summary_detailed": "No LLM Configured. Please add API keys to configuration.",
            "revision_notes": "No LLM Configured. Please add API keys to configuration.",
            "takeaways": "1. Set API keys in configuration.",
            "glossary": "AI Keys: Required credentials."
        }

        if not self.is_configured():
            return default_response

        def _call_mistral(system_msg: str, user_msg: str, max_tokens: int = 3000) -> str:
            """Call Mistral with fallback to OpenAI/Gemini."""
            if settings.OPENAI_API_KEY:
                try:
                    resp = self.openai_client.chat.completions.create(
                        model=settings.OPENAI_MODEL,
                        messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
                        response_format={"type": "json_object"},
                        max_tokens=max_tokens,
                        temperature=0.3
                    )
                    return resp.choices[0].message.content
                except Exception as e:
                    print(f"OpenAI notes call failed: {e}")

            if settings.GEMINI_API_KEY:
                try:
                    resp = self.gemini_client.models.generate_content(
                        model=settings.GEMINI_MODEL,
                        contents=user_msg,
                        config=types.GenerateContentConfig(response_mime_type="application/json", system_instruction=system_msg, temperature=0.3)
                    )
                    return resp.text
                except Exception as e:
                    print(f"Gemini notes call failed: {e}")

            if settings.MISTRAL_API_KEY and self.mistral_client:
                try:
                    resp = self.mistral_client.chat.complete(
                        model=settings.MISTRAL_MODEL,
                        messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
                        response_format={"type": "json_object"},
                        max_tokens=max_tokens,
                        temperature=0.3
                    )
                    return resp.choices[0].message.content
                except Exception as e:
                    print(f"Mistral notes call failed: {e}")

            return ""

        def _parse_json_safe(raw: str) -> Optional[Dict]:
            """Try to parse JSON, then attempt to fix truncated JSON."""
            if not raw:
                return None
            cleaned = raw.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            try:
                return json.loads(cleaned)
            except Exception:
                # Attempt repair: truncate at last valid closing brace
                last_brace = cleaned.rfind("}")
                if last_brace > 0:
                    try:
                        return json.loads(cleaned[:last_brace + 1])
                    except Exception:
                        pass
            return None

        # --- Call 1: Executive + Detailed summary (with inline slide images) ---
        summary_prompt = f"""Review this compiled knowledge base of a video lecture (contains transcripts, slide text, and keyframe descriptions):
---
{consolidated_knowledge}
---
{keyframes_instruction}

Generate ONLY the following two fields as a valid JSON object:
{{
  "summary_exec": "A high-level executive summary (2-3 paragraphs) outlining the key themes and overall thesis of the video.",
  "summary_detailed": "A comprehensive detailed summary in Markdown with subsections. Weave the keyframe slide images inline exactly where they belong using the ![Slide at MM:SS](image_url) syntax."
}}

Provide ONLY valid JSON. Start with '{{' and end with '}}'."""

        summary_raw = _call_mistral(system_prompt, summary_prompt, max_tokens=3000)
        summary_data = _parse_json_safe(summary_raw) or {}
        if not summary_data.get("summary_exec"):
            print("[Notes] Summary call failed or returned empty, using placeholder.")

        # --- Call 2: Revision notes, takeaways, glossary ---
        revision_prompt = f"""Review this compiled knowledge base of a video lecture:
---
{consolidated_knowledge[:8000]}
---

Generate ONLY the following three fields as a valid JSON object:
{{
  "revision_notes": "Student-focused study guide with step-by-step revision tips and a checklist.",
  "takeaways": "A numbered list of 5-10 core key takeaways or actionable learnings.",
  "glossary": "A definition list of key technical terms and jargon mentioned in the lecture."
}}

Provide ONLY valid JSON. Start with '{{' and end with '}}'."""

        revision_raw = _call_mistral(system_prompt, revision_prompt, max_tokens=2000)
        revision_data = _parse_json_safe(revision_raw) or {}

        # Merge both responses
        result = {
            "summary_exec": summary_data.get("summary_exec") or default_response["summary_exec"],
            "summary_detailed": summary_data.get("summary_detailed") or default_response["summary_detailed"],
            "revision_notes": revision_data.get("revision_notes") or default_response["revision_notes"],
            "takeaways": revision_data.get("takeaways") or default_response["takeaways"],
            "glossary": revision_data.get("glossary") or default_response["glossary"],
        }
        return result


    def generate_flashcards(self, consolidated_knowledge: str) -> List[Dict[str, Any]]:
        """
        Generates flashcards testing key concepts on-demand.
        """
        prompt = f"""Review this compiled knowledge base of a video lecture:
---
{consolidated_knowledge}
---
Generate a JSON list of 5-10 flashcards testing key concepts from the video.
Output must match this structure exactly:
[
  {{
    "question": "A question testing a definition or concept.",
    "answer": "The brief, clear answer."
  }}
]
Provide ONLY valid JSON. Do not wrap in markdown blocks or prefix in any way."""

        try:
            raw = ""
            if settings.MISTRAL_API_KEY and self.mistral_client:
                response = self.mistral_client.chat.complete(
                    model=settings.MISTRAL_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"} if hasattr(settings, "MISTRAL_MODEL") else None,
                    max_tokens=2000,
                    temperature=0.4
                )
                raw = response.choices[0].message.content
            elif settings.OPENAI_API_KEY:
                response = self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    max_tokens=2000,
                    temperature=0.4
                )
                raw = response.choices[0].message.content
            elif settings.GEMINI_API_KEY:
                response = self.gemini_client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                raw = response.text

            cleaned = raw.strip()
            if cleaned.startswith("```json"): cleaned = cleaned[7:]
            if cleaned.endswith("```"): cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except Exception as e:
            print(f"Failed to generate flashcards: {e}")
            return []

    def generate_quiz(self, consolidated_knowledge: str) -> List[Dict[str, Any]]:
        """
        Generates MCQ quiz on-demand.
        """
        prompt = f"""Review this compiled knowledge base of a video lecture:
---
{consolidated_knowledge}
---
Generate a JSON list of 5-10 multiple choice questions testing understanding.
Output must match this structure exactly:
[
  {{
    "question": "Multiple choice question testing conceptual understanding.",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": "The full exact text of the correct option.",
    "explanation": "Clear explanation of why this option is correct."
  }}
]
Provide ONLY valid JSON. Do not wrap in markdown blocks or prefix in any way."""

        try:
            raw = ""
            if settings.MISTRAL_API_KEY and self.mistral_client:
                response = self.mistral_client.chat.complete(
                    model=settings.MISTRAL_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"} if hasattr(settings, "MISTRAL_MODEL") else None,
                    max_tokens=3000,
                    temperature=0.4
                )
                raw = response.choices[0].message.content
            elif settings.OPENAI_API_KEY:
                response = self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    max_tokens=3000,
                    temperature=0.4
                )
                raw = response.choices[0].message.content
            elif settings.GEMINI_API_KEY:
                response = self.gemini_client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                raw = response.text

            cleaned = raw.strip()
            if cleaned.startswith("```json"): cleaned = cleaned[7:]
            if cleaned.endswith("```"): cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except Exception as e:
            print(f"Failed to generate MCQs: {e}")
            return []

    def generate_mindmap(self, consolidated_knowledge: str) -> str:
        """
        Generates Mermaid mindmap on-demand.
        """
        prompt = f"""Review this compiled knowledge base of a video lecture:
---
{consolidated_knowledge}
---
Generate a Mermaid.js graph code block (use 'graph TD' or 'mindmap' format) mapping out the hierarchy of concepts.
Provide ONLY the Mermaid syntax lines, do NOT wrap it in ```mermaid code block. Output only raw mermaid syntax."""

        try:
            if settings.MISTRAL_API_KEY and self.mistral_client:
                response = self.mistral_client.chat.complete(
                    model=settings.MISTRAL_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1500,
                    temperature=0.3
                )
                return response.choices[0].message.content.strip()
            elif settings.OPENAI_API_KEY:
                response = self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1500,
                    temperature=0.3
                )
                return response.choices[0].message.content.strip()
            elif settings.GEMINI_API_KEY:
                response = self.gemini_client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt
                )
                return response.text.strip()
        except Exception as e:
            print(f"Failed to generate mindmap: {e}")
            
        return "graph TD\n  Start[Setup App] --> Error[Failed to compile Mindmap]"


    def answer_chat(self, question: str, contexts: List[Dict[str, Any]], history: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        RAG chatbot. Answering based on retrieved transcript chunks.
        Returns a dict: {"answer": str, "citations": List[Dict]}
        """
        system_prompt = """You are VidNotes AI, a helpful virtual study assistant. 
Answering the user's questions about their video/audio lecture based strictly on the provided context passages.
Every context passage has timestamps and text. When answering:
1. Synthesize a detailed, accurate response.
2. Cite the sources you use. A citation is a text snippet mapped to its exact start_time and end_time.
3. If the answer cannot be found in the context, state that clearly rather than hallucinating.
"""

        # Construct context segment texts
        context_str = ""
        for idx, ctx in enumerate(contexts):
            context_str += f"[{idx}] (Time: {ctx['start_time']}s - {ctx['end_time']}s): {ctx['text']}\n\n"

        # Build message history
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
            
        user_msg = f"""Here are the relevant snippets from the lecture transcript:
---
{context_str}
---
User Question: {question}

Please answer the user's question. Provide the answer and format your citations list as a JSON array of citations you actually used. Return a JSON object with this structure:
{{
  "answer": "Your detailed markdown answer with inline numbers [0], [1] indicating citations.",
  "citations": [
     {{
       "text": "The sentence/phrase from the context you cited.",
       "start_time": 10.5,
       "end_time": 25.0
     }}
  ]
}}
Ensure the response is a strict valid JSON object."""

        messages.append({"role": "user", "content": user_msg})

        default_response = {
            "answer": "I'm sorry, I cannot answer questions without an active LLM key configuration.",
            "citations": []
        }

        if not self.is_configured():
            return default_response

        raw_response = ""
        if settings.OPENAI_API_KEY:
            try:
                response = self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.2
                )
                raw_response = response.choices[0].message.content
            except Exception as e:
                print(f"OpenAI Chat RAG failed: {e}")
                if not settings.GEMINI_API_KEY and not settings.MISTRAL_API_KEY:
                    return default_response

        if not raw_response and settings.GEMINI_API_KEY:
            try:
                # Combine messages list into plain text context for Gemini or let Gemini parse
                prompt_content = f"{system_prompt}\n\nHistory:\n"
                for h in history:
                    prompt_content += f"{h['role'].upper()}: {h['content']}\n"
                prompt_content += f"\nContexts:\n{context_str}\n\nUser Question: {question}\n\n{user_msg}"
                
                response = self.gemini_client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt_content,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2
                    )
                )
                raw_response = response.text
            except Exception as e:
                print(f"Gemini Chat RAG failed: {e}")
                if not settings.MISTRAL_API_KEY:
                    return default_response

        if not raw_response and settings.MISTRAL_API_KEY and self.mistral_client:
            try:
                response = self.mistral_client.chat.complete(
                    model=settings.MISTRAL_MODEL,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.2
                )
                raw_response = response.choices[0].message.content
            except Exception as e:
                print(f"Mistral Chat RAG failed: {e}")
                return default_response


        try:
            cleaned_raw = raw_response.strip()
            if cleaned_raw.startswith("```json"):
                cleaned_raw = cleaned_raw[7:]
            if cleaned_raw.endswith("```"):
                cleaned_raw = cleaned_raw[:-3]
            cleaned_raw = cleaned_raw.strip()
            return json.loads(cleaned_raw)
        except Exception as parse_err:
            print(f"Chat RAG parsing failed: {parse_err}. Raw was:\n{raw_response}")
            return {
                "answer": raw_response if raw_response else "Failed to analyze references.",
                "citations": []
            }

llm_service = LLMService()
