from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bookloop.db'
app.config['SECRET_KEY'] = 'bookloopsecret'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# -------------------- MODELS --------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user_books = db.relationship('UserBook', backref='owner', lazy=True, foreign_keys='UserBook.user_id')
    sent_requests = db.relationship('ExchangeRequest', backref='requester', lazy=True, foreign_keys='ExchangeRequest.requester_id')
    received_requests = db.relationship('ExchangeRequest', backref='book_owner', lazy=True, foreign_keys='ExchangeRequest.owner_id')

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    genre = db.Column(db.String(50))
    rating = db.Column(db.Float, default=0.0)
    cover_image = db.Column(db.String(500))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    user_books = db.relationship('UserBook', backref='book', lazy=True)

class UserBook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    condition = db.Column(db.String(50), default='Good')
    status = db.Column(db.String(50), default='Available')  # Available, Exchanged, Reserved
    added_date = db.Column(db.DateTime, default=datetime.utcnow)

class ExchangeRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_book_id = db.Column(db.Integer, db.ForeignKey('user_book.id'), nullable=False)
    requester_name = db.Column(db.String(200))
    requester_email = db.Column(db.String(150))
    pickup_address = db.Column(db.Text)
    exchange_mode = db.Column(db.String(100))
    message = db.Column(db.Text)
    status = db.Column(db.String(50), default='Pending')  # Pending, Accepted, Rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    user_book = db.relationship('UserBook', backref='exchange_requests')

# -------------------- HELPER FUNCTIONS --------------------

def is_logged_in():
    return 'user_id' in session

def get_current_user():
    if is_logged_in():
        return User.query.get(session['user_id'])
    return None

# -------------------- ROUTES --------------------

@app.route('/')
def home():
    books = Book.query.limit(4).all()
    user = get_current_user()
    return render_template('index.html', books=books, user=user)

@app.route('/categories')
def categories():
    genre = request.args.get('genre')
    user = get_current_user()
    
    if genre:
        books = Book.query.filter_by(genre=genre).all()
    else:
        books = Book.query.all()
    
    return render_template('categories.html', books=books, selected_genre=genre, user=user)

