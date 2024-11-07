import json
import importlib
import subprocess
import sys
from flask import Flask, render_template, send_from_directory
import os

# ANSI escape codes for colored output
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

# Function to check and install libraries
def check_and_install_libraries(libraries):
    for lib, import_name in libraries.items():
        try:
            importlib.import_module(import_name)
            print(f"[{GREEN}✔{RESET}] Library '{lib}' is already installed.")
        except ImportError:
            print(f"[{RED}✖{RESET}] Library '{lib}' is not installed. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

# Load libraries from the JSON file
def load_libraries_from_json(file_path):
    try:
        with open(file_path, 'r') as file:
            libraries = json.load(file)
        return libraries
    except FileNotFoundError:
        print(f"[{RED}✖{RESET}] JSON file '{file_path}' not found!")
        return {}

# Define the path to the JSON file
json_file_path = 'static/json/lib.json'

# Load the libraries from the JSON file
libraries = load_libraries_from_json(json_file_path)

# If libraries are found in the JSON file, check and install them
if libraries:
    check_and_install_libraries(libraries)
else:
    print(f"[{RED}✖{RESET}] No libraries found in '{json_file_path}'.")

app = Flask(__name__)

# Serve files from the 'assets' folder
@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(os.path.join(app.root_path, 'assets'), filename)

# Serve files from the 'assets2' folder
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

# Custom error handler for 404 Not Found
@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)
