"""
Grad-CAM (Gradient-weighted Class Activation Mapping) for the SGreen Intel
35-class plant disease CNN.

Grad-CAM highlights which regions of a leaf image the model focused on when
making its prediction. If the highlighted region corresponds to the actual
disease lesion/spot, this is evidence the model learned meaningful visual
features rather than background artifacts.

Method: Selvaraju et al. (2017), "Grad-CAM: Visual Explanations from Deep
Networks via Gradient-based Localization."
https://arxiv.org/abs/1610.02391

For MobileNetV2, the target layer is model.features[-1] -- the last
convolutional block before global average pooling. This is the standard,
correct choice for this architecture: it's the deepest layer that still
retains spatial information before the classifier collapses it to a vector.

Usage:
    python training\gradcam.py path\to\leaf_image.jpg
    python training\gradcam.py path\to\leaf_image.jpg --save output_dir\
    python training\gradcam.py path\to\leaf_image.jpg --no-show
"""

import sys
import argparse
from pathlib import Path

import torch
import torch.nn as nn
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from torchvision import models, transforms

try:
    from . import config
except ImportError:
    import config

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

predict_transform = transforms.Compose([
    transforms.Resize((config.IMAGE_SIZE, config.IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])


# ---------------------------------------------------------------------------
# Model loading (same as predict.py)
# ---------------------------------------------------------------------------

def build_and_load_model():
    model = models.mobilenet_v2(weights=None)
    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, config.NUM_CLASSES)
    model = model.to(config.DEVICE)

    checkpoint = torch.load(config.BEST_MODEL_PATH, map_location=config.DEVICE)
    model.load_state_dict(checkpoint["model_state_dict"])
    class_names = checkpoint["class_names"]

    # Keep in eval mode for batchnorm/dropout, but do NOT use torch.no_grad()
    # during the forward pass -- Grad-CAM requires gradients to flow back
    # through the network to the target layer.
    model.eval()
    return model, class_names


# ---------------------------------------------------------------------------
# Grad-CAM core
# ---------------------------------------------------------------------------

class GradCAM:
    """
    Hooks into a target layer to capture:
      - the forward activations (feature maps) at that layer
      - the gradients of the predicted class score w.r.t. those activations

    The CAM is computed as: ReLU(sum_k(alpha_k * A_k))
    where alpha_k = global average of gradients for channel k,
    and A_k is the activation map for channel k.
    (Selvaraju et al. 2017, Eq. 1-2)
    """

    def __init__(self, model, target_layer):
        self.model = model
        self.target_layer = target_layer
        self.activations = None
        self.gradients = None

        # Register hooks -- these fire automatically during forward/backward
        self._fwd_hook = target_layer.register_forward_hook(self._save_activations)
        self._bwd_hook = target_layer.register_full_backward_hook(self._save_gradients)

    def _save_activations(self, module, input, output):
        self.activations = output.detach()

    def _save_gradients(self, module, grad_input, grad_output):
        self.gradients = grad_output[0].detach()

    def __call__(self, input_tensor, class_idx=None):
        """
        Runs a forward + backward pass and returns the Grad-CAM heatmap.

        input_tensor: [1, 3, H, W] preprocessed image tensor
        class_idx: which class to explain (None = top predicted class)

        Returns: numpy array of shape [H, W], values in [0, 1]
        """
        self.model.zero_grad()

        # Forward pass -- gradients ARE computed (no torch.no_grad())
        output = self.model(input_tensor)
        probs = torch.softmax(output, dim=1)[0]

        if class_idx is None:
            class_idx = output.argmax(dim=1).item()

        # Backward pass for the target class only
        score = output[0, class_idx]
        score.backward()

        # alpha_k = global average pooling of gradients for channel k
        # shape: [C] where C = number of channels in the target layer
        alphas = self.gradients.mean(dim=(2, 3))[0]  # [C]

        # Weighted sum of activation maps
        activations = self.activations[0]  # [C, h, w]
        cam = torch.zeros(activations.shape[1:], device=activations.device)
        for k, alpha in enumerate(alphas):
            cam += alpha * activations[k]

        # ReLU: only keep regions that positively influenced the score
        cam = torch.relu(cam)

        # Normalise to [0, 1] for visualisation
        if cam.max() > 0:
            cam = cam / cam.max()

        return cam.cpu().numpy(), class_idx, probs.detach().cpu()

    def remove_hooks(self):
        self._fwd_hook.remove()
        self._bwd_hook.remove()


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------

def overlay_cam_on_image(original_image, cam, alpha=0.45):
    """
    Resizes the CAM to the original image size and overlays it as a
    semi-transparent heatmap (jet colormap -- blue=low attention,
    red=high attention, the standard Grad-CAM convention).

    alpha: blend weight for the heatmap (0=invisible, 1=heatmap only).
    """
    # Resize CAM to original image dimensions
    cam_img = Image.fromarray(np.uint8(255 * cam))
    cam_img = cam_img.resize(original_image.size, Image.BILINEAR)
    cam_array = np.array(cam_img) / 255.0

    # Apply jet colormap
    heatmap = cm.jet(cam_array)[:, :, :3]  # RGB only, drop alpha channel
    heatmap = np.uint8(255 * heatmap)

    # Blend with original
    original_array = np.array(original_image)
    blended = np.uint8(alpha * heatmap + (1 - alpha) * original_array)
    return Image.fromarray(blended), Image.fromarray(heatmap)


def run_gradcam(image_path, save_dir=None, show=True, top_k=3):
    """
    Full pipeline: load image -> run Grad-CAM -> display and/or save.

    Produces a 3-panel figure:
      Left: original image
      Middle: Grad-CAM heatmap only
      Right: heatmap overlaid on original

    Also prints the top-k predictions with confidence scores.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        print(f"Error: image not found at '{image_path}'")
        sys.exit(1)

    # Load model
    model, class_names = build_and_load_model()

    # Target layer: last convolutional block of MobileNetV2
    # model.features[-1] is a ConvBNActivation module wrapping the final
    # depthwise-separable conv block. This is the correct layer for
    # MobileNetV2 -- deepest spatial features before global avg pooling.
    target_layer = model.features[-2]
    gradcam = GradCAM(model, target_layer)

    # Load and preprocess image
    original_image = Image.open(image_path).convert("RGB")
    input_tensor = predict_transform(original_image).unsqueeze(0).to(config.DEVICE)

    # Run Grad-CAM
    cam, predicted_idx, probs = gradcam(input_tensor)
    gradcam.remove_hooks()

    predicted_class = class_names[predicted_idx]
    confidence = probs[predicted_idx].item()

    # Print predictions
    print(f"\nImage: {image_path.name}")
    print(f"Top prediction: {predicted_class}  ({confidence*100:.1f}%)\n")
    top_probs, top_indices = torch.topk(probs, min(top_k, len(class_names)))
    print("Top predictions:")
    for prob, idx in zip(top_probs, top_indices):
        marker = " <-- Grad-CAM target" if idx.item() == predicted_idx else ""
        print(f"  {class_names[idx.item()]:55s}  {prob.item()*100:.2f}%{marker}")

    # Create overlay
    overlaid, heatmap_only = overlay_cam_on_image(original_image, cam)

    # Build figure
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(
        f"Grad-CAM: {predicted_class.replace('___', ' / ').replace('_', ' ')}  "
        f"({confidence*100:.1f}% confidence)\n"
        f"Image: {image_path.name}",
        fontsize=12, fontweight="bold"
    )

    axes[0].imshow(original_image)
    axes[0].set_title("Original image", fontsize=10)
    axes[0].axis("off")

    axes[1].imshow(heatmap_only)
    axes[1].set_title("Grad-CAM heatmap\n(red = high attention)", fontsize=10)
    axes[1].axis("off")

    axes[2].imshow(overlaid)
    axes[2].set_title("Overlay (heatmap + original)", fontsize=10)
    axes[2].axis("off")

    plt.tight_layout()

    # Save if requested
    if save_dir is not None:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        stem = image_path.stem
        out_path = save_dir / f"{stem}_gradcam.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        print(f"\nSaved: {out_path}")

    if show:
        plt.show()

    plt.close()
    return predicted_class, confidence, cam


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Grad-CAM on a single leaf image using the SGreen Intel 35-class model."
    )
    parser.add_argument("image", help="Path to the leaf image file")
    parser.add_argument(
        "--save", metavar="DIR",
        help="Directory to save the output PNG (optional)",
        default=None
    )
    parser.add_argument(
        "--no-show", action="store_true",
        help="Don't display the plot interactively (useful when saving only)"
    )
    parser.add_argument(
        "--top-k", type=int, default=3,
        help="Number of top predictions to print (default: 3)"
    )
    args = parser.parse_args()

    run_gradcam(
        image_path=args.image,
        save_dir=args.save,
        show=not args.no_show,
        top_k=args.top_k,
    )
