from flask import Flask, render_template, url_for, session, redirect, request, jsonify, send_from_directory, Response, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta, datetime
import time
import json
import random

from dotenv import load_dotenv
load_dotenv()

import os
SECRET_KEY = os.getenv('SECRET_KEY')
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = timedelta(hours=4)

# In-memory storage (replace with a database in production)
users = {
    'admin': {
        'password': generate_password_hash('adminpass'),  # Change this password!
        'is_admin': True,
        'is_checked_in': True
    },

    # temp create some users
    'a':{
        'password': generate_password_hash('a'),
        'is_admin': False
    },
    'b':{
        'password': generate_password_hash('b'),
        'is_admin': False
    },
    'c':{
        'password': generate_password_hash('c'),
        'is_admin': False
    },
    'd':{
        'password': generate_password_hash('d'),
        'is_admin': False
    }
}
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
        username = request.form['username']
        password = request.form['password']
        user = users.get(username)
        if user and check_password_hash(user['password'], password):
            session.permanent = True
            session['user'] = username
            # Redirect to admin panel if user is admin, otherwise go to home
            if user.get('is_admin', False):
                return redirect(url_for('admin'))
            return redirect(url_for('home'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if username in users:
            return 'Username already exists', 400
        users[username] = {'password': password, 'is_admin': False}
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
    app.run(debug=True)