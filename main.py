import os
import uvicorn

if __name__ == "__main__":
    # Support cloud deployment (Railway, Render, Fly.io, Cloud Run) and local dev
    port = int(os.getenv("PORT", 8000))
    # In cloud environments PORT is set, bind to 0.0.0.0; locally default to 127.0.0.1
    host = os.getenv("HOST", "0.0.0.0" if os.getenv("PORT") else "127.0.0.1")
    reload = os.getenv("ENV", "development").lower() == "development" and not bool(os.getenv("PORT"))

    print(f"Starting RepoViva Graph server on http://{host}:{port}")
    uvicorn.run("repoviva.api:app", host=host, port=port, reload=reload)
