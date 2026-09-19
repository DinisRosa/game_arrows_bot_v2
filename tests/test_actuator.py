import unittest
from src.game_types import Direction, ArrowHead, Move
from src.actuator import Actuator


class TestActuator(unittest.TestCase):

    def test_dry_run_tap(self):
        actuator = Actuator(dry_run=True)
        head = ArrowHead(arrow_id=1, row=0, col=0, direction=Direction.UP, x_px=100, y_px=200)
        move = Move(arrow_id=1, head=head, tap_x_px=100, tap_y_px=200)

        result = actuator.execute_move(move, delay_after=0.0)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
