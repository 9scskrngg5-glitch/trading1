"""
S9 — Personal Alpha RL Agent (online Q-learning with experience replay).

Motivation
----------
Classic strates use fixed rules or offline-trained models. S9 is different:
it *learns online* from the oracle's own live/paper trade outcomes,
adapting its policy to the specific market behaviour of the operator's
chosen pairs and timeframes.

Architecture
------------
  - State space  : 8-dim vector of normalized features
  - Action space : {-1 (SHORT), 0 (NEUTRAL), 1 (LONG)}
  - Q-function   : 2-layer MLP with optional torch; else tabular with state hashing
  - Exploration  : ε-greedy with annealing (ε: 0.5 → 0.05 over 2000 steps)
  - Experience replay : ring buffer (1000 transitions), mini-batches of 32
  - Update rule  : TD(0) Q-learning, γ=0.99

Reward signal
-------------
Reward = realized PnL% from the trade that followed the action.
This creates a tight feedback loop: if LONG → price drops → negative reward.

Online learning means the model adapts within sessions, not just between them.

Safety
------
S9 never directly executes trades. It produces a parliament vote that is
gated by S0 (regime) and SafetyKernel before any order is placed.

Optional dependency: torch >= 2.2
Graceful fallback: tabular Q-table with hashed states when torch absent.
"""
from __future__ import annotations

import json
import logging
import pickle
import random
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from oracle_v2.ml.base_model import OracleModel

logger = logging.getLogger("ORACLE.ML.S9")

# ── Optional PyTorch ──────────────────────────────────────────────────────────
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import torch.optim as optim
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.debug("S9: torch not available — using tabular Q-table fallback")


# ── Constants ─────────────────────────────────────────────────────────────────

N_ACTIONS = 3          # SHORT / NEUTRAL / LONG
ACTION_MAP = {0: -1, 1: 0, 2: 1}     # action index → signal
SIGNAL_MAP = {-1: "SHORT", 0: "NEUTRAL", 1: "LONG"}
REVERSE_ACTION = {"SHORT": 0, "NEUTRAL": 1, "LONG": 2}


# ── Neural Q-network ──────────────────────────────────────────────────────────

if HAS_TORCH:

    class QNetwork(nn.Module):
        """
        Simple 2-layer MLP for Q-value approximation.
        Input  : state_dim floats
        Output : N_ACTIONS Q-values
        """

        def __init__(self, state_dim: int, hidden: int = 64):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(state_dim, hidden),
                nn.ReLU(),
                nn.Linear(hidden, hidden),
                nn.ReLU(),
                nn.Linear(hidden, N_ACTIONS),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.net(x)


# ── Experience replay ─────────────────────────────────────────────────────────

@dataclass
class Transition:
    state: np.ndarray
    action: int           # index in [0, 1, 2]
    reward: float
    next_state: np.ndarray
    done: bool


class ReplayBuffer:
    def __init__(self, maxlen: int = 1000):
        self._buf: deque[Transition] = deque(maxlen=maxlen)

    def push(self, t: Transition) -> None:
        self._buf.append(t)

    def sample(self, n: int) -> list[Transition]:
        return random.sample(self._buf, min(n, len(self._buf)))

    def __len__(self) -> int:
        return len(self._buf)


# ── S9 RL Agent ───────────────────────────────────────────────────────────────

