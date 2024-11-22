from flask import Flask, render_template, redirect, url_for, request, session, send_from_directory, jsonify, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import json, importlib, subprocess, sys, os, time, logging, bleach 

# ======================================== Auto Installer ========================================
# ANSI escape codes for colored output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# Global flag to prevent redundant library loading messages
libraries_loaded = False

def colored_output(message, color):
    """Print the message with the given color for the tick or cross."""
    # Color only the tick or cross, not the entire message
    if "[✔]" in message:
        print(f"{color}[✔]{RESET} {message[3:]}")
    elif "[✖]" in message:
        print(f"{color}[✖]{RESET} {message[3:]}")
    else:
        print(message)

def check_and_install_libraries(libraries):
    """Check if libraries are installed and install them if needed."""
    global libraries_loaded
    if libraries_loaded:
        return  # Prevent redundant checks once libraries are loaded

    for lib, import_name in libraries.items():
        try:
            importlib.import_module(import_name)
            colored_output(f"[✔] Library '{lib}' is already installed.", GREEN)
        except ImportError:
            colored_output(f"[✖] Library '{lib}' is not installed. Attempting to install...", YELLOW)
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
                colored_output(f"[✔] Successfully installed '{lib}'.", GREEN)
            except subprocess.CalledProcessError:
                colored_output(f"[✖] Failed to install '{lib}'. Please install it manually.", RED)

    libraries_loaded = True

def load_libraries_from_json(file_path):
    """Load libraries from a JSON file."""
    if not os.path.exists(file_path):
        colored_output(f"[✖] JSON file '{file_path}' not found!", RED)
        return {}
    try:
        with open(file_path, 'r') as file:
            libraries = json.load(file)
        colored_output(f"[✔] Loaded libraries from '{file_path}'.", GREEN)
        return libraries
    except json.JSONDecodeError:
        colored_output(f"[✖] Error parsing JSON file '{file_path}'. Check file format.", RED)
        return {}

# Load libraries from JSON and check/install them
json_file_path = 'static/json/lib.json'
libraries = load_libraries_from_json(json_file_path)
if libraries:
    check_and_install_libraries(libraries)
else:
    colored_output(f"[✖] No valid libraries found in '{json_file_path}'.", RED)

# ======================================== Flask app Setup ========================================
app = Flask(__name__)

# Secret key for sessions
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))

# Session lifetime configuration
app.permanent_session_lifetime = timedelta(minutes=60)

# ======================================== Constants ========================================
USER_JSON_PATH = "static/json/credentials.json"
DEFAULT_PFP = 'default.png'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE = 10 * 1024 * 1024

# Log folder configuration
log_folder = "chatbot-logs"
os.makedirs(log_folder, exist_ok=True)

# ======================================== Helper Functions ========================================

