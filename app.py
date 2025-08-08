\
import os
import sys
import argparse
from datetime import datetime
from random import randint
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "app.db"))


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

db = SQLAlchemy(app)

# ---------------------------
# Models
# ---------------------------

class House(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    join_code = db.Column(db.String(20), nullable=False)

class Village(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)

class Store(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    village_id = db.Column(db.Integer, db.ForeignKey('village.id'), nullable=False)
    village = db.relationship('Village', backref=db.backref('stores', lazy=True))

class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    house_id = db.Column(db.Integer, db.ForeignKey('house.id'), nullable=False)
    house = db.relationship('House', backref=db.backref('trips', lazy=True))
    village_id = db.Column(db.Integer, db.ForeignKey('village.id'), nullable=False)
    village = db.relationship('Village', backref=db.backref('trips', lazy=True))
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=True)
    store = db.relationship('Store', backref=db.backref('trips', lazy=True))
    departure_time = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.String(300), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="planned")  # planned, completed

class RequestItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    house_id = db.Column(db.Integer, db.ForeignKey('house.id'), nullable=False)  # requester
    house = db.relationship('House', backref=db.backref('requests', lazy=True))
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    store = db.relationship('Store', backref=db.backref('requests', lazy=True))
    item_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price_limit = db.Column(db.Float, nullable=True)
    notes = db.Column(db.String(300), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="open")  # open, claimed, fulfilled, cancelled
    claimed_by_trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=True)
    fulfilled_by_trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Delivery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('request_item.id'), nullable=False)
    request = db.relationship('RequestItem', backref=db.backref('delivery', uselist=False))
    trip_id = db.Column(db.Integer, db.ForeignKey('trip.id'), nullable=False)
    trip = db.relationship('Trip', backref=db.backref('deliveries', lazy=True))
    delivered_by_house_id = db.Column(db.Integer, db.ForeignKey('house.id'), nullable=False)
    delivered_by_house = db.relationship('House', foreign_keys=[delivered_by_house_id])
    delivered_to_house_id = db.Column(db.Integer, db.ForeignKey('house.id'), nullable=False)
    delivered_to_house = db.relationship('House', foreign_keys=[delivered_to_house_id])
    item_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    delivered_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.String(300), nullable=True)

class LedgerEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_house_id = db.Column(db.Integer, db.ForeignKey('house.id'), nullable=False)
    from_house = db.relationship('House', foreign_keys=[from_house_id])
    to_house_id = db.Column(db.Integer, db.ForeignKey('house.id'), nullable=False)
    to_house = db.relationship('House', foreign_keys=[to_house_id])
    amount = db.Column(db.Float, nullable=False)  # positive charge; negative for payment/refund
    entry_type = db.Column(db.String(20), default="charge")  # charge, payment
    description = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    delivery_id = db.Column(db.Integer, db.ForeignKey('delivery.id'), nullable=True)


# Admin config
app.config["ADMIN_PIN"] = os.environ.get("ADMIN_PIN", "1234")

def require_admin():
    if not session.get("is_admin"):
        flash("Admin access required.", "danger")
        return redirect(url_for("admin_login"))
    return None

def rand_code():
    from random import randint
    return f"{randint(100000, 999999)}"

def house_in_use(house_id: int) -> bool:
    # any references in Trips, Requests, Deliveries, LedgerEntries?
    from sqlalchemy import func
    cnt = 0
    cnt += db.session.query(func.count()).select_from(Trip).filter(Trip.house_id==house_id).scalar()
    cnt += db.session.query(func.count()).select_from(RequestItem).filter(RequestItem.house_id==house_id).scalar()
    cnt += db.session.query(func.count()).select_from(Delivery).filter(Delivery.delivered_by_house_id==house_id).scalar()
    cnt += db.session.query(func.count()).select_from(Delivery).filter(Delivery.delivered_to_house_id==house_id).scalar()
    cnt += db.session.query(func.count()).select_from(LedgerEntry).filter((LedgerEntry.from_house_id==house_id)|(LedgerEntry.to_house_id==house_id)).scalar()
    return cnt > 0

