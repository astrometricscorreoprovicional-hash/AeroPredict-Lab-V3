
import numpy as np
from src.model import train_logit, synth_dataset

def test_train_shapes():
    X,y = synth_dataset(n=500, seed=1)
    model, mu, sigma = train_logit(X, y, lr=0.05, epochs=10, l2=1e-3)
    assert model.w.shape[0] == X.shape[1]
    assert sigma.shape[0] == X.shape[1]