# Save user credentials with pretty formatting
def save_credentials_pretty(data):
    try:
        with open(USER_JSON_PATH, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving to {USER_JSON_PATH}: {e}")

# Check if an email already exists
def email_exists(email):
    try:
        if os.path.exists(USER_JSON_PATH):
            with open(USER_JSON_PATH, 'r') as f:
                users = json.load(f)
                return any(user['email'] == email for user in users)
    except Exception as e:
        print(f"Error reading {USER_JSON_PATH}: {e}")
    return False

# Authenticate a user
def authenticate_user(email, password):
    try:
        if os.path.exists(USER_JSON_PATH):
            with open(USER_JSON_PATH, 'r') as f:
                users = json.load(f)
                return next(
                    (user for user in users if user['email'] == email and check_password_hash(user['password'], password)),
                    None
                )
    except Exception as e:
        print(f"Error reading {USER_JSON_PATH}: {e}")
    return None

# Sanitize user input to prevent XSS
def sanitize_input(input_data):
    return bleach.clean(input_data)

# Load all user credentials
def load_credentials():
    try:
        if os.path.exists(USER_JSON_PATH):
            with open(USER_JSON_PATH, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error loading {USER_JSON_PATH}: {e}")
        return []

# Log cleanup function
def clear_logs():
    for file_name in os.listdir(log_folder):
        file_path = os.path.join(log_folder, file_name)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file {file_name}: {e}")

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

# Query Ollama AI with retries
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

# ======================================== Routes ========================================

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory('assets', filename)

@app.route('/assets2/<path:filename>')
def serve_assets2(filename):
    return send_from_directory('assets2', filename)

@app.route('/check-email', methods=['POST'])
def check_email():
    email = sanitize_input(request.json.get('email'))
    return jsonify({"exists": email_exists(email)})

@app.route('/clear-cookies', methods=['POST'])
def clear_cookies():
    resp = make_response('Cookies cleared')
    resp.delete_cookie('BBAIcurrentuser')
    resp.delete_cookie('BBAIemail')
    print('Cookies cleared')
    return resp

@app.route('/signout')
def signout():
    session.pop('user', None)  # Clear user session
    resp = make_response(redirect(url_for('index')))  # Redirect to the homepage after clearing session
    resp.set_cookie('BBAIemail', '', expires=0)  # Clear the cookies
    resp.set_cookie('BBAIcurrentuser', '', expires=0)
    return resp

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/faqs')
def faqs():
    current_user_name = request.cookies.get('BBAIcurrentuser')
    if not current_user_name:  # If no user is logged in
        return redirect(url_for('login'))  # Redirect to login page

    user_data = load_credentials()
    current_user = next((user for user in user_data if user['name'] == current_user_name), None)
    
    if current_user:
        profile_pic = current_user.get('profile_pic')
        if not profile_pic or not os.path.exists(f"static/img/PFPs/{profile_pic}"):
            profile_pic = 'default.png'  # Fallback to default if the image doesn't exist

        profile_pic_path = f"static/img/PFPs/{profile_pic}"
        return render_template('faqs.html', profile_pic=profile_pic_path)
    else:
        # Handle case when the user isn't found in the credentials file
        return redirect(url_for('login'))  # Redirect to login if user not found


@app.route('/in-dev')
def in_dev():
    return render_template('in-dev.html')

@app.route('/chatbot')
def chatbot():
    current_user_name = request.cookies.get('BBAIcurrentuser')
    if not current_user_name:  # If no user is logged in
        return redirect(url_for('login'))  # Redirect to login page

    user_data = load_credentials()
    current_user = next((user for user in user_data if user['name'] == current_user_name), None)
    
    if current_user:
        profile_pic = current_user.get('profile_pic')
        if not profile_pic or not os.path.exists(f"static/img/PFPs/{profile_pic}"):
            profile_pic = 'default.png'  # Fallback to default if the image doesn't exist

        profile_pic_path = f"static/img/PFPs/{profile_pic}"
        return render_template('chatbot.html', profile_pic=profile_pic_path)
    else:
        # Handle case when the user isn't found in the credentials file
        return redirect(url_for('login'))  # Redirect to login if user not found

# Define the chatbot API endpoint
@app.route("/chatbot", methods=["POST"])
def chatbot_api():
    user_input = request.json.get("prompt", "")
    print(f"Received prompt from user: {user_input}")
    response = query_ollama(user_input)
    print(f"Sending response back to user: {response}")
    return jsonify({"response": response})

@app.route('/dashboard')
def dashboard():
    current_user_name = request.cookies.get('BBAIcurrentuser')
    if current_user_name:
        user_data = load_credentials()
        current_user = next((user for user in user_data if user['name'] == current_user_name), None)
        if current_user:
            # Attempt to get the profile picture, falling back to 'default.png' if it's unavailable or invalid
            profile_pic = current_user.get('profile_pic')
            if not profile_pic or not os.path.exists(f"static/img/PFPs/{profile_pic}"):
                profile_pic = 'default.png'  # Fallback to default if the image doesn't exist

            profile_pic_path = f"static/img/PFPs/{profile_pic}"
            return render_template('dashboard.html', profile_pic=profile_pic_path)
    
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            email = sanitize_input(data.get('email'))
            password = sanitize_input(data.get('password'))
            user = authenticate_user(email, password)
            
            if user:
                session['user'] = user['email']
                resp = make_response(jsonify({
                    "success": True,
                    "message": "Login successful",
                    "redirect": url_for('dashboard'),
                    "name": user['name']
                }))
                resp.set_cookie('BBAIcurrentuser', user['name'], max_age=timedelta(days=30), httponly=False, path='/')
                resp.set_cookie('BBAIemail', user['email'], max_age=timedelta(days=30), httponly=False, path='/')
                return resp
            else:
                return jsonify({"success": False, "message": "Incorrect email or password"})
        return jsonify({"success": False, "message": "Request must be JSON"})

    email = request.cookies.get('BBAIemail')
    name = request.cookies.get('BBAIcurrentuser')
    if email and name:
        session['user'] = email
        return redirect(url_for('dashboard'))
    return render_template('login.html')

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

            existing_users = load_credentials()
            existing_users.append(user_data)
            save_credentials_pretty(existing_users)

            resp = make_response(jsonify({"success": True, "message": "Account created successfully!"}))
            resp.set_cookie('BBAIcurrentuser', name, max_age=timedelta(days=30), httponly=False, path='/')
            resp.set_cookie('BBAIemail', email, max_age=timedelta(days=30), httponly=False, path='/')

            return resp
        
        except Exception as e:
            return jsonify({"success": False, "message": "Server error"}), 500

    return render_template('signup.html')

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# ======================================== Run the Application ========================================
if __name__ == '__main__':
    # Run the app without debug-level logs from Flask
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=1000)