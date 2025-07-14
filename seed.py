# seed.py
from app import app, db, Court, TimerState, ClubState, User, Group
from werkzeug.security import generate_password_hash
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
        timer_state = TimerState(is_running=False)
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
    print("✅ Seeding done!")
