import subprocess
import time
from typing import Optional
from src.game_types import Move


class Actuator:
    """
    Sends touch inputs to the Android device via ADB.
    Supports dry-run mode for safe testing.
    """
    def __init__(self, device_id: Optional[str] = None, dry_run: bool = True):
        self.device_id = device_id
        self.dry_run = dry_run

    def tap(self, x: int, y: int) -> bool:
        """
        Sends a single tap to the screen at (x, y).
        """
        if self.dry_run:
            print(f"[DRY-RUN] Tap at pixel ({x}, {y})")
            return True

        cmd = ["adb"]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(["shell", "input", "tap", str(int(x)), str(int(y))])

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            print(f"[Actuator Error] Failed to tap at ({x}, {y}): {e}")
            return False

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 120) -> bool:
        """
        Executes a fast camera drag/swipe gesture from (x1, y1) to (x2, y2).
        """
        if self.dry_run:
            print(f"[DRY-RUN] Fast swipe from ({x1}, {y1}) to ({x2}, {y2}) in {duration_ms}ms")
            return True

        cmd = ["adb"]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(["shell", "input", "swipe", str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration_ms))])

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            print(f"[Actuator Error] Failed to swipe from ({x1}, {y1}) to ({x2}, {y2}): {e}")
            return False

    def execute_move(self, move: Move, delay_after: float = 0.05) -> bool:
        """
        Executes a Move by tapping its arrowhead coordinates.
        """
        success = self.tap(move.tap_x_px, move.tap_y_px)
        if success and delay_after > 0:
            time.sleep(delay_after)
        return success
