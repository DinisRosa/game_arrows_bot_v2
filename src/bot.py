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
from src.stitch import GlobalStitcher
from src.pan import PanController


class AutoArrowsBot:
    """
    Unified game bot loop for Auto-ARROWS-V2.
    Orchestrates FrameSource -> VisionDetector -> GlobalStitcher -> Solver -> PanController -> Actuator.
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
        self.stitcher = GlobalStitcher(self.vision)
        self.pan_controller = PanController(self.actuator, self.vision)
        self.max_iterations = max_iterations
        self.captured_frames = []

    def run_step(self) -> int:
        """
        Executes a single perception-decision-action cycle.
        Returns the number of playable moves executed.
        """
        frame = self.frame_source.get_frame()
        if frame is None:
            print("[Bot] No frame available.")
            return 0

        self.captured_frames.append(frame)

        # Step 1: Detect grid geometry
        geom = self.vision.detect_grid_geometry(frame)

        # Step 2: Detect arrowheads
        heads = self.vision.detect_arrow_heads(frame, geom)
        grid = self.vision.build_grid(frame, geom, heads)

        # Step 3: Check white margin border rule (3 consecutive empty lines)
        borders = self.pan_controller.check_borders(grid, geom)
        detected_borders_str = ", ".join([d.value for d, found in borders.items() if found]) or "None"
        print(f"[Bot] Detected {len(heads)} arrowheads. Borders found: [{detected_borders_str}].")

        # Step 4: Calculate playable moves on current view
        moves = Solver.playable_moves(grid, heads)

        if len(moves) > 0:
            print(f"[Bot] Found {len(moves)} playable moves on current view.")
            # Execute playable moves with spatial locality
            for move in moves:
                self.actuator.execute_move(move, delay_after=0.05)
            return len(moves)

        # Step 5: If no local moves exist, trigger adaptive smart pan sweep if borders remain
        if not self.pan_controller.is_all_borders_found():
            print("[Bot] No moves on local view. Executing adaptive fast camera pan...")
            swiped_dir = self.pan_controller.step(duration_ms=120, pitch=geom.pitch)
            if swiped_dir:
                print(f"[Bot] Camera panned [{swiped_dir.value}]. Capturing updated frame...")
                new_frame = self.frame_source.get_frame()
                if new_frame is not None:
                    self.captured_frames.append(new_frame)
                    # Stitch captured frames into global board
                    primary_cluster = self.stitcher.stitch_frames(self.captured_frames, min_confidence=0.65)
                    stitched_moves = Solver.playable_moves(primary_cluster.grid, primary_cluster.heads)
                    print(f"[Bot] Stitched global grid ({primary_cluster.global_rows}x{primary_cluster.global_cols}). Found {len(stitched_moves)} playable moves on stitched board.")
                    if len(stitched_moves) > 0:
                        for move in stitched_moves[:1]:
                            self.actuator.execute_move(move, delay_after=0.05)
                        return len(stitched_moves)
        else:
            print("[Bot] All 4 level borders reached and no more moves available.")

        return 0

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