def village_in_use(village_id: int) -> bool:
    from sqlalchemy import func
    cnt = 0
    cnt += db.session.query(func.count()).select_from(Store).filter(Store.village_id==village_id).scalar()
    cnt += db.session.query(func.count()).select_from(Trip).filter(Trip.village_id==village_id).scalar()
    return cnt > 0

def store_in_use(store_id: int) -> bool:
    from sqlalchemy import func
    cnt = 0
    cnt += db.session.query(func.count()).select_from(RequestItem).filter(RequestItem.store_id==store_id).scalar()
    cnt += db.session.query(func.count()).select_from(Trip).filter(Trip.store_id==store_id).scalar()
    return cnt > 0
# ---------------------------
# Helpers
# ---------------------------

def require_login():
    if not session.get("house_id"):
        flash("Please sign in first.", "info")
        return redirect(url_for("signup"))
    return None

def current_house():
    if session.get("house_id"):
        return db.session.get(House, session["house_id"])
    return None

# ---------------------------
# Routes
# ---------------------------

@app.route("/")
def dashboard():
    open_requests = RequestItem.query.filter(RequestItem.status=="open").order_by(RequestItem.created_at.desc()).limit(10).all()
    upcoming_trips = Trip.query.filter(Trip.status=="planned").order_by(Trip.departure_time.asc().nulls_last()).limit(10).all()
    return render_template("dashboard.html", open_requests=open_requests, upcoming_trips=upcoming_trips)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    houses = House.query.order_by(House.id.asc()).all()
    if request.method == "POST":
        house_id = int(request.form.get("house_id"))
        join_code = request.form.get("join_code", "").strip()
        display_name = request.form.get("display_name", "").strip()
        house = db.session.get(House, house_id)
        if not house or house.join_code != join_code:
            flash("Wrong house or join code.", "danger")
            return render_template("signup.html", houses=houses)
        session["house_id"] = house.id
        session["house_name"] = house.name
        session["display_name"] = display_name
        flash(f"Signed in as {display_name} ({house.name}).", "success")
        return redirect(url_for("dashboard"))
    return render_template("signup.html", houses=houses)

@app.route("/logout")
def logout():
    session.clear()
    flash("Signed out.", "success")
    return redirect(url_for("dashboard"))

# Requests
@app.route("/requests")
def list_requests():
    open_requests = RequestItem.query.filter(RequestItem.status.in_(["open", "claimed"])).order_by(RequestItem.created_at.desc()).all()
    # last 10 deliveries
    recent_deliveries = (
        db.session.query(Delivery)
        .order_by(Delivery.delivered_at.desc())
        .limit(10)
        .all()
    )
    # map for template row building
    recent_rows = []
    for d in recent_deliveries:
        recent_rows.append(type("Row", (), {
            "item_name": d.item_name,
            "quantity": d.quantity,
            "store_name": f"{d.request.store.name} ({d.request.store.village.name})",
            "to_house": d.delivered_to_house.name,
            "from_house": d.delivered_by_house.name,
            "total_price": d.total_price
        }))
    return render_template("requests.html", open_requests=open_requests, recent_deliveries=recent_rows)

@app.route("/requests/new", methods=["GET", "POST"])
def new_request():
    stores = Store.query.order_by(Store.name.asc()).all()
    if request.method == "POST":
        if not session.get("house_id"):
            return require_login()
        store_id = int(request.form["store_id"])
        item_name = request.form["item_name"].strip()
        quantity = int(request.form.get("quantity", 1))
        price_limit_raw = request.form.get("price_limit")
        price_limit = float(price_limit_raw) if price_limit_raw else None
        notes = request.form.get("notes", "").strip()
        r = RequestItem(
            house_id=session["house_id"],
            store_id=store_id,
            item_name=item_name,
            quantity=quantity,
            price_limit=price_limit,
            notes=notes
        )
        db.session.add(r)
        db.session.commit()
        flash("Request created.", "success")
        return redirect(url_for("list_requests"))
    return render_template("new_request.html", stores=stores)

