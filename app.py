from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
import os
from dotenv import load_dotenv
from datetime import datetime
import hashlib

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 't1cket_secret_2024')

# ── DB Connection ──────────────────────────────────────────────────────────────
def get_db(autocommit=True):
    # Railway/Cloud Fallbacks: Detect multiple naming conventions (underscore vs no-underscore)
    host = os.getenv('MYSQLHOST', os.getenv('DB_HOST', 'localhost'))
    user = os.getenv('MYSQLUSER', os.getenv('DB_USER', 'root'))
    password = os.getenv('MYSQLPASSWORD', os.getenv('DB_PASSWORD', ''))
    database = os.getenv('MYSQLDATABASE', os.getenv('MYSQL_DATABASE', os.getenv('DB_NAME', 't1cket')))
    port = int(os.getenv('MYSQLPORT', 3306))

    conn = mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port
    )
    conn.autocommit = autocommit
    return conn

# ── Auth helpers ───────────────────────────────────────────────────────────────
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('username') != 'admin':
            flash('Access denied. Admin privileges required.')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    from datetime import date
    return render_template('index.html', today=date.today().isoformat())

@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        cursor = db.cursor(dictionary=True)
        hashed = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute("SELECT * FROM users WHERE username=%s AND password_hash=%s", (username, hashed))
        user = cursor.fetchone()
        cursor.close(); db.close()
        if user:
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('auth.html', active_mode='login')


@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT username, email, full_name, created_at FROM users WHERE user_id = %s", (session['user_id'],))
    user_info = cursor.fetchone()
    cursor.close(); db.close()
    return render_template('profile.html', user=user_info)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email    = request.form['email']
        password = request.form['password']
        name     = request.form['name']
        db = get_db()
        cursor = db.cursor()
        try:
            hashed = hashlib.sha256(password.encode()).hexdigest()
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, full_name) VALUES (%s,%s,%s,%s)",
                (username, email, hashed, name)
            )
            flash('Account created! Please log in.')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('Username or email already exists.')
        finally:
            cursor.close(); db.close()
    return render_template('auth.html', active_mode='register')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/search', methods=['GET', 'POST'])
def search():
    trains = []
    search_params = {}
    if request.method == 'POST':
        from_city = request.form['from_city']
        to_city   = request.form['to_city']
        travel_date = request.form['travel_date']
        travel_class = request.form.get('travel_class', 'ALL')
        search_params = {
            'from_city': from_city,
            'to_city': to_city,
            'travel_date': travel_date,
            'travel_class': travel_class
        }
        db = get_db()
        cursor = db.cursor(dictionary=True)
        # Using string aliases to ensure ui templates aren't broken by the schema upgrade
        query = """
            SELECT s.schedule_id, t.train_number, t.train_name, t.train_type,
                   s.departure_time, s.arrival_time, s.travel_date,
                   s.available_sleeper, s.available_ac3, s.available_ac2, s.available_ac1,
                   s.price_sl AS price_sleeper, 
                   s.price_3ac AS price_ac3, 
                   s.price_2ac AS price_ac2, 
                   s.price_1ac AS price_ac1,
                   t.from_station, t.to_station
            FROM schedules s
            JOIN trains t ON s.train_id = t.train_id
            WHERE t.from_station = %s AND t.to_station = %s AND s.travel_date = %s
        """
        cursor.execute(query, (from_city, to_city, travel_date))
        trains = cursor.fetchall()
        
        # MySQL date/time delta objects need converting for Jinja formatting
        for t in trains:
            if t['departure_time']:
                # converting timedelta to string essentially mapped to %H:%M
                total_seconds = int(t['departure_time'].total_seconds())
                t['departure_time'] = type('obj', (object,), {'strftime': lambda self, f, s=total_seconds: f"{s//3600:02d}:{(s%3600)//60:02d}"})()
            if t['arrival_time']:
                total_seconds = int(t['arrival_time'].total_seconds())
                t['arrival_time'] = type('obj', (object,), {'strftime': lambda self, f, s=total_seconds: f"{s//3600:02d}:{(s%3600)//60:02d}"})()

        cursor.close(); db.close()
    return render_template('search.html', trains=trains, search_params=search_params)


