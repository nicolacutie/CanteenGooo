from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-key-before-deployment"
DB = "canteengo.db"

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student','vendor'))
    );
    CREATE TABLE IF NOT EXISTS vendors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        stall_name TEXT NOT NULL,
        pickup_location TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        price REAL NOT NULL,
        available INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY(vendor_id) REFERENCES vendors(id)
    );
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        vendor_id INTEGER NOT NULL,
        total REAL NOT NULL,
        payment_method TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(student_id) REFERENCES users(id),
        FOREIGN KEY(vendor_id) REFERENCES vendors(id)
    );
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id)
    );
    """)
    # Demo vendor accounts are created automatically on first run.
    demo_vendors = [
        ("Rice Meals Stall", "ricevendor@demo.com", "rice123", "Rice Meals", "Stall 1"),
        ("Snacks Stall", "snacksvendor@demo.com", "snacks123", "Snacks", "Stall 2"),
        ("Drinks Stall", "drinksvendor@demo.com", "drinks123", "Drinks", "Stall 3"),
    ]
    for name, email, password, stall, pickup in demo_vendors:
        existing = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if not existing:
            cur = con.execute(
                "INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                (name, email, generate_password_hash(password), "vendor")
            )
            vendor_id = cur.lastrowid
            con.execute(
                "INSERT INTO vendors(user_id,stall_name,pickup_location) VALUES(?,?,?)",
                (vendor_id, stall, pickup)
            )
    # Seed sample products only if the menu is empty.
    if con.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        seed = [
            (1, "Chicken Adobo Rice", "Rice meal", 65),
            (1, "Fried Chicken Rice", "Rice meal", 75),
            (2, "Lumpia", "Snack", 15),
            (2, "Siomai", "Snack", 25),
            (3, "Iced Tea", "Cold drink", 20),
            (3, "Bottled Water", "Drink", 15),
        ]
        for vendor_id, name, desc, price in seed:
            con.execute("INSERT INTO products(vendor_id,name,description,price) VALUES(?,?,?,?)",
                        (vendor_id, name, desc, price))
    con.commit()
    con.close()

def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("user_id"):
                flash("Please log in first.")
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("You do not have permission to view that page.")
                return redirect(url_for("home"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@app.route("/")
def home():
    con = db()
    vendors = con.execute("""
        SELECT v.id, v.stall_name, v.pickup_location, u.name
        FROM vendors v JOIN users u ON u.id=v.user_id ORDER BY v.id
    """).fetchall()
    con.close()
    return render_template("home.html", vendors=vendors)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        if len(password) < 6:
            flash("Password must be at least 6 characters.")
            return redirect(url_for("register"))
        con = db()
        try:
            con.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                        (name, email, generate_password_hash(password), "student"))
            con.commit()
            flash("Account created. You can now log in.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email is already registered.")
        finally:
            con.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        con = db()
        user = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        con.close()
        if user and check_password_hash(user["password"], request.form["password"]):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            return redirect(url_for("vendor_dashboard") if user["role"] == "vendor" else url_for("home"))
        flash("Incorrect email or password.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/vendor/<int:vendor_id>")
def vendor_menu(vendor_id):
    con = db()
    vendor = con.execute("SELECT * FROM vendors WHERE id=?", (vendor_id,)).fetchone()
    products = con.execute("SELECT * FROM products WHERE vendor_id=? AND available=1 ORDER BY name",
                           (vendor_id,)).fetchall()
    con.close()
    if not vendor:
        flash("Vendor not found.")
        return redirect(url_for("home"))
    return render_template("menu.html", vendor=vendor, products=products)

@app.route("/add-to-cart/<int:product_id>", methods=["POST"])
@login_required("student")
def add_to_cart(product_id):
    con = db()
    product = con.execute("""
        SELECT p.*, v.stall_name FROM products p
        JOIN vendors v ON v.id=p.vendor_id
        WHERE p.id=? AND p.available=1
    """, (product_id,)).fetchone()
    con.close()
    if not product:
        flash("That item is unavailable.")
        return redirect(url_for("home"))
    cart = session.get("cart", {})
    current_vendor = session.get("cart_vendor")
    if current_vendor and current_vendor != product["vendor_id"]:
        flash("Your cart is for another vendor. Please checkout or clear your cart first.")
        return redirect(url_for("cart"))
    cart[str(product_id)] = int(cart.get(str(product_id), 0)) + 1
    session["cart"] = cart
    session["cart_vendor"] = product["vendor_id"]
    flash("Item added to your cart.")
    return redirect(url_for("vendor_menu", vendor_id=product["vendor_id"]))

@app.route("/cart")
@login_required("student")
def cart():
    cart_data = []
    total = 0
    vendor = None
    con = db()
    vendor_id = session.get("cart_vendor")
    if vendor_id:
        vendor = con.execute("SELECT * FROM vendors WHERE id=?", (vendor_id,)).fetchone()
    for product_id, quantity in session.get("cart", {}).items():
        product = con.execute("SELECT * FROM products WHERE id=? AND vendor_id=?",
                              (product_id, vendor_id)).fetchone()
        if product:
            subtotal = product["price"] * quantity
            total += subtotal
            cart_data.append({"product": product, "quantity": quantity, "subtotal": subtotal})
    con.close()
    return render_template("cart.html", items=cart_data, total=total, vendor=vendor)

@app.route("/clear-cart", methods=["POST"])
@login_required("student")
def clear_cart():
    session.pop("cart", None)
    session.pop("cart_vendor", None)
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["POST"])
@login_required("student")
def checkout():
    cart = session.get("cart", {})
    vendor_id = session.get("cart_vendor")
    if not cart or not vendor_id:
        flash("Your cart is empty.")
        return redirect(url_for("cart"))
    payment = request.form.get("payment_method")
    if payment not in ("Cash on Pickup", "Online Payment (Demo)"):
        flash("Choose a payment method.")
        return redirect(url_for("cart"))
    con = db()
    total = 0
    valid_items = []
    for product_id, quantity in cart.items():
        product = con.execute("SELECT * FROM products WHERE id=? AND vendor_id=? AND available=1",
                              (product_id, vendor_id)).fetchone()
        if product:
            quantity = max(1, min(int(quantity), 20))
            total += product["price"] * quantity
            valid_items.append((product, quantity))
    if not valid_items:
        con.close()
        flash("Your cart items are no longer available.")
        return redirect(url_for("cart"))
    cur = con.execute(
        "INSERT INTO orders(student_id,vendor_id,total,payment_method) VALUES(?,?,?,?)",
        (session["user_id"], vendor_id, total, payment)
    )
    order_id = cur.lastrowid
    for product, quantity in valid_items:
        con.execute("""INSERT INTO order_items(order_id,product_id,product_name,quantity,unit_price)
                       VALUES(?,?,?,?,?)""",
                    (order_id, product["id"], product["name"], quantity, product["price"]))
    con.commit()
    con.close()
    session.pop("cart", None)
    session.pop("cart_vendor", None)
    flash(f"Order #{order_id} placed successfully!")
    return redirect(url_for("my_orders"))

@app.route("/my-orders")
@login_required("student")
def my_orders():
    con = db()
    orders = con.execute("""
        SELECT o.*, v.stall_name, v.pickup_location
        FROM orders o JOIN vendors v ON v.id=o.vendor_id
        WHERE o.student_id=? ORDER BY o.id DESC
    """, (session["user_id"],)).fetchall()
    con.close()
    return render_template("my_orders.html", orders=orders)

@app.route("/vendor/dashboard")
@login_required("vendor")
def vendor_dashboard():
    con = db()
    vendor = con.execute("SELECT * FROM vendors WHERE user_id=?", (session["user_id"],)).fetchone()
    orders = con.execute("""
        SELECT o.*, u.name AS student_name FROM orders o
        JOIN users u ON u.id=o.student_id
        WHERE o.vendor_id=? ORDER BY o.id DESC
    """, (vendor["id"],)).fetchall()
    con.close()
    return render_template("vendor_dashboard.html", vendor=vendor, orders=orders)

@app.route("/vendor/order/<int:order_id>/status", methods=["POST"])
@login_required("vendor")
def update_status(order_id):
    status = request.form.get("status")
    allowed = {"Confirmed", "Preparing", "Ready for Pickup", "Completed", "Rejected"}
    if status not in allowed:
        flash("Invalid order status.")
        return redirect(url_for("vendor_dashboard"))
    con = db()
    vendor = con.execute("SELECT id FROM vendors WHERE user_id=?", (session["user_id"],)).fetchone()
    con.execute("UPDATE orders SET status=? WHERE id=? AND vendor_id=?",
                (status, order_id, vendor["id"]))
    con.commit()
    con.close()
    flash("Order status updated.")
    return redirect(url_for("vendor_dashboard"))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
