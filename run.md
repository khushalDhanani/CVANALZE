# CV Analyzer - How to Run

This document outlines the steps required to run the CV Analyzer pipeline, including the FastAPI backend, the asynchronous RQ workers, the CLI batch processor, and the new React Native frontend.

## 1. Prerequisites

Before starting the application, ensure the following services are running:

- **Redis Server**: Used for the task queue and PubSub event streaming.
  ```bash
  redis-server
  ```
- **Ollama**: Used for local LLM semantic matching. Ensure the required model is pulled.
  ```bash
  ollama serve
  ```

## 2. Environment Setup

Ensure your `.env` file is present in the `backend` directory. It should contain the MSSQL connection details (if using the remote DB) and any other configuration overrides.

> **macOS Note**: Due to `PyTorch` (used by `docling`) fork-safety issues on macOS, you **MUST** prefix commands that spawn workers or run ML models with `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`.

## 3. Starting the Backend

The backend code is located in the `backend/` directory. You should run these commands in separate terminal tabs, making sure to `cd backend` in each one.

### A. Start the RQ Workers (Background Processing)
The background workers process the heavy CV extraction and LLM matching tasks. You can start one or more workers:

```bash
cd backend
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run python start_worker.py
```
*(To scale up, simply open another terminal, `cd backend`, and run the exact same command to spawn a second worker).*

### B. Start the FastAPI Server (Web API & WebSockets)
The FastAPI server exposes the REST endpoints and the real-time WebSocket progress endpoint.

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```
*(The API documentation will be available at http://localhost:8000/docs)*

### C. Run the CLI Batch Processor (Testing)
If you want to manually trigger a batch scan of the `uploads/` directory from the terminal (instead of calling the FastAPI endpoint), run:

```bash
cd backend
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run python main.py
```

Because of our recent PubSub optimization, this command will instantly print real-time progress events as the background workers complete each CV, and then exit automatically once the batch is fully processed.

## 4. Testing the WebSocket (Optional)
If you want to verify that real-time events are being broadcasted to connected clients, you can run the test script while a batch is processing:

```bash
cd backend
uv run python test_ws.py
```

## 5. Starting the Frontend (React Native)

The UI code is located in the `frontend/` directory.

To start the React Native development server (Expo):

```bash
cd frontend
npm start
```
From here, you can press `w` to open it in a web browser, `i` to open an iOS simulator, or `a` for Android.
