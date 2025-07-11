from flask import Flask, render_template, url_for, session, redirect, request, jsonify, send_from_directory, Response, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta, datetime
import time
import json
import random
from gevent import sleep

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

class Court(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    
    # Now we have groups both on court and in queue
    # The groups relationship is defined in the Group model
    
    def to_dict(self):
        # Get active groups on court
        active_groups = [group for group in self.groups if not group.is_in_queue]
        
        # Get groups in queue, sorted by position
        queue_groups = sorted(
            [group for group in self.groups if group.is_in_queue],
            key=lambda g: g.queue_position
        )
        
        return {
            'id': self.id,
            'name': self.name,
            'active_groups': [group.to_dict() for group in active_groups],
            'queue_groups': [group.to_dict() for group in queue_groups]
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

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_checked_in = db.Column(db.Boolean, default=False)
    
    # Add the group_id foreign key to connect User to Group
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    
    # Keep the old court_id for compatibility during transition
    court_id = db.Column(db.Integer, db.ForeignKey('court.id'), nullable=True)

    # Queue entry
    queue_entry = db.relationship('QueueEntry', back_populates='user', uselist=False)

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    court_id = db.Column(db.Integer, db.ForeignKey('court.id'), nullable=True)
    is_in_queue = db.Column(db.Boolean, default=True)  # True if in queue, False if on court
    queue_position = db.Column(db.Integer, nullable=True)  # Position in queue (NULL if on court)
    
    # Relationships
    court = db.relationship('Court', backref='groups')
    # Define the relationship from Group to User (players)
    # The backref here creates the 'group' attribute on User objects
    players = db.relationship('User', backref='group', lazy=True, foreign_keys=[User.group_id])
    
    def is_full(self):
        return len(self.players) >= MAX_PLAYERS
        
    def to_dict(self):
        return {
            'id': self.id,
            'is_in_queue': self.is_in_queue,
            'queue_position': self.queue_position,
            'players': [player.username for player in self.players],
            'is_full': self.is_full()
        }
def get_user_group(user):
    """Get the group a user belongs to"""
    if isinstance(user, str):
        user = User.query.filter_by(username=user).first()
    if not user:
        return None
    return user.group

def is_user_active(user):
    """Check if user is in any group"""
    if isinstance(user, str):
        user = User.query.filter_by(username=user).first()
    if not user:
        return False
    return user.group is not None

def get_next_queue_position(court):
    """Get the next position for a new group in the queue"""
    max_position = db.session.query(db.func.max(Group.queue_position)).filter(
        Group.court_id == court.id, 
        Group.is_in_queue == True
    ).scalar()
    
    return 1 if max_position is None else max_position + 1
# Old court model
# courts = {f'Court {i}': {'players': [], 'queue': []} for i in range(1, 5)}  # 4 courts

MAX_PLAYERS = 4

def is_user_active_elsewhere(user):
    """Check if user is active on any court or in any queue"""
    if isinstance(user, str):
        user = User.query.filter_by(username=user).first()
    if not user:
        return False
    return user.court is not None or user.queue_entry is not None

def is_user_on_court_or_queue(username, court):
    """Check if user is on this specific court or in its queue"""
    if not username:
        return False
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return False
    
    # Check if user is on this court
    if user.court_id == court.id:
        return True
    
    # Check if user is in this court's queue
    for queue_entry in court.queue:
        if queue_entry.user_id == user.id:
            return True
    
    return False
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
    
    # Check if current user is admin
    username = session.get('user')
    is_admin = False
    if username:
        user = User.query.filter_by(username=username).first()
        if user and user.is_admin:
            is_admin = True
            
    return {
        'MAX_PLAYERS': MAX_PLAYERS,
        'is_user_active': is_user_active,  # Use the new helper function
        'is_user_active_elsewhere': is_user_active_elsewhere,  # Keep for backward compatibility
        'club_state': club_state,
        'is_player_on_court': is_player_on_court,
        'timer_state': timer_state,
        'is_user_on_court_or_queue': is_user_on_court_or_queue,
        'signature': get_random_signature(),
        'is_admin': is_admin 
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
        _username = request.form['username']
        _password = request.form['password']

        user = User.query.filter_by(username=_username).first()
        if user and check_password_hash(user.password_hash, _password):
            session['user'] = user.username
            
            # If user is admin, redirect to admin panel
            if user.is_admin:
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'error')
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
            flash('Username already exists', 'error')
            return render_template('signup.html', error='Username already exists')
        password_hash = generate_password_hash(password)
        new_user = User(username=username, password_hash=password_hash, is_admin=False)
        db.session.add(new_user)
        db.session.commit()

        flash('User created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/join-slot/<int:group_id>', methods=['POST'])
def join_slot(group_id):
    if 'user' not in session:
        flash('You must be logged in', 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'You must be logged in'}), 401
        return redirect(url_for('login'))
    
    username = session['user']
    user = User.query.filter_by(username=username).first()
    group = Group.query.get(group_id)
    
    if not group:
        flash('Group not found', 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Group not found'})
        return redirect(url_for('home'))
    
    if user.group:
        flash('You are already in a group', 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'You are already in a group'})
        return redirect(url_for('home'))
    
    if len(group.players) >= MAX_PLAYERS:
        flash('Group is full', 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Group is full'})
        return redirect(url_for('home'))
    
    # Add user to group
    user.group = group
    db.session.commit()
    
    court_name = group.court.name
    message = f'You joined a {"court" if not group.is_in_queue else "queue"} group for {court_name}'
    flash(message, 'success')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'court_id': group.court.id,
            'group_id': group.id,
            'message': message
        })
    
    return redirect(url_for('home'))

