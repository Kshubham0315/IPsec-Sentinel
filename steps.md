Aapke README.md ke upgraded research roadmap ke mutabiq, pure project ko 4 core phases me divide kiya gaya hai:

Phase 1 (Week 1): Temporal ML & Sequence Modeling (1D-CNN, TCN, Packet-Sequence Tensors)
Phase 2 (Week 2): Self-Supervised Representation Learning & Open-Set / OOD Detection
Phase 3 (Week 3): Security Anomaly Detection, Traffic Morphing & Adversarial Robustness
Phase 4 (Week 4): Cross-Network Generalization, ONNX / Streaming Production Deployment
Neeche Phase 1: Temporal Packet-Sequence Modeling & Deep Flow Encoders ka complete, structured aur actionable distribution (step-by-step breakdown) hai:

🚀 Phase 1: Temporal ML & Sequence Modeling (Week 1)
Phase 1 ka primary goal hai: Handcrafted 42 tabular features (XGBoost/RF) se aage badhkar raw temporal packet sequences se deep temporal patterns (bursts, jitter, directionality transitions) ko learn karna.

                          ESP Flow Packet Stream
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │ Step 1.1: Sequence Extraction & Tensor Pipeline        │
       │ - [size, IAT, direction] per packet                    │
       │ - Sliding Windows (N = 64, 128, 256)                   │
       │ - Zero-padding & Attention / Validity Masks            │
       └────────────────────────────┬───────────────────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
   ┌─────────────────────────────┐     ┌─────────────────────────────┐
   │ Step 1.2: Baseline Benchmark│     │ Step 1.3: Deep Sequence     │
   │ - Existing Tabular XGBoost  │     │           Encoders          │
   │ - Grouped Cross-Validation  │     │ - 1D-CNN (Local bursts)     │
   │ - Baseline Macro-F1 & ECE   │     │ - TCN (Dilated long-range)  │
   │                             │     │ - Flow Embedding (d = 128)  │
   └──────────────┬──────────────┘     └──────────────┬──────────────┘
                  │                                   │
                  └─────────────────┬─────────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │ Step 1.4: Training Pipeline & Loss Calibration         │
       │ - PyTorch Training Loop, AdamW, Cosine Annealing       │
       │ - GroupKFold (zero cross-capture data leakage)         │
       └────────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │ Step 1.5: Comparative Evaluation & CLI Integration     │
       │ - Tabular vs 1D-CNN vs TCN Benchmark Report            │
       │ - CLI: `sentinel model train-sequence`                 │
       │ - Complete Unit Tests & Lint Passes                    │
       └────────────────────────────────────────────────────────┘
📋 Phase 1 Detailed Task Breakdown
🔹 Milestone 1.1: Sequence Data Extraction & Tensor Pipeline
Files to create/modify:

src/ipsec_sentinel/features/sequence.py (New)
src/ipsec_sentinel/features/dataset.py (Extend)
Tasks:

Raw Packet-Level Sequence Extractor:
Har encrypted ESP flow se ordered sequence extract karna: $$\mathbf{x}_i = [\text{packet_size}_i, ;; \Delta t_i (\text{inter_arrival_time}), ;; d_i (\text{direction} \in {+1, -1})]$$
Windowing & Padding:
Configurable fixed window lengths: $N \in {64, 128, 256}$.
Flows shorter than $N$: Right zero-padding + binary attention mask ($1$ for valid packet, $0$ for pad).
Long flows: Non-overlapping ya rolling sliding windows.
Feature Scaling / Normalization:
packet_size: Normalized by link MTU ($1500$ bytes).
inter_arrival_time: Log-scaled $\log_{10}(\Delta t + 10^{-6})$ ya clipped min-max.
direction: Binary float $(+1.0, -1.0)$.
PyTorch Dataset Adapter:
IPsecSequenceDataset (inherits torch.utils.data.Dataset) jo tensors (batch, channels=3, seq_len=N) yield kare.
🔹 Milestone 1.2: Tabular Baseline Benchmark (Rigorous Ground Truth)
Files to create/modify:

src/ipsec_sentinel/ml/baseline.py (Or utilize src/ipsec_sentinel/ml/train.py)
Tasks:

