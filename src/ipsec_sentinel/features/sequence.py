"""Temporal packet-sequence extraction from encrypted ESP flows.

Extracts ordered [packet_size, inter_arrival_time, direction] sequence representations
from encrypted ESP flows for temporal deep learning (1D-CNN, TCN, BiLSTM, Transformer).

Properties guaranteed:
1. Determinism: Same packet list -> exact float-equal tensor every time.
2. Total, never NaN: Empty flows, single-packet flows, zero IAT flows produce valid finite numbers.
3. Attention / Validity Masking: Distinguishes real observed packets from zero-padded slots.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Sequence

import numpy as np

from ipsec_sentinel.features.flow import DirectedPacket

if TYPE_CHECKING:  # pragma: no cover
    import torch
    from torch.utils.data import Dataset
else:
    try:
        import torch
        from torch.utils.data import Dataset
    except ImportError:  # pragma: no cover
        torch = None
        Dataset = object

DEFAULT_SEQUENCE_LENGTH: Final[int] = 128
MTU_NORMALIZATION_BYTES: Final[float] = 1500.0
MAX_IAT_CLAMP_SECONDS: Final[float] = 10.0


@dataclass(frozen=True)
class PacketSequence:
    """A fixed-length temporal sequence extracted from an ESP flow window.

    Attributes:
        sizes: Normalized packet sizes of shape (N,), values in [0, 1+].
        iats: Inter-arrival times of shape (N,), values in [0, 1] (log-scaled).
        directions: Directionality indicators of shape (N,), +1.0 (forward), -1.0 (backward), 0.0 (pad).
        mask: Validity/attention mask of shape (N,), 1.0 for valid observed packets, 0.0 for padding.
        raw_sizes: Unnormalized raw packet sizes in bytes of shape (N,).
        raw_iats: Unnormalized inter-arrival times in seconds of shape (N,).
        packet_count: Number of real observed packets before padding.
        seq_len: The sequence window length N.
    """

    sizes: np.ndarray
    iats: np.ndarray
    directions: np.ndarray
    mask: np.ndarray
    raw_sizes: np.ndarray
    raw_iats: np.ndarray
    packet_count: int
    seq_len: int

    def to_array(self, channel_first: bool = True) -> np.ndarray:
        """Stack the sequence features into a 2D numpy array of shape (3, N) or (N, 3).

        Channels in order:
            0: normalized packet size
            1: normalized log inter-arrival time
            2: direction (+1.0 forward, -1.0 backward, 0.0 pad)
        """
        stacked = np.stack([self.sizes, self.iats, self.directions], axis=0)  # (3, N)
        if not channel_first:
            stacked = np.transpose(stacked, (1, 0))  # (N, 3)
        return stacked

    def to_tensor(self, channel_first: bool = True) -> torch.Tensor:
        """Convert the sequence to a PyTorch float32 tensor."""
        if torch is None:  # pragma: no cover
            raise RuntimeError("PyTorch is not installed in the environment.")
        return torch.from_numpy(self.to_array(channel_first=channel_first)).float()

    def mask_tensor(self) -> torch.Tensor:
        """Convert validity mask to a PyTorch float32 tensor of shape (N,)."""
        if torch is None:  # pragma: no cover
            raise RuntimeError("PyTorch is not installed in the environment.")
        return torch.from_numpy(self.mask).float()


def extract_sequence(
    packets: Sequence[DirectedPacket],
    max_len: int = DEFAULT_SEQUENCE_LENGTH,
    normalize: bool = True,
) -> PacketSequence:
    """Extract a single fixed-length PacketSequence from a sequence of directed packets.

    If fewer than max_len packets are provided, the sequence is right-padded with zeros
    and the mask indicates valid positions. If more than max_len packets are provided,
    the sequence is truncated to the first max_len packets.

    Args:
        packets: Ordered sequence of DirectedPacket objects.
        max_len: Target sequence length N (default 128).
        normalize: Whether to normalize packet sizes by MTU (1500) and log-scale IATs.
    """
    if max_len <= 0:
        raise ValueError(f"max_len must be positive, got {max_len}")

    n_packets = len(packets)
    valid_len = min(n_packets, max_len)

    raw_sizes = np.zeros(max_len, dtype=np.float32)
    raw_iats = np.zeros(max_len, dtype=np.float32)
    directions = np.zeros(max_len, dtype=np.float32)
    mask = np.zeros(max_len, dtype=np.float32)

    if valid_len > 0:
        mask[:valid_len] = 1.0

        for i in range(valid_len):
            pkt = packets[i]
            raw_sizes[i] = float(pkt.size)
            directions[i] = 1.0 if pkt.forward else -1.0

            if i == 0:
                raw_iats[i] = 0.0
            else:
                prev_pkt = packets[i - 1]
                delta = (pkt.timestamp - prev_pkt.timestamp).total_seconds()
                raw_iats[i] = max(0.0, float(delta))

    if normalize:
        sizes = raw_sizes / MTU_NORMALIZATION_BYTES
        # Log-scaling for IAT: log10(1 + delta * 1000) / log10(1 + MAX_IAT_CLAMP * 1000)
        # Yields a smooth monotonic value in [0.0, 1.0] without infinite outliers.
        clamped_iats = np.minimum(raw_iats, MAX_IAT_CLAMP_SECONDS)
        denom = math.log10(1.0 + MAX_IAT_CLAMP_SECONDS * 1000.0)
        iats = np.log10(1.0 + clamped_iats * 1000.0) / denom
        iats = iats.astype(np.float32)
    else:
        sizes = raw_sizes.copy()
        iats = raw_iats.copy()

    return PacketSequence(
        sizes=sizes,
        iats=iats,
        directions=directions,
        mask=mask,
        raw_sizes=raw_sizes,
        raw_iats=raw_iats,
        packet_count=valid_len,
        seq_len=max_len,
    )


def extract_sliding_sequences(
    packets: Sequence[DirectedPacket],
    window_len: int = DEFAULT_SEQUENCE_LENGTH,
    stride: int | None = None,
    min_packets: int = 10,
    normalize: bool = True,
) -> list[PacketSequence]:
    """Extract multiple sliding sequence windows from a flow.

    Args:
        packets: Ordered sequence of DirectedPacket objects.
        window_len: Length of each window in packets (default 128).
        stride: Stride between window starts. Defaults to window_len // 2 (50% overlap).
        min_packets: Minimum packets in a window to be included.
        normalize: Whether to normalize features.
    """
    if window_len <= 0:
        raise ValueError(f"window_len must be positive, got {window_len}")
    if stride is None:
        stride = max(1, window_len // 2)
    elif stride <= 0:
        raise ValueError(f"stride must be positive, got {stride}")

    n_packets = len(packets)
    if n_packets < min_packets:
        return []

    sequences: list[PacketSequence] = []
    start = 0

    while start < n_packets:
        chunk = packets[start : start + window_len]
        if len(chunk) < min_packets:
            break
        seq = extract_sequence(chunk, max_len=window_len, normalize=normalize)
        sequences.append(seq)
        start += stride
        if len(chunk) < window_len:
            # Reached the end of available packets
            break

    return sequences


class IPsecSequenceDataset(Dataset):  # type: ignore[misc]
    """PyTorch Dataset for IPsec temporal packet sequences.

    Yields dictionaries with:
        - "sequence": Tensor of shape (3, N)
        - "mask": Tensor of shape (N,)
        - "label": Tensor scalar integer (class index)
        - "metadata": Arbitrary dict with flow identifiers
    """

    def __init__(
        self,
        samples: list[tuple[PacketSequence, int, dict[str, Any]]],
        channel_first: bool = True,
    ) -> None:
        self.samples = samples
        self.channel_first = channel_first

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        seq, label, meta = self.samples[idx]
        return {
            "sequence": seq.to_tensor(channel_first=self.channel_first),
            "mask": seq.mask_tensor(),
            "label": torch.tensor(label, dtype=torch.long) if torch is not None else label,
            "metadata": meta,
        }