@app.route('/booking/<int:schedule_id>', methods=['GET', 'POST'])
@login_required
def booking(schedule_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.*, 
            s.price_sl AS price_sleeper, s.price_3ac AS price_ac3, s.price_2ac AS price_ac2, s.price_1ac AS price_ac1,
            t.train_name, t.train_number, t.train_type, t.from_station, t.to_station
        FROM schedules s JOIN trains t ON s.train_id = t.train_id
        WHERE s.schedule_id = %s
    """, (schedule_id,))
    schedule = cursor.fetchone()

    # Get booked seats directly using our abstracted View!
    cursor.execute("SELECT seat_number, travel_class FROM available_seats_view WHERE schedule_id = %s", (schedule_id,))
    booked = cursor.fetchall()
    booked_seats = [(b['seat_number'], b['travel_class']) for b in booked]
    
    cursor.close(); db.close()
    selected_class = request.args.get('class', 'Sleeper')
    return render_template('booking.html', schedule=schedule, booked_seats=booked_seats, selected_class=selected_class)


@app.route('/confirm_booking', methods=['POST'])
@login_required
def confirm_booking():
    schedule_id  = int(request.form['schedule_id'])
    seat_number  = request.form['seat_number']
    travel_class = request.form['travel_class']
    passenger_name = request.form['passenger_name']
    passenger_age  = request.form['passenger_age']
    user_id = session['user_id']

    # Retrieve connection with specific autocommit=False to enforce ACID
    db = get_db(autocommit=False)
    cursor = db.cursor(dictionary=True)
    
    try:
        cursor.execute("START TRANSACTION")

        # TRANSACTIONS & CONCURRENCY: Pessimistic Row-level Locking execution
        # By querying the booking with FOR UPDATE, we lock this exact coordinate 
        # so no other active socket thread can book it simultaneously!
        cursor.execute("""
            SELECT status FROM bookings 
            WHERE schedule_id=%s AND travel_class=%s AND seat_number=%s 
            FOR UPDATE
        """, (schedule_id, travel_class, seat_number))
        existing = cursor.fetchone()
        
        if existing and existing['status'] == 'confirmed':
            db.rollback()
            flash('Seat just got booked by someone else! Please choose another.')
            return redirect(url_for('booking', schedule_id=schedule_id))

        cursor.execute("SELECT * FROM schedules WHERE schedule_id = %s", (schedule_id,))
        schedule = cursor.fetchone()

        # Map UI class identifiers to underlying schema
        class_map = {
            'Sleeper': ('price_sl', 'available_sleeper'),
            'AC3':     ('price_3ac', 'available_ac3'),
            'AC2':     ('price_2ac', 'available_ac2'),
            'AC1':     ('price_1ac', 'available_ac1'),
        }
        price_col, avail_col = class_map[travel_class]
        price = schedule[price_col]
        avail = schedule[avail_col]

        if avail <= 0:
            db.rollback()
            flash('No seats available in this class.')
            return redirect(url_for('booking', schedule_id=schedule_id))

        # Atomic Insert (Safe due to transaction block)
        cursor.execute("""
            INSERT INTO bookings (user_id, schedule_id, seat_number, travel_class, passenger_name, passenger_age, price_paid, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'confirmed')
        """, (user_id, schedule_id, seat_number, travel_class, passenger_name, passenger_age, price))

        # Decrement hardware availability
        cursor.execute(f"UPDATE schedules SET {avail_col} = {avail_col} - 1 WHERE schedule_id = %s", (schedule_id,))

        db.commit()
        flash('Booking confirmed!')
        return redirect(url_for('dashboard'))

    except mysql.connector.Error as e:
        db.rollback()
        flash('Booking transaction violated. System halted mapping block.')
        return redirect(url_for('booking', schedule_id=schedule_id))
    finally:
        cursor.close(); db.close()


@app.route('/cancel_booking/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    db = get_db(autocommit=False)
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("START TRANSACTION")
        # Lock the specific booking safely
        cursor.execute("SELECT * FROM bookings WHERE booking_id = %s AND user_id = %s FOR UPDATE", (booking_id, session['user_id']))
        booking = cursor.fetchone()
        
        if not booking or booking['status'] == 'cancelled':
            db.rollback()
            flash('Invalid booking or already cancelled.')
            return redirect(url_for('dashboard'))
            
        schedule_id = booking['schedule_id']
        t_class = booking['travel_class']
        
        # Map UI class identifiers to underlying db schema
        class_map = {
            'Sleeper': 'available_sleeper',
            'AC3':     'available_ac3',
            'AC2':     'available_ac2',
            'AC1':     'available_ac1',
        }
        avail_col = class_map.get(t_class)
        
        if avail_col:
            cursor.execute("UPDATE bookings SET status='cancelled' WHERE booking_id = %s", (booking_id,))
            cursor.execute(f"UPDATE schedules SET {avail_col} = {avail_col} + 1 WHERE schedule_id = %s", (schedule_id,))
            db.commit()
            flash('Booking successfully cancelled.')
    except mysql.connector.Error as e:
        db.rollback()
        flash('Cancellation failed due to system error.')
    finally:
        cursor.close(); db.close()
        
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    # Using our custom generated View `user_boarding_pass_view`
    cursor.execute("""
        SELECT * FROM user_boarding_pass_view 
        WHERE user_id = %s 
        ORDER BY travel_date DESC
    """, (session['user_id'],))
    bookings = cursor.fetchall()
    
    # Compatibility aliasing for the dashboard jinja template 
    for b in bookings:
        b['price'] = b['price_paid']
        b['class'] = b['travel_class']
        
        # MySQL time formatting wrapper 
        if b['departure_time']:
            ts = int(b['departure_time'].total_seconds())
            b['departure_time'] = f"{ts//3600:02d}:{(ts%3600)//60:02d}:00"
        if b['arrival_time']:
            ts = int(b['arrival_time'].total_seconds())
            b['arrival_time'] = f"{ts//3600:02d}:{(ts%3600)//60:02d}:00"
            
    cursor.close(); db.close()
    return render_template('dashboard.html', bookings=bookings, username=session['username'])


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS c FROM users")
    user_count = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) AS c FROM trains")
    train_count = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) AS c FROM stations")
    station_count = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) AS c FROM schedules")
    schedule_count = cursor.fetchone()['c']
    cursor.execute("SELECT COUNT(*) AS c FROM bookings WHERE status='confirmed'")
    booking_count = cursor.fetchone()['c']
    cursor.execute("SELECT SUM(price_paid) AS rev FROM bookings WHERE status='confirmed'")
    revenue = cursor.fetchone()['rev'] or 0
    cursor.close(); db.close()
    stats = {
        'users': user_count, 'trains': train_count, 'stations': station_count,
        'schedules': schedule_count, 'bookings': booking_count, 'revenue': float(revenue)
    }
    return render_template('admin/dashboard.html', stats=stats)


# ── ADMIN: TRAINS ──────────────────────────────────────────────────────────────

@app.route('/admin/trains')
@admin_required
def admin_trains():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM trains ORDER BY train_id")
    trains = cursor.fetchall()
    cursor.close(); db.close()
    return render_template('admin/trains.html', trains=trains)

@app.route('/admin/trains/add', methods=['POST'])
@admin_required
def admin_add_train():
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO trains (train_number, train_name, train_type, from_station, to_station) VALUES (%s,%s,%s,%s,%s)",
            (request.form['train_number'], request.form['train_name'], request.form['train_type'],
             request.form['from_station'], request.form['to_station'])
        )
        flash('Train added successfully.')
    except mysql.connector.IntegrityError:
        flash('Train number already exists.')
    finally:
        cursor.close(); db.close()
    return redirect(url_for('admin_trains'))

@app.route('/admin/trains/delete/<int:train_id>', methods=['POST'])
@admin_required
def admin_delete_train(train_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM trains WHERE train_id = %s", (train_id,))
    cursor.close(); db.close()
    flash('Train deleted (cascading schedules & bookings).')
    return redirect(url_for('admin_trains'))


# ── ADMIN: STATIONS ────────────────────────────────────────────────────────────

@app.route('/admin/stations')
@admin_required
def admin_stations():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM stations ORDER BY station_name")
    stations = cursor.fetchall()
    cursor.close(); db.close()
    return render_template('admin/stations.html', stations=stations)

@app.route('/admin/stations/add', methods=['POST'])
@admin_required
def admin_add_station():
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO stations (station_name) VALUES (%s)", (request.form['station_name'],))
        flash('Station added successfully.')
    except mysql.connector.IntegrityError:
        flash('Station already exists.')
    finally:
        cursor.close(); db.close()
    return redirect(url_for('admin_stations'))

@app.route('/admin/stations/delete/<int:station_id>', methods=['POST'])
@admin_required
def admin_delete_station(station_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM stations WHERE station_id = %s", (station_id,))
    cursor.close(); db.close()
    flash('Station removed.')
    return redirect(url_for('admin_stations'))


# ── ADMIN: SCHEDULES (Dates) ───────────────────────────────────────────────────

@app.route('/admin/schedules')
@admin_required
def admin_schedules():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.*, t.train_name, t.train_number
        FROM schedules s JOIN trains t ON s.train_id = t.train_id
        ORDER BY s.travel_date DESC, s.departure_time
    """)
    schedules = cursor.fetchall()
    for s in schedules:
        if s['departure_time']:
            ts = int(s['departure_time'].total_seconds())
            s['departure_time'] = f"{ts//3600:02d}:{(ts%3600)//60:02d}"
        if s['arrival_time']:
            ts = int(s['arrival_time'].total_seconds())
            s['arrival_time'] = f"{ts//3600:02d}:{(ts%3600)//60:02d}"
    cursor.execute("SELECT train_id, train_number, train_name FROM trains ORDER BY train_name")
    trains = cursor.fetchall()
    cursor.close(); db.close()
    return render_template('admin/schedules.html', schedules=schedules, trains=trains)

