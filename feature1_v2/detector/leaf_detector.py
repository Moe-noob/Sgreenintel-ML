"""
Leaf detector wrapper (plan, Step 3.3). A small YOLO model (ultralytics)
trained on PlantDoc's bounding boxes, all classes merged into one class
"leaf" (see prepare_plantdoc.py and RUNBOOK.md). The classifier then
labels each detected leaf.

    det = LeafDetector("work/detector/runs/leaf/weights/best.pt")
    boxes = det.leaves(pil_image)          # [(x0, y0, x1, y1), ...], largest first
"""


class LeafDetector:
    def __init__(self, weights, conf=0.35, max_leaves=4, min_side=48, pad=0.08):
        from ultralytics import YOLO          # imported lazily: only needed when a detector is used
        self.model = YOLO(str(weights))
        self.conf, self.max_leaves, self.min_side, self.pad = conf, max_leaves, min_side, pad

    def leaves(self, img):
        res = self.model.predict(img, conf=self.conf, verbose=False)[0]
        boxes = res.boxes.xyxy.cpu().numpy().tolist() if res.boxes is not None else []
        return select_boxes(boxes, img.size, self.max_leaves, self.min_side, self.pad)


def select_boxes(boxes, size, max_leaves=4, min_side=48, pad=0.08):
    """Pad, clip, drop tiny boxes, keep the largest max_leaves."""
    w, h = size
    out = []
    for x0, y0, x1, y1 in boxes:
        bw, bh = x1 - x0, y1 - y0
        if min(bw, bh) < min_side:
            continue
        x0, y0 = max(0, x0 - pad * bw), max(0, y0 - pad * bh)
        x1, y1 = min(w, x1 + pad * bw), min(h, y1 + pad * bh)
        out.append((int(x0), int(y0), int(x1), int(y1)))
    out.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    return out[:max_leaves]
