import json
import importlib
import subprocess
import sys

# ANSI escape codes for colored output
GREEN = "\033[92m"  # Green text
RED = "\033[91m"    # Red text
RESET = "\033[0m"   # Reset to default color

# Function to check and install libraries
def check_and_install_libraries(libraries):
    for lib, import_name in libraries.items():
        try:
            # Attempt to import the library
            importlib.import_module(import_name)
            print(f"[{GREEN}✔{RESET}] Library '{lib}' is already installed.")
        except ImportError:
            # If import fails, try to install the library
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

from flask import Flask, render_template, send_from_directory
import os  # os module is already part of Python, no need to install it

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

@app.route('/404')
def page_not_found():
    return render_template('404.html')

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

if __name__ == '__main__':
    app.run(debug=True)