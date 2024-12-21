from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import os

app = FastAPI()

CHUNKS_DIRECTORY = "Data/chunks-sharks-1080p"

@app.get("/getPodIP")
async def getPodIP():
    pod_ip = os.getenv("POD_IP")
    return f"Pod IP: {pod_ip}"

@app.get("/chunks")
async def get_chunks():
    chunk_files = os.listdir(CHUNKS_DIRECTORY)
    chunk_files.sort()
    return {"chunks": chunk_files}

@app.get("/stream/{chunk_name}")
async def stream_chunk(chunk_name: str):
    chunk_path = os.path.join(CHUNKS_DIRECTORY, chunk_name)
    if not os.path.exists(chunk_path):
        raise HTTPException(status_code=404, detail="Chunk not found")
    return StreamingResponse(open(chunk_path, "rb"), media_type="video/mp4")