@app.route('/create-new-group/<int:court_id>', methods=['POST'])
def create_new_group(court_id):
    if 'user' not in session:
        flash('You must be logged in', 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'You must be logged in'}), 401
        return redirect(url_for('login'))
    
    username = session['user']
    user = User.query.filter_by(username=username).first()
    court = Court.query.get(court_id)
    
    if not court:
        flash('Court not found', 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Court not found'})
        return redirect(url_for('home'))
    
    if user.group:
        flash('You are already in a group', 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'You are already in a group'})
        return redirect(url_for('home'))
    
    # Create new group in queue
    next_position = get_next_queue_position(court)
    new_group = Group(
        court=court,
        is_in_queue=True,
        queue_position=next_position
    )
    
    db.session.add(new_group)
    db.session.flush()  # Flush to get the new group ID
    
    # Add user to the new group
    user.group = new_group
    db.session.commit()
    
    message = f'You created a new group in the queue for {court.name}'
    flash(message, 'success')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'court_id': court.id,
            'group_id': new_group.id,
            'message': message
        })
    
    return redirect(url_for('home'))
@app.route('/leave-group', methods=['POST'])
def leave_group():
    if 'user' not in session:
        flash('You must be logged in', 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'You must be logged in'}), 401
        return redirect(url_for('login'))
    
    username = session['user']
    user = User.query.filter_by(username=username).first()
    
    if not user.group:
        flash('You are not in any group', 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'You are not in any group'})
        return redirect(url_for('home'))
    
    group = user.group
    court = group.court
    court_name = court.name
    
    # Check if group is on court and timer is running
    timer_state = TimerState.query.first()
    if not group.is_in_queue and timer_state.is_running:
        flash('Cannot leave court while timer is running', 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Cannot leave court while timer is running'})
        return redirect(url_for('home'))
    
    # Remove user from group
    user.group = None
    
    # MODIFIED: We don't delete empty groups anymore, we keep them with empty slots
    # We only want to reorder queue positions if it's an empty queue group at the END of the queue
    if group.is_in_queue:
        # Count players in the group
        remaining_players = [p for p in group.players if p.id != user.id]
        
        # If this is an empty group AND it's the last group in the queue, delete it
        last_position = db.session.query(db.func.max(Group.queue_position)).filter(
            Group.court_id == court.id,
            Group.is_in_queue == True
        ).scalar() or 0
        
        if not remaining_players and group.queue_position == last_position:
            db.session.delete(group)
    
    db.session.commit()
    
    message = f'You left the {"court" if not group.is_in_queue else "queue"} group for {court_name}'
    flash(message, 'warning')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'court_id': court.id,
            'message': message
        })
    
    return redirect(url_for('home'))

