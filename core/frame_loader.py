from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import cv2


def _natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


@dataclass(frozen=True)
class FrameData:
    index: int
    path: Path
    image: "cv2.typing.MatLike"
    width: int
    height: int


class FrameLoader:
    def __init__(
        self,
        frames_dir: Path | str,
        exts: Sequence[str] | None = None,
        recursive: bool = False,
        start: int = 0,
        stop: int | None = None,
        step: int = 1,
    ) -> None:
        self.frames_dir = Path(frames_dir)
        if not self.frames_dir.exists():
            raise FileNotFoundError(f"Frames folder not found: {self.frames_dir}")
        self.exts = {e.lower() for e in (exts or [".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"])}
        self.recursive = recursive
        self.start = start
        self.stop = stop
        self.step = step
        self._files = self._scan()

    def _scan(self) -> list[Path]:
        pattern = "**/*" if self.recursive else "*"
        files = [
            p
            for p in self.frames_dir.glob(pattern)
            if p.is_file() and p.suffix.lower() in self.exts
        ]
        files.sort(key=lambda p: _natural_key(p.name))
        return files

    def __len__(self) -> int:
        return len(self._files[self.start : self.stop : self.step])

    def paths(self) -> list[Path]:
        return list(self._files[self.start : self.stop : self.step])

    def __iter__(self) -> Iterator[FrameData]:
        files = self._files[self.start : self.stop : self.step]
        for idx, path in enumerate(files):
            img = cv2.imread(str(path))
            if img is None:
                continue
            h, w = img.shape[:2]
            yield FrameData(index=idx, path=path, image=img, width=w, height=h)

    def iter_images(self) -> Iterable["cv2.typing.MatLike"]:
        for frame in self:
            yield frame.image
