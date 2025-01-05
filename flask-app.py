import os
import sys
import re
import pandas as pd
import time
import platform
import json
import logging
import subprocess
import importlib
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Any, List, Optional
import chardet
import emoji

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
ORDERS_FILE = "static/json/orders.json"
WEIGHT_JSON_PATH = "static/json/weight.json"
UPLOAD_FOLDER = 'static/img/PFPs'
DEFAULT_PFP = 'default.png'
TEACHABLE_MACHINE_URL = "https://teachablemachine.withgoogle.com/models/M6fwGM3tz/"
AUTHENTICATION_TOKEN = 'a123'  # For protected endpoints
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'heic', 'svg'}
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
                extension = file.filename.rsplit('.', 1)[-1].lower()
                
                if extension not in {'jpg', 'jpeg', 'png', 'gif'}:  # Validate file type
                    return jsonify({'success': False, 'message': 'Invalid file type'})
                
                # Define new filename and filepath
                filename = f"{username}.{extension}"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                
                # Check if a previous profile picture exists and delete it
                existing_pic = current_user.get('profile_pic', 'default.png')
                if existing_pic != 'default.png':
                    old_filepath = os.path.join(UPLOAD_FOLDER, existing_pic)
                    if os.path.exists(old_filepath):
                        os.remove(old_filepath)
                
                # Save new profile image
                file.save(filepath)
                
                # Update user's profile picture in JSON or database
                update_user_profile(current_user['email'], {'profile_pic': filename})
                
                return jsonify({'success': True, 'new_image_url': filepath})
        
        # If no file provided, return failure
        return jsonify({'success': False, 'message': 'No file provided'})

    @app.route('/remove-profile-image', methods=['POST'])
    @login_required
    def remove_profile_image():
        current_user = get_current_user()
        if current_user:
            # Get current profile picture filename
            current_pic = current_user.get('profile_pic', 'default.png')
            
            # Delete the existing profile picture (if it's not the default)
            if current_pic != 'default.png':
                current_filepath = os.path.join(UPLOAD_FOLDER, current_pic)
                if os.path.exists(current_filepath):
                    os.remove(current_filepath)
            
            # Reset profile picture to default in JSON or database
            update_user_profile(current_user['email'], {'profile_pic': 'default.png'})
            return jsonify({'success': True, 'new_image_url': os.path.join(UPLOAD_FOLDER, 'default.png')})
        
        return jsonify({'success': False, 'message': 'User not authenticated'})


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
    
    @app.route('/update_orders', methods=['POST'])
    def update_orders():
        try:
            # Get the updated orders data from the request
            order_data = request.get_json()

            # Path to the orders.json file
            orders_file = './static/json/orders.json'

            # Retrieve the current user's name from the request
            current_user_name = order_data.get('currentUserName')  # From the client-side request

            # Retrieve the recommendation data (dish, restaurant, price)
            dish_name = order_data.get('dishName')
            restaurant_name = order_data.get('restaurantName')
            price = order_data.get('price')

            # Get today's date in the format "dd/mm/yyyy"
            today_date = datetime.today().strftime('%d/%m/%Y')

            # Construct the order object
            new_order = {
                "Date": today_date,
                "Name of dish": dish_name,
                "Restaurant": restaurant_name,
                "Price": price,
                "userName": current_user_name
            }

            # Read the existing orders data
            with open(orders_file, 'r') as file:
                orders_data = json.load(file)

            # Add the new order to the orders list
            orders_data.append(new_order)

            # Save the updated orders data back to the JSON file
            with open(orders_file, 'w') as file:
                json.dump(orders_data, file, indent=4)

            return jsonify({"status": "success"}), 200
        except Exception as e:
            print(f"Error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500


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

    @app.route('/update_user', methods=['POST'])
    def update_user():
        try:
            # Get the updated user data from the request body
            updated_data = request.json

            # Check if the data contains a name (for example)
            if "Full Name" not in updated_data:
                return jsonify({"error": "User data must include 'Full Name'"}), 400

            # Read the existing users.json file
            if os.path.exists(USER_DATA_FILE):
                with open(USER_DATA_FILE, 'r') as file:
                    users_data = json.load(file)
            else:
                users_data = []

            # Find and update the user data based on the "Full Name"
            user_found = False
            for user in users_data:
                if user["Full Name"].lower() == updated_data["Full Name"].lower():
                    user_found = True

                    # Handle Liked Food (append to the existing list if present)
                    if "Liked Food" in updated_data:
                        if "Liked Food" not in user:
                            user["Liked Food"] = []
                        for food in updated_data["Liked Food"]:
                            if food not in user["Liked Food"]:
                                user["Liked Food"].append(food)

                    # Handle Disliked Food (append to the existing list if present)
                    if "Disliked Food" in updated_data:
                        if "Disliked Food" not in user:
                            user["Disliked Food"] = []
                        for food in updated_data["Disliked Food"]:
                            if food not in user["Disliked Food"]:
                                user["Disliked Food"].append(food)

                    break

            if not user_found:
                users_data.append(updated_data)  # Add new user if not found

            # Write the updated data back to users.json
            with open(USER_DATA_FILE, 'w') as file:
                json.dump(users_data, file, indent=4)

            return jsonify({"message": "User data updated successfully"}), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500


    # Function to load data from weight.json
    def load_weight_data():
        try:
            with open(WEIGHT_JSON_PATH, "r") as file:
                return json.load(file)
        except FileNotFoundError:
            # If the file doesn't exist, return an empty list (to represent no users)
            return []


    # Function to save updated data to weight.json
    def save_weight_data(data):
        with open(WEIGHT_JSON_PATH, "w") as file:
            json.dump(data, file, indent=4)

    # Utility function to remove .0 from float values
    def remove_decimal(weight):
        if weight.endswith('.0'):
            return str(int(float(weight)))  # Convert to int and back to string to remove .0
        return weight

    @app.route("/update-weight-json", methods=["POST"])
    def update_weight_json():
        # Parse the incoming request data
        incoming_data = request.json
        if not incoming_data:
            return jsonify({"success": False, "message": "Invalid data received"}), 400

        # Load existing weight.json data (which should now be a list of users)
        weight_data = load_weight_data()

        # Extract relevant fields
        user_name = incoming_data.get("Name")
        current_weight = incoming_data.get("Weight")[0]  # Get first element from Weight array
        target_weight = incoming_data.get("TargetWeight")
        current_date = incoming_data.get("Date")[0]  # Get first element from Date array

        if not user_name or not current_weight or not target_weight or not current_date:
            return jsonify({"success": False, "message": "Missing required fields"}), 400

        # Remove .0 if the weight ends with .0
        current_weight = remove_decimal(current_weight)

        # Search for the user in the list of users
        user_data = None
        for user in weight_data:
            if user["Name"] == user_name:
                user_data = user
                break  # Exit the loop once we find the user

        # If user does not exist, initialize the user data
        if user_data is None:
            user_data = {
                "Name": user_name,
                "Weight": [],
                "Target Weight": "",
                "Date": []
            }
            weight_data.append(user_data)  # Add the new user data to the list

        # Logic for updating Weight and Dates
        date_added = False  # Flag to ensure Date is added only once for Weight
        if len(user_data["Weight"]) == 0 or user_data["Weight"][-1] != current_weight:
            user_data["Weight"].append(current_weight)
            user_data["Date"].append(current_date)  # Append date only for weight change
            date_added = True  # Mark Date as added for weight change

        # Logic for updating Target Weight (no date appended)
        if user_data["Target Weight"] != target_weight:
            user_data["Target Weight"] = target_weight  # Update target weight without date

        # Save the updated data back to weight.json
        save_weight_data(weight_data)

        # Respond with success
        return jsonify({"success": True, "message": "Weight data updated successfully"}), 200

    # Load the JSON data
    def load_weight_data_2():
        file_path = os.path.join('static', 'json', 'weight.json')
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        return []

    # Route to get weight data
    @app.route("/get-weight-data", methods=["GET"])
    def get_weight_data():
        # Get the username from the query parameter
        user_name = request.args.get('username')

        if not user_name:
            return jsonify({"success": False, "message": "Username not provided"}), 400

        # Load users data
        users_data = load_weight_data_2()  # This will load the JSON as a list of users
        
        # Find the user data that matches the current user
        user_data = None
        for user in users_data:
            if user["Name"] == user_name:
                user_data = user
                break  # Exit the loop once we find the user

        if user_data is None:
            return jsonify({"success": False, "message": "User not found"}), 404

        # If user is found, extract data for chart
        target_weight = user_data["Target Weight"]
        weight_data = user_data["Weight"]
        date_data = user_data["Date"]

        # Process data as needed for chart
        chart_data = {
            "target_weight": target_weight,
            "weight_data": weight_data,
            "date_data": date_data
        }

        # Respond with success and the data
        return jsonify({"success": True, "data": chart_data}), 200




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
    
    def remove_emoji(text):
        return ''.join(c for c in text if c.isalnum() or c.isspace())

    @app.route('/my-profile')
    @login_required
    def myprofile():
        current_user = get_current_user()

        if current_user:
            # Determine the operating system
            system_name = platform.system().lower()

            # Choose the appropriate JSON file based on the OS
            if system_name == 'darwin':  # macOS ("Darwin")
                country_codes_file = 'static/json/COUNTRY_CODES_MAC.json'
            elif system_name == 'linux':  # Unix/Linux
                country_codes_file = 'static/json/COUNTRY_CODES_MAC.json'
            elif system_name == 'windows':  # Explicit check for Windows
                country_codes_file = 'static/json/COUNTRY_CODES_WIN.json'
            else:
                # Fallback in case there's an unexpected system name
                country_codes_file = 'static/json/COUNTRY_CODES_WIN.json'

            # Load country codes from the chosen file
            with open(country_codes_file, 'r') as f:
                country_codes = json.load(f)

            # Extract nationalities from country codes and normalize
            nationalities = [remove_emoji(n) for n in country_codes.keys()]

            # Load user data
            with open(USER_DATA_FILE, 'r') as f:
                users = json.load(f)

            user_data = next((user for user in users if user['Full Name'] == current_user['name']), None)

            if user_data:
                profile_pic = user_data.get('profile_pic', DEFAULT_PFP)

                # Validate the profile picture path
                if not profile_pic or not os.path.exists(os.path.join('static/img/PFPs', profile_pic)):
                    profile_pic = DEFAULT_PFP

                # Pass sanitized nationalities to the template
                return render_template(
                    'my-profile.html',
                    user_data=user_data,
                    profile_pic=profile_pic,
                    nationalities=nationalities,
                    country_codes=country_codes,
                    remove_emoji=remove_emoji  # Pass the function to the template
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
        data = request.json  # Expecting JSON data from the front-end

        # Validation: Verify Full Name
        full_name = data.get('fullName', '').strip()
        if not full_name or not full_name.replace(" ", "").isalpha():
            return jsonify({"success": False, "message": "Invalid full name. Only letters and spaces allowed."}), 400

        # Validation: Verify "About" Section
        about = data.get('about', '').strip()
        if len(about) > 300:
            return jsonify({"success": False, "message": "The 'About' section exceeds the 300-character limit."}), 400
        forbidden_words = [
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
                        ]
        if any(word.lower() in about.lower() for word in forbidden_words):
            return jsonify({"success": False, "message": "The 'About' section contains inappropriate content."}), 400

        # Validation: Verify Date of Birth and Age
        dob = data.get('dob', '').strip()
        if dob:
            from datetime import datetime
            try:
                dob_date = datetime.strptime(dob, "%Y-%m-%d")
                age = (datetime.now() - dob_date).days // 365
                if age < 16:
                    return jsonify({"success": False, "message": "You must be at least 16 years old to proceed."}), 400
            except ValueError:
                return jsonify({"success": False, "message": "Invalid date format for DOB."}), 400

        # Validation: Verify Email
        email = data.get('email', '').strip()
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, email):
            return jsonify({"success": False, "message": "Invalid email address."}), 400

        # Retrieve the current user
        current_user = get_current_user()
        if not current_user:
            return jsonify({"success": False, "message": "User not found."}), 403

        # Load the existing user profile from `user.json`
        with open(USER_DATA_FILE, 'r') as file:
            users = json.load(file)

        user_profile = next((user for user in users if user['Email'] == current_user['email']), None)
        if not user_profile:
            return jsonify({"success": False, "message": "User profile not found."}), 404

        # Prepare the updated profile
        updated_profile = user_profile.copy()

        # Update fields only if they change
        name_changed = full_name != user_profile.get("Full Name", "")
        if name_changed:
            updated_profile["Full Name"] = full_name

        about_changed = about != user_profile.get("about", "")
        if about_changed:
            updated_profile["about"] = sanitize_input(about)

        if dob and dob != user_profile.get("DOB", ""):
            dob_parts = dob.split("-")  # Convert YYYY-MM-DD to DD/MM/YYYY
            updated_profile["DOB"] = f"{dob_parts[2]}/{dob_parts[1]}/{dob_parts[0]}"

        # Update Occupation and Current Course fields
        new_occupation = data.get('occupation', '').strip()
        current_course = data.get('currentCourse', '').strip()

        # Update occupation only if it has changed
        if new_occupation != user_profile.get("Occupation", ""):
            updated_profile["Occupation"] = new_occupation

            # Check if the new occupation supports 'currentCourse'
            occupations_with_course = [
                "Student @ University of Malta", 
                "Lecturer @ University of Malta"
            ]
            
            # If the new occupation doesn't support 'currentCourse', retain the existing value
            if new_occupation not in occupations_with_course:
                current_course = user_profile.get("Current Course", "")

        # Update currentCourse only if it has changed and is still relevant
        if current_course != user_profile.get("Current Course", ""):
            updated_profile["Current Course"] = current_course

        if data.get('nationality', '') != user_profile.get("Nationality", ""):
            updated_profile["Nationality"] = data.get('nationality', '')
        if data.get('mobileNumber', '') != user_profile.get("Mobile Number", ""):
            updated_profile["Mobile Number"] = data.get('mobileNumber', '')

        email_changed = email != user_profile.get("Email", "")
        if email_changed:
            updated_profile["Email"] = email

        # Update social links only if provided
        social_links = data.get('socialLinks', {})
        updated_profile["Social Links"] = {
            "Instagram": social_links.get("instagram", user_profile["Social Links"].get("Instagram", "")),
            "Facebook": social_links.get("facebook", user_profile["Social Links"].get("Facebook", "")),
            "Twitter": social_links.get("twitter", user_profile["Social Links"].get("Twitter", "")),
            "Threads": social_links.get("threads", user_profile["Social Links"].get("Threads", ""))
        }

        # Update `credentials.json` if name or email changes
        if name_changed or email_changed:
            with open(CREDENTIALS_FILE, 'r') as cred_file:
                credentials = json.load(cred_file)

            for cred in credentials:
                if cred['email'] == current_user['email']:
                    if name_changed:
                        cred['name'] = full_name
                    if email_changed:
                        cred['email'] = email
                    break

            with open(CREDENTIALS_FILE, 'w') as cred_file:
                json.dump(credentials, cred_file, indent=4)

        # Save the profile only if there are changes
        if updated_profile != user_profile:
            # Update the user in USER_DATA_FILE
            for i, user in enumerate(users):
                if user['Email'] == current_user['email']:
                    users[i] = updated_profile
                    break
            with open(USER_DATA_FILE, 'w') as file:
                json.dump(users, file, indent=4)

            # Update `credentials.json` if name or email changes
            if name_changed or email_changed:
                with open(CREDENTIALS_FILE, 'r') as cred_file:
                    credentials = json.load(cred_file)

                for cred in credentials:
                    if cred['email'] == current_user['email']:
                        if name_changed:
                            cred['name'] = full_name
                        if email_changed:
                            cred['email'] = email
                        break

                with open(CREDENTIALS_FILE, 'w') as cred_file:
                    json.dump(credentials, cred_file, indent=4)

            # Update `orders.json` for matching `userName`
            if name_changed:
                with open(ORDERS_FILE, 'r') as orders_file:
                    orders = json.load(orders_file)

                for order in orders:
                    if order.get("userName") == user_profile.get("Full Name", ""):
                        order["userName"] = full_name

                with open(ORDERS_FILE, 'w') as orders_file:
                    json.dump(orders, orders_file, indent=4)

            # Update `weight.json` for matching `userName`
            if name_changed:
                try:
                    with open(WEIGHT_JSON_PATH, 'r') as weight_file:
                        weight_data = json.load(weight_file)

                    # Update occurrences of the old name in both `userName` and `Name` fields
                    old_name = user_profile.get("Full Name", "")
                    for record in weight_data:
                        if record.get("userName") == old_name:
                            record["userName"] = full_name
                        if record.get("Name") == old_name:
                            record["Name"] = full_name

                    # Save the updated weight data
                    with open(WEIGHT_JSON_PATH, 'w') as weight_file:
                        json.dump(weight_data, weight_file, indent=4)

                except FileNotFoundError:
                    logging.error(f"File {WEIGHT_JSON_PATH} not found. Skipping name update.")
                except json.JSONDecodeError:
                    logging.error(f"Error decoding JSON from {WEIGHT_JSON_PATH}. Skipping name update.")
                except Exception as e:
                    logging.error(f"Unexpected error updating {WEIGHT_JSON_PATH}: {e}")

            # Return response and update cookies
            resp = jsonify({"success": True, "message": "Profile updated successfully."})
            if name_changed:
                # Set cookie and signal the front-end to update localStorage
                resp.set_cookie('BBAIcurrentuser', full_name, max_age=30 * 24 * 60 * 60, httponly=False)
                resp.headers['X-Update-LocalStorage'] = f"BBAIcurrentuser={full_name}"
            if email_changed:
                resp.set_cookie('BBAIemail', email, max_age=30 * 24 * 60 * 60, httponly=False)
            return resp

        return jsonify({"success": True, "message": "No changes were made to the profile."})


    @app.route('/save-settings', methods=['POST'])
    @login_required
    def save_settings():
        data = request.json  # Expecting JSON data from the front-end

        # Retrieve the current user
        current_user = get_current_user()
        if not current_user:
            return jsonify({"success": False, "message": "User not found."}), 403

        # Load the existing user profile from `user.json`
        with open(USER_DATA_FILE, 'r') as file:
            users = json.load(file)

        user_profile = next((user for user in users if user['Email'] == current_user['email']), None)
        if not user_profile:
            return jsonify({"success": False, "message": "User profile not found."}), 404

        # Prepare the updated profile
        updated_profile = user_profile.copy()

        # Update food preferences
        favourite_food = data.get('favouriteFood', '').strip()
        custom_food = data.get('customFood', '').strip()
        if favourite_food == 'Other' and custom_food:
            updated_profile['Favourite Food'] = custom_food
        elif favourite_food and favourite_food != user_profile.get('Favourite Food', ''):
            updated_profile['Favourite Food'] = favourite_food

        # Update favorite restaurant
        favourite_restaurant = data.get('favouriteRestaurant', '').strip()
        if favourite_restaurant and favourite_restaurant != user_profile.get('Favourite Restaurant', ''):
            updated_profile['Favourite Restaurant'] = favourite_restaurant

        # Update dietary requirements
        updated_profile['Vegetarian'] = int(data.get('vegetarian', 0))
        updated_profile['Nut Allergy'] = int(data.get('nutAllergy', 0))
        updated_profile['Gluten Allergy'] = int(data.get('glutenAllergy', 0))

        # Update health details
        current_weight = data.get('currentWeight')
        target_weight = data.get('targetWeight')
        height = data.get('height')

        if current_weight:
            try:
                current_weight = float(current_weight)
                if 20 <= current_weight <= 300:
                    updated_profile['Weight'] = current_weight
                else:
                    return jsonify({"success": False, "message": "Invalid current weight. Must be between 20 and 300 kg."}), 400
            except ValueError:
                return jsonify({"success": False, "message": "Invalid current weight format."}), 400

        if target_weight:
            try:
                target_weight = float(target_weight)
                if 20 <= target_weight <= 300:
                    updated_profile['Target_weight'] = target_weight
                else:
                    return jsonify({"success": False, "message": "Invalid target weight. Must be between 20 and 300 kg."}), 400
            except ValueError:
                return jsonify({"success": False, "message": "Invalid target weight format."}), 400

        if height:
            try:
                height = float(height)
                if 0.5 <= height <= 2.5:
                    updated_profile['Height'] = height
                else:
                    return jsonify({"success": False, "message": "Invalid height. Must be between 0.5 and 2.5 meters."}), 400
            except ValueError:
                return jsonify({"success": False, "message": "Invalid height format."}), 400

        # Update the last update time for weight
        updated_profile['Weight_LastUpdate'] = datetime.now().strftime('%d/%m/%Y, %I:%M %p')

        # Save the profile only if there are changes
        if updated_profile != user_profile:
            for i, user in enumerate(users):
                if user['Email'] == current_user['email']:
                    users[i] = updated_profile
                    break
            with open(USER_DATA_FILE, 'w') as file:
                json.dump(users, file, indent=4)

            return jsonify({"success": True, "message": "Settings updated successfully."})

        return jsonify({"success": True, "message": "No changes were made to the settings."})


    @app.route('/change-password', methods=['POST'])
    @login_required
    def change_password():
        data = request.json  # Expecting JSON data from the front-end

        # Retrieve the current user
        current_user = get_current_user()
        if not current_user:
            return jsonify({"success": False, "message": "User not found."}), 403

        # Load credentials from `credentials.json`
        with open(CREDENTIALS_FILE, 'r') as cred_file:
            credentials = json.load(cred_file)

        # Find the user's credentials
        user_cred = next((cred for cred in credentials if cred['email'] == current_user['email']), None)
        if not user_cred:
            return jsonify({"success": False, "message": "User credentials not found."}), 404

        # Validate current password
        current_password = data.get('currentPassword', '').strip()
        if not check_password_hash(user_cred['password'], current_password):
            return jsonify({"success": False, "message": "Current password is incorrect."}), 400

        # Validate new password and confirmation
        new_password = data.get('newPassword', '').strip()
        confirm_password = data.get('confirmPassword', '').strip()

        if not new_password or not confirm_password:
            return jsonify({"success": False, "message": "New password and confirmation are required."}), 400

        if new_password != confirm_password:
            return jsonify({"success": False, "message": "New password and confirmation do not match."}), 400

        if len(new_password) < 8 or not any(char.isdigit() for char in new_password):
            return jsonify({"success": False, "message": "Password must be at least 8 characters long and contain at least one number."}), 400

        # Hash and update the new password
        hashed_password = generate_password_hash(new_password)
        user_cred['password'] = hashed_password

        # Save updated credentials
        with open(CREDENTIALS_FILE, 'w') as cred_file:
            json.dump(credentials, cred_file, indent=4)

        return jsonify({"success": True, "message": "Password changed successfully."})

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

    def initialize_user_data(name, email):
        from datetime import datetime
        return {
            "Full Name": name,
            "profile_pic": DEFAULT_PFP,
            "about": "",
            "DOB": "",
            "Occupation": "",
            "Current Course": "",
            "Nationality": "",
            "Mobile Number": "",
            "Email": email,
            "Member Since": datetime.now().strftime("%Y-%m-%d"),
            "Height": "",
            "Weight": "",
            "Target_weight": "",
            "Weight_LastUpdate": "",
            "Favourite Food": "",
            "Favourite Restaurant": "",
            "Vegetarian": 0,
            "Nut Allergy": 0,
            "Gluten Allergy": 0,
            "Social Links": {
                "Instagram": "https://instagram.com/",
                "Facebook": "https://facebook.com/",
                "Twitter": "https://x.com/",
                "Threads": "https://www.threads.net/"
            },
            "Disliked Food": [],
            "Liked Food": []
        }

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if request.method == 'POST':
            try:
                # Parse incoming JSON data
                data = request.get_json()
                print(f"Full payload received: {data}")  # Debugging log

                # Extract and sanitize input
                name = sanitize_input(data.get('name', '').strip())
                email = sanitize_input(data.get('email', '').strip())
                password = sanitize_input(data.get('password', '').strip())
                confirm_password = sanitize_input(data.get('confirmPassword', '').strip())

                print(f"Name: {name}, Email: {email}, Password: {password}, Confirm Password: {confirm_password}")  # Debugging

                # Validate inputs
                if not all([name, email, password, confirm_password]):
                    print("Validation failed: Missing required fields.")
                    return jsonify({"success": False, "message": "Invalid input"}), 400

                if email_exists(email):
                    print("Validation failed: Email already exists.")
                    return jsonify({"success": False, "message": "An account with this email already exists."}), 400

                if password != confirm_password:
                    print("Validation failed: Passwords do not match.")
                    return jsonify({"success": False, "message": "Passwords do not match"}), 400

                if len(password) < 8 or not any(char.isdigit() for char in password):
                    print("Validation failed: Password does not meet complexity requirements.")
                    return jsonify({
                        "success": False,
                        "message": "Password must be at least 8 characters and include a number"
                    }), 400

                # Hash password
                hashed_password = generate_password_hash(password)

                # Save user to credentials.json
                user_credential = {
                    "name": name,
                    "email": email,
                    "password": hashed_password,
                    "profile_pic": DEFAULT_PFP
                }
                existing_credentials = load_credentials()
                existing_credentials.append(user_credential)
                save_credentials_pretty(existing_credentials)

                # Save user to users.json
                if 'userData' in data:
                    user_data = data['userData']
                else:
                    user_data = initialize_user_data(name, email)

                if not os.path.exists(USER_DATA_FILE):
                    users = [user_data]
                else:
                    with open(USER_DATA_FILE, 'r') as file:
                        users = json.load(file)
                    users.append(user_data)

                with open(USER_DATA_FILE, 'w') as file:
                    json.dump(users, file, indent=4)

                # Respond with success and set cookies
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
                print(f"Server error: {e}")  # Debugging log
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
