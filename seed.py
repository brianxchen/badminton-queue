# seed.py
from app import app, db, Court, TimerState, ClubState, User
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()  # or db.drop_all(); db.create_all() if you want fresh tables

    # Seed default courts
    if not Court.query.first():
        default_courts = ['Court 1', 'Court 2', 'Court 3', 'Court 4']
        for name in default_courts:
            db.session.add(Court(name=name))

    # Seed default TimerState
    if not TimerState.query.first():
        db.session.add(TimerState(is_running=False))

    # Seed default ClubState
    if not ClubState.query.first():
        db.session.add(ClubState())

    # Seed default admin user
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(
            username='admin',
            password_hash=generate_password_hash('adminpass'),
            is_admin=True
        ))

    # Add test users
    for username in ['a', 'b', 'c']:
        if not User.query.filter_by(username=username).first():
            db.session.add(User(
                username=username,
                password_hash=generate_password_hash(username),
                is_admin=False
            ))

    db.session.commit()
    print("✅ Seeding done!")
