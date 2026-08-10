"""The CNN, plus the baselines it must beat to mean anything.

Sizing note. The usable dataset is roughly 2,200 daily samples, of which
a fold trains on ~1,000-1,800. A network with more parameters than it has
training rows will memorise, score ~100% in-sample, and produce noise out
of sample. So the default architecture is deliberately small (order 5k
parameters), heavily regularised, and stopped early on a time-separated
validation tail.

``padding="causal"`` matters: with "same" padding a filter centred on the
last position of the window would read padded future slots. Causal padding
guarantees position ``i`` of a feature map depends only on inputs at
positions ``<= i``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]


class Classifier(Protocol):
    """Minimal interface every arm of the study implements."""

    name: str

    def fit(
        self,
        x_fit: FloatArray,
        y_fit: IntArray,
        x_val: FloatArray | None = None,
        y_val: IntArray | None = None,
    ) -> None: ...

    def predict_proba_up(self, x: FloatArray) -> FloatArray:
        """P(UP) for each row, as a 1-D array."""
        ...


@dataclass
class CNNConfig:
    """Hyper-parameters. Every value here is a research choice that counts
    as a trial if it is varied — keep the grid small and pre-registered."""

    filters: tuple[int, ...] = (16, 16)
    kernel_size: int = 3
    dilations: tuple[int, ...] = (1, 2)
    dropout: float = 0.4
    l2: float = 1e-3
    learning_rate: float = 1e-3
    batch_size: int = 64
    max_epochs: int = 200
    patience: int = 20
    seed: int = 7


def build_cnn(window: int, n_channels: int, config: CNNConfig) -> Any:
    """Construct the compiled Keras model (imported lazily: TF is slow to load)."""
    import keras
    from keras import layers, regularizers

    if len(config.filters) != len(config.dilations):
        raise ValueError("filters and dilations must have the same length")

    keras.utils.set_random_seed(config.seed)

    inputs = keras.Input(shape=(window, n_channels), name="bar_window")
    x = inputs
    for n_filters, dilation in zip(config.filters, config.dilations, strict=True):
        x = layers.Conv1D(
            filters=n_filters,
            kernel_size=config.kernel_size,
            dilation_rate=dilation,
            padding="causal",  # never reads a future position
            activation="relu",
            kernel_regularizer=regularizers.l2(config.l2),
        )(x)
        x = layers.BatchNormalization()(x)
    x = layers.GlobalAveragePooling1D()(x)
    x = layers.Dropout(config.dropout)(x)
    outputs = layers.Dense(1, activation="sigmoid", name="p_up")(x)

    model = keras.Model(inputs=inputs, outputs=outputs, name="tsla_direction_cnn")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=config.learning_rate),
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )
    return model


class CNNClassifier:
    """Keras 1D CNN over the raw (window, channel) tensor."""

    def __init__(self, window: int, n_channels: int, config: CNNConfig | None = None) -> None:
        self.name = "cnn"
        self.window = window
        self.n_channels = n_channels
        self.config = config or CNNConfig()
        self.model: Any = None
        self.epochs_run: int = 0

    def fit(
        self,
        x_fit: FloatArray,
        y_fit: IntArray,
        x_val: FloatArray | None = None,
        y_val: IntArray | None = None,
    ) -> None:
        import keras

        self.model = build_cnn(self.window, self.n_channels, self.config)
        callbacks: list[Any] = []
        validation_data = None
        monitor = "loss"
        if x_val is not None and y_val is not None and x_val.shape[0] > 0:
            validation_data = (x_val, y_val.astype(np.float32))
            monitor = "val_loss"
        callbacks.append(
            keras.callbacks.EarlyStopping(
                monitor=monitor,
                patience=self.config.patience,
                restore_best_weights=True,
                mode="min",
            )
        )

        # Class weights stop the net from collapsing onto whichever barrier
        # happened to be touched more often in this particular fold.
        counts = np.bincount(y_fit.astype(np.int64), minlength=2).astype(np.float64)
        total = float(counts.sum())
        class_weight = {i: (total / (2.0 * counts[i])) if counts[i] > 0 else 1.0 for i in range(2)}

        history = self.model.fit(
            x_fit,
            y_fit.astype(np.float32),
            validation_data=validation_data,
            epochs=self.config.max_epochs,
            batch_size=self.config.batch_size,
            callbacks=callbacks,
            class_weight=class_weight,
            shuffle=True,  # safe: rows are already assigned to a fold
            verbose=0,
        )
        self.epochs_run = len(history.history["loss"])

    def predict_proba_up(self, x: FloatArray) -> FloatArray:
        if self.model is None:
            raise RuntimeError("fit() must be called before predict_proba_up()")
        preds = self.model.predict(x, verbose=0)
        return np.asarray(preds, dtype=np.float64).reshape(-1)

    def n_parameters(self) -> int:
        if self.model is None:
            return 0
        return int(self.model.count_params())


class MajorityClassifier:
    """Predicts the training set's base rate for every sample.

    The floor. Any model that cannot beat this has learned nothing, and
    on a stock with a strong upward drift this floor is well above 50%.
    """

    def __init__(self) -> None:
        self.name = "majority"
        self.rate = 0.5

    def fit(
        self,
        x_fit: FloatArray,
        y_fit: IntArray,
        x_val: FloatArray | None = None,
        y_val: IntArray | None = None,
    ) -> None:
        self.rate = float(np.mean(y_fit)) if y_fit.size else 0.5

    def predict_proba_up(self, x: FloatArray) -> FloatArray:
        return np.full(x.shape[0], self.rate, dtype=np.float64)


class LogisticClassifier:
    """L2 logistic regression on the flattened window.

    A linear control: if this matches the CNN, the convolutional structure
    is contributing nothing and the honest conclusion is that a linear
    model on the same features is the better answer.
    """

    def __init__(self, c: float = 0.1, seed: int = 7) -> None:
        self.name = "logistic"
        self.c = c
        self.seed = seed
        self.model: Any = None

    def fit(
        self,
        x_fit: FloatArray,
        y_fit: IntArray,
        x_val: FloatArray | None = None,
        y_val: IntArray | None = None,
    ) -> None:
        from sklearn.linear_model import LogisticRegression

        self.model = LogisticRegression(
            C=self.c, max_iter=2000, class_weight="balanced", random_state=self.seed
        )
        self.model.fit(_flatten(x_fit), y_fit)

    def predict_proba_up(self, x: FloatArray) -> FloatArray:
        if self.model is None:
            raise RuntimeError("fit() must be called before predict_proba_up()")
        proba = self.model.predict_proba(_flatten(x))
        return np.asarray(proba[:, 1], dtype=np.float64)


class GradientBoostingClassifier:
    """Histogram gradient boosting on the flattened window.

    The control arm that usually wins on tabular financial data. Included
    because "the CNN scored 0.52 AUC" is only interpretable next to what a
    strong non-deep model does with identical inputs and splits.
    """

    def __init__(self, seed: int = 7) -> None:
        self.name = "gbm"
        self.seed = seed
        self.model: Any = None

    def fit(
        self,
        x_fit: FloatArray,
        y_fit: IntArray,
        x_val: FloatArray | None = None,
        y_val: IntArray | None = None,
    ) -> None:
        from sklearn.ensemble import HistGradientBoostingClassifier as _HGB

        self.model = _HGB(
            max_iter=300,
            learning_rate=0.05,
            max_depth=3,
            l2_regularization=1.0,
            early_stopping=True,
            validation_fraction=0.2,
            random_state=self.seed,
        )
        self.model.fit(_flatten(x_fit), y_fit)

    def predict_proba_up(self, x: FloatArray) -> FloatArray:
        if self.model is None:
            raise RuntimeError("fit() must be called before predict_proba_up()")
        proba = self.model.predict_proba(_flatten(x))
        return np.asarray(proba[:, 1], dtype=np.float64)


def _flatten(x: FloatArray) -> FloatArray:
    return x.reshape(x.shape[0], -1)
