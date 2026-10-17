🗺️ Master Implementation Roadmap (Phases 1 to 4)
mermaid
flowchart LR
    P1["Phase 1 (Week 1)<br/><b>Temporal Sequence ML</b><br/>(CNN, TCN, Packet Tensors)"] 
    --> P2["Phase 2 (Week 2)<br/><b>Self-Supervised & OOD</b><br/>(Contrastive SSL, Open-Set)"]
    --> P3["Phase 3 (Week 3)<br/><b>Security & Robustness</b><br/>(Anomaly, C2, Traffic Morphing)"]
    --> P4["Phase 4 (Week 4)<br/><b>Production Streaming</b><br/>(ONNX, NetEm Generalization)"]
🟢 PHASE 1: Temporal Packet-Sequence Modeling (Immediate Next)
Goal: Handcrafted tabular 42 features (XGBoost) ke sath-sath raw packet sequences se deep temporal patterns (burst dynamics, inter-arrival jitter, directionality transitions) learn karna.

Milestone	File / Module	Kya Implement Hoga?
1.1 Sequence Tensor Pipeline	src/ipsec_sentinel/features/sequence.py	• Har ESP packet se 3-tuple extract karna: [packet_size, IAT, direction]
• Sliding windows ($N = 64, 128, 256$ packets)
• Zero-padding aur validity/attention masks for short flows
• PyTorch Dataset & DataLoader integration
1.2 Tabular Baseline Benchmarking	src/ipsec_sentinel/ml/baseline.py	• Existing XGBoost / Random Forest ka grouped cross-validation score freeze karna (Macro-F1, ECE, Latency)
• Deep models se compare karne ke liye ground truth file save karna
1.3 Deep Sequence Encoders	src/ipsec_sentinel/ml/sequence/cnn.py
src/ipsec_sentinel/ml/sequence/tcn.py
src/ipsec_sentinel/ml/sequence/models.py	• 1D-CNN: Multi-kernel convolutions (3, 5, 7) burst patterns capture karne ke liye
• TCN: Dilated causal convolutions ($d=1,2,4,8,16$) long-range beaconing ke liye
• 128-dimensional unified Flow Embedding vector export
1.4 Sequence Training Engine	src/ipsec_sentinel/ml/sequence/train.py	• PyTorch training loop (AdamW, Cosine Annealing, Class-weighted CrossEntropy)
• Capture-grouped splitting taaki test data me data leakage na ho
1.5 Comparative Evaluation & CLI	src/ipsec_sentinel/ml/sequence/evaluate.py
src/ipsec_sentinel/cli.py	• sentinel model train-sequence --arch tcn
• Tabular XGBoost vs 1D-CNN vs TCN comparative report
🟡 PHASE 2: Self-Supervised Learning & Open-Set (OOD) Detection (Week 2)
Goal: Labeled data ki kami ko door karna aur anjaan (unknown) traffic aane par galat guess lagane ke bajaye "Unknown" ya "Abstain" bolna.

Component	File / Module	Kya Implement Hoga?
Self-Supervised Pretraining (SSL)	src/ipsec_sentinel/ml/ssl/augmentations.py
src/ipsec_sentinel/ml/ssl/contrastive.py	• Unlabeled encrypted flows par Contrastive Learning (SimCLR style)
• Protocol-aware data augmentations (timing jitter, packet masking, MTU-constrained size perturbations)
• Pretrained Flow Encoder jo bina labels ke traffic representations seekh sake
Open-Set / OOD Detection	src/ipsec_sentinel/ml/ood/mahalanobis.py
src/ipsec_sentinel/ml/ood/energy.py	• Test traffic sample agar 7 known classes se bahar ka ho, to use detect karna
• Mahalanobis distance & Energy-based scoring layer
Decision & Abstention Engine	src/ipsec_sentinel/ml/decision.py	• Final decision logic: KNOWN, UNKNOWN, SUSPICIOUS, ya ABSTAIN ("Insufficient Evidence")
🟠 PHASE 3: Security Anomaly Detection & Traffic Morphing Robustness (Week 3)
Goal: Encrypted tunnels ke andar malicious behavior (C2 beacons, Exfiltration) pakadna, aur adversarial attacks (traffic padding/morphing) se model ko defend karna.

Component	File / Module	Kya Implement Hoga?
Encrypted Flow Anomaly Detection	src/ipsec_sentinel/ml/anomaly/deep_svdd.py
src/ipsec_sentinel/ml/anomaly/ensemble.py	• Application classification se alag Security Anomaly Detection
• Deep SVDD + Isolation Forest ensemble
• Exfiltration flows (abnormal upload-heavy) aur covert channels identify karna
Periodicity & Spectral Analysis	src/ipsec_sentinel/features/spectral.py	• FFT-based dominant frequency, autocorrelation, aur burst interval analysis (Cobalt Strike / C2 beaconing detection)
Traffic Morphing Engine	src/ipsec_sentinel/ml/robustness/morphing.py	• Adversarial evasion simulator: Packet padding, dummy packet injection, timing jitter
• Test karna ki kya attacker model ko fool kar sakta hai
Adversarial Training	src/ipsec_sentinel/ml/robustness/adversarial.py	• Morphed traffic ke sath model ko retrain karna taaki model tamper-proof ban sake
🟣 PHASE 4: Generalization, ONNX Optimization & Streaming Inference (Week 4)
Goal: Laboratory se nikaal kar production enterprise network me high-throughput deployment ready karna.

Component	File / Module	Kya Implement Hoga?
Cross-Network Generalization	testbed/netem/
scripts/generalisation_report.py	• Linux NetEm ke through alag-alag MTU (576, 1200, 1500), Latency (5ms to 100ms), aur Packet Loss par model ki robustness evaluate karna
Production ONNX Export	src/ipsec_sentinel/ml/deployment/export_onnx.py	• PyTorch models ko ONNX format me convert karna
• FP32, FP16, aur INT8 quantization benchmarks (p50, p95, p99 latency)
Real-Time Streaming Inference	src/ipsec_sentinel/ml/deployment/streaming.py	• Flow khatam hone ka wait kiye bina first 32, 64 packets aate hi live streaming predictions generate karna
🎯 Abhi Hum Kahan Hain Aur Next Kya Shuru Karein?
Hum bilkul Phase 1 ke Milestone 1.1 par khade hain:

src/ipsec_sentinel/features/sequence.py file banayenge.
Har ESP packet se sequence tensor builder ([size, IAT, direction]) aur sliding window engine likhenge.
Uske tests likhkar verify karenge.
Kya main Phase 1 -> Milestone 1.1 (sequence.py) likhna shuru karoon?