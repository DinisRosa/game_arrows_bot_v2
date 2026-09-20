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
    Performs perception-decision-action cycle with mandatory mask validation and real-time frame re-capture.
    """
    def __init__(
        self,
        frame_source: FrameSource,
        vision: Optional[VisionDetector] = None,
        actuator: Optional[Actuator] = None,
        max_iterations: int = 200,
        enable_pan: bool = False,
    ):
        self.frame_source = frame_source
        self.mask = BoardMask("mask/mask.png")
        self.vision = vision or VisionDetector(self.mask)
        self.actuator = actuator or Actuator(dry_run=True)
        self.stitcher = GlobalStitcher(self.vision)
        self.pan_controller = PanController(self.actuator, self.vision)
        self.max_iterations = max_iterations
        self.enable_pan = enable_pan
        self.captured_frames = []

    def run_step(self, single_move: bool = True) -> int:
        """
        Executes a single perception-decision-action cycle.
        If single_move=True, executes 1 move per cycle and re-captures the frame for maximum safety.
        Returns the number of playable moves executed in this cycle.
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

        # Step 3: Check white margin border rule
        borders = self.pan_controller.check_borders(grid, geom)
        detected_borders_str = ", ".join([d.value for d, found in borders.items() if found]) or "None"
        print(f"[Bot] Detected {len(heads)} arrowheads. Borders found: [{detected_borders_str}].")

        # Step 4: Calculate playable moves on current view with pixel-level ray tracing verification
        moves = Solver.playable_moves(grid, heads, frame=frame, pitch=geom.pitch, mask=self.mask)

        if len(moves) > 0:
            print(f"[Bot] Found {len(moves)} playable moves on current view.")
            
            # Filter moves by allowed mask and grid bounds
            valid_moves = [
                m for m in moves
                if self.mask.is_allowed_tap(m.tap_x_px, m.tap_y_px)
                and geom.min_y <= m.tap_y_px <= geom.max_y
            ]

            if not valid_moves:
                print("[Bot] No moves passed mask validation.")
                return 0

            if single_move:
                # Execute ONLY 1 move per cycle to allow screen re-capture & animation stability
                target_move = valid_moves[0]
                print(f"[Bot] Executing 1 move: Arrow #{target_move.arrow_id} at ({target_move.tap_x_px}, {target_move.tap_y_px})")
                self.actuator.execute_move(target_move, delay_after=0.35)
                return 1
            else:
                executed_count = 0
                for move in valid_moves:
                    self.actuator.execute_move(move, delay_after=0.35)
                    executed_count += 1
                return executed_count

        # Step 5: Panning/Stitching fallback only if explicitly enabled
        if self.enable_pan and not self.pan_controller.is_all_borders_found():
            print("[Bot] No local moves. Executing adaptive camera pan...")
            swiped_dir = self.pan_controller.step(duration_ms=120, pitch=geom.pitch)
            if swiped_dir:
                print(f"[Bot] Camera panned [{swiped_dir.value}]. Capturing updated frame...")
                new_frame = self.frame_source.get_frame()
                if new_frame is not None:
                    self.captured_frames.append(new_frame)
                    primary_cluster = self.stitcher.stitch_frames(self.captured_frames, min_confidence=0.65)
                    stitched_moves = Solver.playable_moves(primary_cluster.grid, primary_cluster.heads)
                    print(f"[Bot] Stitched global grid ({primary_cluster.global_rows}x{primary_cluster.global_cols}). Found {len(stitched_moves)} playable moves.")
                    if len(stitched_moves) > 0:
                        r_off, c_off = primary_cluster.frame_offsets[-1]
                        for m in stitched_moves:
                            r_screen = m.head.row - r_off
                            c_screen = m.head.col - c_off
                            if 0 <= r_screen < geom.rows and 0 <= c_screen < geom.cols:
                                tap_x = geom.min_x + c_screen * geom.pitch
                                tap_y = geom.min_y + r_screen * geom.pitch
                                if self.mask.is_allowed_tap(tap_x, tap_y) and geom.min_y <= tap_y <= geom.max_y:
                                    self.actuator.tap(tap_x, tap_y)
                                    return 1
        else:
            print("[Bot] No more moves available on current view.")

        return 0

    def run_loop(self, delay_between_steps: float = 0.1):
        """
        Runs the game loop continuously until level complete or max iterations reached.
        """
        print("[Bot] Starting Auto-ARROWS-V2 Game Loop...")
        iteration = 0
        total_moves = 0
        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n--- Iteration {iteration}/{self.max_iterations} ---")
            moves_count = self.run_step(single_move=True)
            if moves_count == 0:
                print(f"[Bot] Stopping loop (no more moves). Executed {total_moves} total moves.")
                break
            total_moves += moves_count
            time.sleep(delay_between_steps)


def main():
    parser = argparse.ArgumentParser(description="Auto-ARROWS-V2 Bot")
    parser.add_argument("--fixture", type=str, help="Path to offline frame image fixture")
    parser.add_argument("--live", action="store_true", help="Run live via scrcpy-server H.264 stream")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run without tapping screen")
    parser.add_argument("--no-dry-run", action="store_false", dest="dry_run", help="Send actual ADB touches")
    parser.add_argument("--pan", action="store_true", help="Enable multi-frame camera panning and stitching")
    args = parser.parse_args()

    if args.fixture:
        frame_source = FileFrameSource(args.fixture)
    elif args.live:
        frame_source = ScrcpyFrameSource()
    else:
        frame_source = FileFrameSource("fixtures/frames/screenshots/screenshot_1.png")

    actuator = Actuator(dry_run=args.dry_run)
    bot = AutoArrowsBot(frame_source=frame_source, actuator=actuator, enable_pan=args.pan)
    
    if args.live:
        bot.run_loop(delay_between_steps=0.1)
    else:
        bot.run_step(single_move=True)


if __name__ == "__main__":
    main()