@app.route('/admin/schedules/add', methods=['POST'])
@admin_required
def admin_add_schedule():
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("""
            INSERT INTO schedules (train_id, travel_date, departure_time, arrival_time,
                price_sl, price_3ac, price_2ac, price_1ac)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form['train_id'], request.form['travel_date'],
            request.form['departure_time'], request.form['arrival_time'],
            request.form['price_sl'], request.form['price_3ac'],
            request.form['price_2ac'], request.form['price_1ac']
        ))
        flash('Schedule added successfully.')
    except mysql.connector.IntegrityError:
        flash('Schedule for this train on this date already exists.')
    except mysql.connector.Error as e:
        flash(f'Error: {e}')
    finally:
        cursor.close(); db.close()
    return redirect(url_for('admin_schedules'))

@app.route('/admin/schedules/delete/<int:schedule_id>', methods=['POST'])
@admin_required
def admin_delete_schedule(schedule_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM schedules WHERE schedule_id = %s", (schedule_id,))
    cursor.close(); db.close()
    flash('Schedule deleted (cascading bookings).')
    return redirect(url_for('admin_schedules'))


# ── ADMIN: USERS ───────────────────────────────────────────────────────────────

@app.route('/admin/users')
@admin_required
def admin_users():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT user_id, username, email, full_name, created_at FROM users ORDER BY user_id")
    users = cursor.fetchall()
    cursor.close(); db.close()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/add', methods=['POST'])
@admin_required
def admin_add_user():
    db = get_db()
    cursor = db.cursor()
    try:
        hashed = hashlib.sha256(request.form['password'].encode()).hexdigest()
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, full_name) VALUES (%s,%s,%s,%s)",
            (request.form['username'], request.form['email'], hashed, request.form['full_name'])
        )
        flash('User added successfully.')
    except mysql.connector.IntegrityError:
        flash('Username or email already exists.')
    finally:
        cursor.close(); db.close()
    return redirect(url_for('admin_users'))

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    if user_id == session['user_id']:
        flash('Cannot delete your own admin account.')
        return redirect(url_for('admin_users'))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
    cursor.close(); db.close()
    flash('User deleted (cascading bookings).')
    return redirect(url_for('admin_users'))


# ── ADMIN: TICKETS (Bookings) ──────────────────────────────────────────────────

@app.route('/admin/tickets')
@admin_required
def admin_tickets():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT b.*, u.username, t.train_name, t.train_number,
               s.travel_date, s.departure_time
        FROM bookings b
        JOIN users u ON b.user_id = u.user_id
        JOIN schedules s ON b.schedule_id = s.schedule_id
        JOIN trains t ON s.train_id = t.train_id
        ORDER BY b.booked_at DESC
    """)
    tickets = cursor.fetchall()
    for tk in tickets:
        if tk.get('departure_time'):
            ts = int(tk['departure_time'].total_seconds())
            tk['departure_time'] = f"{ts//3600:02d}:{(ts%3600)//60:02d}"
    # For admin ticket creation form we need users and schedules
    cursor.execute("SELECT user_id, username FROM users ORDER BY username")
    users = cursor.fetchall()
    cursor.execute("""
        SELECT s.schedule_id, t.train_name, t.train_number, s.travel_date
        FROM schedules s JOIN trains t ON s.train_id = t.train_id
        ORDER BY s.travel_date
    """)
    schedules = cursor.fetchall()
    cursor.close(); db.close()
    return render_template('admin/tickets.html', tickets=tickets, users=users, schedules=schedules)

