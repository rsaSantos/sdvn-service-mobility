import requests
import time
import sys
import signal
import configparser
import requests
import cv2
from queue import Queue
import threading
import os
from datetime import datetime

SLEEP_TIME = 1
UP_TIME = 0
DOWN_TIME = 0

FETCH_THREAD = None
FETCH_THREAD_RUNNING = False

def signal_handler(sig, frame):
    global FETCH_THREAD, FETCH_THREAD_RUNNING, UP_TIME, DOWN_TIME

    print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Program exiting due to user interrupt")
    if FETCH_THREAD is not None:
        FETCH_THREAD_RUNNING = False
        FETCH_THREAD.join()

    with open("client.log", "a") as f:
        f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Uptime: {UP_TIME}\n")
        f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Downtime: {DOWN_TIME}\n")
        
    print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Uptime: {UP_TIME}")
    print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Downtime: {DOWN_TIME}")

    sys.exit(0)

def get_chunks_list(SERVER_URL):
    chunks = None
    while chunks is None:
        try:
            response = requests.get(f"{SERVER_URL}/chunks")
            chunks = response.json()["chunks"]
        except requests.exceptions.ConnectionError:
            print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Connection error while fetching chunks list, retrying in {SLEEP_TIME}s...")
            with open("client.log", "a") as f:
                f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Connection error while fetching chunks list, retrying in {SLEEP_TIME}s...\n")
            time.sleep(SLEEP_TIME)
            continue
    
    return chunks    

def get_chunk(SERVER_URL, chunk_name):
    try:
        response = requests.get(f"{SERVER_URL}/stream/{chunk_name}", stream=True, timeout=10)
        return response.raw.read()
    except Exception as e:
        print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Error fetching chunk {chunk_name}: {e}")
        with open("client.log", "a") as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Error fetching chunk {chunk_name}: {e}\n")
        return None

def fetch_chunks(server_url, chunks_list, chunk_queue):
    global FETCH_THREAD_RUNNING, SLEEP_TIME

    FETCH_THREAD_RUNNING = True
    fetched_count = 0
    while fetched_count < len(chunks_list):
        if not FETCH_THREAD_RUNNING:
            return

        chunk_name = chunks_list[fetched_count]
        chunk_data = get_chunk(server_url, chunk_name)
        pod_ip = requests.get(f"{server_url}/getPodIP").text
        if chunk_data is not None:
            chunk_queue.put((chunk_name, chunk_data))
            fetched_count += 1
            print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Fetched {chunk_name} from {pod_ip}")
            with open("client.log", "a") as f:
                f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Fetched {chunk_name} from {pod_ip}\n")
        else:
            # Wait for a while before retrying
            time.sleep(SLEEP_TIME)

def main(SERVER_URL):
    global UP_TIME, SLEEP_TIME, DOWN_TIME, FETCH_THREAD

    chunks_list = get_chunks_list(SERVER_URL)
    chunk_queue = Queue()

    FETCH_THREAD = threading.Thread(target=fetch_chunks, args=(SERVER_URL, chunks_list, chunk_queue))
    
    FETCH_THREAD.start()

    cv2.namedWindow("Video", cv2.WINDOW_NORMAL)

    while FETCH_THREAD.is_alive() or not chunk_queue.empty():
        try:
            start_time = time.perf_counter()
            if not chunk_queue.empty():
                chunk_name, chunk_data = chunk_queue.get()

                temp_filename = f"temp_{chunk_name}"
                with open(temp_filename, "wb") as f:
                    f.write(chunk_data)
                
                video_capture = cv2.VideoCapture(temp_filename)
                while video_capture.isOpened():
                    ret, frame = video_capture.read()
                    if not ret:
                        break
                    cv2.imshow("Video", frame)
                    if cv2.waitKey(40) & 0xFF == ord('q'):
                        break
                
                with open("client.log", "a") as f:
                    f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Displayed: {chunk_name}\n")
                print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Displayed: {chunk_name}")
                
                video_capture.release()
                os.remove(temp_filename)

            end_time = time.perf_counter()
            UP_TIME += (end_time - start_time)
        except requests.exceptions.ConnectionError:
            end_time = time.perf_counter()
            DOWN_TIME += (end_time - start_time) + SLEEP_TIME
            with open("client.log", "a") as f:
                    f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Connection error, retrying...\n")
            print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} : Connection error, retrying...")
            time.sleep(SLEEP_TIME)
            continue
        
    cv2.destroyAllWindows()

if __name__ == '__main__':
    if len(sys.argv) != 1:
        print("This script takes no arguments!")
        sys.exit(1)
    
    configPath = '../client.ini'
    config = configparser.ConfigParser()
    config.read_file(open(configPath))
    SERVER_IP = config.get('DEFAULT', 'bootstrap_worker_ip')
    
    signal.signal(signal.SIGINT, signal_handler)
    
    port = 30001
    if SERVER_IP == 'localhost':
        port = 8080
    main(f"http://{SERVER_IP}:{port}")
