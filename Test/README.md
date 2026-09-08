                    ┌──────────────────────┐
                    │   PCAP / PCAPNG      │
                    │   VPN Configuration  │
                    └──────────┬───────────┘
                               │
                               ▼
                 ┌─────────────────────────┐
                 │ Packet Ingestion Layer   │
                 │ Scapy / PyShark / tshark │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ Protocol Identification  │
                 │ IKE / ESP / AH / UDP/IP │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ Feature Extraction       │
                 │ Protocol + Timing +      │
                 │ Crypto + Session         │
                 └────────────┬────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
          ┌──────────────────┐ ┌──────────────────┐
          │ Rule Engine      │ │ ML Engine        │
          │ Security Rules   │ │ Anomaly Detection│
          └────────┬─────────┘ └────────┬─────────┘
                   │                    │
                   └─────────┬──────────┘
                             ▼
                  ┌──────────────────────┐
                  │ Risk Assessment      │
                  │ Score + Severity     │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ Explainability       │
                  │ SHAP / Feature       │
                  │ Importance            │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ Recommendation Engine│
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ PostgreSQL           │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ FastAPI              │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │ React Dashboard       │
                  └──────────────────────┘
