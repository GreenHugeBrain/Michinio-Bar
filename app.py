from flask import Flask, render_template, redirect, request, send_from_directory, jsonify
from flask_login import LoginManager, current_user, login_user, UserMixin, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FileField, PasswordField
from wtforms.validators import DataRequired, Length
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from flask_migrate import Migrate

app = Flask(__name__)
db = SQLAlchemy()
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads' 
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
migrate = Migrate(app, db)

class Company(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    playlists = db.relationship('Playlists', backref="company")

class Playlists(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    musics = db.relationship('Musics', backref="playlist")
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)

class Musics(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    music = db.Column(db.String(120), nullable=False)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlists.id'), nullable=False)
    order = db.Column(db.Integer, nullable=False)

with app.app_context():
    db.create_all()

class CompanyForm(FlaskForm):
    name = StringField('Company Name', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=3, max=80)])
    submit = SubmitField('Register')

class CompanyFormLogin(FlaskForm):
    name = StringField('Company Name', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=3, max=80)])
    submit = SubmitField('Login')

class PlaylistForm(FlaskForm):
    name = StringField('Playlist Name', validators=[DataRequired(), Length(min=3, max=80)])
    submit = SubmitField('Submit')

class MusicsForm(FlaskForm):
    music = FileField('Music File', validators=[DataRequired()])
    submit = SubmitField('Submit')

@login_manager.user_loader
def load_user(company_id):
    return Company.query.get(company_id)

@app.route('/', methods=['GET'])
def home():
    if current_user.is_authenticated:
        playlists = Playlists.query.filter_by(company_id=current_user.id).all()
        return render_template('index.html', playlists=playlists)
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect('/')
    form = CompanyFormLogin()
    if form.validate_on_submit():
        company = Company.query.filter_by(name=form.name.data).first()
        if company and check_password_hash(company.password, form.password.data):
            login_user(company)
            return redirect('/')
        return 'Invalid credentials'
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect('/')
    form = CompanyForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        company = Company(name=form.name.data, password=hashed_password)
        db.session.add(company)
        db.session.commit()
        return redirect('/login')
    return render_template('register.html', form=form)

@app.route('/company/<int:company_id>', methods=['GET'])
def company(company_id):
    if not current_user.is_authenticated:
        return redirect('/login')
    company = Company.query.filter_by(id=company_id).first()
    playlists = Playlists.query.filter_by(company_id=company_id).all()
    return render_template("company.html", company=company, playlists=playlists)

@app.route('/create_playlist/<int:company_id>', methods=['GET', 'POST'])
def create_playlist(company_id):
    if not current_user.is_authenticated:
        return redirect('/login')
    form = PlaylistForm()
    if form.validate_on_submit():
        playlist = Playlists(name=form.name.data, company_id=company_id)
        db.session.add(playlist)
        db.session.commit()
        return redirect('/')
    return render_template('create_playlist.html', form=form)

@app.route('/add_music/<int:playlist_id>', methods=['GET', 'POST'])
def add_music(playlist_id):
    if not current_user.is_authenticated:
        return redirect('/login')
    
    form = MusicsForm()
    
    if form.validate_on_submit():
        music_file = request.files['music']  # Get the uploaded file
        
        if music_file:
            music_filename = music_file.filename
            music_name = music_filename  # Set the music name to the filename
            # Save file to the 'uploads' directory
            music_file.save(os.path.join(app.config['UPLOAD_FOLDER'], music_filename))
            
            # Determine the order based on current count of music in the playlist
            order = Musics.query.filter_by(playlist_id=playlist_id).count()
            
            music = Musics(name=music_name, music=music_filename, playlist_id=playlist_id, order=order)
            db.session.add(music)
            db.session.commit()
            return redirect(f'/playlist/{playlist_id}')
    
    return render_template('add_music.html', form=form)

@app.route('/playlist/<int:playlist_id>f', methods=['GET'])
def playlist(playlist_id):
    if not current_user.is_authenticated:
        return redirect('/login')
    playlist = Playlists.query.filter_by(id=playlist_id).first()
    musics = Musics.query.filter_by(playlist_id=playlist_id).order_by(Musics.id).all()  # Sort by ID
    return render_template('playlist.html', playlist=playlist, musics=musics)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/reorder', methods=['POST'])
def reorder_music():
    data = request.get_json()
    order = data.get('order', [])

    # Update the order of each music item
    for index, music_id in enumerate(order):
        music = Musics.query.get(music_id)
        if music:
            music.id = index  # Update the order based on the new position
            db.session.add(music)

    db.session.commit()  # Commit the changes to the database
    return jsonify({'status': 'success'})

@app.route('/logout')
def logout():
    logout_user()  # Flask-Login ფუნქცია, რომელიც იღებს სესიას
    return redirect('/login')  # დაბრუნდება შესვლის გვერდზე


if __name__ == '__main__':
    # Make sure the upload directory exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
