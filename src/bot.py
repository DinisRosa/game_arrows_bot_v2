import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
import argparse
import cv2
from typing import Optional
from src.frame_source import FrameSource, ScrcpyFrameSource, FileFrameSource
from src.mask import BoardMask
from src.vision import VisionDetector
from src.solver import Solver
from src.actuator import Actuator


class AutoArrowsBot:
    """
    Unified game bot loop for Auto-ARROWS-V2.
    Orchestrates FrameSource -> VisionDetector -> Solver -> Actuator.
    """
    def __init__(
        self,
        frame_source: FrameSource,
        vision: Optional[VisionDetector] = None,
        actuator: Optional[Actuator] = None,
        max_iterations: int = 100,
    ):
        self.frame_source = frame_source
        self.mask = BoardMask("mask/mask.png")
        self.vision = vision or VisionDetector(self.mask)
        self.actuator = actuator or Actuator(dry_run=True)
        self.max_iterations = max_iterations

    def run_step(self) -> int:
        """
        Executes a single perception-decision-action cycle.
        Returns the number of playable moves executed.
        """
        frame = self.frame_source.get_frame()
        if frame is None:
            print("[Bot] No frame available.")
            return 0

        # Step 1: Detect grid geometry
        geom = self.vision.detect_grid_geometry(frame)

        # Step 2: Detect arrowheads
        heads = self.vision.detect_arrow_heads(frame, geom)
        if len(heads) == 0:
            print("[Bot] No arrowheads detected (level cleared or empty board).")
            return 0

        # Step 3: Build grid mapping
        grid = self.vision.build_grid(frame, geom, heads)

        # Step 4: Calculate playable moves
        moves = Solver.playable_moves(grid, heads)
        print(f"[Bot] Detected {len(heads)} arrowheads. Found {len(moves)} playable moves.")

        if len(moves) == 0:
            print("[Bot] Board active but no clear playable moves found.")
            return 0

        # Step 5: Execute playable moves
        for move in moves:
            self.actuator.execute_move(move, delay_after=0.05)

        return len(moves)

    def run_loop(self, delay_between_steps: float = 0.2):
        """
        Runs the game loop continuously until level complete or max iterations reached.
        """
        print("[Bot] Starting Auto-ARROWS-V2 Game Loop...")
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n--- Iteration {iteration}/{self.max_iterations} ---")
            moves_count = self.run_step()
            if moves_count == 0:
                print("[Bot] Stopping loop (no moves executed).")
                break
            time.sleep(delay_between_steps)


def main():
    parser = argparse.ArgumentParser(description="Auto-ARROWS-V2 Bot")
    parser.add_argument("--fixture", type=str, help="Path to offline frame image fixture")
    parser.add_argument("--live", action="store_true", help="Run live via scrcpy-server H.264 stream")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run without tapping screen")
    parser.add_argument("--no-dry-run", action="store_false", dest="dry_run", help="Send actual ADB touches")
    args = parser.parse_args()

    if args.fixture:
        frame_source = FileFrameSource(args.fixture)
    elif args.live:
        frame_source = ScrcpyFrameSource()
    else:
        frame_source = FileFrameSource("fixtures/frames/screenshots/screenshot_1.png")

    actuator = Actuator(dry_run=args.dry_run)
    bot = AutoArrowsBot(frame_source=frame_source, actuator=actuator)
    bot.run_step()


if __name__ == "__main__":
    main()
