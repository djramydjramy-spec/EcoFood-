from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import csv, os
from werkzeug.security import generate_password_hash, check_password_hash 

# Initialisation de l'application Flask
app = Flask(__name__)
# CRITIQUE: Clé secrète requise pour Flask-Login et les sessions
app.config['SECRET_KEY'] = 'your_strong_and_secret_key_here' 

CSV_FILENAME = "offers.csv"
USERS_CSV_FILENAME = "users.csv" # Nom du fichier pour stocker les utilisateurs


# --- 1. CONFIGURATION FLASK-LOGIN & MODÈLE UTILISATEUR ---

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 
login_manager.login_message = "You must log in to access this partner-only feature."
login_manager.login_message_category = "info"


# Modèle utilisateur utilisé par Flask-Login
class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

# --- Fonctions de Gestion des Utilisateurs (Modèle Sécurisé) ---

def read_users():
    """Reads all users from USERS_CSV_FILENAME and returns them as a dictionary of User objects."""
    users = {}
    if os.path.exists(USERS_CSV_FILENAME):
        with open(USERS_CSV_FILENAME, newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                users[row['id']] = User(row['id'], row['username'], row['password_hash'])
    return users

def write_users(users):
    """Writes the current dictionary of User objects back into USERS_CSV_FILENAME."""
    user_data = [{'id': u.id, 'username': u.username, 'password_hash': u.password_hash} for u in users.values()]
    
    with open(USERS_CSV_FILENAME, "w", newline="", encoding="utf-8") as file:
        fieldnames = ["id", "username", "password_hash"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(user_data)

def generate_user_id(users):
    """Generates a unique ID for a new user."""
    if not users:
        return "1"
    max_id = max(int(uid) for uid in users.keys())
    return str(max_id + 1)


# Required function by Flask-Login to load the user object
@login_manager.user_loader
def load_user(user_id):
    users = read_users()
    return users.get(user_id)


# --- 4. ROUTES D'AUTHENTIFICATION & ENREGISTREMENT ---

@app.route("/register", methods=["GET", "POST"])
def register():
    """Handles new user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('offers'))

    if request.method == "POST":
        username = request.form.get('username').strip()
        password = request.form.get('password')
        
        users = read_users()
        
        # 1. Check if username is already taken
        if any(u.username == username for u in users.values()):
            flash("Username already taken. Please choose a different one.", 'error')
            return render_template("register.html")

        # 2. Check password length
        if len(password) < 6:
            flash("Password must be at least 6 characters long.", 'error')
            return render_template("register.html")

        # 3. Hash the password (CRITICAL Security Step)
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        # 4. Create and Save the new user
        new_id = generate_user_id(users)
        new_user = User(new_id, username, hashed_password)
        users[new_id] = new_user
        write_users(users)
        
        flash("Registration successful! You can now log in.", 'success')
        return redirect(url_for('login'))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        return redirect(url_for('offers'))
        
    if request.method == "POST":
        username = request.form.get('username').strip()
        password = request.form.get('password')
        
        users = read_users()
        
        # Find user by username
        user = next((u for u in users.values() if u.username == username), None)
        
        # Check if user exists AND if the hashed password matches the input password
        if user and check_password_hash(user.password_hash, password):
            login_user(user) 
            flash("Login successful!", 'success')
            return redirect(request.args.get('next') or url_for('offers')) 
        else:
            flash("Invalid Username or Password. Please try again.", 'error')
            return render_template("login.html") 

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    """Handles user logout."""
    logout_user()
    flash("You have been logged out successfully.", 'info')
    return redirect(url_for('index'))


# --- 5. ROUTES DE L'APPLICATION (SECURED ACTIONS) ---

# --- Fonctions de gestion des offres (Non modifiées) ---

def read_offers():
    """Reads all offers from CSV file."""
    offers = []
    if os.path.exists(CSV_FILENAME):
        with open(CSV_FILENAME, newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            offers = list(reader)
    return offers


def write_offers(offers):
    """Writes list of offers back into CSV file."""
    with open(CSV_FILENAME, "w", newline="", encoding="utf-8") as file:
        fieldnames = ["id", "restaurant", "plat", "prix", "type", "status", "image"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(offers)


def generate_id(offers):
    """Assigns a unique ID."""
    if not offers:
        return "1"
    max_id = max(int(o.get("id", 0)) for o in offers)
    return str(max_id + 1)


def get_offer_by_id(offers, offer_id):
    """Finds an offer by its unique ID."""
    return next((o for o in offers if o.get("id") == offer_id), None)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/offers")
def offers():
    offers_list = read_offers()
    return render_template("offers.html", offers=offers_list)


@app.route("/add", methods=["GET", "POST"])
@login_required 
def add():
    """Adds a new food offer (only accessible if logged in)."""
    error_message = None
    if request.method == "POST":
        offers = read_offers()
        
        new_offer = {
            "id": generate_id(offers),
            "restaurant": request.form.get("restaurant", "").strip(),
            "plat": request.form.get("plat", "").strip(),
            "prix": request.form.get("prix", "0").strip(),
            "type": request.form.get("type", "").strip(),
            "status": "Available",
            "image": request.form.get("image", "").strip() 
        }

        if not new_offer["restaurant"] or not new_offer["plat"]:
            error_message = "Please fill in all required fields (Restaurant and Dish)."
            return render_template("add.html", error=error_message), 400

        try:
            int(new_offer["prix"])
        except ValueError:
            error_message = "Price must be a valid number (use 0 for donation)."
            return render_template("add.html", error=error_message), 400

        offers.append(new_offer)
        write_offers(offers)
        flash("Offer successfully posted!", 'success')
        return redirect(url_for('offers'))

    return render_template("add.html", error=error_message)


@app.route("/delete/<offer_id>", methods=["POST"])
@login_required 
def delete(offer_id):
    """Deletes an offer by ID (only if logged in)."""
    offers = read_offers()
    offers = [o for o in offers if o.get("id") != offer_id]
    write_offers(offers)
    flash("Offer deleted successfully.", 'success')
    return redirect(url_for('offers'))


@app.route("/sold/<offer_id>", methods=["POST"])
@login_required 
def sold(offer_id):
    """Marks item as sold out (only if logged in)."""
    offers = read_offers()
    for o in offers:
        if o.get("id") == offer_id:
            o["status"] = "Sold Out"
            break
    write_offers(offers)
    flash("Offer marked as Sold Out.", 'success')
    return redirect(url_for('offers'))


@app.route("/edit/<offer_id>", methods=["GET", "POST"])
@login_required
def edit(offer_id):
    """Displays edit form and processes update (only if logged in)."""
    offers = read_offers()
    offer_to_edit = get_offer_by_id(offers, offer_id)
    
    if offer_to_edit is None:
        return "Offer not found", 404

    if request.method == "POST":
        for o in offers:
            if o.get("id") == offer_id:
                o["restaurant"] = request.form.get("restaurant", "").strip()
                o["plat"] = request.form.get("plat", "").strip()
                o["prix"] = request.form.get("prix", "0").strip()
                o["type"] = request.form.get("type", "").strip()
                break
        
        write_offers(offers)
        flash("Offer updated successfully.", 'success')
        return redirect(url_for('offers'))
        
    return render_template("edit.html", offer=offer_to_edit)


@app.route("/search")
def search():
    """Search by restaurant or dish."""
    q = request.args.get("q", "").lower().strip()
    offers = read_offers()
    results = [o for o in offers
               if q in o["restaurant"].lower() or q in o["plat"].lower()]
    return render_template("offers.html", offers=results)


@app.route("/filter/<category>")
def filter_offers(category):
    """Filter by category (Sale / Donation)."""
    offers = read_offers()
    results = [o for o in offers if o["type"].lower() == category.lower()]
    return render_template("offers.html", offers=results)


# Démarrer le serveur
if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)