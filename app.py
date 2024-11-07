from flask import Flask, render_template, send_from_directory
import os

app = Flask(__name__)

# Route to serve files from the 'assets' folder
@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(os.path.join(app.root_path, 'assets'), filename)

# Route to serve files from the 'assets2' folder
@app.route('/assets2/<path:filename>')
def serve_assets2(filename):
    return send_from_directory(os.path.join(app.root_path, 'assets2'), filename)

# Your regular routes for HTML pages
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
