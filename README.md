# Semantix

Semantic labeling and training pipeline with async ingestion, human-in-the-loop labeling, and automated training dataset generation.

## Features

- **Async File Ingestion**: Watch `/input` directory or POST files via API
- **Semantic Labeling**: Human UI in NiceGUI for voting/labeling items
- **Auto-labeling**: Optional LLM-based auto-labeling (Ollama/OpenAI)
- **Vote Thresholds**: Configurable approval gates based on votes and quality
- **Training Pipeline**: Stream approved items → featureize → write Parquet datasets
- **Live Telemetry**: WebSocket updates for real-time progress
- **Reproducible Artifacts**: Versioned datasets by hash

## Tech Stack

- **FastAPI**: Async REST API and WebSocket endpoints
- **NiceGUI**: Modern Python UI framework
- **Redis**: Primary store with streams and pub/sub
- **Polars + PyArrow**: Fast data processing and Parquet writing
- **Arq**: Async Redis-based task queue
- **watchfiles**: Async directory watcher

## Quick Start

### Docker Compose (Recommended)

```bash
# Start all services
make up

# View logs
make logs

# Stop services
make down
```

The application will be available at:
- **UI**: http://localhost:8080
- **API**: http://localhost:8080/backend/api

### Development Setup

```bash
# Install dependencies
make install

# Run development server
make dev
```

## Project Structure

```
semantix/
├── semantix/
│   ├── api/          # FastAPI routes and WebSocket
│   ├── ui/           # NiceGUI pages and components
│   ├── ingest/       # File watcher and parsers
│   ├── store/        # Redis helpers and schemas
│   ├── labeling/     # Voting logic and auto-labeling
│   ├── train/        # Training pipeline and workers
│   └── utils/        # Utilities (hashing, textnorm, logging)
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── README.md
```

## Configuration

Environment variables (see `semantix/config.py`):

- `REDIS_URL`: Redis connection URL (default: `redis://localhost:6379/0`)
- `VOTE_THRESHOLD`: Minimum vote score for approval (default: `3`)
- `QUALITY_MIN`: Minimum quality score (default: `1`)
- `INPUT_DIR`: Directory to watch for files (default: `/data/input`)
- `ARTIFACTS_DIR`: Output directory for training datasets (default: `./artifacts`)
- `AUTO_LABEL_ENABLED`: Enable auto-labeling (default: `false`)
- `OLLAMA_BASE_URL`: Ollama API URL (default: `http://localhost:11434`)
- `OLLAMA_MODEL`: Ollama model name (default: `llama2`)

## API Endpoints

### REST API

- `POST /api/ingest` - Ingest text or file
- `GET /api/item/{id}` - Get item details
- `POST /api/vote/{id}` - Cast a vote
- `POST /api/moderate/{id}` - Admin approve/reject
- `POST /api/train/kick` - Enqueue training job
- `GET /api/metrics` - Get metrics
- `GET /api/items` - List items

### WebSocket

- `WS /ws` - Live updates (ingest, votes, training progress)

## Usage

### 1. Ingest Files

Drop files into `/data/input` or POST to `/api/ingest`:

```bash
# Via API
curl -X POST http://localhost:8080/backend/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "Your text content here", "source": "api:test"}'

# Or upload file
curl -X POST http://localhost:8080/backend/api/ingest/file \
  -F "file=@/path/to/file.txt"
```

### 2. Label Items

Use the NiceGUI UI at http://localhost:8080:
- Navigate to **Inbox** to see pending items
- Click an item to view details
- Cast votes (positive/negative, quality)
- Items auto-approve when threshold is met

### 3. Train Dataset

- Navigate to **Training** page
- Configure filters (label, quality, size)
- Start training job
- Monitor progress via WebSocket
- Download Parquet files from `./artifacts/`

## Redis Key Schema

- `semx:item:{sha256}` - Item payload (JSON)
- `semx:votes:{sha256}` - Votes (HASH: `label:{name}` = int, `quality` = int)
- `semx:voters:{sha256}` - Voter IDs (SET)
- `semx:status:{sha256}` - Status: "voting" | "approved" | "rejected"
- `semx:stream:ingest` - Ingest events (Redis Stream)
- `semx:stream:approved` - Approval events (Redis Stream)
- `semx:stream:training` - Training progress (Redis Stream)
- `semx:index:pending` - Pending item IDs (SET)
- `semx:index:approved` - Approved item IDs (SET)
- `semx:events` - Pub/sub channel for WebSocket events

## Threshold Rule

An item is **approved** when:
```
sum(label:positive) - sum(label:negative) >= VOTE_THRESHOLD
AND
quality >= QUALITY_MIN
```

## Auto-labeling

Enable auto-labeling with Ollama:

```bash
# Set environment variables
export AUTO_LABEL_ENABLED=true
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama2

# Start Ollama (if not running)
ollama serve
```

Auto-labeling runs heuristics or LLM-based labeling on ingested items.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
make test

# Format code
black semantix/

# Lint code
ruff check semantix/
```

## License

MIT

