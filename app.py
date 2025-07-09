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

    # Foreign key for court association (this is the primary key assigning each user to a court)
    court_id = db.Column(db.Integer, db.ForeignKey('court.id'), nullable=True)

    # Queue entry
    queue_entry = db.relationship('QueueEntry', back_populates='user', uselist=False)


class Court(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    
    # players = users that have court_id == this court's id
    players = db.relationship('User', backref='court', lazy=True)
    
    # queue = users waiting to play on this court
    queue = db.relationship('QueueEntry', backref='court', lazy=True, order_by='QueueEntry.position')

    # e.g. to get the players on court 1, do
    # court = Court.query.filter_by(id=1).first()
    # court.players

    # Likewise, to get the court that a user is on, do
    # user = User.query.filter_by(username='some_username').first()
    # user.court

    # Assigning to a court can be done with
    # court = Court.query.filter_by(id=1).first()
    # user = User.query.filter_by(username='some_username').first()
    # user.court = court
    # db.session.commit()

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'players': [player.username for player in self.players],
            'queue': [entry.user.username for entry in self.queue]
        }

class QueueEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    court_id = db.Column(db.Integer, db.ForeignKey('court.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    position = db.Column(db.Integer, nullable=False)

    # Link back to User
    user = db.relationship('User', back_populates='queue_entry')

class ClubState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    is_active = db.Column(db.Boolean, default=False)
    last_modified = db.Column(db.DateTime, default=datetime.utcnow)

class TimerState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    duration = db.Column(db.Integer, default=900)  # 15 minutes in seconds
    remaining_time = db.Column(db.Integer, default=900)
    is_running = db.Column(db.Boolean, default=False)
    start_time = db.Column(db.Float, nullable=True)
    end_time = db.Column(db.Float, nullable=True)

# Old court model
# courts = {f'Court {i}': {'players': [], 'queue': []} for i in range(1, 5)}  # 4 courts

MAX_PLAYERS = 2

def is_user_active_elsewhere(user):
    """Check if user is active on any court or in any queue"""
    if isinstance(user, str):
        user = User.query.filter_by(username=user).first()
    if not user:
        return False
    return user.court is not None or user.queue_entry is not None

def is_player_on_court(user):
    """Check if player is currently on any court"""
    if isinstance(user, str):
        user = User.query.filter_by(username=user).first()
    if not user:
        return False
    return user.court is not None

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
    club_state = ClubState.query.first()
    timer_state = TimerState.query.first()
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
    # Get current username and check if club is active
    username = session.get('user')
    user = None
    is_admin = False
    if username:
        user = User.query.filter_by(username=username).first()
        if user and user.is_admin:
            is_admin = True
    
    logged_in = user is not None

    # Get club state from database
    club_state = ClubState.query.first()
    courts = Court.query.all()

    # If club inactive, and user not admin, show inactive page
    if not club_state.is_active and (not user or not user.is_admin):
        return render_template('inactive.html')
    
    # Otherwise, if club is active OR user is admin, show home page
    return render_template('home.html', 
                         courts=courts, 
                         logged_in=logged_in, 
                         username=session.get('user'), 
                         is_admin=is_admin)


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

@app.route('/join_court/<court_name>', methods=['POST'])
def join_court(court_name):
    username = session.get('user')
    if not username:
        flash('You must be logged in to join a court')
        return redirect(url_for('login'))

    user = User.query.filter_by(username=username).first()
    court = Court.query.filter_by(name=court_name).first()

    if court and len(court.players) < MAX_PLAYERS:
        if not is_user_active_elsewhere(user):
            if not user.court:  # Already handled by FK
                user.court = court
                db.session.commit()
                flash(f'You joined {court.name}')
            else:
                flash('You are already on a court.')
        else:
            flash('You are already active elsewhere.')
    else:
        flash('Court is full or does not exist.')

    return redirect(url_for('home'))

@app.route('/join_queue/<court_name>', methods=['POST'])
def join_queue(court_name):
    username = session.get('user')
    if not username:
        flash('You must be logged in to join a queue')
        return redirect(url_for('login'))

    user = User.query.filter_by(username=username).first()
    court = Court.query.filter_by(name=court_name).first()

    # Check if user is already in any queue
    if court and not user.queue_entry:
        if not is_user_active_elsewhere(user):
            if not user.court:
                # Add to queue
                next_position = len(court.queue) + 1
                new_entry = QueueEntry(court=court, user=user, position=next_position)
                db.session.add(new_entry)
                db.session.commit()
                flash(f'You joined the queue for {court.name}')
            else:
                flash('You are already on a court.')
        else:
            flash('You are already active elsewhere.')
    else:
        flash('You are already in a queue or court does not exist.')

    return redirect(url_for('home'))

@app.route('/leave_court/<court_name>', methods=['POST'])
def leave_court(court_name):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    username = session['user']
    user = User.query.filter_by(username=username).first()
    court = Court.query.filter_by(name=court_name).first()
    timer_state = TimerState.query.first()
    
    if not user or not court:
        return redirect(url_for('home'))

    app.logger.info(f"User {username} leaving court or queue for {court_name}")

    did_something = False

    # Leave *any* queue entry
    if user.queue_entry:
        db.session.delete(user.queue_entry)
        did_something = True

        # Reorder the queue for that court if it was this court's queue
        if user.queue_entry.court_id == court.id:
            for i, entry in enumerate(court.queue, 1):
                entry.position = i

    # Leave court if they’re on this court and timer is not running
    if user.court == court:
        if not timer_state.is_running:
            user.court = None
            did_something = True

            # Promote next players from queue
            while len(court.players) < MAX_PLAYERS and court.queue:
                next_entry = court.queue[0]
                next_entry.user.court = court
                db.session.delete(next_entry)
                for i, entry in enumerate(court.queue[1:], 1):
                    entry.position = i
        else:
            flash('Cannot leave court while timer is running')

    if did_something:
        db.session.commit()

    return redirect(url_for('home'))


@app.route('/admin')
def admin():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    username = session['user']
    user = User.query.filter_by(username=username).first()
    courts = Court.query.all()
    users = User.query.all()
    if not user or not user.is_admin:

        # optional: don't even give this warning, just redirect to home immediately?
        flash('You do not have permission to access the admin page')
        return redirect(url_for('home'))
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
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.filter_by(username=session['user']).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401
    
    timer_state = TimerState.query.first()
    now = datetime.now().timestamp()
    
    if not timer_state.is_running and timer_state.remaining_time > 0:
        timer_state.end_time = now + timer_state.remaining_time
    else:
        timer_state.remaining_time = timer_state.duration
        timer_state.end_time = now + timer_state.duration
    
    timer_state.start_time = now
    timer_state.is_running = True
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'remaining': timer_state.remaining_time,
        'end_time': timer_state.end_time
    })
