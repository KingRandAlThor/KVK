from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime, timedelta
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'reservations.db')

app = Flask(__name__)
app.secret_key = 'change-me-to-a-random-secret'  # changez en production


RESERVATION_DATE = '2025-12-02'  # Fixed reservation date as requested (Tuesday Dec 2, 2025)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            slot TEXT NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(date, slot)
        )
        '''
    )
    conn.commit()
    conn.close()


def generate_slots():
    # retourne une liste de créneaux (HH:MM) toutes les 30 minutes de 00:00 à 23:30
    slots = []
    t = datetime(2000, 1, 1, 0, 0)
    while True:
        slots.append(t.strftime('%H:%M'))
        t += timedelta(minutes=30)
        if t.hour == 0 and t.minute == 0:
            break
    return slots


def slot_required_speedups(slot):
    """
    Détermine le nombre de speedups requis pour un créneau donné.
    Par défaut: on utilise l'heure (0-23) comme seuil minimal.
    Modifiez ici si vous voulez une autre logique.
    """
    hour = int(slot.split(':')[0])
    return hour


@app.route('/', methods=['GET'])


def index():
    # Use a fixed reservation date (no calendar) as requested
    date_str = RESERVATION_DATE

    slots = generate_slots()

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT slot, name FROM reservations WHERE date = ?', (date_str,))
    rows = cur.fetchall()
    reserved = {r['slot']: r['name'] for r in rows}
    conn.close()

    # build list of slot dicts with reservation info (no filtering par speedups)
    slot_infos = []
    for s in slots:
        is_reserved = s in reserved
        # allowed si non réservé (les vérifications de speedups ont lieu au moment de la réservation)
        allowed = not is_reserved
        slot_infos.append({'slot': s, 'reserved': is_reserved, 'name': reserved.get(s), 'allowed': allowed})

    return render_template('index.html', date=date_str, slots=slot_infos)


@app.route('/reserve', methods=['POST'])
def reserve():
    date = request.form.get('date')
    slot = request.form.get('slot')
    name = request.form.get('name', '').strip()
    speedups_val = request.form.get('speedups', '').strip()

    if not date or not slot or not name:
        flash('Please provide the date, slot and your name.', 'error')
        return redirect(url_for('index', date=date))

    try:
        user_speedups = int(speedups_val)
    except Exception:
        flash('Invalid speedups value (must be a number).', 'error')
        return redirect(url_for('index', date=date))

    req = slot_required_speedups(slot)
    # Exiger un minimum global de 20 speedups lors de l'inscription

    if user_speedups < 20:
        flash('Speedups must be at least 20 to register.', 'error')
        return redirect(url_for('index', date=date))

    if user_speedups < req:
        flash(f'Your speedups ({user_speedups}) are insufficient for slot {slot} (requires {req}).', 'error')
        return redirect(url_for('index', date=date))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO reservations (date, slot, name) VALUES (?, ?, ?)', (date, slot, name))
        conn.commit()
        conn.close()
        flash(f'Slot {slot} on {date} has been successfully reserved for "{name}".', 'success')
    except sqlite3.IntegrityError:
        flash('Sorry, this slot has already been reserved.', 'error')
    except Exception as e:
        flash('Server error: ' + str(e), 'error')

    return redirect(url_for('index'))


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8080, debug=True)
