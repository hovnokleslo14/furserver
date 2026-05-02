import json
import os
import secrets
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


UPLOAD_FOLDER = "videos"
ALLOWED_EXTENSIONS = {"mp4", "webm", "ogg", "mkv"}
METADATA_FILE = "videos/metadata.json"

PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp", "webp"}
PHOTO_FOLDER = "photos"
PHOTO_METADATA_FILE = "photos/metadata.json"

DATA_FOLDER = "data"
USERS_FILE = os.path.join(DATA_FOLDER, "users.json")
SECRET_KEY_FILE = os.path.join(DATA_FOLDER, "secret.key")


app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

for folder in (UPLOAD_FOLDER, PHOTO_FOLDER, DATA_FOLDER):
    os.makedirs(folder, exist_ok=True)


def get_secret_key():
    env_secret = os.environ.get("FURSERVER_SECRET_KEY")
    if env_secret:
        return env_secret
    if os.path.exists(SECRET_KEY_FILE):
        with open(SECRET_KEY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    secret = secrets.token_hex(32)
    with open(SECRET_KEY_FILE, "w", encoding="utf-8") as f:
        f.write(secret)
    return secret


app.secret_key = get_secret_key()


def read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_photo(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in PHOTO_EXTENSIONS


def load_metadata():
    return read_json(METADATA_FILE, {})


def save_metadata(meta):
    write_json(METADATA_FILE, meta)


def load_photo_metadata():
    return read_json(PHOTO_METADATA_FILE, {})


def save_photo_metadata(meta):
    write_json(PHOTO_METADATA_FILE, meta)


def load_users():
    return read_json(USERS_FILE, {})


def save_users(users):
    write_json(USERS_FILE, users)


def has_users():
    return bool(load_users())


def current_user():
    username = session.get("username")
    if not username:
        return None
    users = load_users()
    if username not in users:
        session.clear()
        return None
    return {"username": username, **users[username]}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("auth", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def normalize_tags(raw_tags):
    if not raw_tags:
        return []
    if isinstance(raw_tags, str):
        candidates = raw_tags.replace(";", ",").replace("\n", ",").split(",")
    else:
        candidates = raw_tags
    tags = []
    seen = set()
    for tag in candidates:
        clean = " ".join(str(tag).strip().split())
        if not clean:
            continue
        key = clean.lower()
        if key not in seen:
            tags.append(clean[:32])
            seen.add(key)
    return tags[:12]


def ensure_media_entry(meta, filename, folder, kind):
    path = os.path.join(folder, filename)
    entry = meta.get(filename, {})
    entry.setdefault("original_name", filename)
    entry.setdefault("size", os.path.getsize(path))
    entry.setdefault("added", datetime.fromtimestamp(os.path.getctime(path)).isoformat())
    entry.setdefault("tags", [])
    if kind == "video":
        entry.setdefault("watched", 0)
        entry.setdefault("duration", 0)
    entry["kind"] = kind
    meta[filename] = entry


def get_video_metadata():
    meta = load_metadata()
    files = [f for f in os.listdir(app.config["UPLOAD_FOLDER"]) if allowed_file(f)]
    changed = False

    for filename in files:
        before = json.dumps(meta.get(filename, {}), sort_keys=True)
        ensure_media_entry(meta, filename, app.config["UPLOAD_FOLDER"], "video")
        after = json.dumps(meta.get(filename, {}), sort_keys=True)
        changed = changed or before != after

    for key in list(meta.keys()):
        if key not in files:
            del meta[key]
            changed = True

    if changed:
        save_metadata(meta)
    return meta


def get_photo_metadata():
    meta = load_photo_metadata()
    files = [f for f in os.listdir(PHOTO_FOLDER) if allowed_photo(f)]
    changed = False

    for filename in files:
        before = json.dumps(meta.get(filename, {}), sort_keys=True)
        ensure_media_entry(meta, filename, PHOTO_FOLDER, "photo")
        after = json.dumps(meta.get(filename, {}), sort_keys=True)
        changed = changed or before != after

    for key in list(meta.keys()):
        if key not in files:
            del meta[key]
            changed = True

    if changed:
        save_photo_metadata(meta)
    return meta


def tag_matches(entry, tag):
    if not tag:
        return True
    return tag.lower() in {item.lower() for item in entry.get("tags", [])}


def text_matches(entry, query):
    if not query:
        return True
    haystack = " ".join([entry.get("original_name", ""), *entry.get("tags", [])]).lower()
    return query.lower() in haystack


def sort_media(items, sort, order):
    reverse = order == "desc"
    if sort == "name":
        items.sort(key=lambda x: x[1].get("original_name", "").lower(), reverse=reverse)
    elif sort == "size":
        items.sort(key=lambda x: x[1].get("size", 0), reverse=reverse)
    elif sort == "watched":
        items.sort(key=lambda x: x[1].get("watched", 0), reverse=reverse)
    else:
        items.sort(key=lambda x: x[1].get("added", ""), reverse=reverse)
    return items


def unique_filename(folder, filename):
    base, ext = os.path.splitext(filename)
    candidate = filename
    counter = 2
    while os.path.exists(os.path.join(folder, candidate)):
        candidate = f"{base}-{counter}{ext}"
        counter += 1
    return candidate


def media_stats(videos, photos):
    all_entries = [entry for _, entry in videos] + [entry for _, entry in photos]
    total_size = sum(entry.get("size", 0) for entry in all_entries)
    total_duration = sum(entry.get("duration", 0) or 0 for _, entry in videos)
    return {
        "videos": len(videos),
        "photos": len(photos),
        "tags": len(collect_tags(videos, photos)),
        "size_mb": round(total_size / 1024 / 1024, 1),
        "duration_min": round(total_duration / 60, 1),
    }


def collect_tags(videos, photos):
    tags = {}
    for _, entry in [*videos, *photos]:
        for tag in entry.get("tags", []):
            tags[tag.lower()] = tag
    return sorted(tags.values(), key=str.lower)


def mutate_media_tags(kind, filename, tags):
    if kind == "video":
        meta = load_metadata()
        if filename not in meta:
            abort(404)
        meta[filename]["tags"] = tags
        save_metadata(meta)
    elif kind == "photo":
        meta = load_photo_metadata()
        if filename not in meta:
            abort(404)
        meta[filename]["tags"] = tags
        save_photo_metadata(meta)
    else:
        abort(404)


@app.context_processor
def inject_globals():
    return {
        "current_user": current_user(),
        "has_users": has_users(),
    }


@app.route("/auth", methods=["GET", "POST"])
def auth():
    if current_user():
        return redirect(url_for("index"))

    mode = request.form.get("mode", "login")
    next_url = request.args.get("next") or url_for("index")
    if not has_users():
        mode = "register"

    if request.method == "POST":
        users = load_users()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if len(username) < 3 or len(password) < 6:
            flash("Uživatelské jméno musí mít aspoň 3 znaky a heslo aspoň 6 znaků.", "error")
            return redirect(url_for("auth"))

        if mode == "register":
            if username in users:
                flash("Tenhle účet už existuje.", "error")
                return redirect(url_for("auth"))
            users[username] = {
                "password_hash": generate_password_hash(password),
                "created": datetime.now().isoformat(),
            }
            save_users(users)
            session["username"] = username
            flash("Účet je připravený. Vítej ve FurServeru.", "success")
            return redirect(next_url)

        user = users.get(username)
        if not user or not check_password_hash(user.get("password_hash", ""), password):
            flash("Přihlášení nesedí. Zkus to prosím znovu.", "error")
            return redirect(url_for("auth"))
        session["username"] = username
        flash("Jsi přihlášený.", "success")
        return redirect(next_url)

    return render_template("auth.html", mode=mode)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Odhlášeno. Lokální knihovna zůstává jen u tebe.", "success")
    return redirect(url_for("auth"))


@app.route("/")
@login_required
def index():
    sort = request.args.get("sort", "added")
    order = request.args.get("order", "desc")
    query = request.args.get("q", "").strip()
    active_type = request.args.get("type", "all")
    active_tag = request.args.get("tag", "").strip()

    videos = list(get_video_metadata().items())
    photos = list(get_photo_metadata().items())

    all_tags = collect_tags(videos, photos)

    videos = [item for item in videos if text_matches(item[1], query) and tag_matches(item[1], active_tag)]
    photos = [item for item in photos if text_matches(item[1], query) and tag_matches(item[1], active_tag)]

    sort_media(videos, sort, order)
    sort_media(photos, sort, order)

    visible_videos = videos if active_type in {"all", "videos"} else []
    visible_photos = photos if active_type in {"all", "photos"} else []

    return render_template(
        "index.html",
        videos=visible_videos,
        photos=visible_photos,
        all_tags=all_tags,
        sort=sort,
        order=order,
        query=query,
        active_type=active_type,
        active_tag=active_tag,
        stats=media_stats(videos, photos),
    )


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    custom_name = request.form.get("custom_name", "").strip()
    tags = normalize_tags(request.form.get("tags", ""))

    if "video" in request.files and request.files["video"].filename:
        file = request.files["video"]
        if file and allowed_file(file.filename):
            original = secure_filename(file.filename)
            ext = os.path.splitext(original)[1]
            filename = secure_filename(custom_name + ext) if custom_name and not os.path.splitext(custom_name)[1] else secure_filename(custom_name or original)
            filename = unique_filename(app.config["UPLOAD_FOLDER"], filename)
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)
            meta = load_metadata()
            meta[filename] = {
                "original_name": filename,
                "size": os.path.getsize(save_path),
                "added": datetime.now().isoformat(),
                "watched": 0,
                "duration": 0,
                "tags": tags,
                "kind": "video",
            }
            save_metadata(meta)
            flash("Video bylo nahrané.", "success")

    if "photo" in request.files and request.files["photo"].filename:
        file = request.files["photo"]
        if file and allowed_photo(file.filename):
            original = secure_filename(file.filename)
            ext = os.path.splitext(original)[1]
            filename = secure_filename(custom_name + ext) if custom_name and not os.path.splitext(custom_name)[1] else secure_filename(custom_name or original)
            filename = unique_filename(PHOTO_FOLDER, filename)
            save_path = os.path.join(PHOTO_FOLDER, filename)
            file.save(save_path)
            meta = load_photo_metadata()
            meta[filename] = {
                "original_name": filename,
                "size": os.path.getsize(save_path),
                "added": datetime.now().isoformat(),
                "tags": tags,
                "kind": "photo",
            }
            save_photo_metadata(meta)
            flash("Fotka byla nahraná.", "success")

    return redirect(url_for("index"))


@app.route("/delete/<filename>", methods=["POST"])
@login_required
def delete_video(filename):
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(path) and allowed_file(filename):
        os.remove(path)
        meta = load_metadata()
        meta.pop(filename, None)
        save_metadata(meta)
        flash("Video smazáno.", "success")
    return redirect(url_for("index"))


@app.route("/delete_photo/<filename>", methods=["POST"])
@login_required
def delete_photo(filename):
    path = os.path.join(PHOTO_FOLDER, filename)
    if os.path.exists(path) and allowed_photo(filename):
        os.remove(path)
        meta = load_photo_metadata()
        meta.pop(filename, None)
        save_photo_metadata(meta)
        flash("Fotka smazána.", "success")
    return redirect(url_for("index"))


@app.route("/rename/<filename>", methods=["POST"])
@login_required
def rename_video(filename):
    new_name = request.form.get("new_name", "").strip()
    if not new_name:
        return redirect(url_for("index"))
    if not os.path.splitext(new_name)[1]:
        new_name = new_name + os.path.splitext(filename)[1]
    if not allowed_file(new_name):
        flash("Název videa musí mít podporovanou příponu.", "error")
        return redirect(url_for("index"))
    new_name = secure_filename(new_name)
    old_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    new_path = os.path.join(app.config["UPLOAD_FOLDER"], new_name)
    if os.path.exists(old_path) and not os.path.exists(new_path):
        os.rename(old_path, new_path)
        meta = load_metadata()
        meta[new_name] = meta.pop(filename)
        meta[new_name]["original_name"] = new_name
        save_metadata(meta)
        flash("Video přejmenováno.", "success")
    return redirect(url_for("index"))


@app.route("/rename_photo/<filename>", methods=["POST"])
@login_required
def rename_photo(filename):
    new_name = request.form.get("new_name", "").strip()
    if not new_name:
        return redirect(url_for("index"))
    if not os.path.splitext(new_name)[1]:
        new_name = new_name + os.path.splitext(filename)[1]
    if not allowed_photo(new_name):
        flash("Název fotky musí mít podporovanou příponu.", "error")
        return redirect(url_for("index"))
    new_name = secure_filename(new_name)
    old_path = os.path.join(PHOTO_FOLDER, filename)
    new_path = os.path.join(PHOTO_FOLDER, new_name)
    if os.path.exists(old_path) and not os.path.exists(new_path):
        os.rename(old_path, new_path)
        meta = load_photo_metadata()
        meta[new_name] = meta.pop(filename)
        meta[new_name]["original_name"] = new_name
        save_photo_metadata(meta)
        flash("Fotka přejmenována.", "success")
    return redirect(url_for("index"))


@app.route("/tags/<kind>/<filename>", methods=["POST"])
@login_required
def update_tags(kind, filename):
    tags = normalize_tags(request.form.get("tags", ""))
    mutate_media_tags(kind, filename, tags)
    flash("Tagy uloženy.", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/watch/<filename>")
@login_required
def watch(filename):
    if not allowed_file(filename):
        abort(404)
    meta = get_video_metadata()
    if filename not in meta:
        abort(404)
    return render_template("stream.html", filename=filename, meta=meta[filename])


@app.route("/videos/<filename>")
@login_required
def video(filename):
    if not allowed_file(filename):
        abort(404)
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/photos/<filename>")
@login_required
def photo(filename):
    if not allowed_photo(filename):
        abort(404)
    return send_from_directory(PHOTO_FOLDER, filename)


@app.route("/progress/<filename>", methods=["POST"])
@login_required
def save_progress(filename):
    data = request.get_json() or {}
    watched = data.get("watched", 0)
    duration = data.get("duration", 0)
    meta = load_metadata()
    if filename in meta:
        meta[filename]["watched"] = watched
        meta[filename]["duration"] = duration
        save_metadata(meta)
    return jsonify(success=True)


@app.route("/progress/<filename>", methods=["GET"])
@login_required
def get_progress(filename):
    meta = load_metadata()
    if filename in meta:
        return jsonify(watched=meta[filename].get("watched", 0), duration=meta[filename].get("duration", 0))
    return jsonify(watched=0, duration=0)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
