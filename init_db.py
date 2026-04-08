import mysql.connector
import os
import hashlib
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def init_db():
    print("Connecting to MySQL server...")
    try:
        # Define connection parameters from environment
        host = os.getenv('MYSQLHOST', os.getenv('DB_HOST', 'localhost'))
        user = os.getenv('MYSQLUSER', os.getenv('DB_USER', 'root'))
        password = os.getenv('MYSQLPASSWORD', os.getenv('DB_PASSWORD', ''))
        port = int(os.getenv('MYSQLPORT', 3306))
        db_name = os.getenv('MYSQLDATABASE', os.getenv('MYSQL_DATABASE', os.getenv('DB_NAME', 't1cket')))

        # 1. Try connecting DIRECTLY to the database first (Preferred for Railway/Cloud)
        try:
            conn = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                port=port,
                database=db_name
            )
            print(f"Connected directly to database '{db_name}'.")
        except mysql.connector.Error:
            # 2. Fallback: Connect to server without DB and try to create it (Expected for Local)
            print(f"Direct connection to '{db_name}' failed. Attempting to create it...")
            conn = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                port=port
            )
            c = conn.cursor()
            c.execute(f"CREATE DATABASE IF NOT EXISTS {db_name};")
            c.execute(f"USE {db_name};")
            c.close()
        
        c = conn.cursor()
        print("Creating tables if they don't exist...")
        # 1. users Table
        c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 2. stations Table
        c.execute('''
        CREATE TABLE IF NOT EXISTS stations (
            station_id INT AUTO_INCREMENT PRIMARY KEY,
            station_name VARCHAR(100) UNIQUE NOT NULL
        )
        ''')
        
        # 3. trains Table
        c.execute('''
        CREATE TABLE IF NOT EXISTS trains (
            train_id INT AUTO_INCREMENT PRIMARY KEY,
            train_number VARCHAR(10) UNIQUE NOT NULL,
            train_name VARCHAR(100) NOT NULL,
            train_type ENUM('Rajdhani', 'Shatabdi', 'Duronto', 'Vande Bharat', 'Express', 'Mail') NOT NULL,
            from_station VARCHAR(100) NOT NULL,
            to_station VARCHAR(100) NOT NULL,
            INDEX idx_route (from_station, to_station)
        )
        ''')
        
        # 3. schedules Table
        c.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            schedule_id INT AUTO_INCREMENT PRIMARY KEY,
            train_id INT NOT NULL,
            travel_date DATE NOT NULL,
            departure_time TIME NOT NULL,
            arrival_time TIME NOT NULL,
            price_sl DECIMAL(8,2) NOT NULL,
            price_3ac DECIMAL(8,2) NOT NULL,
            price_2ac DECIMAL(8,2) NOT NULL,
            price_1ac DECIMAL(8,2) NOT NULL,
            available_sleeper INT DEFAULT 72,
            available_ac3 INT DEFAULT 64,
            available_ac2 INT DEFAULT 46,
            available_ac1 INT DEFAULT 18,
            FOREIGN KEY (train_id) REFERENCES trains(train_id) ON DELETE CASCADE,
            UNIQUE KEY uq_train_date (train_id, travel_date),
            INDEX idx_date (travel_date)
        )
        ''')
        
        # 4. bookings Table
        c.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            schedule_id INT NOT NULL,
            passenger_name VARCHAR(100) NOT NULL,
            passenger_age TINYINT UNSIGNED NOT NULL,
            travel_class ENUM('Sleeper', 'AC3', 'AC2', 'AC1') NOT NULL,
            seat_number INT NOT NULL,
            price_paid DECIMAL(8,2) NOT NULL,
            status ENUM('confirmed', 'cancelled', 'pending') DEFAULT 'confirmed',
            booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (schedule_id) REFERENCES schedules(schedule_id) ON DELETE CASCADE,
            UNIQUE KEY uq_seat (schedule_id, travel_class, seat_number),
            INDEX idx_user (user_id)
        )
        ''')
        
        print("Creating Views...")
        # Views
        c.execute("DROP VIEW IF EXISTS available_seats_view")
        c.execute('''
        CREATE VIEW available_seats_view AS
        SELECT 
            s.schedule_id, 
            b.travel_class, 
            b.seat_number
        FROM schedules s
        LEFT JOIN bookings b 
            ON s.schedule_id = b.schedule_id 
            AND b.status = 'confirmed';
        ''')
        
        c.execute("DROP VIEW IF EXISTS user_boarding_pass_view")
        c.execute('''
        CREATE VIEW user_boarding_pass_view AS
        SELECT 
            b.booking_id,
            b.user_id,
            b.passenger_name,
            b.seat_number,
            b.travel_class,
            b.price_paid,
            b.status,
            b.booked_at,
            CONCAT('PNR', LPAD(b.booking_id, 8, '0')) AS pnr_code,
            s.travel_date,
            s.departure_time,
            s.arrival_time,
            t.train_name,
            t.train_number,
            t.from_station,
            t.to_station
        FROM bookings b
        JOIN schedules s ON b.schedule_id = s.schedule_id
        JOIN trains t ON s.train_id = t.train_id;
        ''')
        
        print("Inserting seed data...")
        # Seed Users
        pwd_hash = hashlib.sha256(b'admin67').hexdigest()
        c.execute("INSERT IGNORE INTO users (username, email, password_hash, full_name) VALUES (%s, %s, %s, %s)",
                  ('admin', 'admin@t1cket.in', pwd_hash, 'T1cket Administrator'))
        
        # Seed Stations
        stations = [
            ('Mumbai',), ('Delhi',), ('Bangalore',), ('Chennai',), 
            ('Kolkata',), ('Hyderabad',), ('Pune',), ('Ahmedabad',),
            ('New Delhi',), ('Varanasi',), ('Bengaluru',)
        ]
        c.executemany("INSERT IGNORE INTO stations (station_name) VALUES (%s)", stations)
        
        # Seed Trains
        trains = [
            ('12951', 'Mumbai Rajdhani', 'Rajdhani', 'Mumbai', 'New Delhi'),
            ('12009', 'Mumbai Shatabdi', 'Shatabdi', 'Mumbai', 'Ahmedabad'),
            ('12221', 'Pune Duronto', 'Duronto', 'Pune', 'New Delhi'),
            ('22439', 'Vande Bharat Ex', 'Vande Bharat', 'New Delhi', 'Varanasi'),
            ('12621', 'Tamil Nadu Exp', 'Express', 'Chennai', 'New Delhi'),
            ('12627', 'Karnataka Exp', 'Express', 'Bengaluru', 'New Delhi')
        ]
        # First check if they exist, otherwise insert
        for t in trains:
            c.execute("SELECT train_id FROM trains WHERE train_number=%s", (t[0],))
            if not c.fetchone():
                c.execute("INSERT INTO trains (train_number, train_name, train_type, from_station, to_station) VALUES (%s, %s, %s, %s, %s)", t)
        
        # Map train_number to train_id
        c.execute("SELECT train_number, train_id FROM trains")
        train_map = {row[0]: row[1] for row in c.fetchall()}

        # Seed Schedules
        today = datetime.now()
        d1 = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        d2 = (today + timedelta(days=2)).strftime('%Y-%m-%d')
        d3 = (today + timedelta(days=3)).strftime('%Y-%m-%d')
        
        # Using string mapping down here to grab correct ID
        schedules = [
            (train_map['12951'], d1, '16:35:00', '08:15:00', 850, 1450, 2100, 3800),
            (train_map['12951'], d2, '16:35:00', '08:15:00', 850, 1450, 2100, 3800),
            (train_map['12951'], d3, '16:35:00', '08:15:00', 850, 1450, 2100, 3800),
            (train_map['12009'], d1, '06:25:00', '12:55:00', 680, 1100, 1650, 0),
            (train_map['12009'], d2, '06:25:00', '12:55:00', 680, 1100, 1650, 0),
            (train_map['12221'], d1, '11:05:00', '06:30:00', 790, 1380, 1980, 3500),
            (train_map['12221'], d2, '11:05:00', '06:30:00', 790, 1380, 1980, 3500),
            (train_map['22439'], d1, '06:00:00', '14:00:00', 0, 1200, 1750, 3200),
            (train_map['22439'], d2, '06:00:00', '14:00:00', 0, 1200, 1750, 3200),
            (train_map['12621'], d1, '22:00:00', '06:30:00', 950, 1600, 2300, 4100),
            (train_map['12627'], d1, '20:15:00', '07:45:00', 820, 1390, 2000, 3700)
        ]
        # Ignore if train_id + date duplicates
        for s in schedules:
            try:
                c.execute("INSERT INTO schedules (train_id, travel_date, departure_time, arrival_time, price_sl, price_3ac, price_2ac, price_1ac) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", s)
            except mysql.connector.Error as err:
                if err.errno == 1062: # Duplicate entry
                    pass
                else:
                    raise
        
        conn.commit()
        print("Database initialized successfully.")
    
    except mysql.connector.Error as err:
        print(f"FATAL ERROR during initialization: {err}")
        # Re-raise the error so the deployment fails and we see it in logs
        raise err
    finally:
        if 'c' in locals():
            c.close()
        if 'conn' in locals() and conn.is_connected():
            conn.close()

if __name__ == '__main__':
    init_db()
