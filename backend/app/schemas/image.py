from typing import Optional

from pydantic import BaseModel


class ImageResult(BaseModel):
    """One Unsplash photo, with the attribution Unsplash's API guidelines
    require (photographer name/profile + Unsplash link). Never a fabricated
    URL -- if Unsplash has nothing relevant, the search returns an empty list
    and the frontend falls back to a local placeholder image."""

    id: str
    url: str  # 'regular' size, hotlinked per Unsplash guidelines (not re-hosted)
    thumb_url: str
    width: int
    height: int
    description: Optional[str] = None
    photographer_name: str
    photographer_profile_url: str
    unsplash_url: str  # link back to the photo's Unsplash page (required attribution)


class ImageSearchResponse(BaseModel):
    configured: bool
    images: list[ImageResult] = []
    message: Optional[str] = None
    attribution_note: str = "Photos via Unsplash. Attribution to the photographer and Unsplash is required by Unsplash's API guidelines."
