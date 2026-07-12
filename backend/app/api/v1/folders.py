from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.db import get_db
from app.api.v1.auth import get_current_user
from app.models.models import User, Folder
from app.schemas.schemas import FolderCreate, FolderResponse

router = APIRouter()

@router.get("/", response_model=List[FolderResponse])
async def get_folders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Folder).filter(Folder.user_id == current_user.id).order_by(Folder.created_at.desc())
    )
    return result.scalars().all()

@router.post("/", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    folder_in: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check parent folder ownership if parent_id is supplied
    if folder_in.parent_id:
        parent_result = await db.execute(
            select(Folder).filter(Folder.id == folder_in.parent_id, Folder.user_id == current_user.id)
        )
        parent = parent_result.scalars().first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent folder not found or unauthorized access"
            )

    new_folder = Folder(
        name=folder_in.name,
        user_id=current_user.id,
        parent_id=folder_in.parent_id
    )
    db.add(new_folder)
    await db.flush()
    return new_folder

@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Folder).filter(Folder.id == folder_id, Folder.user_id == current_user.id)
    )
    folder = result.scalars().first()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found or unauthorized access"
        )
        
    await db.delete(folder)
    return None

@router.put("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: int,
    folder_in: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Folder).filter(Folder.id == folder_id, Folder.user_id == current_user.id)
    )
    folder = result.scalars().first()
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found or unauthorized access"
        )

    # Check parent folder if updated
    if folder_in.parent_id:
        parent_result = await db.execute(
            select(Folder).filter(Folder.id == folder_in.parent_id, Folder.user_id == current_user.id)
        )
        parent = parent_result.scalars().first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent folder not found or unauthorized access"
            )
            
    folder.name = folder_in.name
    folder.parent_id = folder_in.parent_id
    db.add(folder)
    return folder
