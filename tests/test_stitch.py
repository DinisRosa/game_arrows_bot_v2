import os
import glob
import cv2
import numpy as np
from src.stitch import GlobalStitcher, StitchedResult
from src.game_types import CellType, Direction


def test_single_frame_stitching():
    fpath = 'fixtures/frames/screenshots/multi_frame/frame_1.png'
    if not os.path.exists(fpath):
        print('Skipping test_single_frame_stitching: fixture frame_1.png not found')
        return

    frame = cv2.imread(fpath)
    stitcher = GlobalStitcher()
    result = stitcher.stitch_frames([frame])

    assert isinstance(result, StitchedResult)
    assert result.global_rows > 0
    assert result.global_cols > 0
    assert len(result.frame_offsets) == 1
    assert result.frame_offsets[0] == (0, 0)
    assert result.occupied_mask.shape == (result.global_rows, result.global_cols)


def test_multi_frame_stitching_dataset():
    frame_paths = sorted(glob.glob('fixtures/frames/screenshots/multi_frame/frame_*.png'))
    if len(frame_paths) < 2:
        print('Skipping test_multi_frame_stitching_dataset: Multi-frame dataset fixtures not found')
        return

    frames = [cv2.imread(p) for p in frame_paths]
    stitcher = GlobalStitcher()
    result = stitcher.stitch_frames(frames)

    assert isinstance(result, StitchedResult)
    assert result.global_rows >= 23
    assert result.global_cols >= 14
    assert len(result.frame_offsets) == len(frames)
    assert result.frame_offsets[0] != result.frame_offsets[1]

    # Verify debug image rendering works
    debug_img = stitcher.draw_stitched_debug(result)
    assert debug_img is not None
    assert debug_img.ndim == 3
    assert debug_img.shape[0] == result.global_rows * 30
    assert debug_img.shape[1] == result.global_cols * 30
