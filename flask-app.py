from flask import Flask, render_template, redirect, url_for, request, session, send_from_directory, jsonify, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import json, importlib, subprocess, sys, os, time, logging, bleach 

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
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))  # Use a secure secret key
app.permanent_session_lifetime = timedelta(minutes=60)  # Session expiry after 60 minutes of inactivity


USER_JSON_PATH = os.path.join(app.static_folder, 'json/credentials.json')  # Path to 'static/credentials.json'
DEFAULT_PFP = 'static/img/PFPs/default.png'  # Default Profile Picture
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit for profile pictures

# Serve files from 'assets' folders
@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory('assets', filename)

@app.route('/assets2/<path:filename>')
def serve_assets2(filename):
    return send_from_directory('assets2', filename)

# Function to pretty-print and write to the credentials JSON file
def save_credentials_pretty(data):
    try:
        with open(USER_JSON_PATH, 'w') as f:
            json.dump(data, f, indent=4)  # Pretty-print with 4 spaces for indentation
    except Exception as e:
        print(f"Error saving to {USER_JSON_PATH}: {e}")

# Function to check if the email already exists in the database (credentials.json)
def email_exists(email):
    if os.path.exists(USER_JSON_PATH):
        with open(USER_JSON_PATH, 'r') as f:
            existing_users = json.load(f)
            return any(user['email'] == email for user in existing_users)
    return False  # Email does not exist

# Function to authenticate user based on email and password
def authenticate_user(email, password):
    if os.path.exists(USER_JSON_PATH):
        with open(USER_JSON_PATH, 'r') as f:
            users = json.load(f)
            return next((user for user in users if user['email'] == email and check_password_hash(user['password'], password)), None)
    return None  # Invalid credentials

# Sanitize input to avoid XSS
def sanitize_input(input_data):
    return bleach.clean(input_data)

def load_credentials():
    try:
        if os.path.exists(USER_JSON_PATH):
            with open(USER_JSON_PATH, 'r') as f:
                return json.load(f)
        return []  # Return empty list if file doesn't exist
    except Exception as e:
        print(f"Error loading {USER_JSON_PATH}: {e}")
        return []
    
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

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            email = sanitize_input(data.get('email'))
            password = sanitize_input(data.get('password'))
            remember_me = data.get('rememberMe', False)
            
            user = authenticate_user(email, password)
            
            if user:
                session['user'] = user['email']
                
                if remember_me:
                    resp = make_response(jsonify({
                        "success": True,
                        "message": "Login successful",
                        "redirect": url_for('dashboard'),
                        "name": user['name']
                    }))
                    resp.set_cookie('email', user['email'], max_age=timedelta(days=30), secure=True, httponly=True)
                    resp.set_cookie('name', user['name'], max_age=timedelta(days=30), secure=True, httponly=True)
                    return resp
                
                return jsonify({
                    "success": True,
                    "message": "Login successful",
                    "redirect": url_for('dashboard'),
                    "name": user['name']
                })
            else:
                user_check = check_email(email)
                if not user_check:
                    return jsonify({"success": False, "message": "Email not found"})
                else:
                    return jsonify({"success": False, "message": "Incorrect password"})
        
        return jsonify({"success": False, "message": "Request must be JSON"})
    
    email = request.cookies.get('email')
    name = request.cookies.get('name')
    if email and name:
        session['user'] = email
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/check-email', methods=['POST'])
def check_email():
    email = sanitize_input(request.json.get('email'))
    return jsonify({"exists": email_exists(email)})

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            data = request.get_json()
            name = sanitize_input(data.get('name'))
            email = sanitize_input(data.get('email'))
            password = sanitize_input(data.get('password'))
            confirm_password = sanitize_input(data.get('confirmPassword'))

            if not all([name, email, password, confirm_password]):
                return jsonify({"success": False, "message": "Invalid input"}), 400

            if email_exists(email):
                return jsonify({"success": False, "message": "An account with this email already exists."}), 400

            if password != confirm_password:
                return jsonify({"success": False, "message": "Passwords do not match"}), 400

            if len(password) < 8 or not any(char.isdigit() for char in password):
                return jsonify({"success": False, "message": "Password must be at least 8 characters long and include a number"}), 400

            hashed_password = generate_password_hash(password)

            user_data = {"name": name, "email": email, "password": hashed_password, "profile_pic": DEFAULT_PFP}

            existing_users = []
            if os.path.exists(USER_JSON_PATH):
                with open(USER_JSON_PATH, 'r') as f:
                    existing_users = json.load(f)

            existing_users.append(user_data)
            save_credentials_pretty(existing_users)  # Save with pretty formatting

            return jsonify({"success": True, "message": "Account created successfully!"})
        
        except Exception as e:
            return jsonify({"success": False, "message": "Server error"}), 500

    return render_template('signup.html')

@app.route('/signout')
def signout():
    session.pop('user', None)

    resp = make_response(redirect(url_for('index')))
    resp.set_cookie('email', '', expires=0)
    resp.set_cookie('name', '', expires=0)

    return resp

# Error handler for 404
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/clear-cookies', methods=['POST'])
def clear_cookies():
    resp = make_response('Cookies cleared')
    resp.delete_cookie('email')
    resp.delete_cookie('name')
    return resp

if __name__ == '__main__':
    # Run the app without debug-level logs from Flask
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=1000)