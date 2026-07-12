from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.db import get_db
from app.api.v1.auth import get_current_user
from app.models.models import User, Video, ChunkEmbedding, ChatMessage
from app.schemas.schemas import ChatMessageCreate, ChatMessageResponse, SearchResultResponse
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

    # Generate question embedding
    query_emb = llm_service.get_embedding(message_in.content)

    # Perform pgvector cosine distance query
    # cosine_distance is defined on pgvector Column type.
    # The lower the distance, the more similar the vector.
    # similarity = 1 - cosine_distance.
    score_col = (1 - ChunkEmbedding.embedding.cosine_distance(query_emb)).label("score")
    
    rag_result = await db.execute(
        select(ChunkEmbedding, score_col)
        .filter(ChunkEmbedding.video_id == video_id)
        .order_by(ChunkEmbedding.embedding.cosine_distance(query_emb))
        .limit(5)
    )
    
    contexts = []
    rag_rows = rag_result.all()
    for row in rag_rows:
        chunk = row[0]
        score = row[1]
        # Include chunks with a reasonable similarity threshold
        contexts.append({
            "text": chunk.text,
            "start_time": chunk.start_time,
            "end_time": chunk.end_time,
            "score": float(score)
        })

    # Retrieve last 10 chat messages for conversation history
    history_result = await db.execute(
        select(ChatMessage)
        .filter(ChatMessage.video_id == video_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    )
    history_rows = reversed(history_result.scalars().all())
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
    
    await db.flush()

    return assistant_msg
