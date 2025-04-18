from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'supersecretkey'

db = SQLAlchemy(app)
migrate = Migrate(app, db) 
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    skills = db.Column(db.String(150), nullable=False)
    password = db.Column(db.String(256), nullable=False)


class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    skills = db.Column(db.Text, nullable=False)
    experience = db.Column(db.Text, nullable=False)
    education = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(255))  # Store PDF path

    user = db.relationship('User', backref=db.backref('resume', lazy=True))

    if __name__ == "__main__":
        db.create_all()
    print("Database created successfully!")