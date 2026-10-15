# IPsec Sentinel

> **Passive IPsec protocol analysis, cryptographic compliance assessment, and automated zero-downtime remediation.**  
> Built for **Smart India Hackathon 2026 — Problem Statement 160**.

Point IPsec Sentinel at a network packet capture (`.pcap`) or a live interface; get back a graded, cited compliance assessment of every VPN tunnel in your estate, an AI-inferred traffic breakdown without payload decryption, and ready-to-deploy, zero-downtime configuration change packages for weak gateways.

---

## Table of Contents

- [1. Executive Summary & Core Philosophy](#1-executive-summary--core-philosophy)
  - [The Fundamental Problem](#the-fundamental-problem)
  - [Core Design Law: Facts vs Estimates](#core-design-law-facts-vs-estimates)
  - [The "Rekey Blind Spot" Problem](#the-rekey-blind-spot-problem)
- [2. End-to-End Architecture & Data Flow](#2-end-to-end-architecture--data-flow)
- [3. Deep Dive: How Each Component Works](#3-deep-dive-how-each-component-works)
  - [3.1 Parser & Correlation Engine (`parser/`)](#31-parser--correlation-engine-parser)
  - [3.2 Kernel State Ingestion (`collect.py` & `--device-state`)](#32-kernel-state-ingestion-collectpy---device-state)
  - [3.3 Deterministic Compliance & Scoring Engine (`assess/`)](#33-deterministic-compliance--scoring-engine-assess)
  - [3.4 Encrypted Traffic Inference via ML (`features/` & `ml/`)](#34-encrypted-traffic-inference-via-ml-features--ml)
  - [3.5 Automated Zero-Downtime Remediation Engine (`remediate/`)](#35-automated-zero-downtime-remediation-engine-remediate)
  - [3.6 Continuous Live Monitoring (`watch.py`)](#36-continuous-live-monitoring-watchpy)
  - [3.7 Web Dashboard & REST API (`dashboard/` & `api/`)](#37-web-dashboard--rest-api-dashboard--api)
- [4. Quickstart Guide](#4-quickstart-guide)
  - [Running via Docker (Recommended)](#running-via-docker-recommended)
  - [Running via Local Python](#running-via-local-python)
- [5. CLI Reference & Usage Workflows](#5-cli-reference--usage-workflows)
- [6. Security Posture of the Tool](#6-security-posture-of-the-tool)
- [7. Repository File Map](#7-repository-file-map)
- [8. Development & Verification](#8-development--verification)

---

## 1. Executive Summary & Core Philosophy

### The Fundamental Problem

Traditional network inspection tools like Wireshark or `tcpdump` show raw protocol bytes. When an engineer inspects an IPsec IKE exchange, Wireshark will decode that the two endpoints agreed on `ENCR_3DES` with `DH_GROUP_2` (1024-bit MODP). 

However, **Wireshark will not tell you**:
- That NIST disallowed 3DES and 1024-bit MODP in 2023.
- That this exchange is vulnerable to the **Logjam** attack (CVE-2015-4000) and **Sweet32** (CVE-2016-2183).
- That the tunnel violates national standards such as **CERT-In** or **NIST SP 800-77 Rev. 1**.
- Exactly what configuration commands must be executed on the specific gateway (Cisco, Fortinet, StrongSwan, etc.) to remediate it safely without cutting off production traffic.

**IPsec Sentinel bridges the gap between *visible* and *judged*.**

```
┌────────────────────────┐      ┌──────────────────────────────┐      ┌─────────────────────────────┐
│      Packet Capture    │ ───▶ │        IPsec Sentinel        │ ───▶ │  Actionable Intelligence    │
│  Raw IKE & ESP Packets │      │  Parse + Assess + Infer + Fix│      │  Grade, CVEs, Fix Script    │
└────────────────────────┘      └──────────────────────────────┘      └─────────────────────────────┘
```

---

### Core Design Law: Facts vs Estimates

One strict principle governs the entire codebase:

> **"Facts are parsed. Estimates are inferred."**

```
                          ┌────────────────────────┐
                          │   Parsed Packet Data   │
                          └───────────┬────────────┘
                                      │
                 ┌────────────────────┴────────────────────┐
                 ▼                                         ▼
     ┌────────────────────────┐               ┌────────────────────────┐
     │  Section A: Verified   │               │  Section B: Inferred   │
     │  Deterministic Facts   │               │  Machine Learning      │
     │  (Confidence: None)    │               │  (Calibrated Conf)     │
     │  From Cleartext IKE/SA │               │  From Encrypted ESP    │
     └────────────────────────┘               └────────────────────────┘
```

- **Section A (Verified Findings)**: Deterministic, cryptographic facts read from cleartext IKE headers and transforms. Every finding here carries `confidence = None`, cites standard clauses, and can withstand regulatory audit.
- **Section B (Inferred Findings)**: Behavioral intelligence derived from encrypted ESP flows (packet sizing, timings, directions). Every finding carries a calibrated confidence score and SHAP explanations. Payload data is **NEVER decrypted**.
- **Code-Enforced Separation**: A Pydantic validator (`Report.enforce_separation`) mathematically rejects the generation of any report that mixes an inference into Section A or a deterministic fact into Section B.

---

### The "Rekey Blind Spot" Problem

A standard packet capture tells you what a tunnel **negotiated** during setup. However, it cannot tell you what cryptographic parameters that tunnel is running **right now**.

**Why?**
1. In IKEv2, only `IKE_SA_INIT` is in cleartext.
2. Subsequent rekeying and child SAs are negotiated inside `CREATE_CHILD_SA`, which is **fully encrypted**.
3. A tunnel might establish with AES-256 and Group 19 (looking 100% secure on the wire), but silently rekey later to deprecated 3DES/MD5 in the Linux/gateway kernel.

```
Time ──▶
[IKE_SA_INIT: Cleartext] ──▶ AES-256 negotiated (Looks Strong on Wire!)
          │
[CREATE_CHILD_SA: Encrypted] ──▶ Silent rekey down to 3DES-CBC in Kernel! (Invisible to wire sniffers)
```

**How IPsec Sentinel Solves It**:
IPsec Sentinel accepts a read-only gateway state export (`ip xfrm state` or `swanctl --list-sas`) via the `--device-state` flag:
```bash
sentinel analyse capture.pcap --device-state gw-state.xfrm.txt
```
It cross-correlates the active kernel SA SPIs with the capture. If a tunnel rekeyed to an insecure cipher in the kernel, Sentinel flags it immediately—dropping an apparently healthy estate score from **33/100 down to 12/100**. This is done **passively without SSH credentials**.

---

## 2. End-to-End Architecture & Data Flow

```
                      ┌──────────────────────────────────────────┐
                      │ Input: PCAP file or Live Wire Interface  │
                      └────────────────────┬─────────────────────┘
                                           │
                                           ▼
                      ┌──────────────────────────────────────────┐
                      │    parser/ Custom Bounds-Safe Parser     │
                      │  - Decodes IKEv1 / IKEv2 / NAT-T 4500    │
                      │  - Reconstructs ESP Flow Assemblies      │
                      │  - Correlates SPIs & 5-Tuples to Tunnels │
                      └────────────────────┬─────────────────────┘
                                           │ Correlated Tunnel Objects
                     ┌─────────────────────┴─────────────────────┐
                     │                                           │
                     ▼                                           ▼
      ┌─────────────────────────────┐             ┌─────────────────────────────┐
      │     DETERMINISTIC LANE      │             │       INFERENCE LANE        │
      │  assess/rules/ (26 Rules)   │             │  features/ (42 Telemetry)   │
      │  NIST, BSI, CERT-In, CNSA   │             │  ml/ (RandomForest/XGBoost) │
      │  Device State Verification  │             │  Calibrated Confidence      │
      │  PQC Readiness (RFC 9370)   │             │  SHAP Explanations          │
      └──────────────┬──────────────┘             └──────────────┬──────────────┘
                     │ Section A Findings                        │ Section B Findings
                     └─────────────────────┬─────────────────────┘
                                           │
                                           ▼
                      ┌──────────────────────────────────────────┐
                      │    report/ Strict Two-Lane Aggregator    │
                      │  - Validates Section A / B separation    │
                      │  - Calculates weighted estate grade      │
                      └────────────────────┬─────────────────────┘
                                           │
             ┌─────────────────────────────┼─────────────────────────────┐
             ▼                             ▼                             ▼
   ┌───────────────────┐         ┌───────────────────┐         ┌───────────────────┐
   │  Human Interfaces │         │ Automated Fixes   │         │ SIEM / Security   │
   │  - HTML / PDF     │         │ - remediate/      │         │ - CEF / LEEF      │
   │  - Web Dashboard  │         │ - 6 Vendor Syntax │         │ - JSON Schema v1.3│
   │  - CLI output     │         │ - 0s Outage Steps │         │ - Syslog stream   │
   └───────────────────┘         └───────────────────┘         └───────────────────┘
```

---

## 3. Deep Dive: How Each Component Works

### 3.1 Parser & Correlation Engine (`parser/`)
Located in [`src/ipsec_sentinel/parser/`](src/ipsec_sentinel/parser/):

- **Bounds-Safe Byte Reader (`reader.py`)**: Custom binary stream parser with memory safety checks. Guarantees that truncated or crafted malicious packets cannot cause buffer over-reads or unhandled exceptions.
- **Payload Chain Walker (`chain.py`)**: Iterates through IKE payload chains using recursion-proof loop guards. If an attacker injects circular next-payload pointers, the parser terminates safely without stalling.
- **IKEv1 & IKEv2 Dissection (`ikev1.py`, `ikev2.py`)**:
  - Parses `IKE_SA_INIT`, `IKE_AUTH`, Proposals, Transforms, Key Exchange (KE), Nonces, Vendor IDs.
  - Detects IKEv1 **Aggressive Mode** and flags exposed Pre-Shared Key (PSK) hashes vulnerable to offline dictionary attacks.
  - Handles **NAT-Traversal (UDP 4500)** by stripping the 4-byte zero non-ESP marker (`0x00000000`) before decoding the encapsulated IKE payload.
- **ESP Flow Assembly (`esp.py`)**: Groups raw ESP packets by Security Parameter Index (SPI), source IP, destination IP, and protocol. Tracks sequence numbers to identify packet loss and replay window violations.
- **Tunnel Correlation (`correlate.py`)**: Connects the control plane (IKE) to the data plane (ESP). Matches negotiated initiator/responder SPIs with active ESP packet headers, assembling a unified `Tunnel` model.

---

### 3.2 Kernel State Ingestion (`collect.py` & `--device-state`)
Located in [`src/ipsec_sentinel/collect.py`](src/ipsec_sentinel/collect.py):

- **No Active Connections / No SSH**: The system strictly forbids running SSH or remote execution agents to protect against network credential exposure.
- **Offline Parser**: Operators provide read-only command output:
  - Linux Native: `ip xfrm state` and `ip xfrm policy`
  - strongSwan: `swanctl --list-sas`
- **Reconciliation**: Parses active encryption ciphers, auth algorithms, replay window sizes, and lifetime counters. If the kernel has downgraded an active SA compared to the wire capture, Sentinel generates an explicit `DEV-01` / `DEV-02` warning.

---

### 3.3 Deterministic Compliance & Scoring Engine (`assess/`)
Located in [`src/ipsec_sentinel/assess/`](src/ipsec_sentinel/assess/):

- **26 Deterministic Rules** ([`docs/RULES.md`](docs/RULES.md)):
  - **Cryptographic Algorithms (CRY-01 to CRY-10)**: 3DES, DES, Blowfish, RC4, MD5, SHA-1, weak DH groups (< 2048-bit MODP or weak elliptic curves).
  - **IKE Configuration (IKE-01 to IKE-04)**: Insecure aggressive mode, unauthenticated notifications, short cookie validation.
  - **Forward Secrecy & SAs (PFS-01 to SA-04)**: Rekey lifetimes > 24 hours or > 250 GB data, absence of Perfect Forward Secrecy.
  - **Anomalies (ANOMALY-01 to ANOMALY-04)**: Replay counter rollover, undocumented tunnel endpoints.
- **Multi-Standard Compliance Baselines**:
  - `nist_800_77r1`: NIST Special Publication 800-77 Revision 1.
  - `bsi_tr_02102_3`: German Federal Office for Information Security (BSI).
  - `cnsa_1_0`: Commercial National Security Algorithm Suite.
  - `cert_in`: Indian Computer Emergency Response Team directives.
  - `rfc_8221_8247`: Core cryptographic requirements for IPsec/IKEv2.
  - `itsar`: Indian Telecom Security Assurance Requirements.
- **Post-Quantum Cryptography (PQC) Grading**:
  - Inspects support for **RFC 9370** (Multiple Key Exchanges in IKEv2) and **RFC 8784** (Post-quantum Pre-Shared Keys - PPK).
- **Scoring Algorithm**:
  - Base score: 100 points.
  - Weighted deductions per finding severity (Critical: -40, High: -25, Medium: -10, Low: -3).
  - Letter Grade Mapping: A (90-100), B (80-89), C (70-79), D (60-69), F (< 60).

---

### 3.4 Encrypted Traffic Inference via ML (`features/` & `ml/`)
Located in [`src/ipsec_sentinel/features/`](src/ipsec_sentinel/features/) and [`src/ipsec_sentinel/ml/`](src/ipsec_sentinel/ml/):

- **Zero Decryption Principle**: Inspects only packet length, inter-arrival timing, burst dynamics, and directionality.
- **42 Flow Features Extracted**:
  - *Packet Size Distribution*: Mean, standard deviation, median, 25th/75th/90th percentiles, forward/backward size ratios.
  - *Inter-Arrival Time (IAT)*: Mean, std, median, 90th percentile jitter.
  - *Burst Dynamics*: Burst packet count, mean burst length, idle time between bursts.
  - *Entropy & Fractions*: Shannon size entropy, small packet fraction (< 128 bytes - indicator for VoIP/chat), MTU packet fraction.
- **Classifier & Explainability**:
  - Model: Calibrated Random Forest / XGBoost trained on laboratory traffic sweeps.
  - Predicts 7 traffic classes: `VoIP`, `Video`, `Web`, `Email`, `Messaging`, `ICMP`, `Replay`.
  - **Abstention Logic**: If class probability falls below threshold (ambiguous traffic), the model yields `Abstain` rather than hallucinating.
  - **SHAP (SHapley Additive exPlanations)**: Every inference provides top contributing flow features so operators understand why a tunnel was labeled VoIP or Bulk.

---

### 3.5 Automated Zero-Downtime Remediation Engine (`remediate/`)
Located in [`src/ipsec_sentinel/remediate/`](src/ipsec_sentinel/remediate/):

- **Multi-Vendor Configuration Generators**:
  - **strongSwan** (`swanctl.conf`)
  - **Libreswan** (`ipsec.conf`)
  - **Cisco ASA / IOS-XE** (`crypto ikev2 proposal`, `crypto ipsec profile`)
  - **Fortinet FortiGate** (`config vpn ipsec phase1-interface`)
  - **Juniper JunOS** (`set security ike proposal`, `set security ipsec proposal`)
  - **Palo Alto PAN-OS** (`set network ike crypto-profiles`)
- **Zero-Downtime Migration Sequencing**:
  - *The Danger*: Changing crypto on both peers simultaneously cuts traffic if one gateway applies the configuration before the other.
  - *The Fix*: Sentinel generates a **3-stage phased rollout**:
    1. **Stage 1 (Add Overlapping Proposal)**: Add the new secure proposal to Peer A without removing the legacy proposal.
    2. **Stage 2 (Switch Active Proposal)**: Switch Peer B to prefer the new proposal. Negotiation renegotiates cleanly to the new cipher with **0.00s downtime**.
    3. **Stage 3 (Deprecate Legacy Proposal)**: Remove the weak legacy cipher from Peer A.
- **Blast Radius & Verification**:
  - Calculates subnets, route dependencies, and estimated impact.
  - `sentinel verify-fix capture2.pcap` verifies whether the new wire capture actually eliminated the vulnerability.

---

### 3.6 Continuous Live Monitoring (`watch.py`)
Located in [`src/ipsec_sentinel/watch.py`](src/ipsec_sentinel/watch.py):

- Runs directly against a live network interface (e.g. `eth0`, `any`).
- Maintains an in-memory ring buffer of observed SAs and SPIs.
- **Drift Detection**: Alerts in real time if:
  - A new undocumented tunnel appears on the network (Shadow VPN alert).
  - An established tunnel rekeys to a weaker cipher suite.
  - Sequence numbers roll over or drop abnormally.
- Outputs structured logs, JSON, or SIEM CEF events.

---

### 3.7 Web Dashboard & REST API (`dashboard/` & `api/`)
Located in [`dashboard/`](dashboard/) and [`src/ipsec_sentinel/api/`](src/ipsec_sentinel/api/):

- **FastAPI Backend**:
  - `POST /api/v1/analyse`: Multipart upload of `.pcap` and optional device state files.
  - `GET /api/v1/tunnels`: Lists discovered tunnels and their individual security scores.
  - `GET /api/v1/report.pdf` / `report.html`: Downloads formatted executive reports.
- **Modern Dashboard UI**:
  - Built with Vanilla HTML5, CSS3, and JavaScript without bloatware frameworks.
  - Zero `unsafe-inline` scripts; strict **Content Security Policy (CSP)**.
  - Interactive estate grade dial, findings viewer, and tunnel drill-down tables.

---

## 4. Quickstart Guide

### Running via Docker (Recommended)

Docker provides an isolated, zero-dependency environment:

```bash
# 1. Clone repository
git clone https://github.com/PrashamJ17/SIH_PS160.git
cd SIH_PS160

# 2. Start the API engine and web dashboard
docker compose up -d
```
- Web Dashboard: **<http://127.0.0.1:8080>**
- REST API Documentation: **<http://127.0.0.1:8000/docs>**

Drop any PCAP from `demo/pcaps/` onto the web dashboard to see immediate analysis.

---

### Running via Local Python

Requirements: **Python 3.11+**

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install package with all extras
pip install -e ".[ml,api,report,dev]"

# 3. Verify installation
sentinel version
```

---

## 5. CLI Reference & Usage Workflows

| Command | Action | Transmits Packets? |
|---|---|:---:|
| `sentinel analyse` | Analyze pcap capture and generate reports | **No** (Passive) |
| `sentinel inventory` | Compare capture against approved `tunnels.yaml` | **No** (Passive) |
| `sentinel remediate` | Generate dual-ended vendor configuration fix | **No** (Passive) |
| `sentinel watch` | Live monitoring on network interface | **No** (Passive) |
| `sentinel scan` | Active capability scanning (requires `--i-have-authorisation`) | **Yes** (Active) |
| `sentinel model` | Train / evaluate encrypted traffic ML models | **No** (Local) |

### Common CLI Examples

#### 1. Analyze a Single Capture
```bash
sentinel analyse demo/pcaps/01-worst-ikev1-aggressive-3des-voip.pcap --out report.html
```

#### 2. Full Audit with Device State, Inventory, and PDF Export
```bash
sentinel analyse demo/pcaps/04-estate.pcap \
  --baseline nist_800_77r1 \
  --known demo/tunnels.yaml \
  --device-state demo/state/gw-chennai.xfrm.txt \
  --out report.html \
  --pdf report.pdf \
  --json report.json
```

#### 3. Identify Undocumented Rogue VPNs
```bash
sentinel inventory demo/pcaps/04-estate.pcap --known demo/tunnels.yaml
```

#### 4. Generate Zero-Downtime strongSwan Fix
```bash
sentinel remediate demo/pcaps/01-worst-ikev1-aggressive-3des-voip.pcap \
  --vendor strongswan \
  --out ./remediation_package/
```

#### 5. Live Interface Monitoring
```bash
sentinel watch eth0 --baseline nist_800_77r1
```

---

## 6. Security Posture of the Tool

IPsec Sentinel is designed for high-security, defense, and sovereign enterprise environments:

1. **Air-Gapped Operation**: Runs completely offline without internet connectivity. Verified under Docker `--network none`.
2. **Zero-Credential Guarantee**: The tool never asks for, stores, or transmits passwords, private keys, or SSH credentials.
3. **No Device Write Permissions**: Contains no SSH, Telnet, NETCONF, or vendor API clients. An automated AST code scanner verifies this in `tests/unit/test_security.py`.
4. **Memory & Parsing Safety**: Custom bounds-checked byte reading prevents buffer overflows and denial-of-service vulnerabilities.
5. **Zero Vulnerabilities**: Checked against `pip-audit` with zero reported CVE advisories across all dependencies.

---

## 7. Repository File Map

```text
SIH_PS160/
├── src/ipsec_sentinel/         # Core application package
│   ├── parser/                 # Binary IKEv1, IKEv2, NAT-T, and ESP decoders
│   ├── assess/                 # 26 Rules, Compliance Baselines, PQC grader
│   ├── collect.py              # Kernel SA state parser (ip xfrm, swanctl)
│   ├── features/               # 42-feature telemetry extractor
│   ├── ml/                     # ML models, calibration, abstention, SHAP
│   ├── remediate/              # Multi-vendor zero-downtime config generators
│   ├── report/                 # HTML, PDF, JSON, and SIEM renderers
│   ├── watch.py                # Live interface drift monitor
│   ├── probe.py                # Active IKE capability prober
│   ├── api/                    # FastAPI REST routes and endpoints
│   └── cli.py                  # CLI command entry point (`sentinel`)
├── dashboard/                  # Lightweight Web UI (HTML5 / Vanilla JS / CSS)
├── demo/                       # Sample PCAP captures, state dumps, and demo assets
│   ├── pcaps/                  # Bundled real testbed captures
│   ├── state/                  # Sample gateway kernel state files
│   └── IPsec-Sentinel-demo.mp4 # Recorded video walkthrough
├── docs/                       # Technical documentation set
│   ├── ARCHITECTURE.md         # Two-lane design specifications
│   ├── RULES.md                # Full registry of all 26 security rules
│   ├── COMPLIANCE_BASELINES.md # Standard citations (NIST, BSI, CERT-In)
│   ├── WALKTHROUGH.md          # 20-minute evaluator walkthrough
│   └── LIMITATIONS.md          # Clear operational boundaries
├── testbed/                    # Docker testbed with strongSwan and traffic generators
├── tests/                      # 2,600+ unit and integration tests (100% coverage)
├── Dockerfile                  # Production container definition (non-root UID 10001)
├── docker-compose.yml          # Container orchestration for API + Dashboard
└── Makefile                    # Single-entrypoint build and test orchestrator
```

---

## 8. Development & Verification

To run the complete verification suite (code formatting, static typing, and 2,600+ unit tests):

```bash
make verify
```

To run integration tests with Docker testbeds and live network emulation:

```bash
make verify-all
```

---

## License & Attribution

Developed by **Team Highlanders** for **Smart India Hackathon (SIH) 2026**.  
Problem Statement: **160** — *Passive IPsec Protocol Analysis and Security Assessment*.
