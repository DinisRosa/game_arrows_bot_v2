import cv2
import numpy as np
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from src.game_types import CellType, Cell, ArrowHead, Direction
from src.vision import VisionDetector, GridGeometry


@dataclass
class StitchedResult:
    global_rows: int
    global_cols: int
    grid: List[List[Cell]]
    heads: List[ArrowHead]
    frame_offsets: List[Tuple[int, int]]  # (row_offset, col_offset) for each frame relative to global top-left (0, 0)
    occupied_mask: np.ndarray


class GlobalStitcher:
    """
    Offline and online multi-frame grid stitching engine.
    Fuses overlapping camera frames into a unified global game board.
    """
    def __init__(self, detector: Optional[VisionDetector] = None):
        self.detector = detector or VisionDetector()

    def align_pair(self, frameA: np.ndarray, geomA: GridGeometry, frameB: np.ndarray, geomB: GridGeometry) -> Tuple[int, int]:
        """
        Calculates cell offset (dr, dc) of frameB relative to frameA.
        Returns (dr, dc) such that:
            Frame B cell (r, c) corresponds to Frame A cell (r + dr, c + dc).
        """
        grayA = cv2.cvtColor(frameA, cv2.COLOR_BGR2GRAY)
        grayB = cv2.cvtColor(frameB, cv2.COLOR_BGR2GRAY)

        _, maskA = cv2.threshold(grayA, 100, 255, cv2.THRESH_BINARY_INV)
        _, maskB = cv2.threshold(grayB, 100, 255, cv2.THRESH_BINARY_INV)

        hA, wA = maskA.shape[:2]
        hB, wB = maskB.shape[:2]

        maskA[self.detector.mask.get_forbidden_mask(hA, wA)] = 0
        maskB[self.detector.mask.get_forbidden_mask(hB, wB)] = 0

        # Extract central template from maskA to avoid edge UI artifacts
        crop_x1 = geomA.min_x + geomA.pitch * 2
        crop_x2 = geomA.max_x - geomA.pitch * 2
        crop_y1 = geomA.min_y + geomA.pitch * 4
        crop_y2 = geomA.max_y - geomA.pitch * 4

        if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
            # Fallback if grid is small
            crop_x1, crop_x2 = geomA.min_x, geomA.max_x
            crop_y1, crop_y2 = geomA.min_y, geomA.max_y

        template = maskA[crop_y1:crop_y2, crop_x1:crop_x2]

        res = cv2.matchTemplate(maskB, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        match_x, match_y = max_loc[0], max_loc[1]
        raw_dx = match_x - crop_x1
        raw_dy = match_y - crop_y1

        pitch = geomA.pitch
        dc = round((raw_dx + geomA.min_x - geomB.min_x) / pitch)
        dr = round((raw_dy + geomA.min_y - geomB.min_y) / pitch)

        return dr, dc

    def stitch_frames(self, frames: List[np.ndarray]) -> StitchedResult:
        """
        Stitches a sequence of overlapping frames into a unified global symbolic grid.
        """
        if not frames:
            raise ValueError("No frames provided for stitching")

        if len(frames) == 1:
            frame = frames[0]
            geom = self.detector.detect_grid_geometry(frame)
            heads = self.detector.detect_arrow_heads(frame, geom)
            grid = self.detector.build_grid(frame, geom, heads)
            occ = np.array([[cell.cell_type == CellType.OCCUPIED for cell in row] for row in grid], dtype=bool)
            return StitchedResult(
                global_rows=geom.rows,
                global_cols=geom.cols,
                grid=grid,
                heads=heads,
                frame_offsets=[(0, 0)],
                occupied_mask=occ
            )

        # 1. Detect geometry, heads, and local grid for each frame
        geoms = [self.detector.detect_grid_geometry(f) for f in frames]
        heads_list = [self.detector.detect_arrow_heads(f, g) for f, g in zip(frames, geoms)]
        grids = [self.detector.build_grid(f, g, h) for f, g, h in zip(frames, geoms, heads_list)]

        # 2. Compute pairwise frame offsets relative to Frame 1
        raw_offsets: List[Tuple[int, int]] = [(0, 0)]  # (rel_r, rel_c) relative to Frame 1
        for i in range(len(frames) - 1):
            dr, dc = self.align_pair(frames[i], geoms[i], frames[i+1], geoms[i+1])
            prev_r, prev_c = raw_offsets[-1]
            raw_offsets.append((prev_r - dr, prev_c - dc))

        # 3. Calculate global bounding box
        min_r = min(off[0] for off in raw_offsets)
        min_c = min(off[1] for off in raw_offsets)
        max_r = max(off[0] + geoms[i].rows for i, off in enumerate(raw_offsets))
        max_c = max(off[1] + geoms[i].cols for i, off in enumerate(raw_offsets))

        global_rows = max_r - min_r
        global_cols = max_c - min_c

        # Shift all frame offsets relative to global top-left (0, 0)
        global_frame_offsets = [(off[0] - min_r, off[1] - min_c) for off in raw_offsets]

        # 4. Fuse OCCUPIED cells into global boolean mask
        global_occupied = np.zeros((global_rows, global_cols), dtype=bool)
        for i, (r_start, c_start) in enumerate(global_frame_offsets):
            g = grids[i]
            for r in range(geoms[i].rows):
                for c in range(geoms[i].cols):
                    if g[r][c].cell_type == CellType.OCCUPIED:
                        global_occupied[r_start + r, c_start + c] = True

        # 5. Fuse and deduplicate arrow heads across overlapping frames
        global_heads_dict: Dict[Tuple[int, int, Direction], ArrowHead] = {}
        for i, (r_start, c_start) in enumerate(global_frame_offsets):
            for head in heads_list[i]:
                gr = r_start + head.row
                gc = c_start + head.col
                key = (gr, gc, head.direction)
                if key not in global_heads_dict:
                    pitch = geoms[i].pitch
                    global_heads_dict[key] = ArrowHead(
                        arrow_id=0,
                        row=gr,
                        col=gc,
                        direction=head.direction,
                        x_px=gc * pitch,
                        y_px=gr * pitch
                    )

        global_heads = list(global_heads_dict.values())
        for idx, head in enumerate(global_heads):
            head.arrow_id = idx + 1

        # 6. Construct global symbolic grid & trace snake bodies from global heads
        global_grid = [[Cell(cell_type=CellType.EMPTY) for _ in range(global_cols)] for _ in range(global_rows)]
        for r in range(global_rows):
            for c in range(global_cols):
                if global_occupied[r, c]:
                    global_grid[r][c].cell_type = CellType.OCCUPIED

        for head in global_heads:
            r, c = head.row, head.col
            global_grid[r][c].cell_type = CellType.OCCUPIED
            global_grid[r][c].arrow_id = head.arrow_id

            curr_r, curr_c = r, c
            visited = set([(curr_r, curr_c)])

            while True:
                next_cell = None
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = curr_r + dr, curr_c + dc
                    if (nr, nc) in visited:
                        continue
                    if 0 <= nr < global_rows and 0 <= nc < global_cols:
                        if global_occupied[nr, nc]:
                            next_cell = (nr, nc)
                            break
                if next_cell is None:
                    break

                curr_r, curr_c = next_cell
                visited.add((curr_r, curr_c))
                global_grid[curr_r][curr_c].cell_type = CellType.OCCUPIED
                global_grid[curr_r][curr_c].arrow_id = head.arrow_id

        return StitchedResult(
            global_rows=global_rows,
            global_cols=global_cols,
            grid=global_grid,
            heads=global_heads,
            frame_offsets=global_frame_offsets,
            occupied_mask=global_occupied
        )

    def draw_stitched_debug(self, result: StitchedResult, cell_sz: int = 30) -> np.ndarray:
        """
        Renders visual debug image of the stitched global grid and all assigned arrow bodies.
        """
        vis_h = result.global_rows * cell_sz
        vis_w = result.global_cols * cell_sz
        canvas = np.ones((vis_h, vis_w, 3), dtype=np.uint8) * 245

        np.random.seed(42)
        unique_ids = len(result.heads)
        colors = {aid: tuple(map(int, np.random.randint(50, 245, size=3))) for aid in range(1, unique_ids + 1)}

        for r in range(result.global_rows):
            for c in range(result.global_cols):
                x1, y1 = c * cell_sz, r * cell_sz
                x2, y2 = x1 + cell_sz, y1 + cell_sz
                cv2.rectangle(canvas, (x1, y1), (x2, y2), (210, 210, 210), 1)

                cell = result.grid[r][c]
                if cell.cell_type == CellType.OCCUPIED:
                    if cell.arrow_id and cell.arrow_id in colors:
                        cv2.rectangle(canvas, (x1+2, y1+2), (x2-2, y2-2), colors[cell.arrow_id], -1)
                    else:
                        cv2.rectangle(canvas, (x1+4, y1+4), (x2-4, y2-4), (100, 100, 100), -1)

        for head in result.heads:
            cx = head.col * cell_sz + cell_sz // 2
            cy = head.row * cell_sz + cell_sz // 2
            color = colors.get(head.arrow_id, (0, 0, 0))
            cv2.circle(canvas, (cx, cy), cell_sz // 3, (255, 255, 255), -1)
            cv2.circle(canvas, (cx, cy), cell_sz // 3, color, 2)
            cv2.putText(canvas, str(head.arrow_id), (cx - 5, cy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)

        return canvas
