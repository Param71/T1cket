-- ═══════════════════════════════════════════════════════════
--  T1CKET — Railway Ticket Booking Database Schema
--  Demonstrates: 3NF normalization, FK constraints, indexing,
--  ACID transactions, and pessimistic concurrency control
-- ═══════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS t1cket CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE t1cket;

-- ── USERS ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50) UNIQUE NOT NULL,
    email         VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(100) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── STATIONS ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stations (
    station_id   INT AUTO_INCREMENT PRIMARY KEY,
    station_name VARCHAR(100) UNIQUE NOT NULL
);

-- ── TRAINS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trains (
    train_id     INT AUTO_INCREMENT PRIMARY KEY,
    train_number VARCHAR(10) UNIQUE NOT NULL,
    train_name   VARCHAR(100) NOT NULL,
    train_type   ENUM('Rajdhani','Shatabdi','Duronto','Vande Bharat','Express','Mail') NOT NULL,
    from_station VARCHAR(100) NOT NULL,
    to_station   VARCHAR(100) NOT NULL,
    INDEX idx_route (from_station, to_station)
);

-- ── SCHEDULES ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schedules (
    schedule_id      INT AUTO_INCREMENT PRIMARY KEY,
    train_id         INT NOT NULL,
    travel_date      DATE NOT NULL,
    departure_time   TIME NOT NULL,
    arrival_time     TIME NOT NULL,
    price_sl         DECIMAL(8,2) NOT NULL,
    price_3ac        DECIMAL(8,2) NOT NULL,
    price_2ac        DECIMAL(8,2) NOT NULL,
    price_1ac        DECIMAL(8,2) NOT NULL,
    available_sleeper INT DEFAULT 72,
    available_ac3     INT DEFAULT 64,
    available_ac2     INT DEFAULT 46,
    available_ac1     INT DEFAULT 18,
    FOREIGN KEY (train_id) REFERENCES trains(train_id) ON DELETE CASCADE,
    UNIQUE KEY uq_train_date (train_id, travel_date),
    INDEX idx_date (travel_date)
);

-- ── BOOKINGS ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bookings (
    booking_id     INT AUTO_INCREMENT PRIMARY KEY,
    user_id        INT NOT NULL,
    schedule_id    INT NOT NULL,
    passenger_name VARCHAR(100) NOT NULL,
    passenger_age  TINYINT UNSIGNED NOT NULL,
    travel_class   ENUM('Sleeper','AC3','AC2','AC1') NOT NULL,
    seat_number    INT NOT NULL,
    price_paid     DECIMAL(8,2) NOT NULL,
    status         ENUM('confirmed','cancelled','pending') DEFAULT 'confirmed',
    booked_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)     REFERENCES users(user_id)     ON DELETE CASCADE,
    FOREIGN KEY (schedule_id) REFERENCES schedules(schedule_id) ON DELETE CASCADE,
    UNIQUE KEY uq_seat (schedule_id, travel_class, seat_number),
    INDEX idx_user (user_id)
);

-- ── VIEWS ──────────────────────────────────────────────────
DROP VIEW IF EXISTS available_seats_view;
CREATE VIEW available_seats_view AS
SELECT 
    s.schedule_id, 
    b.travel_class, 
    b.seat_number
FROM schedules s
LEFT JOIN bookings b 
    ON s.schedule_id = b.schedule_id 
    AND b.status = 'confirmed';

DROP VIEW IF EXISTS user_boarding_pass_view;
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
