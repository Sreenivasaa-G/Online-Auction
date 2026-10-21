from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import os
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "replace-this-secret-before-deployment"),
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///auction_demo.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
)
db = SQLAlchemy(app)
csrf = CSRFProtect(app)

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    bids = db.relationship("Bid", backref="bidder", lazy=True)

class Auction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(60), nullable=False, default="General")
    image_url = db.Column(db.String(500))
    starting_price = db.Column(db.Numeric(10, 2), nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)
    bids = db.relationship("Bid", backref="auction", lazy=True, cascade="all, delete-orphan")

    @property
    def highest_bid(self):
        return max((bid.amount for bid in self.bids), default=self.starting_price)

    @property
    def winning_bid(self):
        return max(self.bids, key=lambda b: (b.amount, b.created_at, b.id), default=None)

    @property
    def winner_name(self):
        return self.winning_bid.bidder.name if self.winning_bid else None

    @property
    def status(self):
        return "Ended" if self.ends_at <= utcnow() else "Live"

    @property
    def bid_count(self):
        return len(self.bids)

class Bid(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(db.Integer, db.ForeignKey("auction.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

class Watchlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    auction_id = db.Column(db.Integer, db.ForeignKey("auction.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    auction = db.relationship("Auction", backref=db.backref("watchlist_entries", lazy=True, cascade="all, delete-orphan"))
    __table_args__ = (db.UniqueConstraint("auction_id", "user_id", name="uq_watchlist_user_auction"),)

def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or not user.is_admin:
            flash("Administrator access is required.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

@app.context_processor
def inject_globals():
    return {"current_user": current_user(), "now": utcnow}

@app.route("/")
def index():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    query = Auction.query.filter_by(is_hidden=False)
    if search:
        query = query.filter(Auction.title.ilike(f"%{search}%"))
    if category:
        query = query.filter_by(category=category)
    auctions = query.order_by(Auction.ends_at.asc()).all()
    categories = [r[0] for r in db.session.query(Auction.category).filter_by().distinct().order_by(Auction.category).all()]
    return render_template("index.html", auctions=auctions, categories=categories,
                           search=search, selected_category=category)

@app.route("/auction/<int:auction_id>")
def auction_detail(auction_id):
    auction = db.session.get(Auction, auction_id) or abort(404)
    if auction.is_hidden and not (current_user() and current_user().is_admin):
        abort(404)
    bids = Bid.query.filter_by(auction_id=auction.id).order_by(Bid.amount.desc(), Bid.created_at.desc()).all()
    saved = bool(current_user() and Watchlist.query.filter_by(user_id=current_user().id, auction_id=auction.id).first())
    return render_template("auction_detail.html", auction=auction, bids=bids, saved=saved)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or len(name) > 80 or not email or len(email) > 120 or len(password) < 8:
            flash("Enter a valid name and email, and use a password of at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            user = User(name=name, email=email, password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            session.clear()
            session["user_id"] = user.id
            flash("Account created successfully.", "success")
            return redirect(url_for("index"))
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session["user_id"] = user.id
            flash(f"Welcome back, {user.name}.", "success")
            return redirect(url_for("index"))
        flash("Email or password is incorrect.", "error")
    return render_template("auth.html", mode="login")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))

@app.route("/auction/<int:auction_id>/bid", methods=["POST"])
def place_bid(auction_id):
    user = current_user()
    if not user:
        flash("Please log in before bidding.", "error")
        return redirect(url_for("login"))
    auction = db.session.get(Auction, auction_id) or abort(404)
    if auction.is_hidden or auction.ends_at <= utcnow():
        flash("This auction is closed and cannot accept bids.", "error")
        return redirect(url_for("auction_detail", auction_id=auction.id))
    try:
        amount = Decimal(request.form.get("amount", "").strip())
        if not amount.is_finite() or amount <= auction.highest_bid or amount <= 0 or amount > Decimal("99999999.99"):
            raise InvalidOperation
        amount = amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        flash(f"Your bid must be greater than ₹{auction.highest_bid:,.2f}.", "error")
        return redirect(url_for("auction_detail", auction_id=auction.id))
    # Re-check the current price immediately before commit. For a classroom demo this is
    # sufficient; production systems should use database row locks/transaction isolation.
    db.session.refresh(auction)
    if amount <= auction.highest_bid or auction.ends_at <= utcnow():
        flash(f"The current bid changed or the auction ended. Bid more than ₹{auction.highest_bid:,.2f}.", "error")
        return redirect(url_for("auction_detail", auction_id=auction.id))
    db.session.add(Bid(auction_id=auction.id, user_id=user.id, amount=amount))
    db.session.commit()
    flash("Your simulated bid was recorded successfully.", "success")
    return redirect(url_for("auction_detail", auction_id=auction.id))

@app.route("/my-bids")
def my_bids():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    bids = Bid.query.filter_by(user_id=user.id).order_by(Bid.created_at.desc()).all()
    return render_template("my_bids.html", bids=bids)

@app.route("/watchlist")
def watchlist():
    user = current_user()
    if not user:
        flash("Please log in to view your watchlist.", "error")
        return redirect(url_for("login"))
    entries = Watchlist.query.filter_by(user_id=user.id).order_by(Watchlist.created_at.desc()).all()
    return render_template("watchlist.html", entries=entries)

@app.route("/auction/<int:auction_id>/watchlist", methods=["POST"])
def toggle_watchlist(auction_id):
    user = current_user()
    if not user:
        flash("Please log in to save auctions.", "error")
        return redirect(url_for("login"))
    auction = db.session.get(Auction, auction_id) or abort(404)
    if auction.is_hidden and not user.is_admin:
        abort(404)
    entry = Watchlist.query.filter_by(user_id=user.id, auction_id=auction.id).first()
    if entry:
        db.session.delete(entry)
        db.session.commit()
        flash("Auction removed from your watchlist.", "success")
    else:
        db.session.add(Watchlist(user_id=user.id, auction_id=auction.id))
        db.session.commit()
        flash("Auction saved to your watchlist.", "success")
    return redirect(url_for("auction_detail", auction_id=auction.id))

@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "General").strip() or "General"
        image_url = request.form.get("image_url", "").strip()
        try:
            price = Decimal(request.form.get("starting_price", "").strip()).quantize(Decimal("0.01"))
            duration = int(request.form.get("duration_hours", "24"))
            if not price.is_finite() or price <= 0 or duration < 1 or duration > 720:
                raise ValueError
        except (InvalidOperation, ValueError):
            flash("Enter a valid positive price and duration between 1 and 720 hours.", "error")
            return redirect(url_for("admin"))
        if not title or len(title) > 140 or not description or len(description) > 5000:
            flash("Title and description are required and must be within the length limits.", "error")
            return redirect(url_for("admin"))
        if image_url and not image_url.startswith(("https://", "http://")):
            flash("Image URL must begin with http:// or https://.", "error")
            return redirect(url_for("admin"))
        auction = Auction(title=title, description=description, category=category[:60],
                          image_url=image_url or None, starting_price=price,
                          ends_at=utcnow() + timedelta(hours=duration))
        db.session.add(auction)
        db.session.commit()
        flash("Auction listing created.", "success")
        return redirect(url_for("auction_detail", auction_id=auction.id))
    auctions = Auction.query.order_by(Auction.created_at.desc()).all()
    stats = {
        "users": User.query.count(),
        "auctions": Auction.query.count(),
        "active": Auction.query.filter(Auction.ends_at > utcnow(), Auction.is_hidden.is_(False)).count(),
        "bids": Bid.query.count(),
    }
    return render_template("admin.html", auctions=auctions, stats=stats)

@app.route("/admin/auction/<int:auction_id>/visibility", methods=["POST"])
@admin_required
def toggle_visibility(auction_id):
    auction = db.session.get(Auction, auction_id) or abort(404)
    auction.is_hidden = not auction.is_hidden
    db.session.commit()
    flash("Auction visibility updated.", "success")
    return redirect(url_for("admin"))

@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404

def seed_data():
    if not User.query.filter_by(email="admin@auction.demo").first():
        db.session.add(User(name="Demo Admin", email="admin@auction.demo",
                            password_hash=generate_password_hash("Admin123!"), is_admin=True))
    if Auction.query.count() == 0:
        samples = [
            ("Wireless Headphones", "Over-ear wireless headphones for music, study sessions and travel.", "Electronics", "https://images.unsplash.com/photo-1509358271058-acd22cc93898?auto=format&fit=crop&w=900&q=80", Decimal("1200.00"), 48),
            ("Classic Wristwatch", "A minimal classic-style wristwatch. Demo item; no physical sale.", "Accessories", "https://images.unsplash.com/photo-1524805444758-089113d48a6d?auto=format&fit=crop&w=900&q=80", Decimal("1800.00"), 36),
            ("DSLR Camera", "Sample DSLR camera listing for testing the bidding flow.", "Electronics", "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?auto=format&fit=crop&w=900&q=80", Decimal("8500.00"), 72),
            ("Study Desk Lamp", "Adjustable desk lamp suitable for a study table.", "Home", "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=900&q=80", Decimal("450.00"), 24),
            ("Running Shoes", "Lightweight sports shoes displayed as a sample auction product.", "Fashion", "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=80", Decimal("999.00"), 30),
            ("Mechanical Keyboard", "Mechanical keyboard for a desk setup. Sample listing only.", "Electronics", "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=900&q=80", Decimal("1500.00"), 60),
        ]
        for title, description, category, image, price, hours in samples:
            db.session.add(Auction(title=title, description=description, category=category,
                                   image_url=image, starting_price=price,
                                   ends_at=utcnow() + timedelta(hours=hours)))
    db.session.commit()

with app.app_context():
    db.create_all()
    seed_data()

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
