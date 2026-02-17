"""Feed item schemas - unified feed (posts + reposts)."""
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from app.schemas.post import PostResponse
from app.schemas.repost import RepostResponse


class FeedItemPost(BaseModel):
    type: Literal["post"] = "post"
    post: PostResponse


class FeedItemRepost(BaseModel):
    type: Literal["repost"] = "repost"
    repost: RepostResponse


FeedItemResponse = Annotated[
    Union[FeedItemPost, FeedItemRepost],
    Field(discriminator="type"),
]