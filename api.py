#!/usr/bin/env python
import os
from flask import Flask, abort, request, jsonify, g, url_for, Response
from flask_cors import CORS
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.httpauth import HTTPBasicAuth
from passlib.apps import custom_app_context as pwd_context
from itsdangerous import (TimedJSONWebSignatureSerializer
                          as Serializer, BadSignature, SignatureExpired)
from datetime import datetime
import time
import json

# initialization
app = Flask(__name__)
app.config['SECRET_KEY'] = 'the quick brown fox jumps over the lazy dog'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True

# extensions
db = SQLAlchemy(app)
auth = HTTPBasicAuth()

# A Flask extension for handling Cross Origin Resource Sharing (CORS)
CORS(app)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), index=True)
    password_hash = db.Column(db.String(64))

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def generate_auth_token(self, expiration=600):
        s = Serializer(app.config['SECRET_KEY'], expires_in=expiration)
        return s.dumps({'id': self.id})

    @staticmethod
    def verify_auth_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except SignatureExpired:
            return None    # valid token, but expired
        except BadSignature:
            return None    # invalid token
        user = User.query.get(data['id'])
        return user

    @staticmethod
    def verify_user_and_password(username_or_token, password):
        # first try to authenticate by token
        user = User.verify_auth_token(username_or_token)
        if not user:
            # try to authenticate with username/password
            user = User.query.filter_by(username=username_or_token).first()
            if not user or not user.verify_password(password):
                return False
        g.user = user
        return True


class ActivityType(db.Model):
    __tablename__ = 'activity_types'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_date = db.Column(db.DateTime, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    show_quantity = db.Column(db.Boolean, nullable=False)
    show_rating = db.Column(db.Boolean, nullable=False)

    def __init__(self):
        self.created_date = datetime.utcnow()

    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'show_quantity': self.show_quantity,
            'show_rating': self.show_rating
        }


class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_date = db.Column(db.DateTime, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    activity_type_id = db.Column(db.Integer, db.ForeignKey('activity_types.id'), nullable=False)
    activity_type = db.relationship('ActivityType', backref=db.backref('activities', lazy='dynamic'))

    def __init__(self):
        self.created_date = datetime.utcnow()

    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'activity_type': ActivityType.serialize(self.activity_type)
        }


