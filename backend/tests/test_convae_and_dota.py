import json
from pathlib import Path
import pytest
import torch
from types import SimpleNamespace

from ConvAE import (
    ConvLSTM,
    ConvLSTMCell,
    ConvLSTMED,
    TemporalRegularityDetector,
    OrigConvAE,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_convae_module_imports_and_instantiation():
    """Verify ConvLSTM and AutoEncoder modules instantiate correctly."""
    cell = ConvLSTMCell(
        input_size=(28, 28),
        input_dim=16,
        hidden_dim=32,
        kernel_size=(3, 3),
        bias=True,
    )
    assert cell is not None

    lstm = ConvLSTM(
        input_size=(28, 28),
        input_dim=16,
        hidden_dim=[32, 64],
        kernel_size=(3, 3),
        num_layers=2,
        batch_first=True,
    )
    assert lstm.num_layers == 2


def test_convae_forward_pass():
    """Verify forward passes of ConvLSTMCell and multi-layer ConvLSTM."""
    cell = ConvLSTMCell(
        input_size=(16, 16),
        input_dim=8,
        hidden_dim=16,
        kernel_size=(3, 3),
        bias=True,
    )
    x = torch.randn(2, 8, 16, 16)
    init_h, init_c = cell.init_hidden(batch_size=2)
    h, c = cell(x, (init_h, init_c))
    assert h.shape == (2, 16, 16, 16)
    assert c.shape == (2, 16, 16, 16)

    # Multi-layer ConvLSTM sequence forward pass (Batch, Time, Channels, Height, Width)
    lstm = ConvLSTM(
        input_size=(16, 16),
        input_dim=8,
        hidden_dim=[16, 32],
        kernel_size=(3, 3),
        num_layers=2,
        batch_first=True,
    )
    seq_input = torch.randn(2, 4, 8, 16, 16)
    layer_output_list, last_state_list = lstm(seq_input)
    assert len(layer_output_list) == 1
    assert layer_output_list[0].shape == (2, 4, 32, 16, 16)


def test_convlstmed_autoencoder_forward_pass():
    """Verify ConvLSTMED Spatio-Temporal AutoEncoder forward pass."""
    args = SimpleNamespace(mode='gray')
    model = ConvLSTMED(args)
    # ConvEncoder maps 227x227 down to 26x26 for temporal ConvLSTM
    x = torch.randn(1, 4, 227, 227)
    out = model(x)
    assert out.shape == (1, 4, 227, 227)


def test_dota_dataset_metadata():
    """Verify DoTA dataset metadata files and train/val splits."""
    dota_dir = PROJECT_ROOT / "dataset" / "DoTA"
    train_meta_file = dota_dir / "metadata_train.json"
    val_meta_file = dota_dir / "metadata_val.json"

    assert train_meta_file.exists(), "metadata_train.json must exist"
    assert val_meta_file.exists(), "metadata_val.json must exist"

    with open(train_meta_file, "r") as f:
        meta_train = json.load(f)

    assert len(meta_train) > 3000, f"Expected >3000 training clips, found {len(meta_train)}"

    # Check key anomaly categories
    categories = set(v.get("anomaly_class") for v in meta_train.values())
    assert any("obstacle" in cat for cat in categories)
    assert any("lateral" in cat for cat in categories)
    assert any("oncoming" in cat for cat in categories)
