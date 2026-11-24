# GRIN Reels — © 2026 Ernest Grin (GRIN studio). All rights reserved.
# Licensed, not sold: see LICENSE.md. Redistribution or resale is prohibited.
from autocut.silence import keep_ranges_from_silences, merge, subtract
from autocut.timeline import Timeline, VideoClip


def test_keep_ranges_pad_and_drop():
    keeps = keep_ranges_from_silences([(2.0, 3.0), (5.0, 5.1)], duration=8.0, pad=0.1)
    assert keeps == [(0.0, 2.1), (2.9, 8.0)]  # 5.0-5.1 pause swallowed by padding


def test_subtract_filler():
    assert subtract([(0, 4)], [(1.0, 1.4)]) == [(0, 1.0), (1.4, 4)]


def test_merge_gap():
    assert merge([(0, 1), (1.5, 2)], gap=0.6) == [(0, 2)]


def test_map_time():
    tl = Timeline(1080, 1920, 30, "x", main=[VideoClip("x", 0, 2, 0), VideoClip("x", 3, 5, 2)])
    assert tl.map_time(3.5) == 2.5 and tl.map_time(2.5) is None
