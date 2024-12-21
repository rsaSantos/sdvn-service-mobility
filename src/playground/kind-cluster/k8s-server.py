from flask import Flask, request
import socket
import os

app = Flask(__name__)

@app.route('/')
def get_ip():
    pod_ip = os.getenv("POD_IP")
    return f"Pod IP: {pod_ip}\n"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
