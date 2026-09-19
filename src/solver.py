from typing import List
from src.types import Direction, CellType, Cell, ArrowHead, Move


class Solver:
    """
    Pure deterministic solver for the Arrows game.
    Determines which arrowheads have a clear line of sight to the edge of the grid.
    """
    @staticmethod
    def playable_moves(grid: List[List[Cell]], heads: List[ArrowHead]) -> List[Move]:
        """
        Returns a list of playable moves.
        An arrowhead is playable if tracing forward along its pointing direction to the grid boundary
        encounters NO occupied cells of OTHER arrows and NO unknown cells.
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

            if is_clear:
                moves.append(
                    Move(
                        arrow_id=head.arrow_id,
                        head=head,
                        tap_x_px=head.x_px,
                        tap_y_px=head.y_px,
                    )
                )

        return moves
