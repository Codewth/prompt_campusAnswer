create table if not exists public.gemini_daily_usage (
    quota_date date primary key,
    request_count integer not null default 0 check (request_count >= 0),
    last_request_at timestamptz,
    updated_at timestamptz not null default now()
);

alter table public.gemini_daily_usage enable row level security;
revoke all on table public.gemini_daily_usage from anon, authenticated;
grant all on table public.gemini_daily_usage to service_role;

create or replace function public.reserve_gemini_request(
    p_daily_limit integer,
    p_min_interval_seconds integer
)
returns text
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_quota_date date := (statement_timestamp() at time zone 'America/Los_Angeles')::date;
    v_request_count integer;
    v_last_request_at timestamptz;
begin
    if p_daily_limit < 1 or p_min_interval_seconds < 0 then
        raise exception 'Invalid Gemini quota configuration';
    end if;

    insert into public.gemini_daily_usage (quota_date, request_count)
    values (v_quota_date, 0)
    on conflict (quota_date) do nothing;

    select request_count, last_request_at
      into v_request_count, v_last_request_at
      from public.gemini_daily_usage
     where quota_date = v_quota_date
     for update;

    if v_request_count >= p_daily_limit then
        return 'daily_limit';
    end if;

    if v_last_request_at is not null
       and v_last_request_at > statement_timestamp() - make_interval(secs => p_min_interval_seconds) then
        return 'throttled';
    end if;

    update public.gemini_daily_usage
       set request_count = request_count + 1,
           last_request_at = statement_timestamp(),
           updated_at = statement_timestamp()
     where quota_date = v_quota_date;

    return 'allowed';
end;
$$;

create or replace function public.mark_gemini_quota_exhausted(p_daily_limit integer)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_quota_date date := (statement_timestamp() at time zone 'America/Los_Angeles')::date;
begin
    insert into public.gemini_daily_usage (quota_date, request_count, last_request_at)
    values (v_quota_date, p_daily_limit, statement_timestamp())
    on conflict (quota_date) do update
       set request_count = greatest(gemini_daily_usage.request_count, excluded.request_count),
           last_request_at = statement_timestamp(),
           updated_at = statement_timestamp();
end;
$$;

revoke all on function public.reserve_gemini_request(integer, integer) from public, anon, authenticated;
revoke all on function public.mark_gemini_quota_exhausted(integer) from public, anon, authenticated;
grant execute on function public.reserve_gemini_request(integer, integer) to service_role;
grant execute on function public.mark_gemini_quota_exhausted(integer) to service_role;

insert into public.gemini_daily_usage (quota_date, request_count, last_request_at)
values (date '2026-11-22', 20, statement_timestamp())
on conflict (quota_date) do update
   set request_count = greatest(gemini_daily_usage.request_count, excluded.request_count),
       last_request_at = statement_timestamp(),
       updated_at = statement_timestamp();
