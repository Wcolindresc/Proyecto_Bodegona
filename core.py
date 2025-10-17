import os
from functools import wraps
from flask import session, redirect, url_for, flash, request
from dotenv import load_dotenv, find_dotenv
from supabase import create_client, Client

load_dotenv(find_dotenv())

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
BUCKET = "products"
CURRENCY = os.environ.get("CURRENCY", "GTQ")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("Faltan SUPABASE_URL y/o SUPABASE_ANON_KEY.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
admin_supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) if SUPABASE_SERVICE_ROLE_KEY else supabase

def db_admin() -> Client:
    return admin_supabase

def storage_admin():
    return admin_supabase.storage

def public_url(path: str | None) -> str | None:
    if not path:
        return None
    data = supabase.storage.from_(BUCKET).get_public_url(path)
    return data.get("publicUrl")

def current_user():
    return session.get("user")

def is_admin(user_id: str | None) -> bool:
    if not user_id:
        return False
    res = db_admin().table("admins").select("user_id").eq("user_id", user_id).execute()
    return len(res.data or []) > 0

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Debes iniciar sesión.", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            flash("Debes iniciar sesión.", "warning")
            return redirect(url_for("login", next=request.path))
        if not is_admin(user.get("id")):
            flash("No autorizado.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper
