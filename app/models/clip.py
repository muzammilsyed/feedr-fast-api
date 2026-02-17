"""Clip model (Reels-like) and AudioTrack."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class AudioTrack(Base):
    __tablename__ = "audio_tracks"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    artist = Column(String(255), nullable=True)
    audio_url = Column(Text, nullable=False)
    duration = Column(Integer, nullable=True)
    usage_count = Column(Integer, default=0)
    is_trending = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    clips = relationship("Clip", back_populates="audio_track")


class Clip(Base):
    __tablename__ = "clips"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    video_url = Column(Text, nullable=False)
    thumbnail_url = Column(Text, nullable=True)
    caption = Column(Text, nullable=True)
    audio_id = Column(PG_UUID(as_uuid=True), ForeignKey("audio_tracks.id", ondelete="SET NULL"), nullable=True)
    duration = Column(Integer, nullable=True)  # seconds
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)
    views_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="clips")
    audio_track = relationship("AudioTrack", back_populates="clips")
    comments = relationship("Comment", back_populates="clip", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="clip", cascade="all, delete-orphan")
