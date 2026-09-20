import time
import numpy as np
from typing import List, Dict, Optional, Tuple
from src.game_types import Direction, CellType, Cell
from src.vision import VisionDetector, GridGeometry
from src.actuator import Actuator


class PanController:
    """
    Adaptive Smart Camera Panning Engine.
    Controls ADB swipes with fast duration (120ms) and automatic border detection (3-line white space rule).
    Prunes pan movements when Outer Level Boundaries are detected.
    """
    def __init__(
        self,
        actuator: Actuator,
        detector: Optional[VisionDetector] = None,
        width: int = 600,
        height: int = 1332,
        settle_delay: float = 0.05
    ):
        self.actuator = actuator
        self.detector = detector or VisionDetector()
        self.width = width
        self.height = height
        self.settle_delay = settle_delay

        # Border detection state: True when >= 3 consecutive empty/white lines are found
        self.borders_detected: Dict[Direction, bool] = {
            Direction.UP: False,
            Direction.DOWN: False,
            Direction.LEFT: False,
            Direction.RIGHT: False,
        }

        # Center-out spiral sequence generator state
        self._spiral_sequence: List[Direction] = [
            Direction.RIGHT,
            Direction.DOWN,
            Direction.LEFT,
            Direction.LEFT,
            Direction.UP,
            Direction.UP,
            Direction.RIGHT,
            Direction.RIGHT,
            Direction.RIGHT,
            Direction.DOWN,
            Direction.DOWN,
            Direction.DOWN,
            Direction.LEFT,
            Direction.LEFT,
            Direction.LEFT,
            Direction.LEFT,
        ]
        self._step_idx = 0

    def check_borders(self, grid: List[List[Cell]], geom: GridGeometry) -> Dict[Direction, bool]:
        """
        Analyses the symbolic grid for the 3-line white space border rule.
        If >= 3 consecutive outer columns/rows are 100% EMPTY, flags border_detected[direction] = True.
        """
        rows = len(grid)
        cols = len(grid[0]) if rows > 0 else 0

        if rows < 3 or cols < 3:
            return self.borders_detected

        # Check LEFT border: column 0 empty
        left_empty = all(
            grid[r][0].cell_type != CellType.OCCUPIED
            for r in range(rows)
        )
        if left_empty:
            self.borders_detected[Direction.LEFT] = True

        # Check RIGHT border: last column empty
        right_empty = all(
            grid[r][cols - 1].cell_type != CellType.OCCUPIED
            for r in range(rows)
        )
        if right_empty:
            self.borders_detected[Direction.RIGHT] = True

        # Check TOP border: row 0 empty
        top_empty = all(
            grid[0][c].cell_type != CellType.OCCUPIED
            for c in range(cols)
        )
        if top_empty:
            self.borders_detected[Direction.UP] = True

        # Check BOTTOM border: last row empty
        bottom_empty = all(
            grid[rows - 1][c].cell_type != CellType.OCCUPIED
            for c in range(cols)
        )
        if bottom_empty:
            self.borders_detected[Direction.DOWN] = True

        return self.borders_detected

    def is_all_borders_found(self) -> bool:
        """Returns True if all 4 level borders (UP, DOWN, LEFT, RIGHT) have been reached."""
        return all(self.borders_detected.values())

    def reset_borders(self):
        """Resets border detection and spiral sequence state for a new level."""
        for d in self.borders_detected:
            self.borders_detected[d] = False
        self._step_idx = 0

    def pan(self, direction: Direction, duration_ms: int = 120, pan_cells: int = 8, pitch: int = 44) -> bool:
        """
        Executes a camera drag/swipe gesture in the given direction.
        Duration default is 120ms (fast swipe).
        Followed by settle_delay to ensure image stabilization without motion blur.
        """
        if self.borders_detected.get(direction, False):
            # Prune pan if border already reached in this direction
            return False

        center_x = self.width // 2
        center_y = self.height // 2
        shift_px = pan_cells * pitch

        margin_x = 50
        margin_y = 150

        if direction == Direction.RIGHT:
            x1, y1 = self.width - margin_x, center_y
            x2, y2 = margin_x, center_y
        elif direction == Direction.LEFT:
            x1, y1 = margin_x, center_y
            x2, y2 = self.width - margin_x, center_y
        elif direction == Direction.DOWN:
            x1, y1 = center_x, self.height - margin_y
            x2, y2 = center_x, margin_y
        elif direction == Direction.UP:
            x1, y1 = center_x, margin_y
            x2, y2 = center_x, self.height - margin_y
        else:
            return False

        success = self.actuator.swipe(x1, y1, x2, y2, duration_ms=duration_ms)
        if success and self.settle_delay > 0:
            time.sleep(self.settle_delay)

        return success

    def step(self, duration_ms: int = 120, pitch: int = 44) -> Optional[Direction]:
        """
        Executes the next adaptive pan step in the spiral sequence.
        Skips any directions whose borders have already been detected.
        Returns the Direction swiped, or None if all borders are reached or sequence completed.
        """
        if self.is_all_borders_found():
            return None

        while self._step_idx < len(self._spiral_sequence):
            target_dir = self._spiral_sequence[self._step_idx]
            self._step_idx += 1

            if not self.borders_detected[target_dir]:
                swiped = self.pan(target_dir, duration_ms=duration_ms, pitch=pitch)
                if swiped:
                    return target_dir

        return None
