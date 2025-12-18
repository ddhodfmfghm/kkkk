import random
import string
import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from PIL import Image
import io
import zipfile

app = Flask(__name__)
app.secret_key = '123'

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
SUPPORTED_FORMATS = ['JPEG', 'PNG', 'BMP', 'GIF', 'WEBP']

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'database.db')


def init_db():
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversion_history (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            filename TEXT,
            original_format TEXT,
            converted_format TEXT,
            width INTEGER,
            height INTEGER,
            file_size INTEGER,
            converted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    connection.commit()
    connection.close()


def get_db_connection():
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def user_exists(username):
    connection = get_db_connection()
    user = connection.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    connection.close()
    return user is not None


def add_user(username, password, role='user'):
    connection = get_db_connection()
    connection.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                       (username, password, role))
    connection.commit()
    connection.close()


def add_to_history(user_id, filename, original_format, converted_format, width, height, file_size):
    connection = get_db_connection()
    connection.execute('''
        INSERT INTO conversion_history (user_id, filename, original_format, converted_format, width, height, file_size)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, filename, original_format, converted_format, width, height, file_size))
    connection.commit()
    connection.close()


def get_user_id(username):
    connection = get_db_connection()
    user = connection.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    connection.close()
    return user['id'] if user else None


def get_conversion_history(user_id, limit=50):
    connection = get_db_connection()
    history = connection.execute('''
        SELECT * FROM conversion_history 
        WHERE user_id = ? 
        ORDER BY converted_at DESC 
        LIMIT ?
    ''', (user_id, limit)).fetchall()
    connection.close()
    return [dict(row) for row in history]


def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Пожалуйста, войдите в систему', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        connection = get_db_connection()
        user = connection.execute(
            'SELECT * FROM users WHERE username = ? AND password = ?', (username, password)
        ).fetchone()
        connection.close()

        if user:
            session['username'] = user['username']
            session['role'] = user['role']
            session['user_id'] = user['id']
            flash('Вход выполнен успешно!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if not username or not password:
            flash('Заполните все поля', 'error')
        elif len(username) < 3:
            flash('Имя пользователя должно быть не менее 3 символов', 'error')
        elif len(password) < 4:
            flash('Пароль должен быть не менее 4 символов', 'error')
        elif password != confirm_password:
            flash('Пароли не совпадают', 'error')
        elif user_exists(username):
            flash('Пользователь с таким именем уже существует', 'error')
        else:
            add_user(username, password)
            flash('Регистрация успешна! Теперь вы можете войти.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))


@app.route('/history')
@login_required
def history():
    user_id = get_user_id(session['username'])
    history_data = get_conversion_history(user_id)
    return render_template('history.html', history=history_data)


def process_image(img, width, height, format):
    if width and height:
        img = img.resize((width, height), Image.Resampling.LANCZOS)
    elif width:
        ratio = width / img.width
        height = int(img.height * ratio)
        img = img.resize((width, height), Image.Resampling.LANCZOS)
    elif height:
        ratio = height / img.height
        width = int(img.width * ratio)
        img = img.resize((width, height), Image.Resampling.LANCZOS)

    if format == 'JPEG' and img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    return img


@app.route('/')
@login_required
def index():
    user_id = get_user_id(session['username'])
    history_count = len(get_conversion_history(user_id, limit=5))
    return render_template('index.html', formats=SUPPORTED_FORMATS, history_count=history_count)


@app.route('/upload', methods=['POST'])
@login_required
def upload_images():
    files = request.files.getlist('images')
    if not files or files[0].filename == '':
        return 'No files selected', 400

    width = request.form.get('width', type=int)
    height = request.form.get('height', type=int)
    format = request.form.get('format', 'JPEG')

    if format not in SUPPORTED_FORMATS:
        format = 'JPEG'

    processed = []
    user_id = get_user_id(session['username'])

    for file in files:
        try:
            original_format = file.filename.rsplit('.', 1)[-1].upper() if '.' in file.filename else 'UNKNOWN'
            img = Image.open(file.stream)
            img = process_image(img, width, height, format)

            img_bytes = io.BytesIO()
            img.save(img_bytes, format=format, quality=90)
            img_bytes.seek(0)
            file_size = len(img_bytes.getvalue())


            add_to_history(
                user_id=user_id,
                filename=file.filename,
                original_format=original_format,
                converted_format=format,
                width=width or img.width,
                height=height or img.height,
                file_size=file_size
            )

            processed.append({
                'data': img_bytes,
                'name': file.filename.rsplit('.', 1)[0] + f'.{format.lower()}'
            })
        except Exception as e:
            print(f"Error processing image: {e}")
            continue

    if not processed:
        return 'Failed to process images', 400

    if len(processed) == 1:
        return send_file(
            processed[0]['data'],
            mimetype=f'image/{format.lower()}',
            as_attachment=True,
            download_name=processed[0]['name']
        )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        for img in processed:
            zip_file.writestr(img['name'], img['data'].getvalue())

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='images.zip'
    )


@app.route('/api/history')
@login_required
def api_history():
    user_id = get_user_id(session['username'])
    history_data = get_conversion_history(user_id, limit=20)


    for item in history_data:
        item['converted_at'] = datetime.strptime(item['converted_at'], '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y %H:%M')
        item['file_size'] = format_file_size(item['file_size'])

    return jsonify(history_data)


def format_file_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)