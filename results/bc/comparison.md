# Balanced against unbalanced behavioural cloning

Two runs differing in exactly one thing: whether the exact-zero steering spike was 
downsampled before training. Everything else, including the split, the seed, the 
architecture and every hyperparameter, is identical. That is what makes the 
difference below attributable to balancing.

Both are scored on the same unbalanced validation set (FR-022). Balancing is a 
property of what the model was shown, so applying it to validation would move the 
yardstick along with the model.

## The two runs

| | Unbalanced | Balanced |
|---|---|---|
| Run | `bc_unbalanced_v01` | `bc_balanced_v01` |
| Policy | none | downsample_zero |
| Training samples | 77,871 | 66,783 |
| Validation samples | 5,576 | 5,576 |
| Epochs | 13 | 13 |
| Validation error | 0.086670 | 0.090899 |
| Mean-predictor baseline | 0.153623 | 0.153992 |
| Beat baseline | True | True |
| KL from human, on the lattice | 1.143888 | 1.206980 |

## The two deltas, kept apart

| Axis | Delta (balanced minus unbalanced) | Reading |
|---|---|---|
| Accuracy | +0.004229 | unbalanced predicts the human targets more closely |
| Distribution | +0.063091 | unbalanced sits closer to the human distribution |

**These are not combined into a verdict.**

**Both axes point the same way: unbalanced wins accuracy and distributional closeness.** That is not what the design predicted. Balancing was expected to buy a closer distributional match at the cost of accuracy, and here it bought neither.

The reason is measurable rather than mysterious, and it is the more interesting finding. Neither model reproduces the human's zero spike at all: the human validation column is 57.2 percent exact zeros, and both models place under 5 percent there. The distance from the human distribution is dominated by that gap, and balancing moves the model further from zero, so it makes the gap slightly worse instead of better.

What actually moved the prediction distribution away from the human one is the three-camera augmentation, not the balancing policy. It cut the zero share of the training targets from 57 percent of rows to 20 percent of samples before balancing was applied to anything. Balancing is a second-order effect on top of a first-order one that was never framed as a distributional choice.

## Notes on the figures

- The KL divergence is computed on the 41-level human lattice, with the model's 
  continuous output quantised onto it first and the human record left untouched 
  (DESIGN section 7). It is smoothed by 1e-09 per level, without 
  which a single prediction on an unused level would make it infinite.
- The validation error is the mean squared error of the raw continuous predictions, 
  not the quantised ones. Quantising before scoring would penalise the model for a 
  resolution the human recording happens to have.
- Both runs carry split digest `f9151b481e7fcd51`.