@app.route("/requests/<int:request_id>/cancel", methods=["POST"])
def cancel_request(request_id):
    r = db.session.get(RequestItem, request_id)
    if not r:
        flash("Not found.", "danger")
        return redirect(url_for("list_requests"))
    if r.house_id != session.get("house_id"):
        flash("You can only cancel your own request.", "danger")
        return redirect(url_for("list_requests"))
    if r.status in ["fulfilled", "cancelled"]:
        flash("This request cannot be cancelled.", "warning")
        return redirect(url_for("list_requests"))
    r.status = "cancelled"
    db.session.commit()
    flash("Request cancelled.", "success")
    return redirect(url_for("list_requests"))

# Trips
@app.route("/trips")
def list_trips():
    upcoming = Trip.query.filter(Trip.status=="planned").order_by(Trip.departure_time.asc().nulls_last()).all()
    recent = Trip.query.filter(Trip.status=="completed").order_by(Trip.departure_time.desc().nulls_last()).limit(10).all()
    return render_template("trips.html", upcoming=upcoming, recent=recent)

@app.route("/trips/new", methods=["GET", "POST"])
def new_trip():
    villages = Village.query.order_by(Village.name.asc()).all()
    stores = Store.query.order_by(Store.name.asc()).all()
    if request.method == "POST":
        if not session.get("house_id"):
            return require_login()
        village_id = int(request.form["village_id"])
        store_id_raw = request.form.get("store_id")
        store_id = int(store_id_raw) if store_id_raw else None
        departure_raw = request.form.get("departure_time", "").strip()
        departure_time = datetime.fromisoformat(departure_raw) if departure_raw else None
        notes = request.form.get("notes", "").strip()
        t = Trip(
            house_id=session["house_id"],
            village_id=village_id,
            store_id=store_id,
            departure_time=departure_time,
            notes=notes,
            status="planned"
        )
        db.session.add(t)
        db.session.commit()
        flash("Trip created.", "success")
        return redirect(url_for("trip_detail", trip_id=t.id))
    return render_template("new_trip.html", villages=villages, stores=stores)

@app.route("/trips/<int:trip_id>")
def trip_detail(trip_id):
    t = db.session.get(Trip, trip_id)
    if not t:
        flash("Trip not found.", "danger")
        return redirect(url_for("list_trips"))
    # matching requests: same village and (store==trip.store or any)
    q = RequestItem.query.filter(RequestItem.status=="open")
    if t.store_id:
        q = q.filter(RequestItem.store_id == t.store_id)
    else:
        # any store in the same village
        store_ids = [s.id for s in t.village.stores]
        if store_ids:
            q = q.filter(RequestItem.store_id.in_(store_ids))
        else:
            q = q.filter(False)  # no stores
    matching_requests = q.order_by(RequestItem.created_at.asc()).all()

    claimed_requests = RequestItem.query.filter(RequestItem.claimed_by_trip_id==t.id).order_by(RequestItem.created_at.asc()).all()
    return render_template("trip_detail.html", trip=t, matching_requests=matching_requests, claimed_requests=claimed_requests)

@app.route("/trips/<int:trip_id>/claim", methods=["POST"])
def claim_requests(trip_id):
    t = db.session.get(Trip, trip_id)
    if not t:
        flash("Trip not found.", "danger")
        return redirect(url_for("list_trips"))
    if t.house_id != session.get("house_id"):
        flash("Only the trip owner can claim requests.", "danger")
        return redirect(url_for("trip_detail", trip_id=trip_id))
    ids = request.form.getlist("request_ids")
    if not ids:
        flash("No requests selected.", "warning")
        return redirect(url_for("trip_detail", trip_id=trip_id))
    count = 0
    for rid in ids:
        r = db.session.get(RequestItem, int(rid))
        if not r or r.status != "open":
            continue
        # ensure still matches
        if t.store_id and r.store_id != t.store_id:
            continue
        if not t.store_id and r.store.village_id != t.village_id:
            continue
        r.status = "claimed"
        r.claimed_by_trip_id = t.id
        count += 1
    db.session.commit()
    flash(f"Claimed {count} request(s).", "success")
    return redirect(url_for("trip_detail", trip_id=trip_id))

