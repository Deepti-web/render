from flask import Flask, request, render_template, redirect, send_file
import mysql.connector
import base64
from io import BytesIO
import os
from dotenv import load_dotenv


app = Flask(__name__)

# ✅ load environment variables from .env
load_dotenv()

def get_db_connection():
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")
    port = os.getenv("DB_PORT")
    ssl_ca = os.getenv("SSL_CA")

    if not all([host, user, password, database, port, ssl_ca]):
        raise ValueError("❌ Missing one or more DB environment variables!")

    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=int(port),
        ssl_ca=ssl_ca
    )

@app.route('/')
def index():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_photo():
    file = request.files['photo']
    if file:
        filename = file.filename
        image_data = file.read()

        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("DELETE FROM photos")
        cursor.execute("INSERT INTO photos (filename, image) VALUES (%s, %s)", (filename, image_data))
        db.commit()
        cursor.close()
        db.close()

        return redirect('/photos')

@app.route('/photos')
def show_photos():
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT id, filename, image FROM photos ORDER BY id DESC LIMIT 1")
    photo = cursor.fetchone()
    cursor.close()
    db.close()

    photo_list = []
    if photo:
        photo_id, filename, image_blob = photo
        b64_image = base64.b64encode(image_blob).decode('utf-8')
        photo_list.append({
            'id': photo_id,
            'filename': filename,
            'image_data': b64_image
        })

    return render_template('display.html', photos=photo_list)

@app.route('/download-image/<int:image_id>')
def download_image(image_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT filename, image FROM photos WHERE id = %s", (image_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result:
        filename, image = result
        file_data = BytesIO(image)
        return send_file(file_data, download_name=filename, as_attachment=True)
    else:
        return "Image not found", 404

if __name__ == '__main__':
    app.run(debug=True)
