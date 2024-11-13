import json
import importlib
import subprocess
import sys
from flask import Flask, render_template, send_from_directory, request, jsonify
import os
import time
import logging
from datetime import datetime

# ANSI escape codes for colored output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# Global flag to prevent redundant library loading messages
libraries_loaded = False

# Function to check and install libraries
def check_and_install_libraries(libraries):
    global libraries_loaded
    if libraries_loaded:
        return  # Prevent further output once libraries are loaded
    for lib, import_name in libraries.items():
        try:
            importlib.import_module(import_name)
            print(f"[{GREEN}✔{RESET}] Library '{lib}' is already installed.")
        except ImportError:
            print(f"[{YELLOW}✖{RESET}] Library '{lib}' is not installed. Attempting to install...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
                print(f"[{GREEN}✔{RESET}] Successfully installed '{lib}'.")
            except subprocess.CalledProcessError:
                print(f"[{RED}✖{RESET}] Failed to install '{lib}'. Please install it manually.")
    libraries_loaded = True

# Load libraries from JSON
def load_libraries_from_json(file_path):
    if not os.path.exists(file_path):
        print(f"[{RED}✖{RESET}] JSON file '{file_path}' not found!")
        return {}
    try:
        with open(file_path, 'r') as file:
            libraries = json.load(file)
        print(f"[{GREEN}✔{RESET}] Loaded libraries from '{file_path}'.")
        return libraries
    except json.JSONDecodeError:
        print(f"[{RED}✖{RESET}] Error parsing JSON file '{file_path}'. Check file format.")
        return {}

# Define path to JSON file and load libraries
json_file_path = 'static/json/lib.json'
libraries = load_libraries_from_json(json_file_path)
if libraries:
    check_and_install_libraries(libraries)
else:
    print(f"[{RED}✖{RESET}] No valid libraries found in '{json_file_path}'.")

app = Flask(__name__)

# Serve files from 'assets' and 'assets2' folders
@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(os.path.join(app.root_path, 'assets'), filename)

@app.route('/assets2/<path:filename>')
def serve_assets2(filename):
    return send_from_directory(os.path.join(app.root_path, 'assets2'), filename)

# Main routes for HTML pages
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')

# Log folder path
log_folder = "chatbot-logs"

# Ensure the 'chatbot-logs' folder exists
os.makedirs(log_folder, exist_ok=True)

# Cleanup function to delete all log files in the 'chatbot-logs' folder
def clear_logs():
    for file_name in os.listdir(log_folder):
        file_path = os.path.join(log_folder, file_name)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"{YELLOW}Deleted log file: {file_name}{RESET}")
        except Exception as e:
            print(f"Error deleting file {file_name}: {e}")

# Run the cleanup function at startup
clear_logs()

# Generate a filename with the current date and time for the new log
log_filename = datetime.now().strftime("ollama_query_%d-%m-%Y_%H:%M.log")
log_path = os.path.join(log_folder, log_filename)

# Create a custom logger for Ollama
ollama_logger = logging.getLogger("ollama_logger")
ollama_logger.setLevel(logging.INFO)

# Configure file handler only for the Ollama logger
file_handler = logging.FileHandler(log_path)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
ollama_logger.addHandler(file_handler)

def query_ollama(prompt, retries=3, delay=2):
    for attempt in range(retries):
        try:
            ollama_logger.info(f"Attempt {attempt + 1}: Sending prompt to Ollama.")
            result = subprocess.run(
                ['ollama', 'run', 'tinyllama:1.1b-chat'],
                input=prompt,
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                ollama_logger.info("Ollama responded successfully.")
                return result.stdout.strip()
            else:
                ollama_logger.warning(f"Attempt {attempt + 1} failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            ollama_logger.warning("Timeout occurred. Retrying...")

        except FileNotFoundError:
            ollama_logger.error("Ollama executable not found.")
            return "Ollama could not be found. Please check if it's installed correctly."

        except Exception as e:
            ollama_logger.error(f"Unexpected error on attempt {attempt + 1}: {str(e)}")

        time.sleep(delay)

    ollama_logger.error("All attempts to reach Ollama failed.")
    return "I'm sorry, your question could not be answered right now! Please contact admin for assistance."


# Define the chatbot API endpoint
@app.route("/chatbot", methods=["POST"])
def chatbot_api():
    user_input = request.json.get("prompt", "")
    print(f"Received prompt from user: {user_input}")
    response = query_ollama(user_input)
    print(f"Sending response back to user: {response}")
    return jsonify({"response": response})

# Additional routes
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/faqs')
def faqs():
    return render_template('faqs.html')

@app.route('/in-dev')
def in_dev():
    return render_template('in-dev.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/sign-up')
def sign_up():
    return render_template('sign-up.html')

# Error handler for 404
@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404

if __name__ == '__main__':
    # Run the app without debug-level logs from Flask
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=1000)