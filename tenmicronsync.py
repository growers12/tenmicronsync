import socket
import signal
import sys
import time
import requests
import argparse

class NINAWeather:
    def __init__(self, ip_address):
        self.base_url = f"http://{ip_address}:1888/api/equipment?property=weather"

    def call_api(self):
        """Makes an API call to retrieve weather data."""
        try:
            response = requests.get(self.base_url)
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                return {"Error": f"Failed to get data: {response.status_code}"}
        except requests.exceptions.RequestException as e:
            return {"Error": f"An error occurred: {e}"}

    def getTemperatureAndPressure(self):
        """Retrieves temperature and pressure from the API and returns them."""
        data = self.call_api()
        response = data.get('Response', {})
        temperature = response.get('Temperature')
        pressure = response.get('Pressure')
        if temperature is not None and pressure is not None:
            return (temperature, pressure)
        else:
            return ("Error: Temperature and/or pressure data missing.",)

class TenMicronManager:
    def __init__(self, ip, port=3490):
        self.ip = ip
        self.port = port
        self.connection = None
        # Set up signal handling for graceful termination
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, signal_received, frame):
        """Handles clean-up when SIGINT (Ctrl-C) is received."""
        print("\nSignal received, closing connection.")
        self.close()
        sys.exit(0)  # Exit gracefully

    def connect(self):
        """Establishes a socket connection to the specified IP and port."""
        for attempt in range(3):  # Retry up to three times
            try:
                self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.connection.connect((self.ip, self.port))
                print(f"Connected to {self.ip} on port {self.port}.")
                return
            except socket.error as e:
                print(f"Attempt {attempt + 1}: An error occurred: {e}")
                self.close()
                if attempt == 2:  # Raise exception if all attempts fail
                    raise ConnectionError(f"Failed to connect after several attempts: {e}")

    def close(self):
        """Closes the socket connection."""
        if self.connection:
            self.connection.close()
            print("Connection closed.")
            self.connection = None

def main(nina_ip, tenmicron_ip, nosync, interval):
    nina = NINAWeather(nina_ip)
    tenmicron = TenMicronManager(tenmicron_ip)
    tenmicron.connect()
    while True:
        try:
            data = nina.getTemperatureAndPressure()
            if len(data) == 2 and all(isinstance(x, (float, int)) for x in data):
                temperature, pressure = data
                print(f"Temperature from NINA: {temperature} °C")
                print(f"Pressure from NINA: {pressure} hPa")
                
                if not nosync:
                    # Sync the values to the TenMicron system if not in no-sync mode
                    tenmicron.setTemperature(temperature)
                    tenmicron.setPressure(pressure)

                print("\n")
                time.sleep(interval)  # Wait for the specified interval before next update
            else:
                print("Error: No valid weather data received from NINA.")
                time.sleep(interval)  # Wait for the specified interval before retrying
        except KeyboardInterrupt:
            print("\nExiting...")
            tenmicron.close()
            sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Connect to NINA and TenMicron systems and optionally sync data.')
    parser.add_argument('--ninaip', default='127.0.0.1', help='IP address for NINA system')
    parser.add_argument('--tenmicronip', default='1.1.1.1', help='IP address for TenMicron system')
    parser.add_argument('--nosync', action='store_true', help='Do not sync data to the TenMicron system')
    parser.add_argument('--interval', type=int, default=1800, help='Interval in seconds between updates')

    args = parser.parse_args()

    main(args.ninaip, args.tenmicronip, args.nosync, args.interval)
