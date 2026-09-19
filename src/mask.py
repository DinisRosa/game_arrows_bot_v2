import cv2
import numpy as np
import os
from typing import Optional, Tuple

class BoardMask:
    """
    Manages the UI exclusion mask.
    Red pixels in mask.png indicate forbidden UI regions (hearts, hint, grid button).
    Blue pixels indicate the allowed playable board area.
    """
    def __init__(self, mask_path: str = "mask/mask.png"):
        self.mask_path = mask_path
        self.mask_img: Optional[np.ndarray] = None
        self.allowed_mask: Optional[np.ndarray] = None  # Boolean mask: True where playable
        self.forbidden_mask: Optional[np.ndarray] = None # Boolean mask: True where forbidden UI
        self._load_mask()

    def _load_mask(self):
        if not os.path.exists(self.mask_path):
            raise FileNotFoundError(f"Mask image not found at {self.mask_path}")
        
        self.mask_img = cv2.imread(self.mask_path)
        if self.mask_img is None:
            raise ValueError(f"Failed to load mask image from {self.mask_path}")

        # In BGR: Red has high R (> 200) and low B (< 50)
        # Blue has high B (> 200) and low R (< 50)
        b = self.mask_img[:, :, 0]
        r = self.mask_img[:, :, 2]
        
        self.forbidden_mask = (r > 200) & (b < 50)
        self.allowed_mask = ~self.forbidden_mask

    def is_allowed_tap(self, x: int, y: int) -> bool:
        """
        Check if pixel coordinate (x, y) is safe/allowed to tap.
        x is horizontal (col), y is vertical (row).
        """
        if self.allowed_mask is None:
            return True
        
        h, w = self.allowed_mask.shape
        if 0 <= x < w and 0 <= y < h:
            return bool(self.allowed_mask[y, x])
        return False

    def apply_mask(self, frame: np.ndarray, fill_color: Tuple[int, int, int] = (255, 255, 255)) -> np.ndarray:
        """
        Applies mask to frame, replacing forbidden UI regions with fill_color (default white).
        """
        masked_frame = frame.copy()
        if self.forbidden_mask is not None:
            h, w = frame.shape[:2]
            # Resize mask if frame resolution differs
            if (h, w) != self.forbidden_mask.shape:
                resized_forbidden = cv2.resize(
                    self.forbidden_mask.astype(np.uint8), 
                    (w, h), 
                    interpolation=cv2.INTER_NEAREST
                ).astype(bool)
                masked_frame[resized_forbidden] = fill_color
            else:
                masked_frame[self.forbidden_mask] = fill_color
        return masked_frame