@app.route("/trips/<int:trip_id>/deliver", methods=["GET", "POST"])
def deliver_trip(trip_id):
    t = db.session.get(Trip, trip_id)
    if not t:
        flash("Trip not found.", "danger")
        return redirect(url_for("list_trips"))
    if t.house_id != session.get("house_id"):
        flash("Only the trip owner can record deliveries.", "danger")
        return redirect(url_for("trip_detail", trip_id=trip_id))

    claimed = RequestItem.query.filter(RequestItem.claimed_by_trip_id==t.id, RequestItem.status=="claimed").all()

    if request.method == "POST":
        deliver_ids = request.form.getlist("deliver_ids")
        delivered_count = 0
        for r in claimed:
            if str(r.id) not in deliver_ids:
                continue
            unit_price_raw = request.form.get(f"unit_price_{r.id}")
            try:
                unit_price = float(unit_price_raw)
            except (TypeError, ValueError):
                unit_price = 0.0
            total_price = unit_price * r.quantity

            d = Delivery(
                request_id=r.id,
                trip_id=t.id,
                delivered_by_house_id=t.house_id,
                delivered_to_house_id=r.house_id,
                item_name=r.item_name,
                quantity=r.quantity,
                unit_price=unit_price,
                total_price=total_price,
            )
            db.session.add(d)
            db.session.flush()  # get d.id

            # ledger charge: requester owes traveler
            entry = LedgerEntry(
                from_house_id=r.house_id,
                to_house_id=t.house_id,
                amount=total_price,
                entry_type="charge",
                description=f"Delivery of {r.item_name} x{r.quantity} from {r.store.name}",
                delivery_id=d.id
            )
            db.session.add(entry)

            r.status = "fulfilled"
            r.fulfilled_by_trip_id = t.id
            delivered_count += 1

        if delivered_count > 0:
            db.session.commit()
            flash(f"Recorded {delivered_count} delivered item(s).", "success")
        else:
            flash("No items delivered.", "warning")
        return redirect(url_for("trip_detail", trip_id=trip_id))

    return render_template("deliver_trip.html", trip=t, claimed_requests=claimed)

@app.route("/trips/<int:trip_id>/complete", methods=["POST"])
def complete_trip(trip_id):
    t = db.session.get(Trip, trip_id)
    if not t:
        flash("Trip not found.", "danger")
        return redirect(url_for("list_trips"))
    if t.house_id != session.get("house_id"):
        flash("Only the trip owner can complete the trip.", "danger")
        return redirect(url_for("trip_detail", trip_id=trip_id))
    t.status = "completed"
    db.session.commit()
    flash("Trip marked as completed.", "success")
    return redirect(url_for("trip_detail", trip_id=trip_id))

# Stores & villages
@app.route("/stores")
def stores():
    villages = Village.query.order_by(Village.name.asc()).all()
    stores = Store.query.order_by(Store.name.asc()).all()
    return render_template("stores.html", villages=villages, stores=stores)

@app.route("/stores/add", methods=["POST"])
def add_store():
    village_id = int(request.form["village_id"])
    name = request.form["name"].strip()
    if not name:
        flash("Store name is required.", "danger")
        return redirect(url_for("stores"))
    s = Store(name=name, village_id=village_id)
    db.session.add(s)
    db.session.commit()
    flash("Store added.", "success")
    return redirect(url_for("stores"))

