-- Ejecuta todo este bloque en Supabase → SQL Editor

alter table public.products
  add column if not exists image_path text,
  add column if not exists slug text,
  add column if not exists description text,
  add column if not exists active boolean default true;
create unique index if not exists products_slug_uindex on public.products(slug);

create table if not exists public.categories (
  id bigserial primary key,
  name text not null,
  slug text unique not null
);
create table if not exists public.product_categories (
  product_id bigint references public.products(id) on delete cascade,
  category_id bigint references public.categories(id) on delete cascade,
  primary key (product_id, category_id)
);

create table if not exists public.admins (
  user_id uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz default now()
);

create table if not exists public.carts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid unique not null references auth.users(id) on delete cascade,
  created_at timestamptz default now()
);
create table if not exists public.cart_items (
  id bigserial primary key,
  cart_id uuid not null references public.carts(id) on delete cascade,
  product_id bigint not null references public.products(id) on delete cascade,
  qty integer not null default 1,
  price_at_add numeric(10,2)
);

create table if not exists public.addresses (
  id bigserial primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  full_name text,
  phone text,
  line1 text,
  line2 text,
  city text,
  region text,
  postal_code text,
  country text default 'GT',
  is_default boolean default false,
  created_at timestamptz default now()
);

create table if not exists public.orders (
  id bigserial primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  status text not null default 'pending',
  total numeric(10,2) not null default 0,
  currency text not null default 'GTQ',
  payment_method text,
  payment_status text,
  gateway_ref text,
  address_snapshot jsonb,
  created_at timestamptz default now()
);
create table if not exists public.order_items (
  id bigserial primary key,
  order_id bigint not null references public.orders(id) on delete cascade,
  product_id bigint references public.products(id),
  name text,
  price numeric(10,2),
  qty integer,
  subtotal numeric(10,2)
);

select case when not exists (select 1 from storage.buckets where id='products')
  then storage.create_bucket('products', public:=true)
  else null end;

alter table storage.objects enable row level security;
do $$
begin
  if not exists (select 1 from pg_policies where polname='public_read_products') then
    create policy public_read_products
    on storage.objects for select to anon, authenticated using (bucket_id = 'products');
  end if;
end $$;

alter table public.products enable row level security;
alter table public.categories enable row level security;
alter table public.product_categories enable row level security;
alter table public.carts enable row level security;
alter table public.cart_items enable row level security;
alter table public.orders enable row level security;
alter table public.order_items enable row level security;
alter table public.addresses enable row level security;

create policy if not exists products_read_public on public.products for select to anon, authenticated using (true);
create policy if not exists categories_read_public on public.categories for select to anon, authenticated using (true);
create policy if not exists product_categories_read_public on public.product_categories for select to anon, authenticated using (true);

create policy if not exists products_write_admin on public.products for all to authenticated
  using (exists (select 1 from public.admins a where a.user_id = auth.uid()))
  with check (exists (select 1 from public.admins a where a.user_id = auth.uid()));
create policy if not exists categories_write_admin on public.categories for all to authenticated
  using (exists (select 1 from public.admins a where a.user_id = auth.uid()))
  with check (exists (select 1 from public.admins a where a.user_id = auth.uid()));
create policy if not exists product_categories_write_admin on public.product_categories for all to authenticated
  using (exists (select 1 from public.admins a where a.user_id = auth.uid()))
  with check (exists (select 1 from public.admins a where a.user_id = auth.uid()));

create policy if not exists carts_self on public.carts for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy if not exists cart_items_self on public.cart_items for all to authenticated
  using (exists(select 1 from public.carts c where c.id=cart_id and c.user_id=auth.uid()))
  with check (exists(select 1 from public.carts c where c.id=cart_id and c.user_id=auth.uid()));
create policy if not exists addresses_self on public.addresses for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy if not exists orders_self on public.orders for select to authenticated
  using (user_id = auth.uid());
