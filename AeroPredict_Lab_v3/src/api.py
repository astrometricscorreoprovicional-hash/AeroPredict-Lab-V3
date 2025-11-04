
    from fastapi import FastAPI
    from fastapi.responses import FileResponse, PlainTextResponse
    from pydantic import BaseModel, Field
    from typing import List, Dict, Any
    import numpy as np, os, time, json
    from loguru import logger
    from .model import train_logit, LogitModel, synth_dataset, standardize, roc_curve, pr_curve, kfold_indices, platt_fit, platt_apply
    from .experiments import CSVLogger

    MODEL_PATH = os.environ.get("MODEL_PATH", "models/model.npz")
    STATS_PATH = os.environ.get("STATS_PATH", "models/stats.json")
    CALIB_PATH = os.environ.get("CALIB_PATH", "models/calib.json")
    CARD_PATH  = os.environ.get("CARD_PATH",  "models/model_card.md")

    app = FastAPI(title="AeroPredict Lab API", version="3.0.0")
    logger.add(lambda m: print(m, end=""), level=os.environ.get("LOG_LEVEL","INFO"))
    exlog = CSVLogger("data/experiments.csv")

    class TrainRequest(BaseModel):
        n_samples: int = Field(8000, ge=1000, le=300000)
        lr: float = 0.05
        epochs: int = 400
        l2: float = 1e-3
        seed: int = 42
        notes: str = ""

    class TrainCVRequest(BaseModel):
        n_samples: int = Field(10000, ge=2000, le=300000)
        k_folds: int = Field(5, ge=2, le=10)
        lr: float = 0.05
        epochs: int = 400
        l2: float = 1e-3
        seed: int = 123
        notes: str = ""

    class FeatureVec(BaseModel):
        airspeed: float; altitude: float; vspeed: float; pitch: float; roll: float; wind_x: float; wind_y: float

    class BatchPredict(BaseModel):
        items: List[FeatureVec]

    def _save_stats(mu, sigma):
        os.makedirs(os.path.dirname(STATS_PATH), exist_ok=True)
        with open(STATS_PATH, "w") as f:
            json.dump({"mu": mu.tolist(), "sigma": sigma.tolist()}, f)

    def _load_stats():
        with open(STATS_PATH, "r") as f:
            s = json.load(f); return np.array(s["mu"]), np.array(s["sigma"])

    def _save_calib(a:float,b:float):
        os.makedirs(os.path.dirname(CALIB_PATH), exist_ok=True)
        with open(CALIB_PATH, "w") as f: json.dump({"a":a,"b":b}, f)

    def _load_calib():
        if not os.path.exists(CALIB_PATH): return None
        with open(CALIB_PATH,"r") as f: c=json.load(f); return float(c["a"]), float(c["b"])

    def _ensure_model():
        if os.path.exists(MODEL_PATH) and os.path.exists(STATS_PATH):
            return LogitModel.load(MODEL_PATH), _load_stats()
        X,y = synth_dataset(n=4000, seed=42)
        model, mu, sigma = train_logit(X, y, lr=0.05, epochs=400, l2=1e-3)
        model.save(MODEL_PATH); _save_stats(mu, sigma)
        return model, (mu, sigma)

    MODEL, (MU, SIGMA) = _ensure_model()

    @app.get("/health")
    def health(): 
        return {"status":"ok","version":"3.0.0","model_exists": os.path.exists(MODEL_PATH), "calibrated": os.path.exists(CALIB_PATH)}

    @app.post("/train")
    def train(req: TrainRequest):
        global MODEL, MU, SIGMA
        X,y = synth_dataset(n=req.n_samples, seed=req.seed)
        MODEL, MU, SIGMA = train_logit(X, y, lr=req.lr, epochs=req.epochs, l2=req.l2)
        MODEL.save(MODEL_PATH); _save_stats(MU, SIGMA)
        exlog.log("train", req.model_dump(), {"ok":True})
        return {"trained": True, "n": int(req.n_samples)}

    @app.post("/train_cv")
    def train_cv(req: TrainCVRequest):
        X,y = synth_dataset(n=req.n_samples, seed=req.seed)
        folds = kfold_indices(len(X), req.k_folds, seed=req.seed)
        per_fold=[]; aucrocs=[]; aucprs=[]
        for i in range(req.k_folds):
            va_idx = folds[i]
            tr_idx = np.concatenate([folds[j] for j in range(req.k_folds) if j!=i])
            model, mu, sigma = train_logit(X[tr_idx], y[tr_idx], lr=req.lr, epochs=req.epochs, l2=req.l2)
            p = model.predict_proba((X[va_idx]-mu)/(sigma+1e-8))
            fpr,tpr,aucroc = roc_curve(y[va_idx], p)
            rec,prec,aucpr  = pr_curve(y[va_idx], p)
            per_fold.append({"fold":i,"n_train":int(len(tr_idx)),"n_val":int(len(va_idx)),"auc_roc":float(aucroc),"auc_pr":float(aucpr)})
            aucrocs.append(aucroc); aucprs.append(aucpr)
        summary = {"k_folds": req.k_folds, "auc_roc_mean": float(np.mean(aucrocs)), "auc_pr_mean": float(np.mean(aucprs))}
        exlog.log("train_cv", req.model_dump(), {"auc_roc_mean": summary["auc_roc_mean"], "auc_pr_mean": summary["auc_pr_mean"]})
        return {"per_fold": per_fold, "summary": summary}

    @app.post("/calibrate")
    def calibrate():
        # use a fresh val set to fit Platt
        X,y = synth_dataset(n=4000, seed=777)
        # load current model stats
        global MODEL, MU, SIGMA
        p = MODEL.predict_proba((X-MU)/(SIGMA+1e-8))
        a,b = platt_fit(p, y, lr=0.1, epochs=400)
        _save_calib(a,b)
        exlog.log("calibrate", {}, {"a":a,"b":b})
        return {"calibrated": True, "a": a, "b": b}

    def _vectorize(v: FeatureVec):
        x = np.array([v.airspeed, v.altitude, v.vspeed, v.pitch, v.roll, v.wind_x, v.wind_y], dtype=float)
        xs = (x - MU) / (SIGMA + 1e-8)
        return xs

    @app.post("/predict")
    def predict(v: FeatureVec):
        xs = _vectorize(v)
        p = float(MODEL.predict_proba(xs))
        calib = _load_calib()
        if calib:
            a,b = calib; p = float(platt_apply(np.array([p]), a, b)[0])
        return {"prob_unstable": p, "ts": time.time(), "calibrated": bool(calib)}

    @app.post("/predict/batch")
    def predict_batch(req: BatchPredict):
        Xs = np.vstack([_vectorize(v) for v in req.items])
        p = MODEL.predict_proba(Xs)
        calib = _load_calib()
        if calib:
            a,b = calib; p = platt_apply(p, a, b)
        return {"probs": [float(x) for x in p], "calibrated": bool(calib)}

    @app.get("/model/download")
    def model_download():
        return FileResponse(MODEL_PATH, filename="model.npz")

    @app.get("/model/card")
    def model_card():
        card = f"""# Model Card — AeroPredict v3
Version: 3.0.0
Features: airspeed, altitude, vspeed, pitch, roll, wind_x, wind_y
Model: Logistic Regression (NumPy) with standardization (mu/sigma) and optional Platt calibration.
Endpoints: /train, /train_cv, /calibrate, /predict, /predict/batch
Logs: data/experiments.csv
"""
        return PlainTextResponse(card)
