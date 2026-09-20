import subprocess
import time
from typing import Optional
from src.game_types import Move


class Actuator:
    """
    Sends touch inputs to the Android device via ADB.
    Automatically scales frame coordinates (e.g. 600x1332) to physical device touch resolution (e.g. 1220x2712).
    Supports dry-run mode for safe testing.
    """
    def __init__(
        self,
        device_id: Optional[str] = None,
        dry_run: bool = True,
        frame_width: int = 600,
        frame_height: int = 1332
    ):
        self.device_id = device_id
        self.dry_run = dry_run
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.scale_x, self.scale_y = self._detect_scale_factors()

    def _detect_scale_factors(self) -> Tuple[float, float]:
        """
        Detects physical Android screen size via ADB 'shell wm size'
        and calculates scale factors from frame coordinates to physical touch coordinates.
        """
        phys_w, phys_h = self.frame_width, self.frame_height
        try:
            cmd = ["adb"]
            if self.device_id:
                cmd.extend(["-s", self.device_id])
            cmd.extend(["shell", "wm", "size"])
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if "Physical size:" in line:
                        parts = line.split("Physical size:")[1].strip().split("x")
                        phys_w, phys_h = int(parts[0]), int(parts[1])
        except Exception as e:
            print(f"[Actuator Warning] Could not detect physical display resolution: {e}")

        scale_x = phys_w / float(self.frame_width)
        scale_y = phys_h / float(self.frame_height)
        print(f"[Actuator] Scale initialized: physical ({phys_w}x{phys_h}) / frame ({self.frame_width}x{self.frame_height}) -> scale_x={scale_x:.4f}, scale_y={scale_y:.4f}")
        return scale_x, scale_y

    def tap(self, x: int, y: int) -> bool:
        """
        Sends a single tap to the screen at frame coordinate (x, y).
        Scales (x, y) to physical touch screen coordinates.
        """
        phys_x = int(round(x * self.scale_x))
        phys_y = int(round(y * self.scale_y))

        if self.dry_run:
            print(f"[DRY-RUN] Tap at frame ({x}, {y}) -> physical ({phys_x}, {phys_y})")
            return True

        print(f"[Actuator] Tap at frame ({x}, {y}) -> physical ({phys_x}, {phys_y})")
        cmd = ["adb"]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(["shell", "input", "tap", str(phys_x), str(phys_y)])

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
        phys_x1 = int(round(x1 * self.scale_x))
        phys_y1 = int(round(y1 * self.scale_y))
        phys_x2 = int(round(x2 * self.scale_x))
        phys_y2 = int(round(y2 * self.scale_y))

        if self.dry_run:
            print(f"[DRY-RUN] Fast swipe frame ({x1}, {y1})->({x2}, {y2}) -> physical ({phys_x1}, {phys_y1})->({phys_x2}, {phys_y2}) in {duration_ms}ms")
            return True

        cmd = ["adb"]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(["shell", "input", "swipe", str(phys_x1), str(phys_y1), str(phys_x2), str(phys_y2), str(int(duration_ms))])

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