@app.route('/book/<int:id>')
def book_detail(id):
    book = Book.query.get_or_404(id)
    user = get_current_user()
    
    # Get all available copies of this book
    available_copies = UserBook.query.filter_by(
        book_id=id, 
        status='Available'
    ).all()
    
    return render_template('book_detail.html', book=book, available_copies=available_copies, user=user)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name', '')
        
        # Check if user exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please login.', 'error')
            return redirect(url_for('signup'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken. Please choose another.', 'error')
            return redirect(url_for('signup'))
        
        # Create new user
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(
            username=username, 
            email=email, 
            password=hashed_password,
            full_name=full_name
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # Log the user in
        session['user_id'] = new_user.id
        session['username'] = new_user.username
        
        flash('Account created successfully!', 'success')
        return redirect(url_for('home'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password. Please try again.', 'error')
            return redirect(url_for('login'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

@app.route('/add_to_exchange/<int:book_id>', methods=['POST'])
def add_to_exchange(book_id):
    if not is_logged_in():
        flash('Please login to add books to exchange.', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Check if user already has this book
    existing = UserBook.query.filter_by(user_id=user_id, book_id=book_id).first()
    if existing:
        flash('You already have this book in your collection.', 'warning')
        return redirect(url_for('home'))
    
    # Add book to user's collection
    user_book = UserBook(
        user_id=user_id,
        book_id=book_id,
        status='Available'
    )
    
    db.session.add(user_book)
    db.session.commit()
    
    flash('Book added to your exchange list!', 'success')
    return redirect(url_for('home'))

@app.route('/exchange/<int:user_book_id>')
def exchange_page(user_book_id):
    if not is_logged_in():
        flash('Please login to request an exchange.', 'error')
        return redirect(url_for('login'))
    
    user_book = UserBook.query.get_or_404(user_book_id)
    user = get_current_user()
    today = datetime.now().strftime('%B %d, %Y')
    
    return render_template('exchange.html', user_book=user_book, user=user, today=today)

@app.route('/request_exchange/<int:user_book_id>', methods=['POST'])
def request_exchange(user_book_id):
    if not is_logged_in():
        flash('Please login to request an exchange.', 'error')
        return redirect(url_for('login'))
    
    user_book = UserBook.query.get_or_404(user_book_id)
    
    # Create exchange request
    exchange_request = ExchangeRequest(
        requester_id=session['user_id'],
        owner_id=user_book.user_id,
        user_book_id=user_book_id,
        requester_name=request.form.get('name'),
        requester_email=request.form.get('email'),
        pickup_address=request.form.get('pickup'),
        exchange_mode=request.form.get('mode'),
        message=request.form.get('message', ''),
        status='Pending'
    )
    
    db.session.add(exchange_request)
    db.session.commit()
    
    flash('Exchange request sent successfully!', 'success')
    return redirect(url_for('my_exchanges'))

@app.route('/my_exchanges')
def my_exchanges():
    if not is_logged_in():
        flash('Please login to view your exchanges.', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = get_current_user()
    
    # Get sent and received requests
    sent_requests = ExchangeRequest.query.filter_by(requester_id=user_id).order_by(ExchangeRequest.created_at.desc()).all()
    received_requests = ExchangeRequest.query.filter_by(owner_id=user_id).order_by(ExchangeRequest.created_at.desc()).all()
    
    return render_template('my_exchanges.html', 
                         sent_requests=sent_requests, 
                         received_requests=received_requests,
                         user=user)

@app.route('/accept_exchange/<int:exchange_id>', methods=['POST'])
def accept_exchange(exchange_id):
    if not is_logged_in():
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    exchange = ExchangeRequest.query.get_or_404(exchange_id)
    
    # Check if current user is the owner
    if exchange.owner_id != session['user_id']:
        flash('Unauthorized action.', 'error')
        return redirect(url_for('my_exchanges'))
    
    # Update exchange status
    exchange.status = 'Accepted'
    
    # Update book status
    user_book = UserBook.query.get(exchange.user_book_id)
    user_book.status = 'Exchanged'
    
    db.session.commit()
    
    flash('Exchange request accepted!', 'success')
    return redirect(url_for('my_exchanges'))

@app.route('/reject_exchange/<int:exchange_id>', methods=['POST'])
def reject_exchange(exchange_id):
    if not is_logged_in():
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    
    exchange = ExchangeRequest.query.get_or_404(exchange_id)
    
    # Check if current user is the owner
    if exchange.owner_id != session['user_id']:
        flash('Unauthorized action.', 'error')
        return redirect(url_for('my_exchanges'))
    
    # Update exchange status
    exchange.status = 'Rejected'
    db.session.commit()
    
    flash('Exchange request rejected.', 'success')
    return redirect(url_for('my_exchanges'))

@app.route('/my_books')
def my_books():
    if not is_logged_in():
        flash('Please login to view your books.', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = get_current_user()
    user_books = UserBook.query.filter_by(user_id=user_id).all()
    
    return render_template('my_books.html', user_books=user_books, user=user)

# -------------------- INITIALIZE DATABASE --------------------

def init_db():
    with app.app_context():
        db.create_all()
        
        # Check if sample books exist
        if Book.query.count() == 0:
            sample_books = [
                Book(
                    title='The Silent Patient',
                    author='Alex Michaelides',
                    genre='Thriller',
                    rating=5.0,
                    cover_image='https://i.imgur.com/3h5cS8J.jpg',
                    description='A psychological thriller about a woman who shoots her husband and then never speaks again.'
                ),
                Book(
                    title='Atomic Habits',
                    author='James Clear',
                    genre='Self-Help',
                    rating=4.0,
                    cover_image='https://i.imgur.com/XcK5XcV.jpg',
                    description='An easy and proven way to build good habits and break bad ones.'
                ),
                Book(
                    title='The Alchemist',
                    author='Paulo Coelho',
                    genre='Fiction',
                    rating=5.0,
                    cover_image='https://i.imgur.com/qUJjPAd.jpg',
                    description='A magical story about following your dreams and listening to your heart.'
                ),
                Book(
                    title='Rich Dad Poor Dad',
                    author='Robert Kiyosaki',
                    genre='Finance',
                    rating=4.0,
                    cover_image='https://i.imgur.com/6Ssjbpr.jpg',
                    description='What the rich teach their kids about money that the poor and middle class do not.'
                ),
                Book(
                    title='1984',
                    author='George Orwell',
                    genre='Fiction',
                    rating=5.0,
                    cover_image='https://images.unsplash.com/photo-1544947950-fa07a98d237f',
                    description='A dystopian social science fiction novel and cautionary tale.'
                ),
                Book(
                    title='Sapiens',
                    author='Yuval Noah Harari',
                    genre='Science',
                    rating=4.5,
                    cover_image='https://images.unsplash.com/photo-1589998059171-988d887df646',
                    description='A brief history of humankind from the Stone Age to the modern age.'
                ),
                Book(
                    title='The Lean Startup',
                    author='Eric Ries',
                    genre='Business',
                    rating=4.0,
                    cover_image='https://images.unsplash.com/photo-1507842217343-583bb7270b66',
                    description='How constant innovation creates radically successful businesses.'
                ),
                Book(
                    title='Pride and Prejudice',
                    author='Jane Austen',
                    genre='Romance',
                    rating=5.0,
                    cover_image='https://images.unsplash.com/photo-1524578271613-d550eacf6090',
                    description='A romantic novel of manners that follows the character development of Elizabeth Bennet.'
                ),
            ]
            
            for book in sample_books:
                db.session.add(book)
            
            db.session.commit()
            print("✅ Database initialized with sample books!")

# -------------------- MAIN --------------------

if __name__ == '__main__':
    init_db()
    app.run(debug=True)