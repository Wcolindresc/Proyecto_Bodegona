from flask import Blueprint, render_template, request, redirect, url_for, flash
from core import db_admin, storage_admin, public_url, admin_required, BUCKET

admin_bp = Blueprint("admin", __name__, template_folder="templates", static_folder="static")

@admin_bp.get("/dashboard")
@admin_required
def dashboard():
    prod_count = db_admin().table("products").select("id", count="exact").execute().count or 0
    cat_count = db_admin().table("categories").select("id", count="exact").execute().count or 0
    order_count = db_admin().table("orders").select("id", count="exact").execute().count or 0
    return render_template("admin/dashboard.html", prod_count=prod_count, cat_count=cat_count, order_count=order_count)

@admin_bp.get("/products")
@admin_required
def products_list():
    res = db_admin().table("products").select("id,name,slug,price,stock,image_path,active").order("name").execute()
    products = res.data or []
    for p in products:
        p["image_url"] = public_url(p.get("image_path"))
    return render_template("admin/products_list.html", products=products)

@admin_bp.get("/products/new")
@admin_required
def products_new():
    cats = db_admin().table("categories").select("id,name,slug").order("name").execute().data or []
    return render_template("admin/product_form.html", product=None, categories=cats, assigned=[])

@admin_bp.post("/products/new")
@admin_required
def products_create():
    form = request.form
    data = {
        "name": form.get("name"),
        "slug": form.get("slug"),
        "description": form.get("description"),
        "price": float(form.get("price") or 0),
        "stock": int(form.get("stock") or 0),
        "active": (form.get("active") == "on"),
    }
    pr = db_admin().table("products").insert(data).execute().data
    pid = pr[0]["id"]
    cat_ids = request.form.getlist("categories")
    for cid in cat_ids:
        db_admin().table("product_categories").insert({"product_id": pid, "category_id": int(cid)}).execute()
    flash("Producto creado ✅", "success")
    return redirect(url_for("admin.products_list"))

@admin_bp.get("/products/<int:pid>/edit")
@admin_required
def products_edit(pid):
    p = db_admin().table("products").select("*").eq("id", pid).single().execute().data
    if not p:
        flash("Producto no encontrado", "danger")
        return redirect(url_for("admin.products_list"))
    cats = db_admin().table("categories").select("id,name,slug").order("name").execute().data or []
    assigned_rows = db_admin().table("product_categories").select("category_id").eq("product_id", pid).execute().data or []
    assigned = [r["category_id"] for r in assigned_rows]
    return render_template("admin/product_form.html", product=p, categories=cats, assigned=assigned)

@admin_bp.post("/products/<int:pid>/edit")
@admin_required
def products_update(pid):
    form = request.form
    data = {
        "name": form.get("name"),
        "slug": form.get("slug"),
        "description": form.get("description"),
        "price": float(form.get("price") or 0),
        "stock": int(form.get("stock") or 0),
        "active": (form.get("active") == "on"),
    }
    db_admin().table("products").update(data).eq("id", pid).execute()

    new_ids = set(int(x) for x in request.form.getlist("categories"))
    cur_rows = db_admin().table("product_categories").select("category_id").eq("product_id", pid).execute().data or []
    cur_ids = set(r["category_id"] for r in cur_rows)
    to_add = new_ids - cur_ids
    to_del = cur_ids - new_ids
    for cid in to_add:
        db_admin().table("product_categories").insert({"product_id": pid, "category_id": cid}).execute()
    for cid in to_del:
        db_admin().table("product_categories").delete().eq("product_id", pid).eq("category_id", cid).execute()
    flash("Producto actualizado ✅", "success")
    return redirect(url_for("admin.products_edit", pid=pid))

@admin_bp.post("/products/<int:pid>/delete")
@admin_required
def products_delete(pid):
    db_admin().table("product_categories").delete().eq("product_id", pid).execute()
    db_admin().table("products").delete().eq("id", pid).execute()
    flash("Producto eliminado ✅", "info")
    return redirect(url_for("admin.products_list"))

