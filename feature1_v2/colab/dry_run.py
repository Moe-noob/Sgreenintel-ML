"""
Developer self-check: execute the whole Colab notebook on CPU with tiny fake
data (DRY_RUN). Also simulates a Colab disconnect in the middle of training.

    python -m feature1_v2.colab.dry_run          (F1V2_DRY_LOG=file.txt keeps the full output)
"""

import os
import shutil
import tempfile
from pathlib import Path

import nbformat
from nbclient import NotebookClient

from feature1_v2.colab import make_fake_drive

NB = Path(__file__).resolve().parent / "train_feature1_v2.ipynb"


def run(nb_cells, env_dir):
    nb = nbformat.v4.new_notebook()
    nb["cells"] = nb_cells
    nb["metadata"] = {"kernelspec": {"name": "python3", "display_name": "Python 3"}}
    NotebookClient(nb, timeout=1800, kernel_name="python3", resources={"metadata": {"path": env_dir}}).execute()
    return "".join(o.get("text", "") for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", []))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="f1v2_dry_"))
    drive, local = tmp / "drive" / "sgreen", tmp / "local"
    print("fake drive:", make_fake_drive.build(drive))
    os.environ.update(F1V2_DRY_RUN="1", F1V2_DRY_DRIVE=str(drive), F1V2_DRY_LOCAL=str(local))
    cells = nbformat.read(NB, as_version=4).cells
    codes = [c for c in cells if c.cell_type == "code"]
    try:
        # session 1: setup (boxes 0-4, skip the self-test to save time) + data prep + baseline + first model,
        # then "disconnect" in the middle of the second model's training (2 of 3 epochs done)
        setup = codes[:5]
        text = run(setup + codes[6:10], str(tmp))
        assert "Final exam locked" in text and "Baseline measured" in text, text[-3000:]
        partial = nbformat.v4.new_code_cell(
            'RUNS["dinov2_s_ft"] = ("dinov2_s", "finetune", 2)\n'
            'import json\n'
            'sh([PY, "-m", "feature1_v2.train", "--backbone", "test", "--mode", "finetune", "--epochs", "2",'
            ' "--out", WORK / "runs" / "dinov2_s_ft", "--resume", "--img-size", "64", "--no-pretrained",'
            ' "--workers", "0", "--ema", "0", "--batch", "16", "--lr", "3e-3"])')
        text = run(setup + [codes[8], partial], str(tmp))
        shutil.rmtree(local)                                   # Colab wipes its disk on disconnect
        # session 2: everything from the top, including the self-test and the final exam
        text = run(codes, str(tmp))
        assert "resuming from epoch 2 of 3" in text, "training did not resume after the disconnect"
        for must in ("All checks passed", "Already prepared in an earlier session", "Winner", "Calibrated",
                     "Final exam done", "Packed"):
            assert must in text, f"missing: {must}\n" + text[-3000:]
        assert (drive / "results_to_send.zip").exists()
        if os.environ.get("F1V2_DRY_LOG"):
            Path(os.environ["F1V2_DRY_LOG"]).write_text(text)
        print(text[-2500:])
        print("\nDRY RUN OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
