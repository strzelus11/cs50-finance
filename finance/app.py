import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Take a dictionary from purchases database
    purchases = db.execute("SELECT * FROM purchases WHERE user_id = ?", session["user_id"])

    # Count cash
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]

    # Count total
    try:
        total = db.execute("SELECT SUM (total) AS total FROM purchases WHERE user_id = ?", session["user_id"])[0]["total"] + cash
    except TypeError:
        total = cash

    # Load index page
    return render_template("index.html", purchases=purchases, total=total, cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        try:
            # Look up for a stock and put it in the variable as a dict
            if lookup(request.form.get("symbol")):
                name = lookup(request.form.get("symbol"))["name"]
                symbol = lookup(request.form.get("symbol"))["symbol"]
                price = int(lookup(request.form.get("symbol"))["price"])
            else:
                return apology("stock does not exist", 400)

            # Validate number of stocks
            if int(request.form.get("shares")) > 0:
                    amount = int(request.form.get("shares"))
            else:
                return apology("Invalid number", 400)

            # Check if user has enough cash
            rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
            cash = int(rows[0]["cash"])
            total = price * amount
            if cash > total:

                # If symbol not already in the portfolio
                if not db.execute("SELECT symbol FROM purchases WHERE symbol = ? AND user_id = ?", symbol, session["user_id"]):

                    # Update purchases table
                    db.execute("INSERT INTO purchases (user_id, symbol, name, amount, price, total) VALUES (?, ?, ?, ?, ?, ?)", session["user_id"], symbol, name, amount, price, total)

                else:
                    # Update purchases table
                    db.execute("UPDATE purchases SET amount = ? + amount, price = ?, total = ? + total WHERE user_id = ? AND symbol = ?", amount, price, total, session["user_id"], symbol)

                # Update users table
                balance = cash - total
                db.execute("UPDATE users SET cash = ? WHERE id = ?", balance, session["user_id"])

                # Update history table
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db.execute("INSERT INTO history (symbol, amount, price, time, type, user_id) VALUES (?, ?, ?, ?, ?, ?)", symbol, amount, price, now, "buy", session["user_id"])

                return redirect("/")

        except ValueError:
            return apology("transaction failed", 400)



    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Take a dictionary from purchases database
    history = db.execute("SELECT * FROM history WHERE user_id = ?", session["user_id"])

    # Load history page
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Look up for a stock and put it in the variable as a dict
        if lookup(request.form.get("symbol")):
            stock = lookup(request.form.get("symbol"))

            # Put name, price, symbol in the variables
            name = stock["name"]
            price = stock["price"]
            symbol = stock["symbol"]

            # Redirect to the page with results
            return render_template("search.html", name=name, price=price, symbol=symbol)

        else:
            return apology("stock does not exist", 400)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        try:
            # Ensure username was submitted
            if not request.form.get("username"):
                return apology("must provide username", 400)

            # Ensure password was submitted
            elif not request.form.get("password"):
                return apology("must provide password", 400)

            # Ensure repeated password is the same as submitted earlier
            elif not request.form.get("password") == request.form.get("confirmation"):
                return apology("passwords aren't matching", 400)

            # Ensure the username is not taken
            elif request.form.get("name") in (db.execute("SELECT username FROM users")):
                return apology("username is already taken", 400)

            # Update a database to include a new username
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))

            # Remember which user has logged in
            rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
            session["user_id"] = rows[0]["id"]

        except ValueError:
            return apology("username is already taken", 400)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get name of the share to sell
        symbol = request.form.get("symbol")

        # Get amount of shares user has
        amount = db.execute("SELECT amount FROM purchases WHERE symbol = ? AND user_id = ?", symbol, session["user_id"])[0]["amount"]

        # Validate number of stocks
        if int(request.form.get("shares")) < 0:
            return apology("Invalid number", 400)

        # Check if he can sell them
        sellamount = int(request.form.get("shares"))

        # If he has not enough
        if amount < sellamount:
            return apology("transaction failed", 400)

        # If he wants to sell all
        elif amount == sellamount:
            db.execute("DELETE FROM purchases WHERE symbol = ? AND user_id = ?", symbol, session["user_id"])

        # If he wants to sell a few
        else:

            # Get price of a stock
            price = int(lookup(request.form.get("symbol"))["price"])
            difference = sellamount * price

            # Update amount and total in database
            db.execute("UPDATE purchases SET amount = amount - ?, total = total - ? WHERE user_id = ? AND symbol = ?", sellamount, difference, session["user_id"], symbol)

            # Update history table
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.execute("INSERT INTO history (symbol, amount, price, time, type, user_id) VALUES (?, ?, ?, ?, ?, ?)", symbol, sellamount, price, now, "sell", session["user_id"])

        return redirect("/")

    else:
        # Take a dictionary from purchases database
        purchases = db.execute("SELECT * FROM purchases WHERE user_id = ?", session["user_id"])
        return render_template("sell.html", purchases=purchases)


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Deposit cash to your finance account"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get amount of deposit
        cash = request.form.get("deposit")

        # Validate cash amount
        if cash <= 0:
            return apology("invalid number", 400)

        # Add deposit to the users database
        db.execute("UPDATE users SET cash = cash + ? WHERE user_id = ?", cash, session["user_id "])

        return redirect("/")

    else:
        return render_template("deposit.html")