@app.route('/timer/status')
def get_timer_status():
    timer_state = TimerState.query.first()
    courts = Court.query.all()

    if timer_state and timer_state.is_running and timer_state.start_time is not None:
        now = datetime.now().timestamp()
        elapsed = now - timer_state.start_time
        remaining = max(0, timer_state.remaining_time - elapsed)

        if remaining <= 0.1:
            app.logger.info("⏰ Timer expired — rotating players!")

            # Mark timer as stopped
            timer_state.is_running = False
            timer_state.remaining_time = 0
            timer_state.start_time = None
            timer_state.end_time = None

            # Clear players safely
            for court in courts:
                for player in court.players[:]:
                    player.court = None

            db.session.flush()

            for court in courts:
                print(f"Checking court {court.name} for players and queue")
                while len(court.players) < MAX_PLAYERS and court.queue:
                    print(f"queue currently: {[entry.user.username for entry in court.queue]}")
                    next_entry = court.queue[0]
                    print(f"Promoting {next_entry.user.username} to court {court.name}")
                    court.players.append(next_entry.user)  # Add to players
                    court.queue = court.queue[1:]  # Remove from queue
                    db.session.delete(next_entry)  # Remove from queue
                    for i, entry in enumerate(court.queue[1:], 1):
                        entry.position = i

            db.session.commit()

            return jsonify({
                'running': False,
                'remaining': 0,
                'expired': True,
                'courts': [court.to_dict() for court in courts]
            })

        return jsonify({
            'running': True,
            'remaining': int(remaining),
            'expired': False,
            'courts': [court.to_dict() for court in courts]
        })

    # When timer not running, always reset to default time!
    if timer_state and not timer_state.is_running and timer_state.remaining_time == 0:
        DEFAULT_DURATION = 900  # 15 min
        timer_state.remaining_time = DEFAULT_DURATION
        db.session.commit()

    return jsonify({
        'running': False,
        'remaining': int(timer_state.remaining_time) if timer_state else 0,
        'expired': False,
        'courts': [court.to_dict() for court in courts]
    })


