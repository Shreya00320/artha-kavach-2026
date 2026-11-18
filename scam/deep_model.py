"""
scam/deep_model.py — a small deep neural network for scam / suspicious / safe messages.

Architecture (fastText-style, but with a real multi-layer head):

    text ──► hashed word 1-2-grams + char 3-5-grams (+ number/URL placeholders)
         ──► EmbeddingBag (mean)            16384 buckets × 64 dims
         ──► Linear 64→128 ─ ReLU ─ Dropout
         ──► Linear 128→64 ─ ReLU
         ──► Linear 64→3  ─ softmax        [safe, suspicious, scam]

Why this shape: the training set is only ~900 messages, so a big transformer would overfit and
would need a heavy runtime. Hashed n-gram embeddings generalise to unseen words and spelling
variants (including Hinglish), and the whole model is ~2 MB.

Train with PyTorch (`python -m scam.train_deep`); the weights are exported to a .npz file and
INFERENCE USES ONLY NUMPY — so the deployed app does not need torch.

Public API:
  DeepScamClassifier.train(csv_paths, ...)   (needs torch)
  DeepScamClassifier.save(path) / .load(path)
  DeepScamClassifier.predict_proba(text) -> {"safe": p, "suspicious": p, "scam": p}
  DeepScamClassifier.predict(text) -> label
  load_default() -> DeepScamClassifier | None      # models/scam_dl.npz
"""

from __future__ import annotations

import logging
import re
import zlib
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

CLASSES = ["safe", "suspicious", "scam"]
N_BUCKETS = 2 ** 14
EMB_DIM = 64
HIDDEN1, HIDDEN2 = 128, 64
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "scam_dl.npz"

_SHORTENERS = ("bit.ly", "tinyurl", "rb.gy", "cutt.ly", "is.gd", "t.ly", "goo.su", "short.link", "t.co", "shorturl")
_URL_RE = re.compile(r"(https?://\S+|www\.\S+|\b[a-z0-9-]+\.(?:com|in|co|net|org|xyz|apk|link|info|me)\b\S*)", re.I)
_PHONE_RE = re.compile(r"\b(?:\+?91[- ]?)?[6-9]\d{9}\b")
_MONEY_RE = re.compile(r"(?:₹|rs\.?|inr)\s*[\d,]+(?:\.\d+)?", re.I)
_NUM_RE = re.compile(r"\d+")
_WORD_RE = re.compile(r"[a-zऀ-ॿ]+|<[a-z]+>")


def _normalise(text: str) -> str:
    """Lower-case and replace volatile surface forms by placeholders the model can learn from."""
    t = text.lower()
    t = _URL_RE.sub(lambda m: " <shorturl> " if any(s in m.group(0) for s in _SHORTENERS) else " <url> ", t)
    t = _PHONE_RE.sub(" <phone> ", t)
    t = _MONEY_RE.sub(" <money> ", t)
    t = _NUM_RE.sub(lambda m: " <num> " if len(m.group(0)) >= 4 else m.group(0), t)
    return t


def _bucket(token: str) -> int:
    # crc32 is deterministic across processes (Python's hash() is salted per run)
    return zlib.crc32(token.encode("utf-8")) % N_BUCKETS


def featurize(text: str) -> list[int]:
    """Hashed feature ids: word unigrams + bigrams + char_wb 3-5-grams."""
    t = _normalise(text)
    words = _WORD_RE.findall(t)
    feats = [f"w:{w}" for w in words]
    feats += [f"b:{a}_{b}" for a, b in zip(words, words[1:])]
    for w in words:
        if w.startswith("<"):
            continue
        padded = f"^{w}$"
        for n in (3, 4, 5):
            feats += [f"c:{padded[i:i + n]}" for i in range(len(padded) - n + 1)]
    ids = [_bucket(f) for f in feats]
    return ids or [_bucket("<empty>")]


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


