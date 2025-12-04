import os
from flask import Flask, render_template, request, send_file, redirect, url_for
from werkzeug.utils import secure_filename
from datetime import datetime
import models
from utils.image_processor import ImageProcessor

app = Flask(__name__)
app.config['SECRET_KEY'] = '123'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///image_converter.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
models.init_app(app)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Check if file was uploaded
        if 'file' not in request.form and 'file' not in request.files:
            return redirect(request.url)

        file = request.files.get('file')

        # Check if file is selected
        if file and file.filename == '':
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            original_path = os.path.join(app.config['UPLOAD_FOLDER'],
                                         f'original_{datetime.now().strftime("%Y%m%d_%H%M%S")}_{filename}')
            file.save(original_path)

            # Get conversion options
            output_format = request.form.get('format', 'jpeg')
            quality = int(request.form.get('quality', 85))
            resize_width = request.form.get('resize_width')
            resize_height = request.form.get('resize_height')

            # Process image
            processor = ImageProcessor(original_path)

            # Apply resize if specified
            if resize_width and resize_height:
                processor.resize(int(resize_width), int(resize_height))

            # Generate output filename
            output_filename = f'converted_{datetime.now().strftime("%Y%m%d_%H%M%S")}.{output_format}'
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

            # Convert image
            processor.convert(output_format.upper(), quality=quality)
            processor.save(output_path)

            # Save to database
            conversion = models.ImageConversion(
                original_filename=filename,
                converted_filename=output_filename,
                original_format=filename.rsplit('.', 1)[1].lower(),
                converted_format=output_format,
                original_size=os.path.getsize(original_path),
                converted_size=os.path.getsize(output_path),
                quality=quality
            )
            models.db.session.add(conversion)
            models.db.session.commit()

            return render_template('upload.html',
                                   original=original_path.replace('static/', ''),
                                   converted=output_path.replace('static/', ''),
                                   conversion=conversion)

    return render_template('upload.html')


@app.route('/download/<filename>')
def download_file(filename):
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(path, as_attachment=True)


@app.route('/history')
def history():
    conversions = models.ImageConversion.query.order_by(models.ImageConversion.created_at.desc()).all()
    return render_template('history.html', conversions=conversions)


@app.route('/delete/<int:id>')
def delete_conversion(id):
    conversion = models.ImageConversion.query.get_or_404(id)

    # Delete files
    original_path = os.path.join(app.config['UPLOAD_FOLDER'], conversion.original_filename)
    converted_path = os.path.join(app.config['UPLOAD_FOLDER'], conversion.converted_filename)

    if os.path.exists(original_path):
        os.remove(original_path)
    if os.path.exists(converted_path):
        os.remove(converted_path)

    # Delete from database
    models.db.session.delete(conversion)
    models.db.session.commit()

    return redirect(url_for('history'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)