# Balances & payments
@app.route("/balances")
def balances():
    houses = House.query.order_by(House.id.asc()).all()
    # matrix[(from, to)] = sum(amounts)
    entries = LedgerEntry.query.order_by(LedgerEntry.created_at.desc()).all()
    matrix = {}
    for e in entries:
        key = (e.from_house_id, e.to_house_id)
        matrix[key] = matrix.get(key, 0.0) + e.amount
    recent_entries = LedgerEntry.query.order_by(LedgerEntry.created_at.desc()).limit(15).all()
    return render_template("balances.html", houses=houses, matrix=matrix, recent_entries=recent_entries)

@app.route("/balances/pay", methods=["POST"])
def record_payment():
    if not session.get("house_id"):
        return require_login()
    from_house_id = session["house_id"]
    to_house_id = int(request.form["to_house_id"])
    amount = float(request.form["amount"])
    note = request.form.get("note", "").strip()
    if amount <= 0 or from_house_id == to_house_id:
        flash("Invalid payment.", "danger")
        return redirect(url_for("balances"))
    entry = LedgerEntry(
        from_house_id=from_house_id,
        to_house_id=to_house_id,
        amount=-amount,  # payment reduces balance
        entry_type="payment",
        description=note or "Payment recorded"
    )
    db.session.add(entry)
    db.session.commit()
    flash("Payment recorded.", "success")
    return redirect(url_for("balances"))


# ---------------------------
# Admin routes
# ---------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pin = (request.form.get("pin") or "").strip()
        if pin == app.config["ADMIN_PIN"]:
            session["is_admin"] = True
            flash("Admin logged in.", "success")
            return redirect(url_for("admin"))
        else:
            flash("Wrong PIN.", "danger")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Admin logged out.", "success")
    return redirect(url_for("dashboard"))

@app.route("/admin")
def admin():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    houses = House.query.order_by(House.id.asc()).all()
    villages = Village.query.order_by(Village.name.asc()).all()
    stores = Store.query.order_by(Store.name.asc()).all()
    return render_template("admin.html", houses=houses, villages=villages, stores=stores)

# Houses
@app.route("/admin/houses/add", methods=["POST"])
def admin_add_house():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    name = request.form.get("name","").strip()
    if not name:
        flash("House name required.", "danger")
        return redirect(url_for("admin"))
    h = House(name=name, join_code=rand_code())
    db.session.add(h)
    db.session.commit()
    flash("House added.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/houses/<int:house_id>/update", methods=["POST"])
