from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import random

app = Flask(__name__)
app.secret_key = "tajna_kljucccc"  # Secret key for session management

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quiz_app.db'  # SQLite database
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Flask-Login configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Database models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    scores = db.relationship('Score', backref='user', lazy=True)

class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=db.func.current_timestamp())

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Home route
@app.route('/', methods=['GET', 'POST'])
def home():
    categories = [
        {"id": 9, "name": "General Knowledge"},
        {"id": 10, "name": "Entertainment: Books"},
        {"id": 11, "name": "Entertainment: Film"},
        {"id": 12, "name": "Entertainment: Music"},
        {"id": 17, "name": "Science & Nature"},
        {"id": 18, "name": "Science: Computers"},
        {"id": 21, "name": "Sports"},
        {"id": 23, "name": "History"},
    ]

    if request.method == 'POST':
        selected_category = request.form.get('category')
        if selected_category:
            session['selected_category'] = selected_category
            return redirect(url_for('quiz'))
        else:
            flash('Please select a category before proceeding.')

    return render_template('index.html', categories=categories)

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        if User.query.filter_by(username=username).first():
            flash('Username already exists!')
            return redirect(url_for('register'))

        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))

    return render_template('register.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and password:
            login_user(user)
            flash('Successfully logged in!')
            return redirect(url_for('quiz'))
        else:
            flash('Invalid username or password.')

    return render_template('login.html')

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Successfully logged out!')
    return redirect(url_for('home'))

# Quiz route
@app.route('/quiz', methods=['GET', 'POST'])
@login_required
def quiz():
    if 'api_token' not in session:
        token_response = requests.get('https://opentdb.com/api_token.php?command=request')
        if token_response.status_code == 200:
            session['api_token'] = token_response.json().get('token')
        else:
            flash('Failed to initialize quiz session. Try again later.')
            return redirect(url_for('home'))

    if 'quiz_questions' not in session or not session.get('quiz_questions'):
        token = session['api_token']
        category = session.get('selected_category', 9)  # Default to General Knowledge
        quiz_response = requests.get(f'https://opentdb.com/api.php?amount=10&category={category}&type=multiple&token={token}')
        if quiz_response.status_code != 200 or not quiz_response.json().get('results'):
            flash('Failed to fetch quiz questions. Please try again later.')
            return redirect(url_for('home'))

        quiz_data = quiz_response.json()
        session['quiz_questions'] = []
        for question in quiz_data['results']:
            options = question['incorrect_answers'] + [question['correct_answer']]
            random.shuffle(options)
            session['quiz_questions'].append({
                'question': question['question'],
                'options': options,
                'correct_answer': question['correct_answer']
            })

        session['current_question_index'] = 0
        session['correct_count'] = 0
        session['total_questions'] = len(session['quiz_questions'])
        session.permanent = True

    current_index = session.get('current_question_index', 0)
    if current_index >= session['total_questions']:
        return redirect(url_for('results'))

    current_question = session['quiz_questions'][current_index]

    if request.method == 'POST':
        selected_answer = request.form.get('answer')
        if not selected_answer:
            flash('Please select an answer before submitting.')
            return redirect(url_for('quiz'))

        if selected_answer == current_question['correct_answer']:
            session['correct_count'] += 1

        session['current_question_index'] += 1
        session.modified = True

        if session['current_question_index'] >= session['total_questions']:
            return redirect(url_for('results'))

        return redirect(url_for('quiz'))

    return render_template(
        'quiz.html',
        question=current_question['question'],
        options=current_question['options'],
        current_question=current_index + 1,
        total_questions=session['total_questions']
    )

# Results route
@app.route('/results')
@login_required
def results():
    correct_count = session.get('correct_count', 0)
    total_questions = session.get('total_questions', 10)

    new_score = Score(user_id=current_user.id, score=correct_count, total_questions=total_questions)
    db.session.add(new_score)
    db.session.commit()

    session.pop('quiz_questions', None)
    session.pop('current_question_index', None)
    session.pop('correct_count', None)
    session.pop('total_questions', None)

    return render_template('results.html', correct_count=correct_count, total_questions=total_questions)

# Scores route
@app.route('/scores')
@login_required
def scores():
    user_scores = Score.query.filter_by(user_id=current_user.id).order_by(Score.date.desc()).all()
    return render_template('scores.html', scores=user_scores)

# Run the app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Ensures database and tables are created

        # Add initial users
        if not User.query.first():  # Only add users if the table is empty
            initial_users = [
                User(username='erten', password=('lozinka')),
                User(username='admin', password=('adminpass')),
                User(username='user1', password=('userpass1')),
                User(username='user2', password=('userpass2'))
            ]
            db.session.add_all(initial_users)
            db.session.commit()
            print("Initial users added to the database.")

    app.run(debug=True)