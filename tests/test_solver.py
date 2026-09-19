import unittest
from src.game_types import Direction, CellType, Cell, ArrowHead, Move
from src.solver import Solver


class TestSolver(unittest.TestCase):

    def test_empty_grid(self):
        self.assertEqual(Solver.playable_moves([], []), [])

    def test_single_clear_arrow(self):
        grid = [[Cell(CellType.EMPTY) for _ in range(3)] for _ in range(3)]
        head = ArrowHead(arrow_id=1, row=1, col=1, direction=Direction.RIGHT, x_px=100, y_px=100)
        grid[1][1] = Cell(CellType.OCCUPIED, arrow_id=1)

        moves = Solver.playable_moves(grid, [head])
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0].arrow_id, 1)

    def test_arrow_blocked_by_other_arrow(self):
        grid = [[Cell(CellType.EMPTY) for _ in range(3)] for _ in range(3)]
        head1 = ArrowHead(arrow_id=1, row=1, col=0, direction=Direction.RIGHT, x_px=50, y_px=100)
        grid[1][0] = Cell(CellType.OCCUPIED, arrow_id=1)
        grid[1][1] = Cell(CellType.OCCUPIED, arrow_id=2)

        moves = Solver.playable_moves(grid, [head1])
        self.assertEqual(len(moves), 0)

    def test_arrow_blocked_by_unknown_cell(self):
        grid = [[Cell(CellType.EMPTY) for _ in range(3)] for _ in range(3)]
        head1 = ArrowHead(arrow_id=1, row=0, col=1, direction=Direction.DOWN, x_px=100, y_px=50)
        grid[0][1] = Cell(CellType.OCCUPIED, arrow_id=1)
        grid[1][1] = Cell(CellType.UNKNOWN)

        moves = Solver.playable_moves(grid, [head1])
        self.assertEqual(len(moves), 0)

    def test_arrow_ignoring_own_body(self):
        grid = [[Cell(CellType.EMPTY) for _ in range(3)] for _ in range(3)]
        head1 = ArrowHead(arrow_id=1, row=2, col=1, direction=Direction.UP, x_px=100, y_px=200)
        grid[2][1] = Cell(CellType.OCCUPIED, arrow_id=1)
        grid[1][1] = Cell(CellType.OCCUPIED, arrow_id=1)

        moves = Solver.playable_moves(grid, [head1])
    def test_solve_cascade(self):
        # 1x3 grid: Arrow 1 at (0, 0) pointing RIGHT, blocked by Arrow 2 at (0, 1) pointing RIGHT (clear).
        grid = [[Cell(CellType.EMPTY) for _ in range(3)]]
        head1 = ArrowHead(arrow_id=1, row=0, col=0, direction=Direction.RIGHT, x_px=10, y_px=10)
        head2 = ArrowHead(arrow_id=2, row=0, col=1, direction=Direction.RIGHT, x_px=20, y_px=10)
        grid[0][0] = Cell(CellType.OCCUPIED, arrow_id=1)
        grid[0][1] = Cell(CellType.OCCUPIED, arrow_id=2)

        # Initially, only Arrow 2 is clear. Removing Arrow 2 unlocks Arrow 1.
        cascade = Solver.solve_cascade(grid, [head1, head2])
        self.assertEqual(len(cascade), 2)
        self.assertEqual(cascade[0].arrow_id, 2)
        self.assertEqual(cascade[1].arrow_id, 1)


if __name__ == "__main__":
    unittest.main()
