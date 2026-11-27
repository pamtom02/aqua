ALTER TABLE public.auth_sessions
    ADD COLUMN last_activity_at timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN mfa_verified boolean NOT NULL DEFAULT false;

-- Existing sessions must reauthenticate after the introduction of MFA.
DELETE FROM public.auth_sessions;

CREATE TABLE public.user_mfa (
    user_id uuid PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
    encrypted_secret text NOT NULL,
    enabled boolean NOT NULL DEFAULT false,
    last_counter bigint NOT NULL DEFAULT -1,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.mfa_recovery_codes (
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    code_hash text NOT NULL,
    PRIMARY KEY (user_id, code_hash)
);