@admin_bp.post("/products/<int:pid>/image")
@admin_required
def products_upload_image(pid):
    file = request.files.get("file")
    if not file:
        flash("Sube un archivo", "warning")
        return redirect(url_for("admin.products_edit", pid=pid))
    prod = db_admin().table("products").select("slug").eq("id", pid).single().execute().data
    if not prod:
        flash("Producto no encontrado", "danger")
        return redirect(url_for("admin.products_list"))
    slug = prod["slug"]
    ext = (file.filename.rsplit(".",1)[-1] if "." in file.filename else "jpg").lower()
    path = f"products/{slug}.{ext}"
    try:
        storage_admin().from_(BUCKET).remove([path])
    except Exception:
        pass
    storage_admin().from_(BUCKET).upload(path, file.stream, file_options={"cacheControl":"3600","upsert":True})
    db_admin().table("products").update({"image_path": path}).eq("id", pid).execute()
    flash("Imagen actualizada ✅", "success")
    return redirect(url_for("admin.products_edit", pid=pid))

@admin_bp.get("/categories")
@admin_required
def categories_list():
    res = db_admin().table("categories").select("id,name,slug").order("name").execute()
    cats = res.data or []
    return render_template("admin/categories_list.html", categories=cats)

@admin_bp.get("/categories/new")
@admin_required
def categories_new():
    return render_template("admin/category_form.html", category=None)

@admin_bp.post("/categories/new")
@admin_required
def categories_create():
    form = request.form
    db_admin().table("categories").insert({"name": form.get("name"), "slug": form.get("slug")}).execute()
    flash("Categoría creada ✅", "success")
    return redirect(url_for("admin.categories_list"))

@admin_bp.get("/categories/<int:cid>/edit")
@admin_required
def categories_edit(cid):
    cat = db_admin().table("categories").select("*").eq("id", cid).single().execute().data
    if not cat:
        flash("Categoría no encontrada", "danger")
        return redirect(url_for("admin.categories_list"))
    return render_template("admin/category_form.html", category=cat)

@admin_bp.post("/categories/<int:cid>/edit")
@admin_required
def categories_update(cid):
    form = request.form
    db_admin().table("categories").update({"name": form.get("name"), "slug": form.get("slug")}).eq("id", cid).execute()
    flash("Categoría actualizada ✅", "success")
    return redirect(url_for("admin.categories_list"))

@admin_bp.post("/categories/<int:cid>/delete")
@admin_required
def categories_delete(cid):
    db_admin().table("product_categories").delete().eq("category_id", cid).execute()
    db_admin().table("categories").delete().eq("id", cid).execute()
    flash("Categoría eliminada ✅", "info")
    return redirect(url_for("admin.categories_list"))

@admin_bp.get("/orders")
@admin_required
def orders_list_admin():
    rows = db_admin().table("orders").select("id,user_id,status,total,currency,payment_status,created_at").order("id", desc=True).execute().data or []
    return render_template("admin/orders_list.html", orders=rows)

@admin_bp.get("/orders/<int:oid>")
@admin_required
def order_detail_admin(oid):
    order = db_admin().table("orders").select("*").eq("id", oid).maybe_single().execute().data
    if not order:
        flash("Orden no encontrada", "danger")
        return redirect(url_for("admin.orders_list_admin"))
    items = db_admin().table("order_items").select("*").eq("order_id", oid).execute().data or []
    return render_template("admin/order_view.html", order=order, items=items)

@admin_bp.post("/orders/<int:oid>/status")
@admin_required
def order_status_admin(oid):
    status = request.form.get("status")
    db_admin().table("orders").update({"status": status}).eq("id", oid).execute()
    flash("Estado actualizado ✅", "success")
    return redirect(url_for("admin.order_detail_admin", oid=oid))
