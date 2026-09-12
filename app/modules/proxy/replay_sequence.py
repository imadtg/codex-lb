"""Sequence translation for one verified replacement upstream lifecycle."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ReplaySequence:
    downstream_watermark: int
    upstream_watermark: int | None = None
    offset: int | None = None

    def advance(self, sequence: int, *, suppressed: bool) -> int:
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ValueError("replacement sequence must be a nonnegative integer")
        if self.upstream_watermark is not None and sequence <= self.upstream_watermark:
            raise ValueError("replacement upstream sequence did not advance")
        self.upstream_watermark = sequence
        if suppressed:
            return sequence
        if self.offset is None:
            self.offset = self.downstream_watermark + 1 - sequence
        mapped = sequence + self.offset
        if mapped <= self.downstream_watermark:
            raise ValueError("replacement downstream sequence did not advance")
        self.downstream_watermark = mapped
        return mapped
