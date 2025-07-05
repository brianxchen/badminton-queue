from flask import Flask, render_template, url_for, session, redirect, request, jsonify, send_from_directory, Response, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta, datetime
import time
import json
import random

# Flask alchemy for database
from flask_sqlalchemy import SQLAlchemy

from dotenv import load_dotenv
load_dotenv()

import os
SECRET_KEY = os.getenv('SECRET_KEY')
app = Flask(__name__)
# print(f"SECRET_KEY: {SECRET_KEY}")  # Debugging line to check if SECRET_KEY is loaded
app.secret_key = SECRET_KEY  # Change this to a secure key in production
app.permanent_session_lifetime = timedelta(hours=4)

# Database config
DATABASE_URL = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# User model for database
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_checked_in = db.Column(db.Boolean, default=False)

courts = {f'Court {i}': {'players': [], 'queue': []} for i in range(1, 5)}  # 4 courts

timer_state = {
    'end_time': None,
    'duration': 15 * 60,  # 15 minutes in seconds
    'is_running': False,
    'remaining_time': 15 * 60  # Add this to store paused time
}

club_state = {
    'is_active': False,
    'last_modified': None
}

MAX_PLAYERS = 2

def is_user_active_elsewhere(user):
    """Check if user is active on any court or queue"""
    for court in courts.values():
        if user in court['players'] or user in court['queue']:
            return True
    return False

def is_player_on_court(username):
    """Check if player is currently on any court"""
    return any(username in court['players'] for court in courts.values())

def rotate_players(court):
    """Helper function to move players from queue to court"""
    # Move players from queue to court
    while len(court['players']) < MAX_PLAYERS and court['queue']:
        next_player = court['queue'].pop(0)  # Remove from front of queue
        court['players'].append(next_player)  # Add to players

def get_random_signature():
    signatures = [
        "❤️", "💻", "☕️", "🍞🥛", "🧸🍯", "🌼🍄", "🌙📖", "🧠🔧", 
        "🦾📟", "👨‍💻⌨️", "🕹️💡", "🎨🧵", "✏️📐", "🪄🖋️", "🐥🐾",
        "🦊🌰", "🐝🌻", "🐈‍⬛🧶", "🔥🧃", "🧂🥲", "🥴⚙️", "👻🍕"
    ]
    return random.choice(signatures)

@app.context_processor
def inject_constants():
    return dict(MAX_PLAYERS=MAX_PLAYERS)

@app.context_processor
def inject_utilities():
    return {
        'MAX_PLAYERS': MAX_PLAYERS,
        'is_user_active_elsewhere': is_user_active_elsewhere,
        'club_state': club_state,
        'is_player_on_court': is_player_on_court,
        'timer_state': timer_state,
        'signature': get_random_signature()
    }

@app.route('/')
def home():
    if not club_state['is_active'] and (not session.get('user') or 
        not users.get(session['user'], {}).get('is_admin', False)):
        return render_template('inactive.html')
    logged_in = 'user' in session
    is_admin = users.get(session.get('user'), {}).get('is_admin', False)
    return render_template('home.html', courts=courts, logged_in=logged_in, username=session.get('user'), is_admin=is_admin)



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # app.logger.info("Login attempt")
        _username = request.form['username']
        _password = request.form['password']

        user = User.query.filter_by(username=_username).first()
        if user and check_password_hash(user.password_hash, _password):
            session['user'] = user.username
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists')
            return render_template('signup.html', error='Username already exists')
        password_hash = generate_password_hash(password)
        new_user = User(username=username, password_hash=password_hash, is_admin=False)
        db.session.add(new_user)
        db.session.commit()

        flash('User created successfully! Please log in.')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/join_court/<court_name>', methods=['GET', 'POST'])
def join_court(court_name):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    court = courts.get(court_name)
    
    if request.method == 'POST':
        if court and len(court['players']) < MAX_PLAYERS:
            if not is_user_active_elsewhere(user) and not is_player_on_court(user):
                court['players'].append(user)
    
    return redirect(url_for('home'))

@app.route('/join_queue/<court_name>', methods=['GET', 'POST'])
def join_queue(court_name):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    court = courts.get(court_name)
    
    if request.method == 'POST':
        if court and user not in court['queue']:
            if not is_user_active_elsewhere(user) and not is_player_on_court(user):
                court['queue'].append(user)
    
    return redirect(url_for('home'))

@app.route('/leave_court/<court_name>', methods=['GET', 'POST'])
def leave_court(court_name):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    court = courts.get(court_name)
    
    if request.method == 'POST':
        if court:
            if user in court['queue']:
                court['queue'].remove(user)
            elif user in court['players'] and not timer_state['is_running']:
                court['players'].remove(user)
    
    return redirect(url_for('home'))

@app.route('/admin')
def admin():
    if 'user' not in session or not users.get(session['user'], {}).get('is_admin', False):
        return redirect(url_for('login'))
    return render_template('admin.html', 
                         courts=courts,
                         users=users)  # Pass users to the template

@app.route('/admin/add_user', methods=['GET', 'POST'])
def add_user():
    if 'user' not in session or not users.get(session['user'], {}).get('is_admin', False):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required')
            return redirect(url_for('admin'))
            
        if username in users:
            flash('User already exists')
            return redirect(url_for('admin'))
            
        users[username] = {
            'password': generate_password_hash(password),
            'is_admin': False,
            'is_checked_in': False
        }
        flash(f'User {username} added successfully')
        
    return redirect(url_for('admin'))

