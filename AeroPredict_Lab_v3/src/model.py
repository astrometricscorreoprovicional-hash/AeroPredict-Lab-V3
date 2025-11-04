
import os, numpy as np, json, time
from dataclasses import dataclass
from typing import Tuple, List

FEAT_NAMES = ["airspeed","altitude","vspeed","pitch","roll","wind_x","wind_y"]

@dataclass
class LogitModel:
    w: np.ndarray
    b: float
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        z = X @ self.w + self.b
        return 1.0/(1.0 + np.exp(-z))
    def predict(self, X: np.ndarray, thr: float=0.5) -> np.ndarray:
        return (self.predict_proba(X) >= thr).astype(float)
    def save(self, path:str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        np.savez(path, w=self.w, b=self.b)
    @staticmethod
    def load(path:str) -> "LogitModel":
        data = np.load(path)
        return LogitModel(w=data["w"], b=float(data["b"]))

def standardize(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mu = X.mean(axis=0)
    sigma = X.std(axis=0) + 1e-8
    return (X-mu)/sigma, mu, sigma

def train_logit(X: np.ndarray, y: np.ndarray, lr=0.05, epochs=400, l2=1e-3):
    Xs, mu, sigma = standardize(X)
    n, d = Xs.shape; w = np.zeros(d); b = 0.0
    for _ in range(epochs):
        z = Xs @ w + b
        p = 1.0/(1.0+np.exp(-z))
        grad_w = (Xs.T @ (p - y))/n + l2*w
        grad_b = float(np.mean(p - y))
        w -= lr * grad_w; b -= lr * grad_b
    return LogitModel(w=w, b=b), mu, sigma

def synth_dataset(n=8000, seed=42):
    rng = np.random.default_rng(seed)
    airspeed = rng.normal(70, 15, n)
    altitude = rng.normal(300, 120, n)
    vspeed   = rng.normal(-1.5, 1.2, n)
    pitch    = rng.normal(0.03, 0.08, n)
    roll     = rng.normal(0.02, 0.05, n)
    wind_x   = rng.normal(0.0, 4.0, n)
    wind_y   = rng.normal(0.0, 4.0, n)
    X = np.vstack([airspeed, altitude, vspeed, pitch, roll, wind_x, wind_y]).T
    risk = (
        (airspeed<60).astype(float)*0.9 +
        (altitude<200).astype(float)*0.8 +
        (vspeed<-2.5).astype(float)*0.7 +
        (np.abs(pitch)>0.12).astype(float) +
        (np.abs(roll)>0.12).astype(float) +
        0.03*(np.abs(wind_x)+np.abs(wind_y))
    ).astype(float)
    prob = 1.0/(1.0+np.exp(-(risk-1.6)))
    y = (rng.random(n) < prob).astype(float)
    return X, y

def auc_xy(x, y):
    return float(np.trapz(y, x))

def roc_curve(y_true, p):
    t = np.sort(np.unique(p))[::-1]
    if len(t) < 2: t = np.array([1.0, 0.0])
    TPR=[]; FPR=[]; P = np.sum(y_true==1); N = np.sum(y_true==0)
    for thr in t:
        yhat = (p>=thr).astype(float)
        TP = np.sum((yhat==1)&(y_true==1))
        FP = np.sum((yhat==1)&(y_true==0))
        TN = np.sum((yhat==0)&(y_true==0))
        TPR.append(TP/max(1,P)); FPR.append(FP/max(1,N))
    FPR=np.array(FPR); TPR=np.array(TPR); idx=np.argsort(FPR)
    return FPR[idx], TPR[idx], auc_xy(FPR[idx],TPR[idx])

def pr_curve(y_true, p):
    t = np.sort(np.unique(p))[::-1]
    if len(t) < 2: t = np.array([1.0, 0.0])
    PREC=[]; REC=[]; P = np.sum(y_true==1)
    for thr in t:
        yhat = (p>=thr).astype(float)
        TP = np.sum((yhat==1)&(y_true==1))
        FP = np.sum((yhat==1)&(y_true==0))
        prec = TP/max(1,TP+FP); rec = TP/max(1,P)
        PREC.append(prec); REC.append(rec)
    REC=np.array(REC); PREC=np.array(PREC); idx=np.argsort(REC)
    return REC[idx], PREC[idx], auc_xy(REC[idx], PREC[idx])

def kfold_indices(n:int, k:int, seed:int=123):
    rng = np.random.default_rng(seed)
    idx = np.arange(n); rng.shuffle(idx)
    folds = np.array_split(idx, k)
    return folds

def platt_fit(p: np.ndarray, y: np.ndarray, lr=0.1, epochs=300):
    # Fit logistic on logit(p) to calibrate to y
    eps=1e-6
    z = np.log((p+eps)/(1-p+eps))
    a=0.0; b=0.0
    for _ in range(epochs):
        s = 1/(1+np.exp(-(a*z + b)))
        da = np.mean((s - y)*z)
        db = np.mean(s - y)
        a -= lr*da; b -= lr*db
    return float(a), float(b)

def platt_apply(p: np.ndarray, a: float, b: float):
    z = np.log((p+1e-6)/(1-p+1e-6))
    s = 1/(1+np.exp(-(a*z + b)))
    return s
