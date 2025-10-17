# La Bodegona — E-commerce (Flask + Supabase + Pagadito, GTQ)

## 1) Variables de entorno
Crea `.env` o variables en tu PaaS (Render/Railway/Fly):
```
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
SECRET_KEY=algo-seguro
CURRENCY=GTQ

PAYMENT_PROVIDER=pagadito
PAGADITO_UID=...
PAGADITO_WKEY=...
PAGADITO_ENV=sandbox
PAGADITO_CHECKOUT_URL=https://sandbox.pagadi.to/checkout
PAGADITO_IPN_SECRET=
```

## 2) Instalar y correr
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Abrir: http://localhost:5000

## 3) SQL para Supabase
Copia todo el bloque del archivo `SQL_SUPABASE.sql` en el **SQL Editor**.

## 4) Admins
Crea `admin@labodegona.com` y `gerente@labodegona.com` en Supabase Auth (Email confirmed) y ejecútalo:
```sql
insert into public.admins (user_id)
select id from auth.users where email in ('admin@labodegona.com','gerente@labodegona.com')
on conflict do nothing;
```

## 5) Despliegue (Render)
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`
- Variables: ver sección 1
- Dominios: agrega tu dominio y usa HTTPS

## 6) Flujo
Catálogo `/`, Registro `/register`, Login `/login`, Perfil `/profile`, Carrito `/cart`, Checkout `/checkout` (Pagadito), Órdenes `/orders`. Panel admin en `/admin/*` con productos, categorías, órdenes e imágenes (Supabase Storage `products`).

## 7) Notas
- La Service Role Key **solo** en servidor.
- Si el panel de Pagadito usa otros nombres de parámetros, ajusta `build_pagadi_payload()` en `app.py`.