class DeepScamClassifier:
    """Numpy-inference wrapper around weights trained with PyTorch."""

    CLASSES = CLASSES

    def __init__(self) -> None:
        self.params: Optional[list[dict[str, np.ndarray]]] = None   # one dict per ensemble member
        self.meta: dict = {}

    # ------------------------------------------------------------------ inference
    @property
    def is_trained(self) -> bool:
        return self.params is not None

    def predict_proba(self, text: str) -> dict[str, float]:
        if self.params is None:
            raise RuntimeError("Model not trained or loaded.")
        ids = np.array(featurize(text))
        probs = np.zeros(len(CLASSES))
        for p in self.params:
            x = p["emb"][ids].astype(np.float32).mean(axis=0)
            h = np.maximum(0.0, p["w1"] @ x + p["b1"])
            h = np.maximum(0.0, p["w2"] @ h + p["b2"])
            probs += _softmax(p["w3"] @ h + p["b3"])
        probs /= len(self.params)
        return {c: round(float(v), 4) for c, v in zip(CLASSES, probs)}

    def predict(self, text: str) -> str:
        pr = self.predict_proba(text)
        return max(pr, key=pr.get)

    # ------------------------------------------------------------------ persistence
    def save(self, path: str | Path = DEFAULT_MODEL_PATH) -> None:
        assert self.params is not None
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        arrays = {"n_members": np.array(len(self.params))}
        for i, p in enumerate(self.params):
            for k, v in p.items():
                arrays[f"{i}_{k}"] = v.astype(np.float16) if k == "emb" else v.astype(np.float32)
        np.savez_compressed(path, **arrays)
        logger.info("Saved deep scam model to %s (%.1f KB)", path, path.stat().st_size / 1024)

    def load(self, path: str | Path = DEFAULT_MODEL_PATH) -> "DeepScamClassifier":
        z = np.load(Path(path))
        n = int(z["n_members"])
        self.params = [{k: z[f"{i}_{k}"] for k in ("emb", "w1", "b1", "w2", "b2", "w3", "b3")} for i in range(n)]
        return self

    # ------------------------------------------------------------------ training (torch)
    def train(self, rows: list[dict], n_members: int = 3, epochs: int = 60, seed: int = 42,
              verbose: bool = True) -> None:
        """Train `n_members` networks (different seeds) on rows [{'text','label'}, ...] and keep them
        as an ensemble. Each member early-stops on its own stratified 15% validation split."""
        try:
            import torch
            from torch import nn
        except ImportError as exc:                      # pragma: no cover
            raise RuntimeError("Training needs PyTorch (pip install torch). Inference does not.") from exc

        label_to_i = {c: i for i, c in enumerate(CLASSES)}
        data = [(featurize(r["text"]), label_to_i[r["label"]]) for r in rows if r["label"] in label_to_i]
        counts = np.bincount([y for _, y in data], minlength=len(CLASSES)).astype(np.float32)
        class_w = torch.tensor(counts.sum() / (len(CLASSES) * np.maximum(counts, 1)), dtype=torch.float32)

        class Net(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.emb = nn.EmbeddingBag(N_BUCKETS, EMB_DIM, mode="mean")
                self.l1, self.l2, self.l3 = nn.Linear(EMB_DIM, HIDDEN1), nn.Linear(HIDDEN1, HIDDEN2), nn.Linear(HIDDEN2, 3)
                self.drop = nn.Dropout(0.3)
                nn.init.zeros_(self.emb.weight)   # unseen n-grams contribute nothing (no random noise)

            def forward(self, flat, offsets):
                x = self.drop(self.emb(flat, offsets))
                x = self.drop(torch.relu(self.l1(x)))
                x = torch.relu(self.l2(x))
                return self.l3(x)

        def batchify(items, feature_dropout=0.0, gen=None):
            flat, offsets, ys = [], [], []
            for ids, y in items:
                if feature_dropout > 0 and len(ids) > 8:
                    keep = [i for i in ids if gen.random() > feature_dropout] or ids
                else:
                    keep = ids
                offsets.append(len(flat))
                flat.extend(keep)
                ys.append(y)
            return (torch.tensor(flat, dtype=torch.long), torch.tensor(offsets, dtype=torch.long),
                    torch.tensor(ys, dtype=torch.long))

        members = []
        for m in range(n_members):
            s = seed + m
            rng = np.random.default_rng(s)
            torch.manual_seed(s)
            idx = rng.permutation(len(data))
            by_class = {c: [i for i in idx if data[i][1] == c] for c in range(3)}
            val_idx = [i for c in by_class.values() for i in c[: max(1, int(0.15 * len(c)))]]
            val_set = set(val_idx)
            train_items = [data[i] for i in idx if i not in val_set]
            val_items = [data[i] for i in val_idx]

            net = Net()
            opt = torch.optim.AdamW(net.parameters(), lr=3e-3, weight_decay=1e-2)
            loss_fn = nn.CrossEntropyLoss(weight=class_w, label_smoothing=0.05)
            pyrand = np.random.default_rng(s + 1000)
            best, best_state, patience = (1e9, None, 0)
            for ep in range(epochs):
                net.train()
                order = rng.permutation(len(train_items))
                for b in range(0, len(order), 32):
                    chunk = [train_items[i] for i in order[b:b + 32]]
                    flat, off, y = batchify(chunk, feature_dropout=0.15, gen=pyrand)
                    opt.zero_grad()
                    loss = loss_fn(net(flat, off), y)
                    loss.backward()
                    opt.step()
                net.eval()
                with torch.no_grad():
                    flat, off, y = batchify(val_items)
                    vloss = float(nn.functional.cross_entropy(net(flat, off), y, weight=class_w))
                    vacc = float((net(flat, off).argmax(1) == y).float().mean())
                if vloss < best - 1e-4:
                    best, patience = vloss, 0
                    best_state = {k: v.clone() for k, v in net.state_dict().items()}
                    best_acc = vacc
                else:
                    patience += 1
                    if patience >= 10:
                        break
            net.load_state_dict(best_state)
            if verbose:
                print(f"  member {m}: stopped at epoch {ep + 1}, val loss {best:.3f}, val acc {best_acc:.2%}")
            members.append({
                "emb": net.emb.weight.detach().numpy().copy(),
                "w1": net.l1.weight.detach().numpy().copy(), "b1": net.l1.bias.detach().numpy().copy(),
                "w2": net.l2.weight.detach().numpy().copy(), "b2": net.l2.bias.detach().numpy().copy(),
                "w3": net.l3.weight.detach().numpy().copy(), "b3": net.l3.bias.detach().numpy().copy(),
            })
        # Round-trip the embeddings through float16 so in-memory == saved model.
        for p in members:
            p["emb"] = p["emb"].astype(np.float16).astype(np.float32)
        self.params = members


def load_default(path: str | Path = DEFAULT_MODEL_PATH) -> Optional[DeepScamClassifier]:
    """Load the shipped model, or None if the weights file is missing/corrupt."""
    try:
        return DeepScamClassifier().load(path)
    except Exception as exc:
        logger.warning("Deep scam model unavailable (%s)", exc)
        return None
