"""logits_for_paths must hold at most one batch of decoded photos at a time (it ran out of memory on the validation split)."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


@unittest.skipUnless(importlib.util.find_spec("torch") is not None, "needs torch")
class TestStreaming(unittest.TestCase):
    def test_one_batch_at_a_time_and_unreadable_photos_are_counted(self):
        from feature1_eval import inference
        tmp = Path(tempfile.mkdtemp())
        paths = []
        for i in range(101):
            p = tmp / f"{i}.jpg"
            Image.new("RGB", (16, 16), (i, 0, 0)).save(p)
            paths.append(str(p))
        bad = tmp / "corrupt.jpg"
        bad.write_bytes(b"not an image")
        paths[50] = str(bad)

        calls = []

        def fake_logits_for_images(model, images, meta, tta=False, batch_size=32):
            calls.append(len(images))
            return np.zeros((len(images), 3), np.float32)

        real = inference.logits_for_images
        inference.logits_for_images = fake_logits_for_images
        try:
            out = inference.logits_for_paths(None, paths, {}, batch_size=16)
        finally:
            inference.logits_for_images = real
        self.assertEqual(out.shape, (101, 3))
        self.assertLessEqual(max(calls), 16)                 # never more than one batch decoded at once
        self.assertEqual(len(calls), 7)                      # ceil(101 / 16)
        self.assertEqual(sum(calls), 101)


if __name__ == "__main__":
    unittest.main()
