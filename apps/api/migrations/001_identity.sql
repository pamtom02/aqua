CREATE TABLE public.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL UNIQUE CHECK(email=lower(email)),
    password_hash text NOT NULL,
    role text NOT NULL DEFAULT 'auditor' CHECK(role IN ('administrador','supervisor','investigador','auditor')),
    status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','inactive')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.auth_sessions (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    refresh_hash text NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON public.auth_sessions(user_id);
CREATE TABLE public.login_attempts (
    key text PRIMARY KEY,
    attempts integer NOT NULL,
    window_start timestamptz NOT NULL
);
