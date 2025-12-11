from flask import Flask, render_template, request, send_file
from PIL import Image
import io
import zipfile

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

SUPPORTED_FORMATS = ['JPEG', 'PNG', 'BMP', 'GIF', 'WEBP']


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
def index():
    return render_template('index.html', formats=SUPPORTED_FORMATS)


@app.route('/upload', methods=['POST'])
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

    for file in files:
        try:
            img = Image.open(file.stream)
            img = process_image(img, width, height, format)

            img_bytes = io.BytesIO()
            img.save(img_bytes, format=format, quality=90)
            img_bytes.seek(0)

            processed.append({
                'data': img_bytes,
                'name': file.filename.rsplit('.', 1)[0] + f'.{format.lower()}'
            })
        except:
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


if __name__ == '__main__':
    app.run(debug=True, port=5000,host='0.0.0.0')