def admin_update_house(house_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    h = db.session.get(House, house_id)
    if not h:
        flash("House not found.", "danger")
        return redirect(url_for("admin"))
    name = request.form.get("name","").strip()
    if not name:
        flash("Name required.", "danger")
        return redirect(url_for("admin"))
    h.name = name
    db.session.commit()
    flash("House updated.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/houses/<int:house_id>/regen", methods=["POST"])
def admin_regen_code(house_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    h = db.session.get(House, house_id)
    if not h:
        flash("House not found.", "danger")
        return redirect(url_for("admin"))
    h.join_code = rand_code()
    db.session.commit()
    flash(f"New join code for {h.name}: {h.join_code}", "warning")
    return redirect(url_for("admin"))

@app.route("/admin/houses/regen_all", methods=["POST"])
def admin_regen_all_codes():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    houses = House.query.all()
    for h in houses:
        h.join_code = rand_code()
    db.session.commit()
    flash("Regenerated all house join codes.", "warning")
    return redirect(url_for("admin"))

@app.route("/admin/houses/<int:house_id>/delete", methods=["POST"])
def admin_delete_house(house_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    h = db.session.get(House, house_id)
    if not h:
        flash("House not found.", "danger")
        return redirect(url_for("admin"))
    if house_in_use(house_id):
        flash("Cannot delete: house is referenced by trips/requests/deliveries/ledger.", "danger")
        return redirect(url_for("admin"))
    db.session.delete(h)
    db.session.commit()
    flash("House deleted.", "success")
    return redirect(url_for("admin"))

# Villages
@app.route("/admin/villages/add", methods=["POST"])
def admin_add_village():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    name = request.form.get("name","").strip()
    if not name:
        flash("Village name required.", "danger")
        return redirect(url_for("admin"))
    v = Village(name=name)
    db.session.add(v)
    db.session.commit()
    flash("Village added.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/villages/<int:village_id>/update", methods=["POST"])
def admin_update_village(village_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    v = db.session.get(Village, village_id)
    if not v:
        flash("Village not found.", "danger")
        return redirect(url_for("admin"))
    name = request.form.get("name","").strip()
    if not name:
        flash("Name required.", "danger")
        return redirect(url_for("admin"))
    v.name = name
    db.session.commit()
    flash("Village updated.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/villages/<int:village_id>/delete", methods=["POST"])
def admin_delete_village(village_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    v = db.session.get(Village, village_id)
    if not v:
        flash("Village not found.", "danger")
        return redirect(url_for("admin"))
    if village_in_use(village_id):
        flash("Cannot delete: village has stores or trips.", "danger")
        return redirect(url_for("admin"))
    db.session.delete(v)
    db.session.commit()
    flash("Village deleted.", "success")
    return redirect(url_for("admin"))

# Stores
@app.route("/admin/stores/add", methods=["POST"])
def admin_add_store():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    name = request.form.get("name","").strip()
    village_id = int(request.form.get("village_id","0"))
    if not name or not village_id:
        flash("Store name and village required.", "danger")
        return redirect(url_for("admin"))
    s = Store(name=name, village_id=village_id)
    db.session.add(s)
    db.session.commit()
    flash("Store added.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/stores/<int:store_id>/update", methods=["POST"])
def admin_update_store(store_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    s = db.session.get(Store, store_id)
    if not s:
        flash("Store not found.", "danger")
        return redirect(url_for("admin"))
    name = request.form.get("name","").strip()
    village_id = int(request.form.get("village_id","0"))
    if not name or not village_id:
        flash("Name and village required.", "danger")
        return redirect(url_for("admin"))
    s.name = name
    s.village_id = village_id
    db.session.commit()
    flash("Store updated.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/stores/<int:store_id>/delete", methods=["POST"])
def admin_delete_store(store_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    s = db.session.get(Store, store_id)
    if not s:
        flash("Store not found.", "danger")
        return redirect(url_for("admin"))
    if store_in_use(store_id):
        flash("Cannot delete: store has requests or trips.", "danger")
        return redirect(url_for("admin"))
    db.session.delete(s)
    db.session.commit()
    flash("Store deleted.", "success")
    return redirect(url_for("admin"))
# ---------------------------
# DB init
# ---------------------------

def init_db():
    db.drop_all()
    db.create_all()

    # seed houses with random 6-digit codes
    houses = []
    codes_output = []
    for i in range(1, 5):
        code = f"{randint(100000, 999999)}"
        h = House(name=f"House {i}", join_code=code)
        db.session.add(h)
        db.session.flush()
        houses.append(h)
        codes_output.append(f"{h.name}: {code}")
    # villages & stores
    v1 = Village(name="North Village")
    v2 = Village(name="South Village")
    db.session.add_all([v1, v2])
    db.session.flush()
    s1 = Store(name="Lidl", village_id=v1.id)
    s2 = Store(name="Pharmacy", village_id=v1.id)
    s3 = Store(name="Hardware", village_id=v2.id)
    s4 = Store(name="Supermarket", village_id=v2.id)
    db.session.add_all([s1, s2, s3, s4])
    db.session.commit()

    with open(os.path.join(BASE_DIR, "house_codes.txt"), "w") as f:
        f.write("\n".join(codes_output))

    print("Database initialized.")
    print("House join codes:")
    for line in codes_output:
        print("  ", line)
    print("Codes are also saved to house_codes.txt")

# ---------------------------
# CLI
# ---------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--initdb", action="store_true", help="Initialize database with sample data")
    args = parser.parse_args()
    if args.initdb:
        with app.app_context():
            init_db()
        sys.exit(0)
    # run the dev server if invoked directly without Flask CLI
    app.run(debug=True)
