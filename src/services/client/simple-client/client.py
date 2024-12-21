import requests
import time
import sys
import signal
import configparser

SLEEP_TIME = 1
UP_TIME = 0
DOWN_TIME = 0

def signal_handler(sig, frame):
    print('Program exiting due to user interrupt')

    with open("client.log", "a") as f:
        f.write(f'Uptime: {UP_TIME}\n')
        f.write(f'Downtime: {DOWN_TIME}\n')
        
    print(f'Uptime: {UP_TIME}')
    print(f'Downtime: {DOWN_TIME}')

    sys.exit(0)

def main(SERVER_IP):
    global UP_TIME, SLEEP_TIME, DOWN_TIME

    while True:
        try:
            start_time = time.perf_counter()
            response = requests.get("http://" + SERVER_IP + ":30001/getPodIP")

            time.sleep(SLEEP_TIME)

            end_time = time.perf_counter()
            UP_TIME += (end_time - start_time)
        except requests.exceptions.ConnectionError:
            end_time = time.perf_counter()
            DOWN_TIME += (end_time - start_time) + SLEEP_TIME
            print("Connection error, retrying...")
            time.sleep(SLEEP_TIME)
            continue
        
        with open("client.log", "a") as f:
            f.write(f'{response.text}\n')
        print(response.text)

if __name__ == '__main__':
    if len(sys.argv) != 1:
        print("This script takes no arguments!")
        sys.exit(1)
    
    configPath = '../client.ini'
    config = configparser.ConfigParser()
    config.read_file(open(configPath))
    SERVER_IP = config.get('DEFAULT', 'bootstrap_worker_ip')
    
    signal.signal(signal.SIGINT, signal_handler)
    main(SERVER_IP)