@app.route('/admin')
def admin():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['user']).first()
    if not user or not user.is_admin:
        flash('You do not have permission to access the admin page', 'error')
        return redirect(url_for('home'))
    
    return render_template('admin.html', 
                         courts=Court.query.all(),
                         users=User.query.all())

@app.route('/admin/<action>', methods=['POST'])
def admin_actions(action):
    """Consolidated admin actions endpoint"""
    if not _is_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json() or {}
    
    if action == 'remove-player-from-group':
        return _admin_remove_player(data.get('player_id'))
    elif action == 'move-player':
        return _admin_move_player(data.get('player_id'), data.get('group_id'))
    elif action == 'create-group':
        return _admin_create_group(data.get('court_id'), data.get('is_queue', False))
    else:
        return jsonify({'success': False, 'message': 'Invalid action'}), 400

def _is_admin():
    """Helper to check admin status"""
    if 'user' not in session:
        return False
    user = User.query.filter_by(username=session['user']).first()
    return user and user.is_admin

def _admin_remove_player(player_id):
    """Remove player from their group"""
    if not player_id:
        return jsonify({'success': False, 'message': 'Missing player_id'})
    
    player = User.query.get(player_id)
    if not player:
        return jsonify({'success': False, 'message': 'Player not found'})
    
    player.group = None
    db.session.commit()
    return jsonify({'success': True, 'message': 'Player removed successfully'})

def _admin_move_player(player_id, group_id):
    """Move player to a different group"""
    if not player_id or not group_id:
        return jsonify({'success': False, 'message': 'Missing required parameters'})
    
    player = User.query.get(player_id)
    group = Group.query.get(group_id)
    
    if not player:
        return jsonify({'success': False, 'message': 'Player not found'})
    if not group:
        return jsonify({'success': False, 'message': 'Group not found'})
    if len(group.players) >= MAX_PLAYERS:
        return jsonify({'success': False, 'message': 'Group is full'})
    
    # Clean up old empty group if needed
    old_group = player.group
    if old_group and len(old_group.players) == 1 and old_group.is_in_queue:
        db.session.delete(old_group)
    
    player.group = group
    db.session.commit()
    return jsonify({'success': True, 'message': 'Player moved successfully'})
