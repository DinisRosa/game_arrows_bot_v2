from typing import List
from src.game_types import Direction, CellType, Cell, ArrowHead, Move


class Solver:
    """
    Pure deterministic solver for the Arrows game.
    Determines which arrowheads have a clear line of sight to the edge of the grid.
    """
    @staticmethod
    def is_pixel_ray_clear(frame: np.ndarray, head: ArrowHead, pitch: int = 28, mask=None) -> bool:
        """
        Performs continuous pixel-level ray tracing from the tip of the arrowhead along its forward direction.
        Returns True if and only if NO dark obstacle pixels exist in image space along the line of sight.
        """
        import cv2
        import numpy as np
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, dark = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
        if mask and hasattr(mask, 'get_forbidden_mask'):
            dark[mask.get_forbidden_mask(h, w)] = 0

        dx, dy = head.direction.pixel_delta
        px_dir, py_dir = -dy, dx

        start_dist = int(pitch * 0.60)
        px = head.x_px + dx * start_dist
        py = head.y_px + dy * start_dist

        while 0 <= px < w and 0 <= py < h:
            if mask and hasattr(mask, 'is_allowed_tap') and not mask.is_allowed_tap(int(px), int(py)):
                break

            for k in range(-3, 4):
                nx = int(px + k * px_dir)
                ny = int(py + k * py_dir)
                if 0 <= nx < w and 0 <= ny < h:
                    if dark[ny, nx] > 0:
                        return False
            px += dx * 3
            py += dy * 3

        return True

    @staticmethod
    def playable_moves(
        grid: List[List[Cell]],
        heads: List[ArrowHead],
        frame: Optional[np.ndarray] = None,
        pitch: int = 28,
        mask=None,
        borders: Optional[dict[Direction, bool]] = None
    ) -> List[Move]:
        """
        Returns a list of playable moves.
        An arrowhead is playable if tracing forward along its pointing direction to the grid boundary
        encounters NO occupied cells of OTHER arrows, NO unknown cells, and NO pixel-level dark line obstacles.
        """
        rows = len(grid)
        if rows == 0:
            return []
        cols = len(grid[0])
        if cols == 0:
            return []

        moves: List[Move] = []

        for head in heads:
            dr, dc = head.direction.grid_delta
            r = head.row + dr
            c = head.col + dc

            is_clear = True
            while 0 <= r < rows and 0 <= c < cols:
                cell = grid[r][c]
                if cell.cell_type == CellType.UNKNOWN:
                    is_clear = False
                    break
                if cell.cell_type == CellType.OCCUPIED and cell.arrow_id != head.arrow_id:
                    is_clear = False
                    break
                r += dr
                c += dc

            if is_clear and borders is not None:
                if not borders.get(head.direction, True):
                    is_clear = False

            if is_clear:
                if frame is not None and not Solver.is_pixel_ray_clear(frame, head, pitch, mask):
                    continue

                moves.append(
                    Move(
                        arrow_id=head.arrow_id,
                        head=head,
                        tap_x_px=head.x_px,
                        tap_y_px=head.y_px,
                    )
                )

        return moves

    @staticmethod
    def solve_cascade(grid: List[List[Cell]], heads: List[ArrowHead]) -> List[Move]:
        """
        Simulates a multi-step cascade solution, returning the complete ordered sequence of moves.
        Prioritizes spatial locality (nearest-neighbor taps) when multiple moves are playable,
        minimizing finger/tap travel distance and unnecessary board panning.
        """
        rows = len(grid)
        if rows == 0:
            return []
        cols = len(grid[0])
        if cols == 0:
            return []

        # Create deep copy of cell grid so we don't mutate original
        grid_copy = [[Cell(cell_type=cell.cell_type, arrow_id=cell.arrow_id) for cell in row] for row in grid]
        remaining_heads = list(heads)
        cascade_sequence: List[Move] = []
        last_pos = None

        while True:
            moves = Solver.playable_moves(grid_copy, remaining_heads)
            if not moves:
                break

            # Pick move with minimum Euclidean distance to last_pos (or top-leftmost if first)
            if last_pos is None:
                next_move = min(moves, key=lambda m: (m.head.row, m.head.col))
            else:
                next_move = min(
                    moves,
                    key=lambda m: (m.tap_x_px - last_pos[0]) ** 2 + (m.tap_y_px - last_pos[1]) ** 2,
                )

            last_pos = (next_move.tap_x_px, next_move.tap_y_px)
            cascade_sequence.append(next_move)

            # Clear all cells belonging to this arrow from grid_copy
            for r in range(rows):
                for c in range(cols):
                    if grid_copy[r][c].arrow_id == next_move.arrow_id:
                        grid_copy[r][c].cell_type = CellType.EMPTY
                        grid_copy[r][c].arrow_id = None

            # Remove from remaining heads
            remaining_heads = [h for h in remaining_heads if h.arrow_id != next_move.arrow_id]

        return cascade_sequence

