from typing import Literal

from pydantic import BaseModel, Field


class V2(BaseModel):
    left: str | None = None
    right: str | None = None
    source: str | None = None
    volume: str | None = None
    left_latency_ms: int = Field(default=0, ge=0)
    right_latency_ms: int = Field(default=0, ge=0)
    left_buffer_time_ms: int = Field(default=250, ge=0)
    right_buffer_time_ms: int = Field(default=250, ge=0)
    source_buffer_time_ms: int = Field(default=250, ge=0)
    left_native_period: Literal[-1, 32, 64, 128, 256, 512, 1024, 2048, 4096] = Field(
        default=-1
    )
    right_native_period: Literal[-1, 32, 64, 128, 256, 512, 1024, 2048, 4096] = Field(
        default=-1
    )
    source_native_period: Literal[-1, 32, 64, 128, 256, 512, 1024, 2048, 4096] = Field(
        default=-1
    )
    language: str = "en_US"
