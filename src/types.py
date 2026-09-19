from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple

class Direction(Enum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"

    @property
    def vector(self) -> Tuple[int, int]:
        """Returns (delta_row, delta_col) for grid movement."""
        if self == Direction.UP:
            return (-1, 0)
        elif self == Direction.DOWN:
            return (1, 0)
        elif self == Direction.LEFT:
            return (0, -1)
        elif self == Direction.RIGHT:
            return (0, 1)
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

@dataclass
class Move:
    arrow_id: int
    row: int
    col: int
    tap_x: int
    tap_y: int
