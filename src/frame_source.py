import subprocess
import threading
import time
import cv2
import numpy as np
import os
from typing import Protocol, Optional

try:
    import av
    AV_AVAILABLE = True
except ImportError:
    AV_AVAILABLE = False


class FrameSource(Protocol):
    def get_frame(self) -> np.ndarray:
        """Returns the latest captured frame as a BGR numpy array."""
        ...

    def is_fresh(self, max_age: float = 0.5) -> bool:
        """Returns True if the frame is fresh and reliable."""
        ...


class ScrcpyFrameSource:
    """
    High-speed real-time frame streaming engine powered by hardware H.264 video stream + PyAV.
    Streams video frames at up to 60+ FPS directly into shared memory.
    """
    def __init__(self, device_id: Optional[str] = None, width: int = 600, height: int = 1332):
        if not AV_AVAILABLE:
            raise ImportError("PyAV ('av') is not installed in the environment.")
        self.device_id = device_id
        self.width = width
        self.height = height
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_ts: float = 0.0
        self._is_running = False
        self._stop_event = threading.Event()

    def _build_stream_cmd(self) -> list[str]:
        cmd = ["adb"]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend([
            "exec-out", "screenrecord",
            "--output-format=h264",
            "--size", f"{self.width}x{self.height}",
            "--time-limit", "180",
            "-"
        ])
        return cmd

    def start(self):
        if self._is_running:
            return
        
        cmd = self._build_stream_cmd()
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        self._is_running = True

    def _stream_loop(self):
        try:
            container = av.open(self._proc.stdout, format="h264")
            for frame in container.decode(video=0):
                if self._stop_event.is_set():
                    break
                img = frame.to_ndarray(format="bgr24")
                self._latest_frame = img
                self._latest_ts = time.monotonic()
        except Exception as e:
            pass
        finally:
            self._is_running = False

    def get_frame(self) -> np.ndarray:
        if not self._is_running or self._proc is None:
            self.start()
            start_wait = time.time()
            while self._latest_frame is None and (time.time() - start_wait) < 3.0:
                time.sleep(0.05)

        if self._latest_frame is None:
            # Fallback to screencap if stream isn't ready
            fb = ADBFrameSource(device_id=self.device_id)
            return fb.get_frame()
            
        return self._latest_frame.copy()

    def is_fresh(self, max_age: float = 0.5) -> bool:
        return self._latest_frame is not None and (time.monotonic() - self._latest_ts) <= max_age

    def stop(self):
        self._stop_event.set()
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.kill()
            except Exception:
                pass
            self._proc = None
        self._is_running = False


class ADBFrameSource:
    """
    Captures frames from Android device using 'adb exec-out screencap -p'.
    Fallback frame source when stream is initializing or resetting.
    """
    def __init__(self, device_id: Optional[str] = None):
        self.device_id = device_id
        self._last_ts: float = 0.0

    def _build_adb_cmd(self) -> list[str]:
        cmd = ["adb"]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(["exec-out", "screencap", "-p"])
        return cmd

    def get_frame(self) -> np.ndarray:
        cmd = self._build_adb_cmd()
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise RuntimeError(f"ADB screencap failed: {proc.stderr.decode('utf-8', errors='ignore')}")
        
        image_bytes = proc.stdout
        frame = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Failed to decode screencap image buffer")
        
        self._last_ts = time.monotonic()
        return frame

    def is_fresh(self, max_age: float = 0.5) -> bool:
        return (time.monotonic() - self._last_ts) <= max_age


class FileFrameSource:
    """
    Loads frames from disk for testing vision and solver offline without device.
    """
    def __init__(self, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Fixture file not found: {file_path}")
        self.frame = cv2.imread(file_path)
        if self.frame is None:
            raise ValueError(f"Failed to read image fixture: {file_path}")

    def get_frame(self) -> np.ndarray:
        return self.frame.copy()

    def is_fresh(self, max_age: float = 0.5) -> bool:
        return True
