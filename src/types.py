from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple

class Direction(Enum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"

    @property
    def grid_delta(self) -> Tuple[int, int]:
        """Returns (delta_row, delta_col) for matrix indexing."""
        if self == Direction.UP:
            return (-1, 0)
        elif self == Direction.DOWN:
            return (1, 0)
        elif self == Direction.LEFT:
            return (0, -1)
        elif self == Direction.RIGHT:
            return (0, 1)
        raise ValueError(f"Unknown direction: {self}")

    @property
    def pixel_delta(self) -> Tuple[int, int]:
        """Returns (dx, dy) for image pixel coordinates."""
        if self == Direction.UP:
            return (0, -1)
        elif self == Direction.DOWN:
            return (0, 1)
        elif self == Direction.LEFT:
            return (-1, 0)
        elif self == Direction.RIGHT:
            return (1, 0)
        raise ValueError(f"Unknown direction: {self}")

class CellType(Enum):
    EMPTY = auto()
    OCCUPIED = auto()
    UNKNOWN = auto()

@dataclass
class Cell:
    cell_type: CellType = CellType.EMPTY
    arrow_id: Optional[int] = None  # ID of the arrow occupying this cell (if any)

@dataclass
class ArrowHead:
    arrow_id: int
    row: int
    col: int
    direction: Direction
    x_px: int
    y_px: int