Grouped cross-validation (by capture_id) par current XGBoost aur Random Forest models ka baseline record karna.
Standardized evaluation metrics collect karna:
Macro-F1 (Overall & Per-Class for VoIP, Video, Web, Email, Messaging, ICMP, Replay)
Balanced Accuracy
Expected Calibration Error (ECE)
Inference Latency per flow
Baseline numbers ko models/baseline_benchmark.json me save karna taki deep models se apple-to-apple comparison ho sake.
🔹 Milestone 1.3: Deep Temporal Sequence Encoders
Files to create:

src/ipsec_sentinel/ml/sequence/__init__.py
src/ipsec_sentinel/ml/sequence/cnn.py
src/ipsec_sentinel/ml/sequence/tcn.py
src/ipsec_sentinel/ml/sequence/models.py (Shared backbone & classification heads)
Tasks:

1D-CNN Encoder (cnn.py):
Multiple 1D convolutional layers with kernel sizes 3, 5, 7 to capture local packet-size burst patterns.
Structure: Conv1d -> BatchNorm1d -> GELU/ReLU -> MaxPool1d -> Dropout.
Global Average Pooling / Adaptive Pooling $\to$ Flow Embedding Vector ($\mathbb{R}^{128}$).
Temporal Convolutional Network - TCN (tcn.py):
Dilated Causal Convolutions with dilation factors $d \in [1, 2, 4, 8, 16]$.
Residual connections & weight normalization / LayerNorm.
Large receptive field jo periodic beaconing aur long-range burst intervals capture kare without recurrent bottlenecks.
Classification & Embedding Head:
Modular architecture: $$\text{Sequence Tensor} \xrightarrow{\text{Temporal Encoder}} \text{Flow Embedding } \mathbf{z} \in \mathbb{R}^{128} \xrightarrow{\text{Classifier Head}} \text{Logits } \in \mathbb{R}^{7}$$
Yeh Flow Embedding baad me Phase 2 (Self-Supervised & OOD) aur Phase 3 (Anomaly Detection) me reuse hogi.
🔹 Milestone 1.4: Sequence Training Engine
Files to create:

src/ipsec_sentinel/ml/sequence/train.py
Tasks:

Leakage-Proof Data Splitting:
GroupKFold partitioning by capture_id taaki ek capture ke packets train aur test dono me leak na hon.
Training Loop & Optimization:
Optimizer: AdamW(lr=1e-3, weight_decay=1e-2).
Scheduler: CosineAnnealingLR with warmup.
Loss Function: CrossEntropyLoss with class-weighting (dataset me minor classes jaise ICMP/Replay ko handle karne ke liye).
Early stopping on validation Macro-F1.
Model Checkpointing & Provenance:
Weights .pt format me save karna along with metadata JSON (checksum, git commit, input dimensions, class mapping).
🔹 Milestone 1.5: Comparative Evaluation & CLI Command
Files to create/modify:

src/ipsec_sentinel/ml/sequence/evaluate.py
src/ipsec_sentinel/cli.py (Naye commands: sentinel model train-sequence, sentinel model compare)
tests/unit/test_sequence.py
tests/unit/test_sequence_models.py
Tasks:

Comparison Report:
Tabular XGBoost vs 1D-CNN vs TCN comparative summary print karna:
text
Model         Macro-F1   Bal-Acc    Params    p50 Latency
XGBoost       0.892      0.884      —         0.4 ms
1D-CNN        0.918      0.912      48.2K     1.2 ms
TCN           0.941      0.936      112.5K    2.1 ms
Unit & Property Tests:
Deterministic tensor extraction tests.
Shape integrity tests (batch size, channel count, sequence length).
Invariance to empty / padded sequences.
Code formatting aur linting: make lint aur make type clean rakhna.
🎯 Deliverables of Phase 1 (End State)
src/ipsec_sentinel/features/sequence.py — ESP packet sequence tensor builder.
src/ipsec_sentinel/ml/sequence/ — 1D-CNN & TCN implementations in PyTorch.
sentinel model train-sequence — Command-line tool sequence models train aur benchmark karne ke liye.
Comprehensive test coverage for all sequence components.
First research question answered: RQ1 — Can temporal packet-sequence models outperform handcrafted flow statistics for encrypted IPsec traffic?
Aap kaise start karna chahte hain?
Milestone 1.1 se start karein: features/sequence.py (raw packet-to-tensor extraction & dataset builder) implement karna?
Ya aap pehle dependencies (pyproject.toml me torch dependency entry) aur directory structure setup karna chahte hain?