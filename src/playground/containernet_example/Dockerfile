# Use an official Python runtime as a parent image
FROM python:3.8-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY server.py /app
COPY requirements.txt /app

RUN apt-get update && apt-get install -y \
    net-tools \
    iputils-ping \
    iproute2 \
    curl \
    procps \
    wget

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

# Run app.py when the container launches
CMD ["python", "server.py"]
