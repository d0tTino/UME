from pathlib import Path
import argparse
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn


def create_app(directory: str) -> FastAPI:
    app = FastAPI()
    app.mount("/dashboard", StaticFiles(directory=directory, html=True), name="dashboard")
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the UME dashboard")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument(
        "--dir",
        default=str(Path(__file__).parent / "dist"),
        help="Directory containing the built frontend",
    )
    args = parser.parse_args()

    app = create_app(args.dir)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
