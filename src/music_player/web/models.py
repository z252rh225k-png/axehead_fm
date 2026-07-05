from pydantic import BaseModel, Field, validator
from typing import Optional
from enum import Enum

class MediaType(str, Enum):
    AUDIO = "audio"
    VIDEO = "video"
    SLIDESHOW = "slideshow"
    RADIO = "radio"
    GAME = "game"

class CatalogEntry(BaseModel):
    """Schema for a catalog entry."""
    type: MediaType
    title: str
    audio: Optional[str] = None
    video: Optional[str] = None
    folder: Optional[str] = None
    stream_url: Optional[str] = None
    image: Optional[str] = None
    station_freq: Optional[str] = None
    interval: Optional[float] = 5.0
    
    class Config:
        use_enum_values = True

class MediaUpload(BaseModel):
    """Schema for file upload metadata."""
    type: str  # 'audio', 'video', 'image'
    title: Optional[str] = None
    
    @validator('type')
    def validate_type(cls, v):
        if v not in ['audio', 'video', 'image']:
            raise ValueError('Must be audio, video, or image')
        return v

class CatalogUpdate(BaseModel):
    """Schema for updating catalog entries."""
    title: Optional[str] = None
    image: Optional[str] = None
    audio: Optional[str] = None
    video: Optional[str] = None