@app.route('/admin/remove_user', methods=['GET', 'POST'])
def remove_user():
    if 'user' not in session or not users.get(session['user'], {}).get('is_admin', False):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        
        if username not in users:
            flash('User does not exist')
            return redirect(url_for('admin'))
            
        if users[username].get('is_admin'):
            flash('Cannot remove admin user')
            return redirect(url_for('admin'))
            
        # Remove user from courts and queues
        for court in courts.values():
            if username in court['players']:
                court['players'].remove(username)
            if username in court['queue']:
                court['queue'].remove(username)
                
        del users[username]
        flash(f'User {username} removed successfully')
        
    return redirect(url_for('admin'))

@app.route('/timer/start', methods=['POST'])
def start_timer():
    if 'user' not in session or not users.get(session['user'], {}).get('is_admin', False):
        return jsonify({'error': 'Unauthorized'}), 401
    
    now = datetime.now().timestamp()
    
    # If timer was paused, use remaining time
    if not timer_state['is_running'] and timer_state['remaining_time'] > 0:
        timer_state['end_time'] = now + timer_state['remaining_time']
    else:
        # Start fresh with full duration
        timer_state['remaining_time'] = timer_state['duration']
        timer_state['end_time'] = now + timer_state['duration']
    
    timer_state['start_time'] = now
    timer_state['is_running'] = True
    
    return jsonify({
        'status': 'success',
        'remaining': timer_state['remaining_time'],
        'end_time': timer_state['end_time']
    })

@app.route('/timer/stop', methods=['POST'])
def stop_timer():
    if 'user' not in session or not users.get(session['user'], {}).get('is_admin', False):
        return {'error': 'Unauthorized'}, 401
    
    if timer_state['is_running'] and timer_state['end_time']:
        timer_state['remaining_time'] = timer_state['end_time'] - datetime.now().timestamp()
        timer_state['is_running'] = False
    
    return {'status': 'success'}

@app.route('/timer/reset', methods=['POST'])
def reset_timer():
    if 'user' not in session or not users.get(session['user'], {}).get('is_admin', False):
        return {'error': 'Unauthorized'}, 401
    
    timer_state['end_time'] = None
    timer_state['is_running'] = False
    timer_state['remaining_time'] = timer_state['duration']
    return {'status': 'success'}

@app.route('/timer/status')
def get_timer_status():
    if timer_state['is_running'] and timer_state['start_time'] is not None:
        now = datetime.now().timestamp()
        elapsed = now - timer_state['start_time']
        remaining = max(0, timer_state['remaining_time'] - elapsed)
        
        if remaining <= 0:
            # Timer expired - rotate players
            timer_state['is_running'] = False
            timer_state['remaining_time'] = 0
            timer_state['end_time'] = None
            timer_state['start_time'] = None
            
            # Clear courts and rotate in queued players
            for court in courts.values():
                # Store current players to prevent them from immediately rejoining
                recently_played = court['players']
                court['players'] = []
                rotate_players(court)
                
                # Add recently played players to a cooldown list if you want to prevent immediate rejoin
                # (optional) court['cooldown'] = recently_played
            
            return jsonify({
                'running': False,
                'remaining': 0,
                'expired': True,
                'courts': courts
            })
        
        return jsonify({
            'running': True,
            'remaining': int(remaining),
            'expired': False,
            'courts': courts
        })
    
    return jsonify({
        'running': False,
        'remaining': int(timer_state['remaining_time']),
        'expired': False,
        'courts': courts
    })

@app.route('/timer/set-duration', methods=['POST'])
def set_timer_duration():
    if 'user' not in session or not users.get(session['user'], {}).get('is_admin', False):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        minutes = float(data.get('minutes', 15))
        
        if not 0 <= minutes <= 60:
            return jsonify({'error': 'Duration must be between 0 and 60 minutes'}), 400
        
        # Convert minutes to seconds and round to nearest second
        seconds = round(minutes * 60)
        timer_state['duration'] = seconds
        timer_state['remaining_time'] = seconds
        timer_state['is_running'] = False
        timer_state['end_time'] = None
        timer_state['start_time'] = None
        
        return jsonify({
            'status': 'success',
            'duration': seconds,
            'message': f'Timer set to {minutes} minutes ({seconds} seconds)'
        })
    
    except (TypeError, ValueError) as e:
        return jsonify({'error': 'Invalid duration format'}), 400

@app.route('/clear-courts', methods=['POST'])
def clear_courts():
    if 'user' not in session or not users.get(session['user'], {}).get('is_admin', False):
        return jsonify({'error': 'Unauthorized'}), 401
    
    for court in courts.values():
        court['players'].clear()
        court['queue'].clear()
    
    return jsonify({'status': 'success', 'message': 'All courts cleared'})

@app.route('/toggle-club-status', methods=['POST'])
def toggle_club_status():
    if 'user' not in session or not users.get(session['user'], {}).get('is_admin', False):
        return jsonify({'error': 'Unauthorized'}), 401
    
    club_state['is_active'] = not club_state['is_active']
    club_state['last_modified'] = datetime.now().timestamp()
    
    return jsonify({
        'status': 'success',
        'is_active': club_state['is_active']
    })

@app.route('/club-status')
def get_club_status():
    return jsonify({
        'is_active': club_state['is_active'],
        'last_modified': club_state['last_modified']
    })

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/court-updates')
def court_updates():
    def generate():
        while True:
            # Only send court data, not timer
            data = f"data: {json.dumps({'courts': courts})}\n\n"
            yield data
            time.sleep(1)
    
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5001, debug=True)
