import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort, jsonify

UPLOAD_FOLDER = 'videos'
ALLOWED_EXTENSIONS = {'mp4', 'webm', 'ogg', 'mkv'}
METADATA_FILE = 'videos/metadata.json'

PHOTO_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'}
PHOTO_FOLDER = 'photos'
PHOTO_METADATA_FILE = 'photos/metadata.json'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PHOTO_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_photo(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in PHOTO_EXTENSIONS

def load_metadata():
    if not os.path.exists(METADATA_FILE):
        return {}
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_metadata(meta):
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def load_photo_metadata():
    if not os.path.exists(PHOTO_METADATA_FILE):
        return {}
    with open(PHOTO_METADATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_photo_metadata(meta):
    with open(PHOTO_METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def get_video_metadata():
    meta = load_metadata()
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    files = [f for f in files if allowed_file(f)]
    # Synchronizace metadat se soubory
    changed = False
    for f in files:
        if f not in meta:
            path = os.path.join(app.config['UPLOAD_FOLDER'], f)
            meta[f] = {
                "original_name": f,
                "size": os.path.getsize(path),
                "added": datetime.fromtimestamp(os.path.getctime(path)).isoformat(),
                "watched": 0,
                "duration": 0
            }
            changed = True
    # Odstranit metadata pro smazané soubory
    for k in list(meta.keys()):
        if k not in files:
            del meta[k]
            changed = True
    if changed:
        save_metadata(meta)
    return meta

def get_photo_metadata():
    meta = load_photo_metadata()
    files = os.listdir(PHOTO_FOLDER)
    files = [f for f in files if allowed_photo(f)]
    changed = False
    for f in files:
        if f not in meta:
            path = os.path.join(PHOTO_FOLDER, f)
            meta[f] = {
                "original_name": f,
                "size": os.path.getsize(path),
                "added": datetime.fromtimestamp(os.path.getctime(path)).isoformat()
            }
            changed = True
    for k in list(meta.keys()):
        if k not in files:
            del meta[k]
            changed = True
    if changed:
        save_photo_metadata(meta)
    return meta

@app.route('/')
def index():
    sort = request.args.get('sort', 'added')
    order = request.args.get('order', 'desc')
    query = request.args.get('q', '').strip().lower()
    meta = get_video_metadata()
    videos = list(meta.items())
    # Vyhledávání podle názvu
    if query:
        videos = [v for v in videos if query in v[1].get('original_name', '').lower()]
    if sort == 'name':
        videos.sort(key=lambda x: x[1].get('original_name', '').lower(), reverse=(order=='desc'))
    elif sort == 'size':
        videos.sort(key=lambda x: x[1].get('size', 0), reverse=(order=='desc'))
    elif sort == 'watched':
        videos.sort(key=lambda x: x[1].get('watched', 0), reverse=(order=='desc'))
    else:  # added
        videos.sort(key=lambda x: x[1].get('added', ''), reverse=(order=='desc'))

    photo_sort = request.args.get('photo_sort', 'added')
    photo_order = request.args.get('photo_order', 'desc')
    photo_query = request.args.get('photo_q', '').strip().lower()
    photos_meta = get_photo_metadata()
    photos = list(photos_meta.items())
    if photo_query:
        photos = [p for p in photos if photo_query in p[1].get('original_name', '').lower()]
    if photo_sort == 'name':
        photos.sort(key=lambda x: x[1].get('original_name', '').lower(), reverse=(photo_order=='desc'))
    elif photo_sort == 'size':
        photos.sort(key=lambda x: x[1].get('size', 0), reverse=(photo_order=='desc'))
    else:
        photos.sort(key=lambda x: x[1].get('added', ''), reverse=(photo_order=='desc'))

    return render_template(
        'index.html',
        videos=videos, sort=sort, order=order, query=query,
        photos=photos, photo_sort=photo_sort, photo_order=photo_order, photo_query=photo_query
    )

@app.route('/upload', methods=['POST'])
def upload():
    custom_name = request.form.get('custom_name', '').strip()
    # Video upload
    if 'video' in request.files and request.files['video'].filename:
        file = request.files['video']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Pokud je custom_name, použij ho (včetně přípony)
            if custom_name:
                ext = os.path.splitext(filename)[1]
                if not os.path.splitext(custom_name)[1]:
                    filename = secure_filename(custom_name + ext)
                else:
                    filename = secure_filename(custom_name)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)
            meta = load_metadata()
            meta[filename] = {
                "original_name": filename,
                "size": os.path.getsize(save_path),
                "added": datetime.now().isoformat(),
                "watched": 0,
                "duration": 0
            }
            save_metadata(meta)
    # Photo upload
    if 'photo' in request.files and request.files['photo'].filename:
        file = request.files['photo']
        if file and allowed_photo(file.filename):
            filename = secure_filename(file.filename)
            if custom_name:
                ext = os.path.splitext(filename)[1]
                if not os.path.splitext(custom_name)[1]:
                    filename = secure_filename(custom_name + ext)
                else:
                    filename = secure_filename(custom_name)
            save_path = os.path.join(PHOTO_FOLDER, filename)
            file.save(save_path)
            meta = load_photo_metadata()
            meta[filename] = {
                "original_name": filename,
                "size": os.path.getsize(save_path),
                "added": datetime.now().isoformat()
            }
            save_photo_metadata(meta)
    return redirect(url_for('index'))

@app.route('/delete/<filename>', methods=['POST'])
def delete_video(filename):
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(path) and allowed_file(filename):
        os.remove(path)
        meta = load_metadata()
        if filename in meta:
            del meta[filename]
            save_metadata(meta)
    return redirect(url_for('index'))

@app.route('/delete_photo/<filename>', methods=['POST'])
def delete_photo(filename):
    path = os.path.join(PHOTO_FOLDER, filename)
    if os.path.exists(path) and allowed_photo(filename):
        os.remove(path)
        meta = load_photo_metadata()
        if filename in meta:
            del meta[filename]
            save_photo_metadata(meta)
    return redirect(url_for('index'))

@app.route('/rename/<filename>', methods=['POST'])
def rename_video(filename):
    new_name = request.form.get('new_name')
    if not new_name or not allowed_file(new_name):
        return redirect(url_for('index'))
    new_name = secure_filename(new_name)
    old_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    new_path = os.path.join(app.config['UPLOAD_FOLDER'], new_name)
    if os.path.exists(old_path) and not os.path.exists(new_path):
        os.rename(old_path, new_path)
        meta = load_metadata()
        # Přenést metadata a aktualizovat název i příponu
        meta[new_name] = meta.pop(filename)
        meta[new_name]['original_name'] = new_name
        save_metadata(meta)
    return redirect(url_for('index'))

@app.route('/rename_photo/<filename>', methods=['POST'])
def rename_photo(filename):
    new_name = request.form.get('new_name')
    if not new_name or not allowed_photo(new_name):
        return redirect(url_for('index'))
    new_name = secure_filename(new_name)
    old_path = os.path.join(PHOTO_FOLDER, filename)
    new_path = os.path.join(PHOTO_FOLDER, new_name)
    if os.path.exists(old_path) and not os.path.exists(new_path):
        os.rename(old_path, new_path)
        meta = load_photo_metadata()
        meta[new_name] = meta.pop(filename)
        meta[new_name]['original_name'] = new_name
        save_photo_metadata(meta)
    return redirect(url_for('index'))

@app.route('/videos/<filename>')
def video(filename):
    if not allowed_file(filename):
        abort(404)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/photos/<filename>')
def photo(filename):
    if not allowed_photo(filename):
        abort(404)
    return send_from_directory(PHOTO_FOLDER, filename)

@app.route('/progress/<filename>', methods=['POST'])
def save_progress(filename):
    data = request.get_json()
    watched = data.get('watched', 0)
    duration = data.get('duration', 0)
    meta = load_metadata()
    if filename in meta:
        meta[filename]['watched'] = watched
        meta[filename]['duration'] = duration
        save_metadata(meta)
    return jsonify(success=True)

@app.route('/progress/<filename>', methods=['GET'])
def get_progress(filename):
    meta = load_metadata()
    if filename in meta:
        return jsonify(watched=meta[filename].get('watched', 0), duration=meta[filename].get('duration', 0))
    return jsonify(watched=0, duration=0)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

