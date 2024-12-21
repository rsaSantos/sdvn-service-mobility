from fastapi import FastAPI

import os

app = FastAPI()

@app.get("/getPodIP")
async def getPodIP():
    pod_ip = os.getenv("POD_IP")
    return f"Pod IP: {pod_ip}"


@app.get("/")
async def root():
    return {"message": "Hello World"}