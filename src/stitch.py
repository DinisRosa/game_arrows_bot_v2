import cv2
import numpy as np
from typing import List, Tuple, Dict, Optional, Set
from dataclasses import dataclass
from collections import deque
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
    frame_indices: List[int]              # Original indices of frames included in this cluster


class GlobalStitcher:
    """
    Offline and online multi-frame grid stitching engine.
    Uses confidence-thresholded graph alignment to fuse overlapping camera frames 
    into unified global game boards without forcing non-overlapping images together.
    """
    def __init__(self, detector: Optional[VisionDetector] = None):
        self.detector = detector or VisionDetector()

    def align_pair(self, frameA: np.ndarray, geomA: GridGeometry, frameB: np.ndarray, geomB: GridGeometry) -> Tuple[int, int, float]:
        """
        Calculates cell offset (dr, dc) and match confidence of frameB relative to frameA.
        Returns (dr, dc, confidence) such that:
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

        return dr, dc, float(max_val)

    def stitch_clusters(self, frames: List[np.ndarray], min_confidence: float = 0.65) -> List[StitchedResult]:
        """
        Discovers overlapping frame clusters using a pairwise alignment graph and 
        stitches each connected component independently.
        """
        if not frames:
            raise ValueError("No frames provided for stitching")

        if len(frames) == 1:
            frame = frames[0]
            geom = self.detector.detect_grid_geometry(frame)
            heads = self.detector.detect_arrow_heads(frame, geom)
            grid = self.detector.build_grid(frame, geom, heads)
            occ = np.array([[cell.cell_type == CellType.OCCUPIED for cell in row] for row in grid], dtype=bool)
            return [StitchedResult(
                global_rows=geom.rows,
                global_cols=geom.cols,
                grid=grid,
                heads=heads,
                frame_offsets=[(0, 0)],
                occupied_mask=occ,
                frame_indices=[0]
            )]

        # 1. Detect geometry, heads, and local grid for each frame
        geoms = [self.detector.detect_grid_geometry(f) for f in frames]
        heads_list = [self.detector.detect_arrow_heads(f, g) for f, g in zip(frames, geoms)]
        grids = [self.detector.build_grid(f, g, h) for f, g, h in zip(frames, geoms, heads_list)]

        # 2. Build pairwise alignment graph for edges >= min_confidence
        n = len(frames)
        adj: Dict[int, List[Tuple[int, int, int, float]]] = {i: [] for i in range(n)}
        
        for i in range(n):
            for j in range(i + 1, n):
                dr, dc, conf = self.align_pair(frames[i], geoms[i], frames[j], geoms[j])
                if conf >= min_confidence:
                    # Edge i -> j means cell in B (j) corresponds to cell in A (i) at (r + dr, c + dc)
                    # So offset of j relative to i is (-dr, -dc)
                    adj[i].append((j, -dr, -dc, conf))
                    adj[j].append((i, dr, dc, conf))

        # 3. Find connected components via BFS
        visited: Set[int] = set()
        results: List[StitchedResult] = []

        for start_node in range(n):
            if start_node in visited:
                continue

            # BFS traversal for this connected component
            component_nodes: List[int] = []
            node_offsets: Dict[int, Tuple[int, int]] = {start_node: (0, 0)}
            queue = deque([start_node])
            visited.add(start_node)

            while queue:
                curr = queue.popleft()
                component_nodes.append(curr)
                curr_r, curr_c = node_offsets[curr]

                for nxt, off_r, off_c, conf in adj[curr]:
                    if nxt not in visited:
                        visited.add(nxt)
                        node_offsets[nxt] = (curr_r + off_r, curr_c + off_c)
                        queue.append(nxt)

            # Sort component nodes by original index
            component_nodes.sort()

            # Calculate bounding box for this cluster
            raw_offsets = [node_offsets[idx] for idx in component_nodes]
            min_r = min(off[0] for off in raw_offsets)
            min_c = min(off[1] for off in raw_offsets)
            max_r = max(off[0] + geoms[idx].rows for idx, off in zip(component_nodes, raw_offsets))
            max_c = max(off[1] + geoms[idx].cols for idx, off in zip(component_nodes, raw_offsets))

            global_rows = max_r - min_r
            global_cols = max_c - min_c

            cluster_frame_offsets = [(off[0] - min_r, off[1] - min_c) for off in raw_offsets]

            # Fuse OCCUPIED cells into cluster boolean mask
            global_occupied = np.zeros((global_rows, global_cols), dtype=bool)
            for idx, (r_start, c_start) in zip(component_nodes, cluster_frame_offsets):
                g = grids[idx]
                for r in range(geoms[idx].rows):
                    for c in range(geoms[idx].cols):
                        if g[r][c].cell_type == CellType.OCCUPIED:
                            global_occupied[r_start + r, c_start + c] = True

            # Fuse and deduplicate arrow heads across cluster frames
            global_heads_dict: Dict[Tuple[int, int, Direction], ArrowHead] = {}
            for idx, (r_start, c_start) in zip(component_nodes, cluster_frame_offsets):
                for head in heads_list[idx]:
                    gr = r_start + head.row
                    gc = c_start + head.col
                    key = (gr, gc, head.direction)
                    if key not in global_heads_dict:
                        pitch = geoms[idx].pitch
                        global_heads_dict[key] = ArrowHead(
                            arrow_id=0,
                            row=gr,
                            col=gc,
                            direction=head.direction,
                            x_px=gc * pitch,
                            y_px=gr * pitch
                        )

            global_heads = list(global_heads_dict.values())
            for h_idx, head in enumerate(global_heads):
                head.arrow_id = h_idx + 1

            # Construct global symbolic grid & trace snake bodies from global heads
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
                head_visited = set([(curr_r, curr_c)])

                while True:
                    next_cell = None
                    for dr_step, dc_step in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = curr_r + dr_step, curr_c + dc_step
                        if (nr, nc) in head_visited:
                            continue
                        if 0 <= nr < global_rows and 0 <= nc < global_cols:
                            if global_occupied[nr, nc]:
                                next_cell = (nr, nc)
                                break
                    if next_cell is None:
                        break

                    curr_r, curr_c = next_cell
                    head_visited.add((curr_r, curr_c))
                    global_grid[curr_r][curr_c].cell_type = CellType.OCCUPIED
                    global_grid[curr_r][curr_c].arrow_id = head.arrow_id

            results.append(StitchedResult(
                global_rows=global_rows,
                global_cols=global_cols,
                grid=global_grid,
                heads=global_heads,
                frame_offsets=cluster_frame_offsets,
                occupied_mask=global_occupied,
                frame_indices=component_nodes
            ))

        return results

    def stitch_frames(self, frames: List[np.ndarray], min_confidence: float = 0.65) -> StitchedResult:
        """
        Stitches frames into the primary (largest) overlapping connected component.
        """
        clusters = self.stitch_clusters(frames, min_confidence=min_confidence)
        # Return cluster with maximum total global area or most frames
        primary = max(clusters, key=lambda res: len(res.frame_indices))
        return primary

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
