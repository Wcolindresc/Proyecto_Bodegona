import os
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode
from flask import Flask, render_template, request, redirect, url_for, flash, session
from core import SECRET_KEY, supabase, db_admin, storage_admin, public_url, current_user, login_required, CURRENCY

app = Flask(__name__)
app.secret_key = SECRET_KEY

def money(x):
    return Decimal(str(x or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _categories():
    rows = supabase.table("categories").select("id,name,slug").order("name").execute().data
    return rows or []

def get_or_create_cart(user_id: str):
    cr = db_admin().table("carts").select("id").eq("user_id", user_id).maybe_single().execute()
    if cr.data:
        return cr.data["id"]
    return db_admin().table("carts").insert({"user_id": user_id}).execute().data[0]["id"]

def load_cart_items(cart_id: str):
    items = db_admin().table("cart_items").select("id,product_id,qty,price_at_add").eq("cart_id", cart_id).execute().data or []
    product_ids = [i["product_id"] for i in items]
    if product_ids:
        pr = db_admin().table("products").select("id,name,slug,price,image_path,stock").in_("id", product_ids).execute().data or []
        m = {p["id"]: p for p in pr}
        for i in items:
            p = m.get(i["product_id"]) or {}
            i["product"] = p
            i["image_url"] = public_url(p.get("image_path"))
            price = money(p.get("price") if p else i.get("price_at_add") or 0)
            qty = int(i["qty"] or 1)
            i["price"] = price
            i["subtotal"] = money(price * qty)
    total = money(sum(i["subtotal"] for i in items))
    return items, total

@app.context_processor
def inject_globals():
    count = 0
    u = current_user()
    if u:
        cid = get_or_create_cart(u["id"])
        cnt = db_admin().table("cart_items").select("id", count="exact").eq("cart_id", cid).execute().count or 0
        count = cnt
    return {"cart_count": count, "CURRENCY": CURRENCY}

@app.get("/")
def index():
    q = request.args.get("q", "").strip()
    cat = request.args.get("category")
    query = supabase.table("products").select("id,name,slug,price,stock,image_path,active")
    if q:
        query = query.filter("name", "ilike", f"%{q}%")
    if cat:
        try:
            cat_row = supabase.table("categories").select("id").eq("slug", cat).single().execute().data
            if cat_row:
                prod_ids = supabase.table("product_categories").select("product_id").eq("category_id", cat_row["id"]).execute().data
                ids = [r["product_id"] for r in (prod_ids or [])]
                if ids:
                    query = query.in_("id", ids)
                else:
                    return render_template("index.html", products=[], categories=_categories(), q=q, user=current_user())
        except Exception:
            pass
    res = query.order("name").execute()
    products = res.data or []
    products = [p for p in products if p.get("active", True)]
    for p in products:
        p["image_url"] = public_url(p.get("image_path"))
    return render_template("index.html", products=products, categories=_categories(), q=q, user=current_user())

@app.get("/login")
def login():
    return render_template("login.html")

@app.post("/login")
def login_post():
    email = request.form.get("email","").strip()
    password = request.form.get("password","")
    try:
        auth_res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if not getattr(auth_res, "user", None):
            flash("Credenciales inválidas", "danger"); return redirect(url_for("login"))
        session["user"] = {"id": auth_res.user.id, "email": email}
        session.permanent = True
        flash("Bienvenido.", "success")
        return redirect(url_for("index"))
    except Exception as e:
        flash(str(e), "danger"); return redirect(url_for("login"))

@app.get("/register")
def register():
    return render_template("register.html")

@app.post("/register")
def register_post():
    email = request.form.get("email","").strip()
    password = request.form.get("password","")
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if getattr(res, "user", None):
            session["user"] = {"id": res.user.id, "email": email}
            session.permanent = True
        flash("Cuenta creada.", "success")
        return redirect(url_for("index"))
    except Exception as e:
        flash(str(e), "danger"); return redirect(url_for("register"))

@app.post("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("index"))

@app.get("/profile")
def profile():
    u = current_user()
    if not u:
        flash("Debes iniciar sesión.", "warning")
        return redirect(url_for("login", next=request.path))
    addrs = db_admin().table("addresses").select("*").eq("user_id", u["id"]).order("created_at").execute().data or []
    return render_template("profile.html", addresses=addrs)

@app.post("/profile/address")
def profile_add_address():
    u = current_user()
    if not u:
        flash("Debes iniciar sesión.", "warning")
        return redirect(url_for("login", next=request.path))
    data = {
        "user_id": u["id"],
        "full_name": request.form.get("full_name"),
        "phone": request.form.get("phone"),
        "line1": request.form.get("line1"),
        "line2": request.form.get("line2"),
        "city": request.form.get("city"),
        "region": request.form.get("region"),
        "postal_code": request.form.get("postal_code"),
        "country": request.form.get("country") or "GT",
        "is_default": bool(request.form.get("is_default")),
    }
    if data["is_default"]:
        db_admin().table("addresses").update({"is_default": False}).eq("user_id", u["id"]).execute()
    db_admin().table("addresses").insert(data).execute()
    flash("Dirección guardada ✅", "success")
    return redirect(url_for("profile"))

@app.post("/profile/address/<int:aid>/delete")
def profile_delete_address(aid):
    u = current_user()
    if not u:
        flash("Debes iniciar sesión.", "warning")
        return redirect(url_for("login", next=request.path))
    db_admin().table("addresses").delete().eq("id", aid).eq("user_id", u["id"]).execute()
    flash("Dirección eliminada ✅", "info")
    return redirect(url_for("profile"))

@app.get("/cart")
def cart_view():
    u = current_user()
    if not u:
        flash("Debes iniciar sesión.", "warning")
        return redirect(url_for("login", next=request.path))
    cid = get_or_create_cart(u["id"])
    items, total = load_cart_items(cid)
    return render_template("cart.html", items=items, total=total)

@app.post("/cart/add")
def cart_add():
    u = current_user()
    if not u:
        flash("Debes iniciar sesión.", "warning")
        return redirect(url_for("login", next=request.path))
    cid = get_or_create_cart(u["id"])
    pid = int(request.form.get("product_id"))
    qty = int(request.form.get("qty") or 1)
    row = db_admin().table("cart_items").select("id,qty").eq("cart_id", cid).eq("product_id", pid).maybe_single().execute().data
    if row:
        db_admin().table("cart_items").update({"qty": row["qty"] + qty}).eq("id", row["id"]).execute()
    else:
        pr = db_admin().table("products").select("price").eq("id", pid).single().execute().data
        db_admin().table("cart_items").insert({"cart_id": cid, "product_id": pid, "qty": qty, "price_at_add": pr["price"]}).execute()
    flash("Producto agregado al carrito 🛒", "success")
    return redirect(request.referrer or url_for("index"))

@app.post("/cart/update")
def cart_update():
    u = current_user()
    if not u:
        flash("Debes iniciar sesión.", "warning")
        return redirect(url_for("login", next=request.path))
    cid = get_or_create_cart(u["id"])
    iid = int(request.form.get("item_id"))
    qty = max(1, int(request.form.get("qty") or 1))
    db_admin().table("cart_items").update({"qty": qty}).eq("id", iid).eq("cart_id", cid).execute()
    return redirect(url_for("cart_view"))

@app.post("/cart/remove")
def cart_remove():
    u = current_user()
    if not u:
        flash("Debes iniciar sesión.", "warning")
        return redirect(url_for("login", next=request.path))
    cid = get_or_create_cart(u["id"])
    iid = int(request.form.get("item_id"))
    db_admin().table("cart_items").delete().eq("id", iid).eq("cart_id", cid).execute()
    flash("Producto removido del carrito", "info")
    return redirect(url_for("cart_view"))

def build_pagadi_payload(order, amount, return_ok, return_error, notify_url):
    uid   = os.environ.get("PAGADITO_UID","")
    wkey  = os.environ.get("PAGADITO_WKEY","")
    ref   = f"ORDER-{order['id']}"
    payload = {
        "uid": uid,
        "wkey": wkey,
        "amount": f"{float(amount):.2f}",
        "currency": "GTQ",
        "reference": ref,
        "url_ok": return_ok,
        "url_error": return_error,
        "url_notify": notify_url,
    }
    return payload

@app.get("/checkout")
def checkout_view():
    u = current_user()
    if not u:
        flash("Debes iniciar sesión.", "warning")
        return redirect(url_for("login", next=request.path))
    cid = get_or_create_cart(u["id"])
    items, total = load_cart_items(cid)
    addrs = db_admin().table("addresses").select("*").eq("user_id", u["id"]).order("is_default").execute().data or []
    return render_template("checkout.html", items=items, total=total, addresses=addrs)

@app.post("/checkout/pay")
def checkout_pay():
    if not current_user():
        flash("Debes iniciar sesión.", "warning"); return redirect(url_for("login"))
    if os.environ.get("PAYMENT_PROVIDER") != "pagadito":
        flash("Configura PAYMENT_PROVIDER=pagadito y credenciales.", "danger")
        return redirect(url_for("checkout_view"))

    u = current_user()
    cid = get_or_create_cart(u["id"])
    items, total = load_cart_items(cid)
    if not items:
        flash("Carrito vacío.", "warning"); return redirect(url_for("cart_view"))

    address_id = request.form.get("address_id")
    if not address_id:
        flash("Selecciona una dirección de envío.", "warning")
        return redirect(url_for("checkout_view"))
    addr = db_admin().table("addresses").select("*").eq("id", int(address_id)).eq("user_id", u["id"]).single().execute().data

    order = db_admin().table("orders").insert({
        "user_id": u["id"],
        "status": "pending",
        "total": float(total),
        "currency": "GTQ",
        "payment_method": "pagadito",
        "payment_status": "unpaid",
        "address_snapshot": addr
    }).execute().data[0]

    for it in items:
        db_admin().table("order_items").insert({
            "order_id": order["id"],
            "product_id": it["product_id"],
            "name": it["product"]["name"],
            "price": float(it["price"]),
            "qty": int(it["qty"]),
            "subtotal": float(it["subtotal"])
        }).execute()

    base_url = os.environ.get("PAGADITO_CHECKOUT_URL", "https://sandbox.pagadi.to/checkout")
    return_ok = url_for("pagadito_return_ok", order_id=order["id"], _external=True)
    return_error = url_for("pagadito_return_error", order_id=order["id"], _external=True)
    notify_url = url_for("pagadito_ipn", _external=True)

    payload = build_pagadi_payload(order, float(total), return_ok, return_error, notify_url)
    query = urlencode(payload)
    return redirect(f"{base_url}?{query}")

@app.get("/payments/pagadito/return-ok")
def pagadito_return_ok():
    if not current_user():
        return redirect(url_for("login"))
    order_id = int(request.args.get("order_id"))
    db_admin().table("orders").update({"status": "paid", "payment_status": "paid"}).eq("id", order_id).execute()
    u = current_user()
    cid = get_or_create_cart(u["id"])
    db_admin().table("cart_items").delete().eq("cart_id", cid).execute()
    flash("Pago realizado. ¡Gracias por tu compra! 🎉", "success")
    return redirect(url_for("orders_list"))

@app.get("/payments/pagadito/return-error")
def pagadito_return_error():
    if not current_user():
        return redirect(url_for("login"))
    order_id = int(request.args.get("order_id"))
    db_admin().table("orders").update({"status": "pending", "payment_status": "failed"}).eq("id", order_id).execute()
    flash("Pago cancelado o fallido.", "warning")
    return redirect(url_for("checkout_view"))

@app.post("/payments/pagadito/ipn")
def pagadito_ipn():
    ref = request.form.get("reference") or request.args.get("reference")
    status = request.form.get("status") or request.args.get("status")
    gateway_ref = request.form.get("txid") or request.args.get("txid")

    if not ref or not status:
        return ("missing params", 400)

    try:
        oid = int(str(ref).split("ORDER-")[-1])
    except Exception:
        return ("bad reference", 400)

    if status.lower() in ("paid","approved","completed","success"):
        db_admin().table("orders").update({
            "status": "paid",
            "payment_status": "paid",
            "gateway_ref": gateway_ref
        }).eq("id", oid).execute()
    else:
        db_admin().table("orders").update({
            "status": "pending",
            "payment_status": "failed",
            "gateway_ref": gateway_ref
        }).eq("id", oid).execute()

    return ("OK", 200)

@app.get("/orders")
def orders_list():
    u = current_user()
    if not u:
        flash("Debes iniciar sesión.", "warning"); return redirect(url_for("login"))
    rows = db_admin().table("orders").select("id,status,total,currency,created_at,payment_status").eq("user_id", u["id"]).order("id", desc=True).execute().data or []
    return render_template("orders.html", orders=rows)

from admin.routes import admin_bp
app.register_blueprint(admin_bp, url_prefix="/admin")

if __name__ == "__main__":
    from datetime import timedelta
    app.permanent_session_lifetime = timedelta(days=7)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