class Day(db.Model):
    __tablename__ = 'days'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_date = db.Column(db.DateTime, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    note = db.Column(db.String(4096))
    life_entries = db.relationship('LifeEntry', backref='days', lazy='dynamic')

    def __init__(self):
        self.created_date = datetime.utcnow()

    def serialize(self):
        return {
            'id': self.id,
            'date': get_date_string(self.date),
            'note': self.note,
            'life_entries': [LifeEntry.serialize(life_entry) for life_entry in self.life_entries]
        }


class LifeEntry(db.Model):
    __tablename__ = 'life_entries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_date = db.Column(db.DateTime, nullable=False)
    day_id = db.Column(db.Integer, db.ForeignKey('days.id'), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time)
    life_entry_activities = db.relationship('LifeEntryActivity', backref='life_entries', lazy='dynamic')

    def __init__(self):
        self.created_date = datetime.utcnow()

    def serialize(self):
        return {
            'id': self.id,
            'day_id': self.day_id,
            'start_time': get_time_string(self.start_time),
            'end_time': get_time_string(self.end_time),
            'life_entry_activities': [LifeEntryActivity.serialize(life_entry_activity) for life_entry_activity in self.life_entry_activities]
        }


class LifeEntryActivity(db.Model):
    __tablename__ = 'life_entry_activities'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_date = db.Column(db.DateTime, nullable=False)
    life_entry_id = db.Column(db.Integer, db.ForeignKey('life_entries.id'), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'), nullable=False)
    description = db.Column(db.String(512))
    quantity = db.Column(db.Float)
    rating = db.Column(db.Integer)
    activity = db.relationship('Activity', backref=db.backref('life_entry_activities', lazy='dynamic'))

    def __init__(self):
        self.created_date = datetime.utcnow()

    def serialize(self):
        return {
            'id': self.id,
            'life_entry_id': self.life_entry_id,
            'description': self.description,
            'quantity': self.quantity,
            'rating': self.rating,
            'activity': Activity.serialize(self.activity)
        }


def get_time_string(my_time):
    if my_time is not None:
        time_tuple = (0, 0, 0, my_time.hour, my_time.minute, my_time.second, 0, 0, 0)
        return time.strftime("%H:%M:%S", time_tuple)
    else:
        return None


def get_date_string(my_date):
    if my_date is not None:
        return my_date.strftime('%Y-%m-%d')
    else:
        return None


@auth.verify_password
def verify_password(username_or_token, password):
    return User.verify_user_and_password(username_or_token, password)


@app.route('/api/authenticate', methods=['POST'])
def authenticate():
    username = request.json.get('username')
    password = request.json.get('password')

    if User.verify_user_and_password(username, password):
        result = 1
    else:
        result = 0

    return (jsonify({'authenticate_result': result}), 200)


@app.route('/api/users', methods=['POST'])
def new_user():
    username = request.json.get('username')
    password = request.json.get('password')
    if username is None or password is None:
        abort(400)    # missing arguments
    if User.query.filter_by(username=username).first() is not None:
        abort(400)    # existing user
    user = User(username=username)
    user.hash_password(password)
    db.session.add(user)
    db.session.commit()
    return (jsonify({'username': user.username}), 201,
            {'Location': url_for('get_user', id=user.id, _external=True)})


@app.route('/api/users/<int:id>')
def get_user(id):
    user = User.query.get(id)
    if not user:
        abort(400)
    return jsonify({'username': user.username})


@app.route('/api/token')
@auth.login_required
def get_auth_token():
    token = g.user.generate_auth_token(600)
    return jsonify({'token': token.decode('ascii'), 'duration': 600})


@app.route('/api/activity_types')
@auth.login_required
def get_activity_types():
    activity_types = ActivityType.query.filter_by(user_id=g.user.id).all()
    serialized_array = [ActivityType.serialize(activity_type) for activity_type in activity_types]
    return Response(json.dumps(serialized_array), mimetype='application/json')


@app.route('/api/activity_types', methods=['POST'])
@auth.login_required
def new_activity_type():
    user_id = g.user.id
    name = request.json.get('name')
    show_rating = request.json.get('show_rating')
    show_quantity = request.json.get('show_quantity')
    
    activity_type = ActivityType()
    activity_type.user_id = user_id
    activity_type.name = name
    activity_type.show_rating = show_rating
    activity_type.show_quantity = show_quantity

    db.session.add(activity_type)
    db.session.commit()
    return (jsonify(ActivityType.serialize(activity_type)), 201,
            {'Location': url_for('get_activity_type', id=activity_type.id, _external=True)})


@app.route('/api/activity_types/<int:id>')
@auth.login_required
def get_activity_type(id):
    activity_type = ActivityType.query.get(id)
    if not activity_type:
        abort(400)
    if activity_type.user_id != g.user.id:
        abort(401)
    return jsonify(ActivityType.serialize(activity_type))


@app.route('/api/activity_types/<int:id>', methods=['PUT'])
@auth.login_required
def update_activity_type(id):
    activity_type = ActivityType.query.get(id)
    if not activity_type:
        abort(400)
    if activity_type.user_id != g.user.id:
        abort(401)

    name = request.json.get('name')
    show_rating = request.json.get('show_rating')

    activity_type.name = name
    activity_type.show_rating = show_rating

    db.session.commit()

    return jsonify(ActivityType.serialize(activity_type))


@app.route('/api/activity_types/<int:id>', methods=['DELETE'])
@auth.login_required
def delete_activity_type(id):
    activity_type = ActivityType.query.get(id)
    if not activity_type:
        abort(400)
    if activity_type.user_id != g.user.id:
        abort(401)

    db.session.delete(activity_type)
    db.session.commit()

    return ''


@app.route('/api/activity_types/search/<search_term>')
@auth.login_required
def search_activity_type(search_term):
    activity_types = ActivityType.query.filter_by(user_id=g.user.id).filter(ActivityType.name.like('%'+search_term+'%')).all()
    serialized_array = [ActivityType.serialize(activity_type) for activity_type in activity_types]
    return Response(json.dumps(serialized_array), mimetype='application/json')


@app.route('/api/activities')
@auth.login_required
def get_activities():
    activities = Activity.query.filter_by(user_id=g.user.id).all()
    serialized_array = [Activity.serialize(activity) for activity in activities]
    return Response(json.dumps(serialized_array), mimetype='application/json')


@app.route('/api/activities', methods=['POST'])
@auth.login_required
def new_activity():
    user_id = g.user.id
    name = request.json.get('name')
    activity_type_id = request.json.get('activity_type_id')
    
    activity_type = ActivityType.query.get(activity_type_id)
    if not activity_type:
        abort(400)
    if activity_type.user_id != g.user.id:
        abort(401)

    activity = Activity()
    activity.user_id = user_id
    activity.name = name
    activity.activity_type_id = activity_type_id

    db.session.add(activity)
    db.session.commit()
    return (jsonify(Activity.serialize(activity)), 201,
            {'Location': url_for('get_activity', id=activity.id, _external=True)})


@app.route('/api/activities/<int:id>')
@auth.login_required
def get_activity(id):
    activity = Activity.query.get(id)
    if not activity:
        abort(400)
    if activity.user_id != g.user.id:
        abort(401)
    return jsonify(Activity.serialize(activity))


@app.route('/api/activities/<int:id>', methods=['PUT'])
@auth.login_required
def update_activity(id):
    activity = Activity.query.get(id)
    if not activity:
        abort(400)
    if activity.user_id != g.user.id:
        abort(401)

    name = request.json.get('name')
    activity_type_id = request.json.get('activity_type_id')

    activity.name = name
    activity.activity_type_id = activity_type_id

    db.session.commit()

    return jsonify(Activity.serialize(activity))


@app.route('/api/activities/<int:id>', methods=['DELETE'])
@auth.login_required
def delete_activity(id):
    activity = Activity.query.get(id)
    if not activity:
        abort(400)
    if activity.user_id != g.user.id:
        abort(401)

    db.session.delete(activity)
    db.session.commit()

    return ''


@app.route('/api/activities/search/<search_term>')
@auth.login_required
def search_activity(search_term):
    activities = Activity.query.filter_by(user_id=g.user.id).filter(Activity.name.like('%'+search_term+'%')).all()
    serialized_array = [Activity.serialize(activity) for activity in activities]
    return Response(json.dumps(serialized_array), mimetype='application/json')


@app.route('/api/days', methods=['POST'])
@auth.login_required
def new_day():
    user_id = g.user.id
    date = datetime.strptime(request.json.get('date'), '%Y-%m-%d')
    note = request.json.get('note')
    
    if Day.query.filter_by(date=date).first() is not None:
        abort(400)

    day = Day()
    day.user_id = user_id
    day.date = date
    day.note = note

    db.session.add(day)
    db.session.commit()
    return (jsonify(Day.serialize(day)), 201,
            {'Location': url_for('get_day', id=day.id, _external=True)})


@app.route('/api/days/<int:id>')
@auth.login_required
def get_day(id):
    day = Day.query.get(id)
    if not day:
        abort(400)
    if day.user_id != g.user.id:
        abort(401)
    return jsonify(Day.serialize(day))


@app.route('/api/days/<selected_date>')
@auth.login_required
def get_day_by_date(selected_date):
    date = datetime.strptime(selected_date, '%Y-%m-%d')
    day = Day.query.filter((Day.user_id == g.user.id) & (Day.date == date)).first()
    if not day:
        abort(404)
    return jsonify(Day.serialize(day))


@app.route('/api/days/<int:id>', methods=['PUT'])
@auth.login_required
def update_day(id):
    day = Day.query.get(id)
    if not day:
        abort(400)
    if day.user_id != g.user.id:
        abort(401)

    note = request.json.get('note')

    day.note = note
    db.session.commit()

    return jsonify(Day.serialize(day))


@app.route('/api/life_entries', methods=['POST'])
@auth.login_required
def new_life_entry():
    user_id = g.user.id
    day_id = request.json.get('day_id')
    request_start_time = request.json.get('start_time')
    request_end_time = request.json.get('end_time')

    start_time = datetime.strptime(request_start_time, '%H:%M').time()
    if request_end_time:
        end_time = datetime.strptime(request_end_time, '%H:%M').time()
    else:
        end_time = None
    
    day = Day.query.get(day_id)
    if not day:
        abort(400)
    if day.user_id != g.user.id:
        abort(401)

    life_entry = LifeEntry()
    life_entry.user_id = user_id
    life_entry.day_id = day_id
    life_entry.start_time = start_time
    life_entry.end_time = end_time

    db.session.add(life_entry)
    db.session.commit()
    return (jsonify(LifeEntry.serialize(life_entry)), 201,
            {'Location': url_for('get_life_entry', id=life_entry.id, _external=True)})


@app.route('/api/life_entries/<int:id>')
@auth.login_required
def get_life_entry(id):
    life_entry = LifeEntry.query.get(id)
    if not life_entry:
        abort(400)
    if life_entry.user_id != g.user.id:
        abort(401)
    return jsonify(LifeEntry.serialize(life_entry))


@app.route('/api/life_entries/<int:id>', methods=['PUT'])
@auth.login_required
def update_life_entry(id):
    life_entry = LifeEntry.query.get(id)
    if not life_entry:
        abort(400)
    if life_entry.user_id != g.user.id:
        abort(401)

    request_start_time = request.json.get('start_time')
    request_end_time = request.json.get('end_time')

    start_time = datetime.strptime(request_start_time, '%H:%M').time()
    if request_end_time:
        end_time = datetime.strptime(request_end_time, '%H:%M').time()
    else:
        end_time = None

    life_entry.start_time = start_time
    life_entry.end_time = end_time

    db.session.commit()

    return jsonify(LifeEntry.serialize(life_entry))


@app.route('/api/life_entries/<int:id>', methods=['DELETE'])
@auth.login_required
def delete_life_entry(id):
    life_entry = LifeEntry.query.get(id)
    if not life_entry:
        abort(400)
    if life_entry.user_id != g.user.id:
        abort(401)

    db.session.query(LifeEntryActivity).filter_by(life_entry_id=life_entry.id).delete()
    db.session.delete(life_entry)

    db.session.commit()
    return ''


@app.route('/api/life_entry_activities', methods=['POST'])
@auth.login_required
def new_life_entry_activity():
    user_id = g.user.id
    life_entry_id = request.json.get('life_entry_id')
    activity_id = request.json.get('activity_id')
    description = request.json.get('description')
    quantity = request.json.get('quantity')
    rating = request.json.get('rating')

    life_entry = LifeEntry.query.get(life_entry_id)
    if not life_entry:
        abort(400)
    if life_entry.user_id != g.user.id:
        abort(401)

    activity = Activity.query.get(activity_id)
    if not activity:
        abort(400)
    if activity.user_id != g.user.id:
        abort(401)

    life_entry_activity = LifeEntryActivity()
    life_entry_activity.user_id = user_id
    life_entry_activity.life_entry_id = life_entry_id
    life_entry_activity.activity_id = activity_id
    life_entry_activity.description = description
    life_entry_activity.quantity = quantity
    life_entry_activity.rating = rating

    db.session.add(life_entry_activity)
    db.session.commit()
    return (jsonify(LifeEntryActivity.serialize(life_entry_activity)), 201,
            {'Location': url_for('get_life_entry_activity', id=life_entry_activity.id, _external=True)})


@app.route('/api/life_entry_activities/<int:id>')
@auth.login_required
def get_life_entry_activity(id):
    life_entry_activity = LifeEntryActivity.query.get(id)
    if not life_entry_activity:
        abort(400)
    if life_entry_activity.user_id != g.user.id:
        abort(401)
    return jsonify(LifeEntryActivity.serialize(life_entry_activity))


@app.route('/api/life_entry_activities/<int:id>', methods=['PUT'])
@auth.login_required
def update_life_entry_activity(id):
    life_entry_activity = LifeEntryActivity.query.get(id)
    if not life_entry_activity:
        abort(400)
    if life_entry_activity.user_id != g.user.id:
        abort(401)

    activity_id = request.json.get('activity_id')
    description = request.json.get('description')
    quantity = request.json.get('quantity')
    rating = request.json.get('rating')

    activity = Activity.query.get(activity_id)
    if not activity:
        abort(400)
    if activity.user_id != g.user.id:
        abort(401)

    life_entry_activity.activity_id = activity_id
    life_entry_activity.description = description
    life_entry_activity.quantity = quantity
    life_entry_activity.rating = rating

    db.session.commit()

    return jsonify(LifeEntryActivity.serialize(life_entry_activity))


@app.route('/api/life_entry_activities/<int:id>', methods=['DELETE'])
@auth.login_required
def delete_life_entry_activity(id):
    life_entry_activity = LifeEntryActivity.query.get(id)
    if not life_entry_activity:
        abort(400)
    if life_entry_activity.user_id != g.user.id:
        abort(401)

    db.session.delete(life_entry_activity)
    db.session.commit()

    return ''


if __name__ == '__main__':
    if not os.path.exists('db.sqlite'):
        db.create_all()
    app.run(debug=True)