@app.route('/admin/remove-queue-group', methods=['POST'])
def admin_remove_queue_group():
    """Admin function to remove a queue group"""
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    current_user = User.query.filter_by(username=session['user']).first()
    if not current_user or not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    group_id = data.get('group_id')
    
    if not group_id:
        return jsonify({'success': False, 'message': 'Missing group_id'})
    
    group = Group.query.get(group_id)
    
    if not group:
        return jsonify({'success': False, 'message': 'Group not found'})
    
    if not group.is_in_queue:
        return jsonify({'success': False, 'message': 'This is not a queue group'})
    
    court = group.court
    removed_position = group.queue_position
    
    # Remove all players from the group first
    for player in group.players:
        player.group = None
    
    # Delete the group
    db.session.delete(group)
    
    # Reorder remaining queue positions
    remaining_queue_groups = Group.query.filter(
        Group.court_id == court.id,
        Group.is_in_queue == True,
        Group.queue_position > removed_position
    ).order_by(Group.queue_position).all()
    
    # Move all groups after the removed one up by one position
    for queue_group in remaining_queue_groups:
        queue_group.queue_position -= 1
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Queue group removed successfully'})
def _admin_create_group(court_id, is_queue):
    """Create a new group on a court"""
    if not court_id:
        return jsonify({'success': False, 'message': 'Missing court_id'})
    
    court = Court.query.get(court_id)
    if not court:
        return jsonify({'success': False, 'message': 'Court not found'})
    
    if is_queue:
        next_position = get_next_queue_position(court)
        new_group = Group(court=court, is_in_queue=True, queue_position=next_position)
    else:
        new_group = Group(court=court, is_in_queue=False, queue_position=None)
    
    db.session.add(new_group)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Created new {"queue" if is_queue else "active"} group',
        'group_id': new_group.id
    })

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
            app.logger.info("⏰ Timer expired — rotating groups!")

            # Mark timer as stopped
            timer_state.is_running = False
            timer_state.remaining_time = 0
            timer_state.start_time = None
            timer_state.end_time = None

            # Process each court
            for court in courts:
                # Get active groups on court and queue groups
                active_groups = [g for g in court.groups if not g.is_in_queue]
                queue_groups = sorted(
                    [g for g in court.groups if g.is_in_queue],
                    key=lambda g: g.queue_position
                )
                
                # Remove all groups from court
                for group in active_groups:
                    # If the group has no players, just delete it
                    if not group.players:
                        db.session.delete(group)
                    else:
                        # Otherwise mark as deleted - will be fully removed after commit
                        db.session.delete(group)
                
                # Promote queue groups to court if available
                for queue_group in queue_groups[:1]:  # Only promote first group
                    queue_group.is_in_queue = False
                    queue_group.queue_position = None
                
                # Reorder remaining queue
                remaining_queue = queue_groups[1:] if queue_groups else []
                for idx, group in enumerate(remaining_queue):
                    group.queue_position = idx + 1
                
                # Ensure there's always an active group on the court
                # Check if court now has any active groups
                has_active_group = any(not g.is_in_queue for g in court.groups)
                if not has_active_group:
                    # Create a new empty active group
                    new_active_group = Group(
                        court=court,
                        is_in_queue=False,
                        queue_position=None
                    )
                    db.session.add(new_active_group)

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

@app.route('/timer/stop', methods=['POST'])
def stop_timer():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.filter_by(username=session['user']).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401
    
    timer_state = TimerState.query.first()
    if timer_state.is_running:
        now = datetime.now().timestamp()
        elapsed = now - timer_state.start_time
        timer_state.remaining_time = max(0, timer_state.remaining_time - elapsed)
        timer_state.is_running = False
        timer_state.start_time = None
        timer_state.end_time = None
        db.session.commit()
    
    return jsonify({
        'status': 'success',
        'remaining': timer_state.remaining_time
    })
@app.route('/clear-courts', methods=['POST'])
def clear_courts():
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.filter_by(username=username).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401

    # Clear all groups from all courts
    users = User.query.all()
    for user in users:
        user.group = None
    
    groups = Group.query.all()
    for group in groups:
        db.session.delete(group)
    
    db.session.commit()
    
    # Create one empty active group per court
    courts = Court.query.all()
    for court in courts:
        active_group = Group(
            court=court,
            is_in_queue=False,
            queue_position=None
        )
        db.session.add(active_group)
    
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'All courts cleared'})

@app.route('/create-empty-active-group/<int:court_id>', methods=['POST'])
def create_empty_active_group(court_id):
    court = Court.query.get(court_id)
    if not court:
        return jsonify({'success': False, 'message': 'Court not found'})
    
    # Check if there's already an active group
    existing_active = Group.query.filter_by(court=court, is_in_queue=False).first()
    if existing_active:
        return jsonify({
            'success': True, 
            'group_id': existing_active.id,
            'message': 'Using existing active group'
        })
    
    # Create a new empty active group
    active_group = Group(
        court=court,
        is_in_queue=False,
        queue_position=None
    )
    db.session.add(active_group)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'group_id': active_group.id,
        'message': 'Created new active group'
    })
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

@app.route('/technical-notes')
def technical_notes():
    return render_template('technical_notes.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')
    
@app.route('/club-status')
def get_club_status():
    club_state = ClubState.query.first()
    return jsonify({
        'is_active': club_state.is_active,
        'last_modified': club_state.last_modified.timestamp()
    })