@app.route('/admin/tickets/add', methods=['POST'])
@admin_required
def admin_add_ticket():
    db = get_db(autocommit=False)
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("START TRANSACTION")
        schedule_id = int(request.form['schedule_id'])
        travel_class = request.form['travel_class']
        seat_number = int(request.form['seat_number'])
        
        cursor.execute("SELECT * FROM schedules WHERE schedule_id = %s FOR UPDATE", (schedule_id,))
        schedule = cursor.fetchone()
        
        class_map = {
            'Sleeper': ('price_sl', 'available_sleeper'),
            'AC3': ('price_3ac', 'available_ac3'),
            'AC2': ('price_2ac', 'available_ac2'),
            'AC1': ('price_1ac', 'available_ac1'),
        }
        price_col, avail_col = class_map[travel_class]
        price = schedule[price_col]
        
        cursor.execute("""
            INSERT INTO bookings (user_id, schedule_id, seat_number, travel_class,
                passenger_name, passenger_age, price_paid, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'confirmed')
        """, (
            request.form['user_id'], schedule_id, seat_number, travel_class,
            request.form['passenger_name'], request.form['passenger_age'], price
        ))
        cursor.execute(f"UPDATE schedules SET {avail_col} = {avail_col} - 1 WHERE schedule_id = %s", (schedule_id,))
        db.commit()
        flash('Ticket created successfully.')
    except mysql.connector.IntegrityError:
        db.rollback()
        flash('Seat already booked for this schedule/class.')
    except Exception as e:
        db.rollback()
        flash(f'Error creating ticket: {e}')
    finally:
        cursor.close(); db.close()
    return redirect(url_for('admin_tickets'))

@app.route('/admin/tickets/delete/<int:booking_id>', methods=['POST'])
@admin_required
def admin_delete_ticket(booking_id):
    db = get_db(autocommit=False)
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("START TRANSACTION")
        cursor.execute("SELECT * FROM bookings WHERE booking_id = %s FOR UPDATE", (booking_id,))
        booking = cursor.fetchone()
        if booking and booking['status'] == 'confirmed':
            class_map = {
                'Sleeper': 'available_sleeper',
                'AC3': 'available_ac3',
                'AC2': 'available_ac2',
                'AC1': 'available_ac1',
            }
            avail_col = class_map.get(booking['travel_class'])
            if avail_col:
                cursor.execute(f"UPDATE schedules SET {avail_col} = {avail_col} + 1 WHERE schedule_id = %s", (booking['schedule_id'],))
        cursor.execute("DELETE FROM bookings WHERE booking_id = %s", (booking_id,))
        db.commit()
        flash('Ticket deleted and seat freed.')
    except mysql.connector.Error as e:
        db.rollback()
        flash(f'Error: {e}')
    finally:
        cursor.close(); db.close()
    return redirect(url_for('admin_tickets'))


if __name__ == '__main__':
    app.run(debug=True)