@app.route('/timer/reset', methods=['POST'])
def reset_timer():
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.filter_by(username=username).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401
    
    timer_state = TimerState.query.first()
    timer_state.end_time = None
    timer_state.start_time = None
    timer_state.is_running = False
    timer_state.remaining_time = timer_state.duration
    db.session.commit()
    
    return jsonify({'status': 'success'})

@app.route('/timer/set-duration', methods=['POST'])
def set_timer_duration():
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.filter_by(username=username).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        minutes = float(data.get('minutes', 15))
        
        if not 0 <= minutes <= 60:
            return jsonify({'error': 'Duration must be between 0 and 60 minutes'}), 400
        
        seconds = round(minutes * 60)
        timer_state = TimerState.query.first()
        timer_state.duration = seconds
        timer_state.remaining_time = seconds
        timer_state.is_running = False
        timer_state.end_time = None
        timer_state.start_time = None
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'duration': seconds,
            'message': f'Timer set to {minutes} minutes ({seconds} seconds)'
        })
    
    except (TypeError, ValueError) as e:
        return jsonify({'error': 'Invalid duration format'}), 400

@app.route('/clear-courts', methods=['POST'])
def clear_courts():
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.filter_by(username=username).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401

    # Clear all courts
    courts = Court.query.all()
    for court in courts:
        # Clear players
        for player in court.players:
            player.court = None
        
        # Clear queue
        for entry in court.queue:
            db.session.delete(entry)
    
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'All courts cleared'})

@app.route('/toggle-club-status', methods=['POST'])
def toggle_club_status():
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.filter_by(username=username).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401
    
    club_state = ClubState.query.first()
    club_state.is_active = not club_state.is_active
    club_state.last_modified = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'is_active': club_state.is_active
    })

@app.route('/club-status')
def get_club_status():
    club_state = ClubState.query.first()
    return jsonify({
        'is_active': club_state.is_active,
        'last_modified': club_state.last_modified.timestamp()
    })

@app.route('/court-updates')
def court_updates():
    def generate():
        while True:
            with app.app_context():
                courts = Court.query.all()
                #print("=== Court state ===")
                #for c in courts:
                #    print(f"{c.name} | Players: {[p.username for p in c.players]} | Queue: {[e.user.username for e in c.queue]}")

                court_data = {}
                for court in courts:
                    court_data[court.name] = {
                        'players': [player.username for player in court.players],
                        'queue': [entry.user.username for entry in court.queue]
                    }
                data = f"data: {json.dumps({'courts': court_data})}\n\n"
                yield data
            time.sleep(1)
    
    return Response(generate(), mimetype='text/event-stream')


if __name__ == '__main__':
    with app.app_context():
        db.drop_all()
        db.create_all()   # Create all tables if they don't exist

        # Add default courts if none exist
        if not Court.query.first():
            default_courts = ['Court 1', 'Court 2', 'Court 3', 'Court 4']
            for name in default_courts:
                court = Court(name=name)
                db.session.add(court)

        # Create default TimerState if none exists
        # app.logger.info("Checking for TimerState...")
        if not TimerState.query.first():
            timer_state = TimerState(is_running=False)  # adjust fields as per your model
            db.session.add(timer_state)

        # Create default ClubState if none exists
        if not ClubState.query.first():
            club_state = ClubState()  # fill in default fields if needed
            db.session.add(club_state)

        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password_hash=generate_password_hash('adminpass'),
                is_admin=True
            )
            db.session.add(admin)
            # print("Created admin user")
                # Add test users a, b, c
        test_users = ['a', 'b', 'c']
        for username in test_users:
            if not User.query.filter_by(username=username).first():
                user = User(
                    username=username,
                    password_hash=generate_password_hash(username),  # password same as username
                    is_admin=False
                )
                db.session.add(user)
                print(f"Created test user: {username}")

        db.session.commit()
    app.run(host="0.0.0.0", port=5001, debug=True)
