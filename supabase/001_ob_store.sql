-- Odyssey Black: cloud storage for the app's saved data.
-- Run once in Supabase: SQL Editor -> New query -> paste -> Run.
-- UNTESTED against a live database (no access from the build environment). Run it in the NEW Odyssey Black project only.

create table if not exists public.ob_store (
  user_id    uuid not null default auth.uid() references auth.users(id) on delete cascade,
  key        text not null check (key in ('ob-pipeline','ob-gatekeepers','ob-messages','ob-cal-progress','ob-event-mode','ob-radar')),
  value      jsonb not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, key)
);

create table if not exists public.ob_store_history (
  id       bigint generated always as identity primary key,
  user_id  uuid not null,
  key      text not null,
  value    jsonb not null,
  saved_at timestamptz not null default now()
);

alter table public.ob_store enable row level security;
alter table public.ob_store_history enable row level security;

-- Only the signed-in owner can see or change their own rows.
create policy "ob_store select own" on public.ob_store for select to authenticated using (user_id = auth.uid());
create policy "ob_store insert own" on public.ob_store for insert to authenticated with check (user_id = auth.uid());
create policy "ob_store update own" on public.ob_store for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "ob_store delete own" on public.ob_store for delete to authenticated using (user_id = auth.uid());
create policy "ob_store_history select own" on public.ob_store_history for select to authenticated using (user_id = auth.uid());

-- Safety net: before a row is overwritten, keep the previous version (at most one per 10 minutes per key).
create or replace function public.ob_store_archive() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if old.updated_at < now() - interval '10 minutes' then
    insert into public.ob_store_history(user_id, key, value) values (old.user_id, old.key, old.value);
  end if;
  new.updated_at := now();
  return new;
end $$;

drop trigger if exists ob_store_archive_trg on public.ob_store;
create trigger ob_store_archive_trg before update on public.ob_store
for each row execute function public.ob_store_archive();