class S9PersonalRLAgent(OracleModel):
    """
    S9 — Online Q-learning personal alpha agent.

    Parameters
    ----------
    state_dim   : int    Dimension of state vector (default 8)
    hidden_dim  : int    QNetwork hidden size (default 64)
    gamma       : float  TD discount factor (default 0.99)
    lr          : float  Adam learning rate (default 1e-3)
    eps_start   : float  Initial ε for ε-greedy (default 0.5)
    eps_end     : float  Final ε (default 0.05)
    eps_decay   : int    Steps over which ε decays (default 2000)
    batch_size  : int    Mini-batch size for replay updates (default 32)
    update_every: int    Steps between Q-network updates (default 4)
    noise_band  : float  Min |Q-gap| to avoid NEUTRAL (default 0.05)
    """

    MODEL_ID = "S9_RL"
    MODEL_VERSION = "1.0"

    def __init__(
        self,
        state_dim: int = 8,
        hidden_dim: int = 64,
        gamma: float = 0.99,
        lr: float = 1e-3,
        eps_start: float = 0.5,
        eps_end: float = 0.05,
        eps_decay: int = 2000,
        batch_size: int = 32,
        update_every: int = 4,
        noise_band: float = 0.05,
    ):
        super().__init__()
        self.state_dim = state_dim
        self.hidden_dim = hidden_dim
        self.gamma = gamma
        self.lr = lr
        self.eps_start = eps_start
        self.eps_end = eps_end
        self.eps_decay = eps_decay
        self.batch_size = batch_size
        self.update_every = update_every
        self.noise_band = noise_band

        self._step_count = 0
        self._episode_rewards: list[float] = []
        self._replay = ReplayBuffer(maxlen=1000)
        self._fitted = False

        # Q-networks
        if HAS_TORCH:
            self._q_net = QNetwork(state_dim, hidden_dim)
            self._q_target = QNetwork(state_dim, hidden_dim)
            self._q_target.load_state_dict(self._q_net.state_dict())
            self._optimizer = optim.Adam(self._q_net.parameters(), lr=lr)
        else:
            # Tabular fallback: state hash → Q-values
            self._q_table: dict[str, np.ndarray] = {}

        logger.info(
            f"S9 RL agent init — state_dim={state_dim} "
            f"{'(neural)' if HAS_TORCH else '(tabular)'}"
        )

    # ── ε-greedy policy ───────────────────────────────────────────────────────

    @property
    def epsilon(self) -> float:
        """Current exploration rate."""
        frac = min(1.0, self._step_count / max(self.eps_decay, 1))
        return self.eps_end + (self.eps_start - self.eps_end) * (1 - frac)

    def select_action(self, state: np.ndarray, greedy: bool = False) -> int:
        """
        ε-greedy action selection.

        Parameters
        ----------
        state  : (state_dim,) array
        greedy : if True, always exploit (no exploration)

        Returns
        -------
        Action index in [0, 1, 2]
        """
        if not greedy and random.random() < self.epsilon:
            return random.randint(0, N_ACTIONS - 1)

        if HAS_TORCH:
            self._q_net.eval()
            with torch.no_grad():
                s = torch.tensor(state, dtype=torch.float32).unsqueeze(0)
                q_vals = self._q_net(s).squeeze(0).cpu().numpy()
        else:
            q_vals = self._tabular_q(state)

        # Check noise band: if max Q - second Q < noise_band → NEUTRAL
        sorted_q = np.sort(q_vals)[::-1]
        if len(sorted_q) >= 2 and (sorted_q[0] - sorted_q[1]) < self.noise_band:
            return 1  # NEUTRAL

        return int(np.argmax(q_vals))

    # ── Online learning ────────────────────────────────────────────────────────

    def observe(
        self,
        state: np.ndarray,
        action_idx: int,
        reward: float,
        next_state: np.ndarray,
        done: bool = False,
    ) -> Optional[float]:
        """
        Record a transition and optionally update Q-network.

        Called after each trade outcome is known.

        Parameters
        ----------
        state      : feature vector at decision time
        action_idx : action taken (index)
        reward     : realized PnL% (signed)
        next_state : feature vector at close time
        done       : episode boundary flag

        Returns
        -------
        float | None : TD loss if update occurred, else None
        """
        self._replay.push(Transition(state, action_idx, reward, next_state, done))
        self._episode_rewards.append(reward)
        self._step_count += 1

        loss = None
        if self._step_count % self.update_every == 0 and len(self._replay) >= self.batch_size:
            loss = self._update()

        # Sync target network every 100 steps
        if self._step_count % 100 == 0 and HAS_TORCH:
            self._q_target.load_state_dict(self._q_net.state_dict())

        return loss

    def _update(self) -> float:
        """One mini-batch TD update."""
        batch = self._replay.sample(self.batch_size)

        if HAS_TORCH:
            return self._update_neural(batch)
        else:
            return self._update_tabular(batch)

    def _update_neural(self, batch: list[Transition]) -> float:
        states = torch.tensor(
            np.array([t.state for t in batch]), dtype=torch.float32
        )
        actions = torch.tensor([t.action for t in batch], dtype=torch.long)
        rewards = torch.tensor([t.reward for t in batch], dtype=torch.float32)
        next_states = torch.tensor(
            np.array([t.next_state for t in batch]), dtype=torch.float32
        )
        dones = torch.tensor([t.done for t in batch], dtype=torch.float32)

        # Q(s, a)
        self._q_net.train()
        q_vals = self._q_net(states).gather(1, actions.unsqueeze(1)).squeeze(1)

        # TD target
        with torch.no_grad():
            next_q = self._q_target(next_states).max(1).values
            targets = rewards + self.gamma * next_q * (1 - dones)

        loss = F.smooth_l1_loss(q_vals, targets)
        self._optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self._q_net.parameters(), 1.0)
        self._optimizer.step()

        return float(loss.item())

    def _update_tabular(self, batch: list[Transition]) -> float:
        total_loss = 0.0
        for t in batch:
            key = self._state_key(t.state)
            nkey = self._state_key(t.next_state)
            q = self._q_table.get(key, np.zeros(N_ACTIONS))
            nq = self._q_table.get(nkey, np.zeros(N_ACTIONS))
            td_target = t.reward + self.gamma * np.max(nq) * (1 - float(t.done))
            td_error = td_target - q[t.action]
            q[t.action] += 0.1 * td_error  # tabular learning rate
            self._q_table[key] = q
            total_loss += td_error ** 2
        return float(total_loss / len(batch))

    def _tabular_q(self, state: np.ndarray) -> np.ndarray:
        return self._q_table.get(self._state_key(state), np.zeros(N_ACTIONS))

    @staticmethod
    def _state_key(state: np.ndarray) -> str:
        """Discretize state for tabular lookup."""
        return ",".join(f"{round(float(v), 1)}" for v in state)

    # ── OracleModel interface ──────────────────────────────────────────────────

    def fit(self, X: np.ndarray, y: np.ndarray, **kwargs) -> "S9PersonalRLAgent":
        """
        Bootstrap from offline data via supervised imitation, then switch to online.

        X : (N, state_dim) — state observations
        y : (N,) — labels {-1, 0, 1} (SHORT/NEUTRAL/LONG)
        """
        logger.info(f"S9: offline bootstrap on {len(X)} samples")
        rewards = y.astype(float) * 0.01   # Treat label as pseudo-reward

        for i in range(len(X) - 1):
            action_idx = REVERSE_ACTION.get(SIGNAL_MAP.get(int(y[i]), "NEUTRAL"), 1)
            self.observe(X[i], action_idx, rewards[i], X[i + 1], done=(i == len(X) - 2))

        self._fitted = True
        logger.info(f"S9: bootstrap complete — {self._step_count} steps, ε={self.epsilon:.3f}")
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict direction signals for array of states."""
        if X.ndim == 1:
            X = X[np.newaxis, :]
        return np.array([ACTION_MAP[self.select_action(x, greedy=True)] for x in X])

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Soft probabilities via softmax over Q-values."""
        if X.ndim == 1:
            X = X[np.newaxis, :]
        N = len(X)
        proba = np.zeros((N, 3), dtype=float)
        for i, x in enumerate(X):
            if HAS_TORCH:
                self._q_net.eval()
                with torch.no_grad():
                    s = torch.tensor(x, dtype=torch.float32).unsqueeze(0)
                    q_vals = self._q_net(s).squeeze(0).cpu().numpy()
            else:
                q_vals = self._tabular_q(x)
            # Softmax
            q_shifted = q_vals - q_vals.max()
            exp_q = np.exp(q_shifted)
            proba[i] = exp_q / exp_q.sum()
        return proba

    def predict_single(self, x: np.ndarray) -> dict:
        proba = self.predict_proba(x[np.newaxis, :])[0]
        action_idx = int(np.argmax(proba))
        direction = SIGNAL_MAP[ACTION_MAP[action_idx]]
        return {
            "direction": direction,
            "confidence": float(proba[action_idx]),
            "proba_short": float(proba[0]),
            "proba_neutral": float(proba[1]),
            "proba_long": float(proba[2]),
            "epsilon": self.epsilon,
            "steps": self._step_count,
        }

    def parliament_vote(self, x: np.ndarray) -> tuple[str, float]:
        result = self.predict_single(x)
        return result["direction"], result["confidence"]

    # ── Statistics ─────────────────────────────────────────────────────────────

    def recent_performance(self, n: int = 50) -> dict:
        rewards = self._episode_rewards[-n:]
        if not rewards:
            return {"n": 0, "mean_reward": 0.0, "total_reward": 0.0, "win_rate": 0.0}
        return {
            "n": len(rewards),
            "mean_reward": float(np.mean(rewards)),
            "total_reward": float(np.sum(rewards)),
            "win_rate": float(np.mean([r > 0 for r in rewards])),
            "epsilon": self.epsilon,
            "steps": self._step_count,
        }

    # ── Persistence ─────────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        meta = {
            "state_dim": self.state_dim,
            "hidden_dim": self.hidden_dim,
            "gamma": self.gamma,
            "lr": self.lr,
            "eps_start": self.eps_start,
            "eps_end": self.eps_end,
            "eps_decay": self.eps_decay,
            "batch_size": self.batch_size,
            "update_every": self.update_every,
            "noise_band": self.noise_band,
            "step_count": self._step_count,
            "episode_rewards_tail": self._episode_rewards[-200:],
        }
        if HAS_TORCH:
            self.save_torch(path, self._q_net)
        else:
            # Save tabular Q-table
            table_path = Path(path).with_suffix(".qtable.pkl")
            with open(table_path, "wb") as f:
                pickle.dump(self._q_table, f)
        meta_path = Path(path).with_suffix(".meta.json")
        with open(meta_path, "w") as f:
            json.dump(meta, f)

    @classmethod
    def load(cls, path: str) -> "S9PersonalRLAgent":
        meta_path = Path(path).with_suffix(".meta.json")
        if not meta_path.exists():
            logger.warning(f"S9: meta file not found at {meta_path}")
            return cls()
        with open(meta_path) as f:
            meta = json.load(f)
        obj = cls(
            state_dim=meta["state_dim"],
            hidden_dim=meta["hidden_dim"],
            gamma=meta["gamma"],
            lr=meta["lr"],
            eps_start=meta["eps_start"],
            eps_end=meta["eps_end"],
            eps_decay=meta["eps_decay"],
            batch_size=meta["batch_size"],
            update_every=meta["update_every"],
            noise_band=meta.get("noise_band", 0.05),
        )
        obj._step_count = meta.get("step_count", 0)
        obj._episode_rewards = meta.get("episode_rewards_tail", [])
        if HAS_TORCH and Path(path).exists():
            try:
                obj.load_torch(path, obj._q_net)
                obj._q_target.load_state_dict(obj._q_net.state_dict())
                obj._fitted = True
            except Exception as e:
                logger.warning(f"S9: torch model load failed: {e}")
        else:
            table_path = Path(path).with_suffix(".qtable.pkl")
            if table_path.exists():
                with open(table_path, "rb") as f:
                    obj._q_table = pickle.load(f)
                obj._fitted = True
        return obj
