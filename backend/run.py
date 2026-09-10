#!/usr/bin/env python
"""启动后端服务：uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
