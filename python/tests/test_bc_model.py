"""The network's shape contract.

Small file, because the model is the least interesting part of this feature: it is the standard
architecture, reproduced rather than designed. What these tests protect is that it stays the
standard architecture, since a baseline that has quietly drifted is not measuring what its name
claims.

The forward-pass test is named by hand in Constitution Principle VIII.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip(
    "torch", reason="the model needs torch; run this under .venv-bc"
)

from python.bc import config, model  # noqa: E402  (after the torch guard, on purpose)


@pytest.fixture(scope="module")
def network():
    return model.build_model()


def a_batch(size: int = 4,
            channels: int = config.INPUT_CHANNELS,
            height: int = config.INPUT_HEIGHT,
            width: int = config.INPUT_WIDTH) -> torch.Tensor:
    return torch.zeros(size, channels, height, width)


# -----------------------------------------------------------------------------------------
# The forward pass. Named by Constitution Principle VIII.
# -----------------------------------------------------------------------------------------


def test_a_forward_pass_returns_one_value_per_sample(network):
    """One output per input, and flat.

    The flatness is not cosmetic. An (N, 1) output against an (N,) target broadcasts to an
    (N, N) matrix, and MSE over that is a real number that falls during training, so the run
    looks healthy while the loss means nothing.
    """
    for size in (1, 4, 32):
        out = network(a_batch(size))

        assert out.shape == (size,)
        assert out.dim() == 1


def test_the_model_accepts_exactly_what_preprocess_produces(network):
    """The two halves of the pipeline agree on a shape, checked rather than assumed.

    `preprocess` returns height-first and the model wants channel-first, so this also documents
    where the permute belongs.
    """
    import numpy as np

    from python.bc import dataset

    frame = np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 3), dtype=np.uint8)
    processed = dataset.preprocess(frame)

    batch = torch.from_numpy(processed).permute(2, 0, 1).unsqueeze(0)
    assert network(batch).shape == (1,)


def test_a_batch_with_the_wrong_channel_count_is_rejected(network):
    """Rather than silently broadcasting, which is the failure the contract names."""
    with pytest.raises(model.ModelError, match="expected a batch of shape"):
        network(a_batch(channels=1))


def test_a_batch_of_the_wrong_size_is_rejected(network):
    """Torch would accept a differently sized image and train on the wrong thing.

    The convolutions have no fixed input size; only the first linear layer does, and it fails
    with a matrix shape error that says nothing about the crop. This check names the problem.
    """
    with pytest.raises(model.ModelError, match="expected a batch of shape"):
        network(a_batch(height=config.INPUT_HEIGHT - 2))

    with pytest.raises(model.ModelError, match="expected a batch of shape"):
        network(a_batch(width=config.INPUT_WIDTH + 10))


def test_an_unbatched_sample_is_rejected(network):
    """A single frame missing its batch dimension is a mistake, not a batch of one."""
    with pytest.raises(model.ModelError, match="expected a batch of shape"):
        network(torch.zeros(config.INPUT_CHANNELS, config.INPUT_HEIGHT, config.INPUT_WIDTH))


# -----------------------------------------------------------------------------------------
# The architecture has not drifted
# -----------------------------------------------------------------------------------------


def test_the_parameter_count_matches_the_design(network):
    """DESIGN 6.2 says about 250k. Measured: 252,219.

    Asserted exactly rather than as a range, because the point is to catch an accidental
    change. A range wide enough to be safe is wide enough to miss a swapped layer width.
    """
    assert model.parameter_count(network) == 252_219


def test_the_flattened_size_is_derived_and_matches_pilotnet():
    """1152 is the figure in the NVIDIA paper, and it is computed here rather than typed."""
    assert model.flattened_size() == 1152


def test_the_stack_is_five_convolutions_and_four_linear_layers(network):
    """DESIGN 6.2 states the shape of the network in words. This is that sentence, asserted."""
    convolutions = [m for m in network.modules() if isinstance(m, torch.nn.Conv2d)]
    linears = [m for m in network.modules() if isinstance(m, torch.nn.Linear)]

    assert len(convolutions) == 5
    assert len(linears) == 4


def test_the_output_layer_has_no_activation(network):
    """A steering command is signed. A rectifier on the output makes left turns unreachable.

    This would not fail loudly: the model would train, converge, and predict only right turns
    and zero, which looks like a data problem rather than an architecture one.
    """
    last = network.regressor[-1]

    assert isinstance(last, torch.nn.Linear)
    assert last.out_features == 1


def test_the_output_is_unclamped_in_both_directions():
    """The same guarantee as the test above, measured on the output rather than the layer list.

    Driven through the final layer rather than read off an untrained forward pass. At
    initialisation this network's ReLU activations are all zero on random input, so the output
    is exactly the final bias and carries whatever sign that bias happens to have. A test
    reading the sign of an untrained prediction measures the initialisation, not the
    architecture.
    """
    torch.manual_seed(config.SEED)
    fresh = model.build_model()
    batch = torch.zeros(4, config.INPUT_CHANNELS, config.INPUT_HEIGHT, config.INPUT_WIDTH)
    last = fresh.regressor[-1]

    with torch.no_grad():
        last.bias.fill_(-0.75)
        assert (fresh(batch) < 0).all(), "the output cannot go negative; left turns are lost"

        last.bias.fill_(0.75)
        assert (fresh(batch) > 0).all(), "the output cannot go positive"

        # Past the steering limits too. The model is not asked to clamp; the lattice and the
        # limits are applied at comparison time, and a model that silently saturated would
        # hide a prediction the evaluation is meant to see and clip explicitly.
        last.bias.fill_(3.0)
        assert (fresh(batch) > 1.0).all()


def test_conv_output_size_matches_the_convolution_it_describes():
    """The formula is written out by hand, so it is checked against torch rather than trusted."""
    for kernel, stride in ((5, 2), (3, 1), (7, 3)):
        layer = torch.nn.Conv2d(1, 1, kernel, stride)
        actual = layer(torch.zeros(1, 1, 66, 200)).shape

        assert model.conv_output_size(66, kernel, stride) == actual[2]
        assert model.conv_output_size(200, kernel, stride) == actual[3]


def test_every_shape_comes_from_config(network):
    """The contract's "no data-dependent constant" rule, as far as a test can reach it.

    The first convolution's input channels and the last linear layer's input width are the two
    places a hardcoded number would show up, since both are derived from config rather than
    written.
    """
    first_conv = next(m for m in network.modules() if isinstance(m, torch.nn.Conv2d))
    linears = [m for m in network.modules() if isinstance(m, torch.nn.Linear)]

    assert first_conv.in_channels == config.INPUT_CHANNELS
    assert first_conv.out_channels == config.CONV_LAYERS[0][0]
    assert linears[0].in_features == model.flattened_size()
    assert [layer.out_features for layer in linears] == list(config.FC_WIDTHS)
