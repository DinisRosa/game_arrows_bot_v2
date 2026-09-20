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
    
    # Test cluster discovery
    clusters = stitcher.stitch_clusters(frames, min_confidence=0.70)
    assert len(clusters) == 4

    # Cluster 1 (Frame 1 + Frame 6)
    c1 = next(c for c in clusters if 0 in c.frame_indices)
    assert 5 in c1.frame_indices
    assert c1.global_rows == 31
    assert c1.global_cols == 14

    # Cluster 3 (Frame 3 + Frame 4)
    c3 = next(c for c in clusters if 2 in c.frame_indices)
    assert 3 in c3.frame_indices
    assert c3.global_rows == 27
    assert c3.global_cols == 14

    # Test primary cluster result
    primary = stitcher.stitch_frames(frames, min_confidence=0.70)
    assert isinstance(primary, StitchedResult)
    assert primary.global_rows >= 27
    assert primary.global_cols == 14

    # Verify debug image rendering works
    debug_img = stitcher.draw_stitched_debug(primary)
    assert debug_img is not None
    assert debug_img.ndim == 3
    assert debug_img.shape[0] == primary.global_rows * 30
    assert debug_img.shape[1] == primary.global_cols * 30
