#!/usr/bin/env python3
# ABOUTME: Simple test server to verify basic FastAPI functionality
# ABOUTME: Minimal server test for troubleshooting agent server issues

import uvicorn
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok", "message": "Simple test server is running"}


@app.get("/")
async def root():
    return {"message": "Test server root"}


if __name__ == "__main__":
    print("🚀 Starting simple test server on port 8002...")
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
