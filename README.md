# Intergalactic Temporal Internet Server (ITIS) 🌌

Welcome to the **Intergalactic Temporal Internet Server (ITIS)**, a revolutionary platform for temporal communication and file sharing across the Temporal Informational Universe. ITIS powers secure, offline temporal email and internet-based file sharing, enabling agents to send and retrieve messages across time offsets (`past`, `present`, `future`) using a 256x256x256 checksum map. Built for the ChronoVoyager crew, ITIS leverages **MPI parallel processing**, **hybrid quantum code verification**, and **AI-driven query optimization** to deliver high-performance, scalable communication.

[![ChronoVoyager](https://img.shields.io/badge/ChronoVoyager-ITIS-blueviolet)](https://github.com/[your_github_username]/itis)
![Test Results](https://img.shields.io/badge/Email%20Retrieval-95%25%20(19%2F20)-green)
![Performance](https://img.shields.io/badge/Performance-~2.8ms%2Fpacket-blue)

## 🌟 Features

- **Offline Temporal Email**: Send and retrieve messages across `past`, `present`, and `future` offsets, stored in `cells.db` with CRC-32C checksums.
- **Preset Checksum Ranges**: Agents (A, B, C) use fixed ranges (e.g., Agent A: `0x00000000–0x7FFFFFFF`) for precise email searches.
- **Internet-Based File Sharing**: Share temporal data via HTTP (`TemporalServer.py:/temporal_share`).
- **MPI Parallel Processing**: Uses `mpi4py` with OpenMPI for scalable checksum formatting, encoding, and searches across 4+ nodes.
- **Hybrid Security**: Combines quantum codes (`Xorshift128Plus.py`) with SHA-256 signatures for robust verification.
- **Tiered Caching**: 1GB in-memory cache and 1TB disk storage with zlib compression (`TemporalStorage.py`).
- **Temporal Email GUI**: Intuitive interface in `WebBrowser.py` for sending/retrieving emails.
- **AI Feedback Loop**: Optimizes Grok 3 queries with precision (0.9) and recall (0.85) in `grok_trainer.py`.
- **Scalability**: Supports 4.295B checksums, 100,000+ packets, and 16+ nodes.
- **Immediate Invalid File Deletion**: Ensures data integrity by removing invalid packets.

## 🚀 Quick Start

### Prerequisites
- **Python**: 3.8+
- **Dependencies**: `mpi4py`, `numpy`, `crc32c`, `requests`, `transformers`, `scikit-learn`, `tkinter`, `lru`
- **MPI**: OpenMPI (local cluster)
- **Grok 3 API**: Optional for AI queries (free tier or SuperGrok at $30/month, see [xAI API](https://x.ai/api))
- **Hardware**: 4+ nodes recommended for MPI, 1GB memory, 1TB disk

### Installation
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/[your_github_username]/itis.git
   cd itis
