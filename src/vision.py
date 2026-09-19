import cv2
import numpy as np
from dataclasses import dataclass
from typing import Tuple, List, Optional
from src.types import Direction, CellType, Cell, ArrowHead
from src.mask import BoardMask


@dataclass
class GridGeometry:
    pitch: int       # Size of each cell in pixels (e.g., 45px or 73px)
    x0: int          # X phase origin (pixel offset modulo pitch)
    y0: int          # Y phase origin (pixel offset modulo pitch)
    cols: int        # Total visible columns
    rows: int        # Total visible rows
    min_x: int       # Leftmost grid line pixel coordinate
    max_x: int       # Rightmost grid line pixel coordinate
    min_y: int       # Topmost grid line pixel coordinate
    max_y: int       # Bottommost grid line pixel coordinate


class VisionDetector:
    """
    Computer vision pipeline for Auto-ARROWS.
    Processes frame images into symbolic grid structures.
    """
    def __init__(self, mask: Optional[BoardMask] = None):
        self.mask = mask or BoardMask()

    def detect_grid_geometry(self, frame: np.ndarray) -> GridGeometry:
        """
        Detects cell size (pitch) and grid origin phase (x0, y0) using projection autocorrelation.
        Works across all zoom levels and pan positions.
        """
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Apply UI mask - replace forbidden areas with white (255)
        masked_gray = self.mask.apply_mask(frame, fill_color=(255, 255, 255))
        masked_gray = cv2.cvtColor(masked_gray, cv2.COLOR_BGR2GRAY)

        # Binarize dark arrow lines
        _, dark_mask = cv2.threshold(masked_gray, 100, 255, cv2.THRESH_BINARY_INV)

        # Calculate horizontal and vertical projections
        proj_x = np.sum(dark_mask, axis=0).astype(float)
        proj_y = np.sum(dark_mask, axis=1).astype(float)

        # Autocorrelation along X to find pitch S
        ac_x = np.correlate(proj_x, proj_x, mode='full')
        ac_x = ac_x[len(proj_x) - 1:]

        # Search pitch S in range [25, 120]
        pitch_search_range = ac_x[25:120]
        pitch = int(np.argmax(pitch_search_range) + 25)

        # Find best phase offset (x0, y0) modulo pitch
        x_scores = [np.sum(proj_x[offset::pitch]) for offset in range(pitch)]
        y_scores = [np.sum(proj_y[offset::pitch]) for offset in range(pitch)]

        x0 = int(np.argmax(x_scores))
        y0 = int(np.argmax(y_scores))

        # Determine active grid bounds (where lines/dots exist)
        x_coords = np.arange(x0, w, pitch)
        y_coords = np.arange(y0, h, pitch)

        # Filter out grid lines outside playable area
        valid_x = [x for x in x_coords if any(self.mask.is_allowed_tap(x, y) for y in range(0, h, 100))]
        valid_y = [y for y in y_coords if any(self.mask.is_allowed_tap(x, y) for x in range(0, w, 100))]

        min_x = valid_x[0] if valid_x else x0
        max_x = valid_x[-1] if valid_x else x_coords[-1]
        min_y = valid_y[0] if valid_y else y0
        max_y = valid_y[-1] if valid_y else y_coords[-1]

        cols = len(valid_x)
        rows = len(valid_y)

        return GridGeometry(
            pitch=pitch,
            x0=x0,
            y0=y0,
            cols=cols,
            rows=rows,
            min_x=min_x,
            max_x=max_x,
            min_y=min_y,
            max_y=max_y
        )

    def draw_grid_debug(self, frame: np.ndarray, geom: GridGeometry) -> np.ndarray:
        """
        Draws grid lines and cell intersections over the frame for visual verification.
        """
        debug_img = frame.copy()
        h, w = frame.shape[:2]

        # Draw vertical grid lines
        for x in range(geom.x0, w, geom.pitch):
            cv2.line(debug_img, (x, 0), (x, h), (0, 255, 0), 1)

        # Draw horizontal grid lines
        for y in range(geom.y0, h, geom.pitch):
            cv2.line(debug_img, (0, y), (w, y), (0, 255, 0), 1)

        # Draw cell intersection centers in red
        for x in range(geom.x0, w, geom.pitch):
            for y in range(geom.y0, h, geom.pitch):
                if self.mask.is_allowed_tap(x, y):
                    cv2.circle(debug_img, (x, y), 3, (0, 0, 255), -1)

        return debug_img
