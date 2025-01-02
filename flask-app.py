import os
import sys
import re
import pandas as pd
import time
import json
import logging
import subprocess
import importlib
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Any, List, Optional
import chardet

import bleach
from flask import (
    Flask, render_template, redirect, url_for, request, session,
    send_from_directory, jsonify, make_response, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ============================= Colored Output for Installation ===================================
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def colored_output(message: str, color: str) -> None:
    """
    Print the message with the given color for the tick or cross.
    Color only the tick or cross, not the entire message.
    """
    if "[✔]" in message:
        print(f"{color}[✔]{RESET} {message[3:]}")
    elif "[✖]" in message:
        print(f"{color}[✖]{RESET} {message[3:]}")
    else:
        print(message)

# ============================= Automatic Library Installer ========================================
class LibraryInstaller:
    """
    A class to handle library installation checks, ensuring we only check/install once.
    """
    _libraries_loaded = False

    @classmethod
    def load_libraries_from_json(cls, file_path: str) -> Dict[str, str]:
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

    @classmethod
    def check_and_install_libraries(cls, libraries: Dict[str, str]) -> None:
        """Check if libraries are installed and install them if needed."""
        if cls._libraries_loaded:
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

        cls._libraries_loaded = True

# ============================= Constants and Configuration ========================================
CREDENTIALS_FILE = "static/json/credentials.json"
USER_DATA_FILE = "static/json/users.json"
DEFAULT_PFP = 'default.png'
TEACHABLE_MACHINE_URL = "https://teachablemachine.withgoogle.com/models/M6fwGM3tz/"
AUTHENTICATION_TOKEN = 'a123'  # For protected endpoints
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_TAGS = ['b', 'i', 'u', 'strong', 'em']  # Basic text formatting
ALLOWED_ATTRIBUTES = {}
ALLOWED_PROTOCOLS = []

# Log folder configuration
LOG_FOLDER = "chatbot-logs"
os.makedirs(LOG_FOLDER, exist_ok=True)

# ============================= Utility / Helper Functions =========================================
def save_credentials_pretty(data: List[Dict[str, Any]]) -> None:
    """Save user credentials with pretty JSON formatting."""
    try:
        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving to {CREDENTIALS_FILE}: {e}")

def email_exists(email: str) -> bool:
    """Check if an email already exists in the credentials file."""
    try:
        if os.path.exists(CREDENTIALS_FILE):
            with open(CREDENTIALS_FILE, 'r') as f:
                users = json.load(f)
                return any(user['email'] == email for user in users)
    except Exception as e:
        print(f"Error reading {CREDENTIALS_FILE}: {e}")
    return False

def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user by email and password."""
    try:
        if os.path.exists(CREDENTIALS_FILE):
            with open(CREDENTIALS_FILE, 'r') as f:
                users = json.load(f)
                return next(
                    (user for user in users
                     if user['email'] == email and check_password_hash(user['password'], password)),
                    None
                )
    except Exception as e:
        print(f"Error reading {CREDENTIALS_FILE}: {e}")
    return None

def is_valid_email(email: str) -> bool:
    """
    Validates an email address format using a regex pattern and checks the domain.
    """
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_regex, email):
        return False
    
    # Additional domain validation (optional)
    domain = email.split('@')[-1]
    if len(domain) > 253 or not re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", domain):
        return False
    
    # Check for reserved or local domains
    invalid_domains = ["localhost", "example.com", "test", "invalid"]
    if domain in invalid_domains:
        return False

    return True

def sanitize_input(input_data: str) -> str:
    """Clean user input with Bleach, allowing only specified tags and no attributes/protocols."""
    return bleach.clean(
        input_data,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True
    )

def load_credentials() -> List[Dict[str, Any]]:
    """Load all user credentials from the JSON file."""
    try:
        if os.path.exists(CREDENTIALS_FILE):
            with open(CREDENTIALS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading {CREDENTIALS_FILE}: {e}")
    return []

def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Retrieve the currently logged-in user by cookie.
    Returns the user object if found, or None otherwise.
    """
    current_user_name = request.cookies.get('BBAIcurrentuser')
    if not current_user_name:
        return None
    
    user_data = load_credentials()
    return next((user for user in user_data if user['name'] == current_user_name), None)

def clear_logs() -> None:
    """Clears old log files from the log folder."""
    for file_name in os.listdir(LOG_FOLDER):
        file_path = os.path.join(LOG_FOLDER, file_name)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file {file_name}: {e}")

def authenticate(token: str) -> bool:
    """Return True if the provided token matches the authentication token, False otherwise."""
    return token == AUTHENTICATION_TOKEN

def login_required(f):
    """
    Decorator to ensure that a route can only be accessed if the user is logged in.
    Otherwise, the user is redirected to the login page.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.cookies.get('BBAIcurrentuser'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def authenticate_and_send_file(token: str, file_path: str):
    """Authenticate and send a static file to the client, or abort with 403 if unauthorized."""
    if authenticate(token):
        print('Authenticated, sending', file_path, 'to the client...')
        return send_from_directory('static', file_path)
    else:
        abort(403)

# ============================= Ollama / Chatbot Setup ============================================
def setup_ollama_logger() -> logging.Logger:
    """
    Sets up a logger dedicated to Ollama interactions and returns it.
    """
    # Clear any old logs first
    clear_logs()

    # Generate a filename with the current date and time for the new log
    log_filename = datetime.now().strftime("ollama_query_%d-%m-%Y_%H:%M.log")
    log_path = os.path.join(LOG_FOLDER, log_filename)

    # Create and configure the Ollama logger
    ollama_logger = logging.getLogger("ollama_logger")
    ollama_logger.setLevel(logging.INFO)

    # Configure file handler only for the Ollama logger
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    ollama_logger.addHandler(file_handler)

    return ollama_logger

# Function to detect encoding of the CSV file
def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read())
    return result['encoding']

# Function to query Ollama with the CSV and prompt
def query_ollama_with_csv(prompt):
    try:
        # Automatically determine the absolute path of the CSV file
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Directory of the script
        CSV_FILE_PATH = os.path.join(BASE_DIR, "static", "menu.csv")

        # Detect the encoding of the CSV file
        encoding = detect_encoding(CSV_FILE_PATH)
        print(f"Detected encoding: {encoding}")

        # Read the CSV file using the detected encoding
        df = pd.read_csv(CSV_FILE_PATH, encoding=encoding)
        csv_data = df.to_string(index=False)  # Convert CSV data to a readable string

        # Combine the CSV data and the user's prompt
        combined_prompt = f"Here is the data from the CSV file:\n{csv_data}\n\n{prompt}"
        print(f"Sending prompt to Ollama with CSV: {combined_prompt}")  # Debugging log

        # Interact with the LLM
        result = subprocess.run(
            ['ollama', 'run', 'orca-mini:latest'],
            input=combined_prompt,
            capture_output=True, text=True, shell=True
        )
        response = result.stdout.strip()

        if result.stderr:
            print(f"Error output: {result.stderr}")
        print(f"Ollama response: {response}")
        
        return response
    except Exception as e:
        print(f"Error querying Ollama with CSV: {str(e)}")
        return f"Error querying Ollama: {str(e)}"

# ============================= Flask App Factory ================================================
def create_app() -> Flask:
    """
    Create and configure the Flask application.
    This function can be imported and called from a WSGI server or directly run.
    """
    # Load and check/install libraries from JSON
    json_file_path = 'static/json/lib.json'
    libraries = LibraryInstaller.load_libraries_from_json(json_file_path)
    if libraries:
        LibraryInstaller.check_and_install_libraries(libraries)
    else:
        colored_output(f"[✖] No valid libraries found in '{json_file_path}'.", RED)

    # Create Flask app
    app = Flask(__name__)
    app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))
    app.static_folder = 'static'
    app.template_folder = 'templates'
    app.permanent_session_lifetime = timedelta(minutes=60)

    # Initialize Ollama logger once (so it's not recreated on each request)
    ollama_logger = setup_ollama_logger()

    # ============================ Flask Routes ==================================

    @app.route('/upload-profile-image', methods=['POST'])
    @login_required
    def upload_profile_image():
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            current_user = get_current_user()
            
            if current_user:
                # Extract username and file format
                username = current_user['name'].replace(" ", "").lower()
                extension = file.filename.rsplit('.', 1)[-1]
                filename = f"{username}.{extension}"
                filepath = os.path.join('static/img/PFPs', filename)
                
                # Save file
                file.save(filepath)
                
                # Update user's profile picture in both JSON files
                update_user_profile(current_user['email'], {'profile_pic': filename})
                return jsonify({'success': True, 'new_image_url': filepath})
        
        # If no file provided, return failure with default profile image
        return jsonify({'success': False, 'new_image_url': 'static/img/PFPs/default.png'})

    @app.route('/remove-profile-image', methods=['POST'])
    @login_required
    def remove_profile_image():
        current_user = get_current_user()
        if current_user:
            # Reset profile picture to default in both JSON files
            update_user_profile(current_user['email'], {'profile_pic': 'default.png'})
            return jsonify({'success': True})
        return jsonify({'success': False})


    @app.route('/update-profile', methods=['POST'])
    @login_required
    def update_profile():
        """
        Endpoint to update profile details with thorough email validation.
        """
        data = request.form
        email = data.get('email', '').strip()

        if not is_valid_email(email):
            return jsonify({"success": False, "message": "Invalid email address provided."}), 400

        # Proceed with updating the profile
        current_user = get_current_user()
        if current_user:
            try:
                update_user_profile(current_user['email'], {'Email': email})
                return jsonify({"success": True, "message": "Profile updated successfully."})
            except Exception as e:
                return jsonify({"success": False, "message": f"Error updating profile: {e}"}), 500
        return jsonify({"success": False, "message": "User not authenticated."}), 403

    def update_user_profile(email, updates):
        """
        Updates the user profile in both `user.json` and `credentials.json`.
        """
        # Update `user.json`
        with open(USER_DATA_FILE, 'r') as f:
            users = json.load(f)

        user_found = False
        for user in users:
            if user['Email'] == email:
                user.update(updates)
                user_found = True
                break

        if user_found:
            with open(USER_DATA_FILE, 'w') as f:
                json.dump(users, f, indent=4)

        # Update `credentials.json`
        with open(CREDENTIALS_FILE, 'r') as f:
            credentials = json.load(f)

        credential_found = False
        for credential in credentials:
            if credential['email'] == email:
                credential.update(updates)
                credential_found = True
                break

        if credential_found:
            with open(CREDENTIALS_FILE, 'w') as f:
                json.dump(credentials, f, indent=4)

    @app.route('/assets/<path:filename>')
    def serve_assets(filename):
        return send_from_directory('assets', filename)

    @app.route('/assets2/<path:filename>')
    def serve_assets2(filename):
        return send_from_directory('assets2', filename)

    @app.route('/check-email', methods=['POST'])
    def check_email():
        email = sanitize_input(request.json.get('email', ''))
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
        session.pop('user', None)
        resp = make_response(redirect(url_for('index')))
        resp.set_cookie('BBAIemail', '', expires=0)
        resp.set_cookie('BBAIcurrentuser', '', expires=0)
        return resp

    # Teachable Machine model files
    @app.route('/model')
    def get_model():
        return send_from_directory('static', 'tm-ByteBite-model/model.json')

    @app.route('/metadata')
    def get_metadata():
        return send_from_directory('static', 'tm-ByteBite-model/metadata.json')

    @app.route('/weights.bin')
    def get_weights():
        return send_from_directory('static', 'tm-ByteBite-model/weights.bin')

    @app.route('/url')
    def get_url():
        if authenticate(request.headers.get('token', '')):
            return TEACHABLE_MACHINE_URL
        else:
            abort(403)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/faqs')
    @login_required
    def faqs():
        current_user = get_current_user()
        if current_user:
            profile_pic = current_user.get('profile_pic', DEFAULT_PFP)
            if not profile_pic or not os.path.exists(f"static/img/PFPs/{profile_pic}"):
                profile_pic = DEFAULT_PFP
            return render_template('faqs.html', profile_pic=f"static/img/PFPs/{profile_pic}")
        return redirect(url_for('login'))

    @app.route('/ar-view')
    @login_required
    def arview():
        current_user = get_current_user()
        if current_user:
            profile_pic = current_user.get('profile_pic', DEFAULT_PFP)
            if not profile_pic or not os.path.exists(f"static/img/PFPs/{profile_pic}"):
                profile_pic = DEFAULT_PFP
            return render_template('ar-view.html', profile_pic=f"static/img/PFPs/{profile_pic}")
        return redirect(url_for('login'))
    
    @app.route('/my-profile')
    @login_required
    def myprofile():
        current_user = get_current_user()
        
        if current_user:
            # Load country codes from JSON
            with open('static/json/COUNTRY_CODES.json', 'r') as f:
                country_codes = json.load(f)

            # Extract nationalities from country codes
            nationalities = list(country_codes.keys())
            
            # Load user data
            with open(USER_DATA_FILE, 'r') as f:
                users = json.load(f)
            
            user_data = next((user for user in users if user['Full Name'] == current_user['name']), None)
            
            if user_data:
                profile_pic = user_data.get('profile_pic', DEFAULT_PFP)
                
                # Validate the profile picture path
                if not profile_pic or not os.path.exists(os.path.join('static/img/PFPs', profile_pic)):
                    profile_pic = DEFAULT_PFP
                
                return render_template(
                    'my-profile.html',
                    user_data=user_data,
                    profile_pic=profile_pic,
                    nationalities=nationalities,
                    country_codes=country_codes  # Pass country codes to template
                )
        return redirect(url_for('login'))

    @app.route('/save-social-links', methods=['POST'])
    @login_required
    def save_social_links():
        current_user = get_current_user()
        if current_user:
            data = request.json
            updates = {
                "Social Links": {
                    "Instagram": data.get("instagram", ""),
                    "Facebook": data.get("facebook", ""),
                    "Twitter": data.get("twitter", ""),
                    "Threads": data.get("threads", ""),
                }
            }
            update_user_profile(current_user['email'], updates)
            return jsonify({"success": True})
        return jsonify({"success": False}), 400

    @app.route('/save-profile', methods=['POST'])
    @login_required
    def save_profile():
        data = request.form

        # Verify Full Name
        full_name = data.get('fullName', '').strip()
        if not full_name or not full_name.replace(" ", "").isalpha():
            return jsonify({"success": False, "message": "Invalid full name. Only letters and spaces allowed."})

        # Sanitize and Verify About Section
        about = data.get('about', '').strip().lower()
        forbidden_words =   [
                            "fuck", "shit", "damn", "bitch", "bastard", "asshole", "dick", "cunt", "piss", "prick",
                            "slut", "whore", "idiot", "stupid", "moron", "nazi", "hitler", "racist", "bigot",
                            "homophobe", "transphobe", "sexist", "misogynist", "terrorist", "violence",
                            "hate", "offensive", "discrimination", "xenophobia", "ableist", "retard",
                            "cripple", "spaz", "fatphobic", "ugly", "loser", "dumbass", "scumbag",
                            "trash", "garbage", "jerk", "creep", "pervert", "predator", "molester", "abuser",

                            "fat", "skinny", "thin", "obese", "anorexic", "bulimic", "starvation", "anorexia",
                            "binge", "purge", "restrict", "underweight", "calorie deficit", "diet pill",
                            "fasting", "body shaming", "self-harm", "body dysmorphia", "weight loss obsession",
                            "thinspo", "fitspo", "pro-ana", "pro-mia", "food guilt", "guilty pleasure",
                            "cheat meal", "calorie counting", "obsessive eating", "emotional eating",
                            "comfort eating", "yo-yo dieting", "unhealthy weight loss", "crash diet",
                            "extreme fasting", "detox diet", "cleanse", "juice fast", "appetite suppressant",
                            "meal replacement", "body negativity", "self-loathing", "unrealistic goals",
                            "ideal weight", "ideal body", "size zero", "weight stigma", "body comparison",
                            "appearance anxiety", "eating disorder", "fasting challenge", "weight obsession",
                            "carb fear", "sugar fear", "food avoidance", "unbalanced diet", "scale addiction",
                            "unrealistic beauty standards", "body goals", "skinny challenge", "waist training",
                            "dangerous habits", "extreme weight loss", "quick fixes", "fat-phobic",
                            "muscle dysmorphia", "compulsive exercise", "over-exercising", "body perfection",
                            "comparison trap", "weight-based judgment", "food shame", "clean eating obsession",
                            "orthorexia", "carb-free", "low-fat obsession", "fad diets", "extreme restriction",
                            "disordered eating", "eating anxiety", "fear foods", "good food vs bad food",
                            "body dissatisfaction", "body perfectionism", "appearance idealization",
                            "self-starvation", "food anxiety", "body anxiety", "self-esteem issues",
                            "weight bullying", "appearance bullying", "unhealthy comparison",
                            "social media pressure", "unhealthy coping", "weight control obsession",
                            "body distortion", "perceived flaws", "self-hate", "dieting obsession",
                            "food obsession", "ideal image", "diet culture", "toxic fitness", "exercise guilt",
                            "weight-focused", "eating guilt", "carb shaming", "size shaming", "unhealthy diet",

                            "kill", "murder", "suicide", "abuse", "trauma", "trigger", "rape", "molest",
                            "pedophile", "exploitation", "incest", "terror", "bomb", "extremist", "violator",
                            "predatory", "assault", "harassment", "lynch", "genocide", "holocaust",
                            "gaslight", "manipulate", "victim", "exclusion", "marginalize", "oppress"
                        ];  
        if any(word in about for word in forbidden_words):
            return jsonify({"success": False, "message": "The 'About' section contains inappropriate content."})

        # If all validations pass, update user profile
        current_user = get_current_user()
        if current_user:
            update_user_profile(current_user['email'], {
                "Full Name": full_name,
                "about": sanitize_input(about)
            })
            return jsonify({"success": True, "message": "Profile updated successfully."})

        return jsonify({"success": False, "message": "User not found."})

    @app.route('/in-dev')
    def in_dev():
        return render_template('in-dev.html')

    @app.route('/chatbot')
    @login_required
    def chatbot():
        current_user = get_current_user()
        if current_user:
            profile_pic = current_user.get('profile_pic', DEFAULT_PFP)
            if not profile_pic or not os.path.exists(f"static/img/PFPs/{profile_pic}"):
                profile_pic = DEFAULT_PFP
            return render_template('chatbot.html', profile_pic=f"static/img/PFPs/{profile_pic}")
        return redirect(url_for('login'))

    @app.route("/chatbot", methods=["POST"])
    def chatbot_api():
        user_input = request.json.get("prompt", "")
        print(f"Received prompt from user: {user_input}")
        response = query_ollama_with_csv(user_input)
        print(f"Sending response back to user: {response}")
        return jsonify({"response": response})

    @app.route('/dashboard')
    @login_required
    def dashboard():
        current_user = get_current_user()
        if current_user:
            profile_pic = current_user.get('profile_pic', DEFAULT_PFP)
            if not profile_pic or not os.path.exists(f"static/img/PFPs/{profile_pic}"):
                profile_pic = DEFAULT_PFP
            return render_template('dashboard.html', profile_pic=f"static/img/PFPs/{profile_pic}")
        return redirect(url_for('login'))

    # ============================ LOGIN ROUTE (UPDATED) ==================================
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            if request.is_json:
                data = request.get_json()
                email = sanitize_input(data.get('email', ''))
                password = sanitize_input(data.get('password', ''))
                remember_me = data.get('rememberMe', False)  # <-- 'rememberMe' from JSON

                user = authenticate_user(email, password)
                if user:
                    # Put user in session
                    session['user'] = user['email']

                    # Build a JSON response
                    response_data = {
                        "success": True,
                        "message": "Login successful",
                        "redirect": url_for('dashboard'),
                        "name": user['name'],
                        "saveToLocalStorage": (remember_me is False)  # This signals front-end storage action
                    }

                    resp = make_response(jsonify(response_data))

                    # If "rememberMe" is True => set 30-day cookies
                    # If "rememberMe" is False => set session cookies (no max_age)
                    if remember_me:
                        max_age = timedelta(days=30)
                    else:
                        max_age = None  # This will create a session cookie

                    resp.set_cookie(
                        'BBAIcurrentuser',
                        user['name'],
                        max_age=max_age,
                        httponly=False,
                        path='/'
                    )
                    resp.set_cookie(
                        'BBAIemail',
                        user['email'],
                        max_age=max_age,
                        httponly=False,
                        path='/'
                    )
                    if remember_me:
                        resp.set_cookie(
                            'BBAIremembered',
                            'true',
                            max_age=max_age,
                            httponly=False,
                            path='/'
                        )
                    else:
                        resp.set_cookie(
                            'BBAIremembered',
                            '',
                            max_age=max_age,
                            httponly=False,
                            path='/'
                        )
                    return resp
                else:
                    return jsonify({"success": False, "message": "Incorrect email or password"})
            return jsonify({"success": False, "message": "Request must be JSON"})

        # If already logged in via cookies and "Remember Me"
        if request.cookies.get('BBAIemail') and request.cookies.get('BBAIcurrentuser') and request.cookies.get('BBAIremembered') == 'true':
            session['user'] = request.cookies.get('BBAIemail')
            return redirect(url_for('dashboard'))
        return render_template('login.html')

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if request.method == 'POST':
            try:
                data = request.get_json()
                name = sanitize_input(data.get('name', ''))
                email = sanitize_input(data.get('email', ''))
                password = sanitize_input(data.get('password', ''))
                confirm_password = sanitize_input(data.get('confirmPassword', ''))

                if not all([name, email, password, confirm_password]):
                    return jsonify({"success": False, "message": "Invalid input"}), 400

                if email_exists(email):
                    return jsonify({"success": False, "message": "An account with this email already exists."}), 400

                if password != confirm_password:
                    return jsonify({"success": False, "message": "Passwords do not match"}), 400

                if len(password) < 8 or not any(char.isdigit() for char in password):
                    return jsonify({
                        "success": False,
                        "message": "Password must be at least 8 characters and include a number"
                    }), 400

                hashed_password = generate_password_hash(password)
                user_data = {
                    "name": name,
                    "email": email,
                    "password": hashed_password,
                    "profile_pic": DEFAULT_PFP
                }

                existing_users = load_credentials()
                existing_users.append(user_data)
                save_credentials_pretty(existing_users)

                resp = make_response(jsonify({"success": True, "message": "Account created successfully!"}))
                resp.set_cookie(
                    'BBAIcurrentuser',
                    name,
                    max_age=timedelta(days=30),
                    httponly=False,
                    path='/'
                )
                resp.set_cookie(
                    'BBAIemail',
                    email,
                    max_age=timedelta(days=30),
                    httponly=False,
                    path='/'
                )
                return resp

            except Exception as e:
                return jsonify({"success": False, "message": f"Server error: {e}"}), 500

        return render_template('signup.html')

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('404.html', error=error), 403

    return app

# ============================= Entry Point ======================================================
if __name__ == '__main__':
    flask_app = create_app()
    # Run the app without debug-level logs from Flask; set debug=False in production.
    flask_app.run(debug=True, use_reloader=True, host='0.0.0.0', port=1000)
