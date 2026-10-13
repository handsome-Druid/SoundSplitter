from pydantic import BaseModel, Field


class V1(BaseModel):
    left: str | None = None
    right: str | None = None
    source: str | None = None
    volume: str | None = None
    left_latency: int = Field(default=0, ge=0)
    right_latency: int = Field(default=0, ge=0)
