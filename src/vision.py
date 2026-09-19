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

    def detect_arrow_heads(self, frame: np.ndarray, geom: GridGeometry) -> List[ArrowHead]:
        """
        Step 3.2: Detects all true arrow heads and classifies their pointing directions.
        Distinguishes sharp triangular tips from flat line tail ends using width gradient analysis.
        """
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, dark_mask = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
        dark_mask[self.mask.forbidden_mask] = 0

        pitch = geom.pitch
        radius = pitch // 2

        candidates: List[ArrowHead] = []

        # 1. Candidate extraction: scan grid intersections with 1 edge connection
        for row_idx, y in enumerate(range(geom.y0, h - radius, pitch)):
            for col_idx, x in enumerate(range(geom.x0, w - radius, pitch)):
                if not self.mask.is_allowed_tap(x, y):
                    continue

                patch = dark_mask[y - radius : y + radius + 1, x - radius : x + radius + 1]
                if patch.shape != (2 * radius + 1, 2 * radius + 1):
                    continue

                c_y, c_x = radius, radius
                if patch[c_y, c_x] == 0:
                    continue

                t_edge = bool(np.sum(patch[0, :]) > 0)
                b_edge = bool(np.sum(patch[-1, :]) > 0)
                l_edge = bool(np.sum(patch[:, 0]) > 0)
                r_edge = bool(np.sum(patch[:, -1]) > 0)

                edges_count = int(t_edge) + int(b_edge) + int(l_edge) + int(r_edge)

                if edges_count == 1:
                    direction: Optional[Direction] = None
                    if b_edge and not (t_edge or l_edge or r_edge):
                        direction = Direction.UP
                    elif t_edge and not (b_edge or l_edge or r_edge):
                        direction = Direction.DOWN
                    elif r_edge and not (l_edge or t_edge or b_edge):
                        direction = Direction.LEFT
                    elif l_edge and not (r_edge or t_edge or b_edge):
                        direction = Direction.RIGHT

                    if direction:
                        candidates.append(
                            ArrowHead(
                                arrow_id=0,
                                row=row_idx,
                                col=col_idx,
                                direction=direction,
                                x_px=x,
                                y_px=y,
                            )
                        )

        # 2. Refinement: width gradient check to filter out flat tail ends
        refined_heads: List[ArrowHead] = []
        for cand in candidates:
            x, y = cand.x_px, cand.y_px
            patch = dark_mask[y - radius : y + radius + 1, x - radius : x + radius + 1]
            if patch.shape != (2 * radius + 1, 2 * radius + 1):
                continue

            dx, dy = cand.direction.pixel_delta
            tip_pt = (radius + dx * (radius // 2), radius + dy * (radius // 2))
            body_pt = (radius - dx * (radius // 2), radius - dy * (radius // 2))

            px_dir, py_dir = -dy, dx

            tip_w = sum(
                1 for k in range(-6, 7)
                if 0 <= int(tip_pt[0] + k * px_dir) < patch.shape[1]
                and 0 <= int(tip_pt[1] + k * py_dir) < patch.shape[0]
                and patch[int(tip_pt[1] + k * py_dir), int(tip_pt[0] + k * px_dir)] > 0
            )
            body_w = sum(
                1 for k in range(-6, 7)
                if 0 <= int(body_pt[0] + k * px_dir) < patch.shape[1]
                and 0 <= int(body_pt[1] + k * py_dir) < patch.shape[0]
                and patch[int(body_pt[1] + k * py_dir), int(body_pt[0] + k * px_dir)] > 0
            )

            if body_w > tip_w:
                refined_heads.append(cand)

        # 3. Assign unique sequential IDs to true arrowheads
        for idx, head in enumerate(refined_heads):
            head.arrow_id = idx + 1

        return refined_heads

    def build_grid(
        self, frame: np.ndarray, geom: GridGeometry, heads: List[ArrowHead]
    ) -> List[List[Cell]]:
        """
        Step 3.3: Constructs symbolic grid mapping cell occupancy and arrow ownership (arrow_id).
        Traces each snake arrow body from head to tail along connected grid segments.
        """
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, dark_mask = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
        dark_mask[self.mask.forbidden_mask] = 0

        pitch = geom.pitch

        def grid_to_px(r: int, c: int) -> Tuple[int, int]:
            return geom.x0 + c * pitch, geom.y0 + r * pitch

        grid = [[Cell(cell_type=CellType.EMPTY) for _ in range(geom.cols)] for _ in range(geom.rows)]

        for head in heads:
            r, c = head.row, head.col
            grid[r][c].cell_type = CellType.OCCUPIED
            grid[r][c].arrow_id = head.arrow_id

            curr_r, curr_c = r, c
            visited = set([(curr_r, curr_c)])

            while True:
                next_cell = None
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = curr_r + dr, curr_c + dc
                    if (nr, nc) in visited:
                        continue
                    if 0 <= nr < geom.rows and 0 <= nc < geom.cols:
                        x1, y1 = grid_to_px(curr_r, curr_c)
                        x2, y2 = grid_to_px(nr, nc)
                        mid_x, mid_y = (x1 + x2) // 2, (y1 + y2) // 2

                        if 0 <= mid_y < h and 0 <= mid_x < w:
                            if dark_mask[mid_y, mid_x] > 0:
                                next_cell = (nr, nc)
                                break

                if next_cell is None:
                    break

                curr_r, curr_c = next_cell
                visited.add((curr_r, curr_c))
                grid[curr_r][curr_c].cell_type = CellType.OCCUPIED
                grid[curr_r][curr_c].arrow_id = head.arrow_id

        return grid

    def draw_grid_debug(self, frame: np.ndarray, geom: GridGeometry) -> np.ndarray:
        """
        Draws grid lines and cell intersections over the frame for visual verification.
        """
        debug_img = frame.copy()
        h, w = frame.shape[:2]

        for x in range(geom.x0, w, geom.pitch):
            cv2.line(debug_img, (x, 0), (x, h), (0, 255, 0), 1)

        for y in range(geom.y0, h, geom.pitch):
            cv2.line(debug_img, (0, y), (w, y), (0, 255, 0), 1)

        for x in range(geom.x0, w, geom.pitch):
            for y in range(geom.y0, h, geom.pitch):
                if self.mask.is_allowed_tap(x, y):
                    cv2.circle(debug_img, (x, y), 3, (0, 0, 255), -1)

        return debug_img

    def draw_heads_debug(self, frame: np.ndarray, heads: List[ArrowHead]) -> np.ndarray:
        """
        Step 3.2 Debug: Color-codes detected arrow heads and draws directional indicators.
        Red=UP, Green=DOWN, Blue=LEFT, Yellow=RIGHT
        """
        debug_img = frame.copy()
        color_map = {
            Direction.UP: (0, 0, 255),      # Red
            Direction.DOWN: (0, 255, 0),    # Green
            Direction.LEFT: (255, 0, 0),    # Blue
            Direction.RIGHT: (0, 255, 255), # Yellow
        }

        for head in heads:
            color = color_map[head.direction]
            x, y = head.x_px, head.y_px
            cv2.circle(debug_img, (x, y), 8, color, -1)

            # Draw arrow line pointing in actual direction of head tip (pixel_delta dx, dy)
            dx, dy = head.direction.pixel_delta
            end_x = x + dx * 20
            end_y = y + dy * 20
            cv2.arrowedLine(debug_img, (x, y), (end_x, end_y), (255, 255, 255), 3, tipLength=0.4)

        return debug_img

    def draw_full_grid_debug(
        self, frame: np.ndarray, geom: GridGeometry, grid: List[List[Cell]], heads: List[ArrowHead]
    ) -> np.ndarray:
        """
        Step 3.3 Debug: Renders full symbolic grid with distinct colors assigned per arrow_id.
        """
        debug_img = frame.copy()
        pitch = geom.pitch

        np.random.seed(42)
        unique_ids = max((cell.arrow_id for row in grid for cell in row if cell.arrow_id), default=0)
        colors = {
            aid: tuple(map(int, np.random.randint(50, 245, size=3)))
            for aid in range(1, unique_ids + 1)
        }

        for r_idx, row in enumerate(grid):
            for c_idx, cell in enumerate(row):
                x = geom.x0 + c_idx * pitch
                y = geom.y0 + r_idx * pitch

                if cell.cell_type == CellType.OCCUPIED and cell.arrow_id:
                    color = colors[cell.arrow_id]
                    cv2.circle(debug_img, (x, y), 6, color, -1)

        for head in heads:
            x, y = head.x_px, head.y_px
            cv2.circle(debug_img, (x, y), 9, (255, 255, 255), 2)

        return debug_img
