"""The PilotNet convolutional network, and nothing else.

This module is deliberately the least interesting one in the feature. DESIGN 6.2 names the
NVIDIA end-to-end architecture, and it is reproduced here without modification, because the
purpose of M4 is to be a **baseline**: the standard answer that M5 measures the reinforcement
learning agent against. An architecture tuned to win would make it a worse baseline, since a
comparison against a tuned opponent no longer says what the standard approach achieves.

Every shape comes from `bc.config`. There is no data-dependent constant here, which is why this
module can be written and tested before the training data is loaded, and why T020 and T021 could
run in parallel with the dataset work.

This is the first module in the package that imports torch, so it runs under `.venv-bc` only.
"""

from __future__ import annotations

import torch
from torch import nn

from python.bc import config


class ModelError(Exception):
    """Raised when the network is asked for something it cannot honestly do."""


_ACTIVATIONS: dict[str, type[nn.Module]] = {
    "relu": nn.ReLU,
    "elu": nn.ELU,
}


def conv_output_size(length: int, kernel: int, stride: int) -> int:
    """One dimension through one convolution, no padding and no dilation.

    Written out rather than inferred from a dummy forward pass, so a shape mistake is a wrong
    number in a readable formula instead of a stack trace inside torch.
    """
    return (length - kernel) // stride + 1


def flattened_size() -> int:
    """How many features reach the first fully connected layer.

    DERIVED from `CONV_LAYERS` and the input size rather than written down as 1152. The literal
    is correct today, and it would stay in place, silently wrong, the first time someone changed
    a stride or the crop height.
    """
    height, width = config.INPUT_HEIGHT, config.INPUT_WIDTH
    channels = config.INPUT_CHANNELS

    for out_channels, kernel, stride in config.CONV_LAYERS:
        height = conv_output_size(height, kernel, stride)
        width = conv_output_size(width, kernel, stride)
        channels = out_channels

        if height <= 0 or width <= 0:
            raise ModelError(
                "the convolution stack collapses the input to nothing: check CONV_LAYERS "
                f"against an input of {config.INPUT_HEIGHT}x{config.INPUT_WIDTH}"
            )

    return channels * height * width


class PilotNet(nn.Module):
    """Five convolutions, four fully connected layers, one continuous steering output.

    The output is a single unbounded value rather than a class over the 41 human lattice
    levels. Both are defensible, and research R3 records why this one: the lattice is an
    artefact of how the human's input was sampled, not a property of steering, and M5 compares
    distributions on that lattice at comparison time. A model that could only emit lattice
    values would have that comparison built into it, and the comparison would then be partly
    measuring its own constraint.
    """

    def __init__(self) -> None:
        super().__init__()

        if config.ACTIVATION not in _ACTIVATIONS:
            raise ModelError(
                f"unknown activation {config.ACTIVATION!r}; "
                f"available: {sorted(_ACTIVATIONS)}"
            )
        activation = _ACTIVATIONS[config.ACTIVATION]

        conv_layers: list[nn.Module] = []
        in_channels = config.INPUT_CHANNELS
        for out_channels, kernel, stride in config.CONV_LAYERS:
            conv_layers.append(nn.Conv2d(in_channels, out_channels, kernel, stride))
            conv_layers.append(activation())
            in_channels = out_channels
        self.features = nn.Sequential(*conv_layers)

        fc_layers: list[nn.Module] = []
        in_features = flattened_size()
        for index, width in enumerate(config.FC_WIDTHS):
            fc_layers.append(nn.Linear(in_features, width))
            # No activation after the last layer. A steering command is signed, so a
            # rectifier there would make every left turn impossible to express.
            if index < len(config.FC_WIDTHS) - 1:
                fc_layers.append(activation())
            in_features = width
        self.regressor = nn.Sequential(*fc_layers)

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        """Takes (N, C, H, W) and returns (N,), one steering value per sample.

        The shape is checked here rather than left to the first convolution. Torch's own error
        names a channel count mismatch clearly enough, but says nothing about height and width,
        and a batch that is merely the wrong size still runs and trains on the wrong thing.
        """
        expected = (config.INPUT_CHANNELS, config.INPUT_HEIGHT, config.INPUT_WIDTH)
        if batch.dim() != 4 or tuple(batch.shape[1:]) != expected:
            raise ModelError(
                f"expected a batch of shape (N, {expected[0]}, {expected[1]}, {expected[2]}), "
                f"got {tuple(batch.shape)}. Note the channel-first layout: `preprocess` returns "
                "height-first, so the batch needs a permute before it reaches the model."
            )

        out = self.features(batch)
        out = torch.flatten(out, start_dim=1)
        out = self.regressor(out)

        # (N, 1) to (N,). Returned flat so a loss against a flat target array cannot broadcast
        # into an (N, N) matrix, which is a silent bug that still produces a falling loss.
        return out.squeeze(-1)


def build_model() -> PilotNet:
    """The network, on the CPU and untrained. Device placement belongs to `bc.train`."""
    return PilotNet()


def parameter_count(model: nn.Module) -> int:
    """Total trainable parameters.

    Recorded in the `RunRecord` so an accidental architecture change shows up in a diff of the
    results rather than only in the code. Two runs that report different counts were not
    comparing what their run identifiers claim.
    """
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
