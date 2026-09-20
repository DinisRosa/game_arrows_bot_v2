import unittest
from src.game_types import Direction, CellType, Cell, ArrowHead
from src.vision import GridGeometry
from src.actuator import Actuator
from src.pan import PanController


class TestPanController(unittest.TestCase):

    def setUp(self):
        self.actuator = Actuator(dry_run=True)
        self.pan_controller = PanController(actuator=self.actuator)
        self.geom = GridGeometry(
            pitch=44, x0=10, y0=10, cols=10, rows=10,
            min_x=10, max_x=450, min_y=10, max_y=450
        )

    def test_check_borders_rule(self):
        # Construct 10x10 grid with 3 left empty columns (col 0, 1, 2)
        grid = [[Cell(CellType.EMPTY) for _ in range(10)] for _ in range(10)]
        for r in range(10):
            for c in range(3, 10):
                grid[r][c] = Cell(CellType.OCCUPIED)

        borders = self.pan_controller.check_borders(grid, self.geom)
        self.assertTrue(borders[Direction.LEFT])
        self.assertFalse(borders[Direction.RIGHT])

    def test_border_pruning(self):
        # Flag LEFT border as detected
        self.pan_controller.borders_detected[Direction.LEFT] = True

        # Pan LEFT should be pruned immediately
        success = self.pan_controller.pan(Direction.LEFT)
        self.assertFalse(success)

        # Pan RIGHT should succeed
        success = self.pan_controller.pan(Direction.RIGHT)
        self.assertTrue(success)

    def test_spiral_step_skips_pruned_borders(self):
        # Flag RIGHT border as detected
        self.pan_controller.borders_detected[Direction.RIGHT] = True

        # First step in spiral sequence is RIGHT; should skip RIGHT and swipe DOWN
        swiped_dir = self.pan_controller.step()
        self.assertEqual(swiped_dir, Direction.DOWN)


if __name__ == "__main__":
    unittest.main()
