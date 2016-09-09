#!/usr/bin/env python
import os
from flask import Flask, abort, request, jsonify, g, url_for
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.httpauth import HTTPBasicAuth
from passlib.apps import custom_app_context as pwd_context
from itsdangerous import (TimedJSONWebSignatureSerializer
                          as Serializer, BadSignature, SignatureExpired)
from datetime import datetime

# initialization
app = Flask(__name__)
app.config['SECRET_KEY'] = 'the quick brown fox jumps over the lazy dog'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True

# extensions
db = SQLAlchemy(app)
auth = HTTPBasicAuth()


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


class ActivityType(db.Model):
    __tablename__ = 'activity_types'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_date = db.Column(db.DateTime, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    show_rating = db.Column(db.Boolean, nullable=False)

    def __init__(self):
        self.created_date = datetime.utcnow()

    def serialize(self):  
        return {           
            'created_date': self.created_date, 
            'name': self.name,
            'show_rating': self.show_rating
        }


class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_date = db.Column(db.DateTime, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    activity_type_id = db.Column(db.Integer, db.ForeignKey('activity_types.id'), nullable=False)

    def __init__(self):
        self.created_date = datetime.utcnow()

    def serialize(self):  
        return {           
            'created_date': self.created_date, 
            'name': self.name
        }


@auth.verify_password
def verify_password(username_or_token, password):
    # first try to authenticate by token
    user = User.verify_auth_token(username_or_token)
    if not user:
        # try to authenticate with username/password
        user = User.query.filter_by(username=username_or_token).first()
        if not user or not user.verify_password(password):
            return False
    g.user = user
    return True


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


@app.route('/api/activity_types', methods=['POST'])
@auth.login_required
def new_activity_type():
    user_id = g.user.id
    name = request.json.get('name')
    show_rating = request.json.get('show_rating')
    
    activity_type = ActivityType()
    activity_type.user_id = user_id
    activity_type.name = name
    activity_type.show_rating = show_rating

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


if __name__ == '__main__':
    if not os.path.exists('db.sqlite'):
        db.create_all()
    app.run(debug=True)