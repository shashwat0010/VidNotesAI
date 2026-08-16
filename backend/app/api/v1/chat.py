import numpy as np
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, text
from app.core.config import settings
from app.core.db import get_db
from app.api.v1.auth import get_current_user
from app.models.models import User, Video, ChunkEmbedding, TranscriptSegment, ChatMessage
from app.schemas.schemas import ChatMessageCreate, ChatMessageResponse
from app.services.llm import llm_service

router = APIRouter()

@router.get("/{video_id}/messages", response_model=List[ChatMessageResponse])
async def get_chat_history(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify owner
    v_res = await db.execute(select(Video).filter(Video.id == video_id, Video.user_id == current_user.id))
    if not v_res.scalars().first():
         raise HTTPException(status_code=404, detail="Video workspace not found")

    result = await db.execute(
        select(ChatMessage)
        .filter(ChatMessage.video_id == video_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return result.scalars().all()

@router.post("/{video_id}", response_model=ChatMessageResponse)
async def chat_with_video(
    video_id: str,
    message_in: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify owner
    v_res = await db.execute(select(Video).filter(Video.id == video_id, Video.user_id == current_user.id))
    video = v_res.scalars().first()
    if not video:
        raise HTTPException(status_code=404, detail="Video workspace not found")

    query_str = message_in.content.strip()
    query_emb = llm_service.get_embedding(query_str) if query_str else None

    vector_rows = []
    # 1. Vector Search (pgvector on PostgreSQL or NumPy cosine on SQLite)
    try:
        if not settings.USE_SQLITE and query_emb:
            score_col = (1 - ChunkEmbedding.embedding.cosine_distance(query_emb)).label("score")
            vector_res = await db.execute(
                select(ChunkEmbedding, score_col)
                .filter(ChunkEmbedding.video_id == video_id)
                .order_by(ChunkEmbedding.embedding.cosine_distance(query_emb))
                .limit(10)
            )
            vector_rows = vector_res.all()
        else:
            chunks_res = await db.execute(select(ChunkEmbedding).filter(ChunkEmbedding.video_id == video_id))
            all_chunks = chunks_res.scalars().all()
            if all_chunks and query_emb:
                q_vec = np.array(query_emb, dtype=np.float32)
                norm_q = np.linalg.norm(q_vec)
                scored = []
                for c in all_chunks:
                    if c.embedding is not None:
                        c_vec = np.array(c.embedding, dtype=np.float32)
                        norm_c = np.linalg.norm(c_vec)
                        if norm_q > 0 and norm_c > 0:
                            sim = float(np.dot(q_vec, c_vec) / (norm_q * norm_c))
                            scored.append((c, sim))
                scored.sort(key=lambda x: x[1], reverse=True)
                vector_rows = [(c, s) for c, s in scored[:10]]
    except Exception as v_err:
        print(f"[RAG Vector Search fallback notice]: {v_err}")

    # 2. Lexical / Keyword Search (Top 10)
    lexical_rows = []
    if query_str:
        words = [w for w in query_str.split() if len(w) > 2]
        if words:
            try:
                conditions = [ChunkEmbedding.text.ilike(f"%{w}%") for w in words[:6]]
                lexical_res = await db.execute(
                    select(ChunkEmbedding)
                    .filter(ChunkEmbedding.video_id == video_id, or_(*conditions))
                    .limit(10)
                )
                lexical_rows = lexical_res.scalars().all()
            except Exception as lex_err:
                print(f"[RAG Lexical search notice]: {lex_err}")

    # 3. Reciprocal Rank Fusion (RRF)
    k = 60
    rrf_scores = {}
    for rank_idx, row in enumerate(vector_rows, start=1):
        chunk = row[0]
        v_score = float(row[1]) if len(row) > 1 else 0.0
        if chunk.id not in rrf_scores:
            rrf_scores[chunk.id] = {"chunk": chunk, "score": 0.0, "vector_score": v_score}
        rrf_scores[chunk.id]["score"] += 1.0 / (k + rank_idx)

    for rank_idx, chunk in enumerate(lexical_rows, start=1):
        if chunk.id not in rrf_scores:
            rrf_scores[chunk.id] = {"chunk": chunk, "score": 0.0, "vector_score": 0.0}
        rrf_scores[chunk.id]["score"] += 1.0 / (k + rank_idx)

    sorted_rrf = sorted(rrf_scores.values(), key=lambda x: x["score"], reverse=True)

    contexts = []
    for item in sorted_rrf[:6]:
        c = item["chunk"]
        contexts.append({
            "text": c.text,
            "start_time": c.start_time,
            "end_time": c.end_time,
            "score": float(item["score"])
        })

    # 4. Fallback directly to TranscriptSegments if no embeddings found
    if not contexts:
        t_res = await db.execute(
            select(TranscriptSegment)
            .filter(TranscriptSegment.video_id == video_id)
            .order_by(TranscriptSegment.start_time.asc())
        )
        t_segs = t_res.scalars().all()
        for t in t_segs[:15]:
            contexts.append({
                "text": t.text,
                "start_time": t.start_time,
                "end_time": t.end_time,
                "score": 1.0
            })

    # Retrieve last 6 chat messages for conversation history
    history_result = await db.execute(
        select(ChatMessage)
        .filter(ChatMessage.video_id == video_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(6)
    )
    history_rows = list(reversed(history_result.scalars().all()))
    history = [{"role": h.role, "content": h.content} for h in history_rows]

    # Invoke LLM RAG
    ai_response = llm_service.answer_chat(
        question=message_in.content,
        contexts=contexts,
        history=history
    )

    # Save User message
    user_msg = ChatMessage(
        video_id=video_id,
        user_id=current_user.id,
        role="user",
        content=message_in.content,
        citations=[]
    )
    db.add(user_msg)

    # Save Assistant message
    assistant_msg = ChatMessage(
        video_id=video_id,
        user_id=current_user.id,
        role="assistant",
        content=ai_response.get("answer", ""),
        citations=ai_response.get("citations", [])
    )
    db.add(assistant_msg)
    
    await db.commit()
    await db.refresh(assistant_msg)

    return assistant_msg

