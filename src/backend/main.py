"""Dev entrypoint: `python main.py` runs the API with auto-reload.

In production, prefer running uvicorn directly:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
