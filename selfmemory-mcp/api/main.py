import datetime
import os

from app.mcp_server import lifespan, setup_mcp_server
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configuration
USER_ID = os.getenv("USER_ID", "default")
DEFAULT_APP_ID = os.getenv("DEFAULT_APP_ID", "selfmemory")

# Initialize FastAPI app with lifespan for MCP session management
app = FastAPI(
    title="SelfMemory API",
    description="Memory operations API with MCP protocol support",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup MCP server
setup_mcp_server(app)


@app.get("/")
def read_root():
    return {"message": "SelfMemory API", "status": "running"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8765"))

    uvicorn.run(app, host=host, port=port)
