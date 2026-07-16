# Deployment

This guide starts AxiomOps locally with Docker Compose and the React console.

## Prerequisites

- Python 3.11+
- Docker Desktop
- Node.js 20+

## Python Environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Start Services

Start the fault lab:

```powershell
.\scripts\start_lab.ps1
```

Start the control plane and infrastructure:

```powershell
.\scripts\start_control_plane.ps1
```

Useful local URLs:

| Service | URL |
| --- | --- |
| Control Plane API | `http://127.0.0.1:18000/docs` |
| Order service | `http://127.0.0.1:18001/docs` |
| Inventory service | `http://127.0.0.1:18002/docs` |
| Prometheus | `http://127.0.0.1:19090` |

## Start Console

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL printed in the terminal.

## Optional Model Configuration

The RCA runtime can use a DeepSeek-compatible chat endpoint. Put local credentials in `.env`; the file is ignored by Git.

```text
DEEPSEEK_MODEL=deepseek-v4-pro
```

Keep credential values only in local environment files or shell sessions.

## Stop Services

```powershell
.\scripts\stop_control_plane.ps1
.\scripts\stop_lab.ps1
```

To reset local database volumes:

```powershell
docker compose -f ops-control-plane/docker-compose.yml down -v
```
