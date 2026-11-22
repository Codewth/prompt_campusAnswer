create table if not exists public.student_profiles (
    uid text primary key,
    name text not null default '',
    university text not null default '',
    enrollment_number text not null default '',
    course text not null default '',
    specialization text not null default '',
    academic_year text not null default '',
    semester text not null default '',
    batch text not null default '',
    theme text not null default 'light' check (theme in ('light', 'dark')),
    updated_at timestamptz not null default now()
);

create table if not exists public.revoked_tokens (
    token_hash text primary key,
    user_id text not null,
    expires_at bigint not null
);

create index if not exists revoked_tokens_expires_at_idx
    on public.revoked_tokens (expires_at);

alter table public.student_profiles enable row level security;
alter table public.revoked_tokens enable row level security;

revoke all on table public.student_profiles, public.revoked_tokens from anon, authenticated;
grant select, insert, update, delete on table public.student_profiles, public.revoked_tokens to service_role;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('campusanswer-documents', 'campusanswer-documents', false, 5242880, null)
on conflict (id) do update
set public = false,
    file_size_limit = 5242880,
    allowed_mime_types = null;