import hashlib

@app.route('/court-updates')
def court_updates():
    def generate():
        last_hash = None
        while True:
            with app.app_context():
                courts = Court.query.all()
                
                court_data = {}
                for court in courts:
                    # Get active groups on court
                    active_groups = [g for g in court.groups if not g.is_in_queue]
                    active_group_data = [{
                        'id': g.id,
                        'players': [p.username for p in g.players],
                        'is_full': len(g.players) >= MAX_PLAYERS
                    } for g in active_groups]
                    
                    # Get queue groups
                    queue_groups = sorted(
                        [g for g in court.groups if g.is_in_queue],
                        key=lambda g: g.queue_position
                    )
                    queue_group_data = [{
                        'id': g.id,
                        'position': g.queue_position,
                        'players': [p.username for p in g.players],
                        'is_full': len(g.players) >= MAX_PLAYERS
                    } for g in queue_groups]
                    
                    court_data[court.name] = {
                        'id': court.id,
                        'active_groups': active_group_data,
                        'queue_groups': queue_group_data
                    }
                
                # Calculate a hash of the data to see if it has changed
                court_json = json.dumps({'courts': court_data})
                current_hash = hashlib.md5(court_json.encode()).hexdigest()
                
                # Only send an update if the data has changed
                if current_hash != last_hash:
                    last_hash = current_hash
                    data = f"data: {court_json}\n\n"
                    yield data
                    
            sleep(1)
    
    return Response(generate(), mimetype='text/event-stream')

# Also update the poll endpoint for consistency
@app.route('/court-updates-poll')
def court_updates_poll():
    """Fallback endpoint for environments where SSE doesn't work"""
    courts = Court.query.all()
    
    court_data = {}
    for court in courts:
        # Get active groups on court
        active_groups = [g for g in court.groups if not g.is_in_queue]
        active_group_data = [{
            'id': g.id,
            'players': [p.username for p in g.players],
            'is_full': len(g.players) >= MAX_PLAYERS
        } for g in active_groups]
        
        # Get queue groups
        queue_groups = sorted(
            [g for g in court.groups if g.is_in_queue],
            key=lambda g: g.queue_position
        )
        queue_group_data = [{
            'id': g.id,
            'position': g.queue_position,
            'players': [p.username for p in g.players],
            'is_full': len(g.players) >= MAX_PLAYERS
        } for g in queue_groups]
        
        court_data[court.name] = {
            'id': court.id,
            'active_groups': active_group_data,
            'queue_groups': queue_group_data
        }
    
    # Add a timestamp to the data
    response_data = {
        'courts': court_data,
        'timestamp': datetime.now().timestamp()
    }
    
    return jsonify(response_data)

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
        if not TimerState.query.first():
            timer_state = TimerState(is_running=False)  # adjust fields as per your model
            db.session.add(timer_state)

        # Create default ClubState if none exists
        if not ClubState.query.first():
            club_state = ClubState()  # fill in default fields if needed
            db.session.add(club_state)
        
        # Add admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password_hash=generate_password_hash('adminpass'),
                is_admin=True
            )
            db.session.add(admin)
            
        # Add test users
        test_users = ['a', 'b', 'c']
        for username in test_users:
            if not User.query.filter_by(username=username).first():
                user = User(
                    username=username,
                    password_hash=generate_password_hash(username),  # password same as username
                    is_admin=False
                )
                db.session.add(user)
                
        # Commit to create courts and users first
        db.session.commit()
                
        # Create one empty active group per court
        courts = Court.query.all()
        for court in courts:
            # Check if court already has an active group
            existing_active = Group.query.filter_by(court=court, is_in_queue=False).first()
            if not existing_active:
                active_group = Group(
                    court=court,
                    is_in_queue=False,
                    queue_position=None
                )
                db.session.add(active_group)
                
        # Commit all changes
        db.session.commit()
        
    app.run(host="0.0.0.0", port=5001, debug=True)
