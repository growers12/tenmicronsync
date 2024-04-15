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

    def send_command(self, command):
        """Sends a command through the socket and reads a one-line response."""
        if self.connection:
            try:
                self.connection.sendall(command.encode())
                return self.receive_response()
            except socket.error:
                print("Connection error on sending command, attempting to reconnect...")
                self.connect()
                return self.send_command(command)  # Retry sending command after reconnecting

    def receive_response(self):
        """Receives a one-line response from the socket."""
        try:
            response = self.connection.recv(1024).decode()
            return response.strip()  # Stripping to ensure it's a clean one-line response
        except socket.error as e:
            print(f"Receive error: {e}, trying to reconnect...")
            self.connect()
            return self.receive_response()  # Retry receiving response after reconnecting

    def setPressure(self, pressure):
        """Sets the pressure used in the refraction model."""
        command = f":SRPRS{pressure:.1f}#"  # Format pressure to one decimal place
        response = self.send_command(command)
        return response == "1"

    def setTemperature(self, temperature):
        """Sets the temperature used in the refraction model."""
        command = f":SRTMP{temperature:+06.1f}#"  # Format temperature to 6 characters wide with one decimal
        response = self.send_command(command)
        return response == "1"

    def getPressure(self):
        """Retrieves the pressure by sending :GRPRS# and parsing the response."""
        response = self.send_command(":GRPRS#")
        if response:
            pressure_str = response.rstrip('#')  # Remove trailing '#' character
            try:
                pressure = float(pressure_str)
                return pressure
            except ValueError:
                return None
        else:
            print("Failed to get pressure response")
            return None

    def getTemperature(self):
        """Retrieves the temperature by sending :GRTMP# and parsing the response."""
        response = self.send_command(":GRTMP#")
        if response:
            temperature_str = response.rstrip('#')  # Remove trailing '#' character
            try:
                temperature = float(temperature_str)
                return temperature
            except ValueError:
                return None
        else:
            print("Failed to get temperature response")
            return None

    def close(self):
        """Closes the socket connection."""
        if self.connection:
            self.connection.close()
            print("Connection closed.")
            self.connection = None

def main(nina_ip, tenmicron_ip):
    nina = NINAWeather(nina_ip)
    tenmicron = TenMicronManager(tenmicron_ip)
    tenmicron.connect()
    while True:
        try:
            data = nina.getTemperatureAndPressure()
            if len(data) == 2:  # Ensure both temperature and pressure are present
                temperature, pressure = data
                print(f"Temperature from NINA: {temperature} °C")
                print(f"Pressure from NINA: {pressure} hPa")
                tenmicron.setTemperature(temperature)
                tenmicron.setPressure(pressure)
                # Read back the data from TenMicronManager
                retrieved_temperature = tenmicron.getTemperature()
                retrieved_pressure = tenmicron.getPressure()
                if retrieved_temperature is not None:
                    print(f"Verified temperature: {retrieved_temperature} °C")
                if retrieved_pressure is not None:
                    print(f"Verified pressure: {retrieved_pressure} hPa")
                print("\n")
                time.sleep(60)  # Wait for one minute before next update
            else:
                print("Error: Temperature and/or pressure data not available.")
                time.sleep(60)  # Wait for one minute before retrying
        except KeyboardInterrupt:
            print("\nExiting...")
            tenmicron.close()
            sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Connect to NINA and TenMicron systems.')
    parser.add_argument('--ninaip', default='127.0.0.1', help='IP address for NINA system')
    parser.add_argument('--tenmicronip', default='1.1.1.1', help='IP address for TenMicron system')

    args = parser.parse_args()

    main(args.ninaip, args.tenmicronip)
