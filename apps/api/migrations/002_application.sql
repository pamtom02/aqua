-- 000_create_roles_table.sql
CREATE TABLE IF NOT EXISTS public.roles (
    id UUID PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

-- 001_create_profiles_table.sql
CREATE TABLE IF NOT EXISTS public.profiles (


    id UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,

    name TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'active' NOT NULL,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);


CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_profiles_updated_at
BEFORE UPDATE ON public.profiles
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();

-- 002_create_organizations_table.sql
CREATE TABLE public.organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);


CREATE TRIGGER set_organizations_updated_at
BEFORE UPDATE ON public.organizations
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();

-- 003_create_memberships_table.sql
CREATE TABLE public.memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'active' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    UNIQUE(user_id, organization_id)
);


CREATE TRIGGER set_memberships_updated_at
BEFORE UPDATE ON public.memberships
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();

-- 004_create_lakes_table.sql
CREATE TABLE public.lakes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    region VARCHAR(255) NOT NULL,
    description TEXT,
    geom JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'active' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);


CREATE TRIGGER set_lakes_updated_at
BEFORE UPDATE ON public.lakes
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();

-- 005_create_stations_table.sql
CREATE TABLE public.stations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lake_id UUID NOT NULL REFERENCES public.lakes(id),
    code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    point JSONB NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,

    UNIQUE(lake_id, code)
);

CREATE TRIGGER set_stations_updated_at
BEFORE UPDATE ON public.stations
FOR EACH ROW
EXECUTE FUNCTION public.handle_updated_at();

-- 007_add_organization_status.sql
ALTER TABLE public.organizations
ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'active' NOT NULL;

CREATE INDEX IF NOT EXISTS idx_organizations_status
ON public.organizations USING btree (status);

-- 008_create_audit_events_table.sql
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor UUID NOT NULL,
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(255) NOT NULL,
    resource_id UUID NOT NULL,
    event_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    organization_id UUID,
    metadata JSONB DEFAULT '{}'::jsonb
);


CREATE OR REPLACE FUNCTION prevent_audit_update()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.actor <> OLD.actor OR NEW.action <> OLD.action OR NEW.event_date <> OLD.event_date THEN
        RAISE EXCEPTION 'Operación denegada: no se permite modificar actor, acción ni fecha de un evento de auditoría';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE TRIGGER enforce_audit_events_immutability
BEFORE UPDATE ON audit_events
FOR EACH ROW
EXECUTE FUNCTION prevent_audit_update();

-- 009_organization_member_support.sql
ALTER TABLE public.organizations
ADD COLUMN IF NOT EXISTS identifier VARCHAR(100);

UPDATE public.organizations
SET identifier = trim(both '-' from regexp_replace(lower(name), '[^a-z0-9]+', '-', 'g'))
    || '-' || substring(replace(id::text, '-', '') from 1 for 8)
WHERE identifier IS NULL OR identifier = '';

ALTER TABLE public.organizations
ALTER COLUMN identifier SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_organizations_identifier
ON public.organizations USING btree (identifier);

ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS email TEXT;

-- 011_create_imports_table.sql
CREATE TABLE IF NOT EXISTS public.imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    content_type TEXT,
    checksum CHAR(64) NOT NULL UNIQUE,
    file_size BIGINT NOT NULL CHECK (file_size > 0),
    idempotency_key VARCHAR(255) UNIQUE,
    storage_path TEXT NOT NULL UNIQUE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 013_create_dataset_versioning_schema.sql
CREATE SCHEMA IF NOT EXISTS dataset;

CREATE TABLE IF NOT EXISTS dataset.datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    description TEXT,
    created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dataset.versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL REFERENCES dataset.datasets(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'archived')),
    created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (dataset_id, version_number)
);

CREATE TABLE IF NOT EXISTS dataset.memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id UUID NOT NULL REFERENCES dataset.versions(id) ON DELETE CASCADE,
    scene_provider TEXT NOT NULL CHECK (length(trim(scene_provider)) > 0),
    scene_external_id TEXT NOT NULL CHECK (length(trim(scene_external_id)) > 0),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (version_id, scene_provider, scene_external_id)
);

CREATE TABLE IF NOT EXISTS dataset.decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    membership_id UUID NOT NULL
        REFERENCES dataset.memberships(id) ON DELETE CASCADE,
    decision TEXT NOT NULL CHECK (decision IN ('accepted', 'rejected')),
    reason TEXT,
    decided_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dataset_versions_dataset_created
ON dataset.versions (dataset_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_dataset_decisions_membership_decided
ON dataset.decisions (membership_id, decided_at DESC);

-- 013_create_prepared_inputs_table.sql
CREATE TABLE IF NOT EXISTS public.prepared_inputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_import_id UUID NOT NULL
        REFERENCES public.imports(id) ON DELETE RESTRICT,
    source_key VARCHAR(255) NOT NULL UNIQUE
        CHECK (length(btrim(source_key)) > 0),
    metadata JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 013_create_scenes_table.sql
CREATE TABLE IF NOT EXISTS public.scenes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lake_id UUID NOT NULL REFERENCES public.lakes(id),
    scene_identifier TEXT NOT NULL,
    acquisition_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT scenes_lake_identifier_unique UNIQUE (lake_id, scene_identifier)
);

CREATE INDEX IF NOT EXISTS idx_scenes_lake_acquisition_date
ON public.scenes (lake_id, acquisition_date DESC);

-- 014_enforce_dataset_organization_isolation.sql
ALTER TABLE dataset.datasets
ADD COLUMN IF NOT EXISTS organization_id UUID
REFERENCES public.organizations(id) ON DELETE CASCADE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'datasets_organization_required'
          AND conrelid = 'dataset.datasets'::regclass
    ) THEN
        ALTER TABLE dataset.datasets
        ADD CONSTRAINT datasets_organization_required
        CHECK (organization_id IS NOT NULL) NOT VALID;
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_dataset_datasets_organization
ON dataset.datasets (organization_id);

-- 015_create_satellite_scenes_table.sql
CREATE SCHEMA IF NOT EXISTS satellite;


ALTER TABLE IF EXISTS public.scenes SET SCHEMA satellite;


ALTER TABLE satellite.scenes
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS file_references JSONB DEFAULT '[]'::jsonb;

-- 016_create_sprectral_observations_table.sql
CREATE SCHEMA IF NOT EXISTS satellite;



CREATE TABLE IF NOT EXISTS satellite.spectral_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scene_id UUID NOT NULL REFERENCES satellite.scenes(id) ON DELETE CASCADE,
    sample_id UUID NOT NULL,
    bands JSONB NOT NULL,
    spectral_index VARCHAR(50) NOT NULL,
    index_value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(50) NOT NULL,
    quality VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS idx_spectral_observations_scene_id ON satellite.spectral_observations(scene_id);
CREATE INDEX IF NOT EXISTS idx_spectral_observations_sample_id ON satellite.spectral_observations(sample_id);

-- 017_add_dataset_version_published_at.sql
ALTER TABLE dataset.versions
ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;

-- 017_dataset_version_lifecycle.sql
ALTER TABLE dataset.versions
  DROP CONSTRAINT IF EXISTS versions_status_check,
  DROP CONSTRAINT IF EXISTS dataset_versions_status_check,
  DROP CONSTRAINT IF EXISTS versions_state_check,
  DROP CONSTRAINT IF EXISTS dataset_versions_state_check;


ALTER TABLE dataset.versions
  ADD COLUMN IF NOT EXISTS state VARCHAR(50) DEFAULT 'DRAFT';


UPDATE dataset.versions
SET state = UPPER(COALESCE(state, status, 'DRAFT')),
    status = UPPER(COALESCE(status, state, 'DRAFT'));


ALTER TABLE dataset.versions
  ADD CONSTRAINT dataset_versions_state_check
  CHECK (state IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'PUBLISHED', 'ARCHIVED')),
  ADD CONSTRAINT dataset_versions_status_check
  CHECK (status IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'PUBLISHED', 'ARCHIVED'));

-- 018_create_training_manifests.sql
CREATE TABLE IF NOT EXISTS dataset.training_manifests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id UUID NOT NULL REFERENCES dataset.versions(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    checksum TEXT NOT NULL CHECK (checksum ~ '^[a-f0-9]{64}$'),
    variables TEXT[] NOT NULL DEFAULT '{"temperatura", "clorofila_a", "turbidez", "ph"}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(version_id)
);

-- 019_create_scientific_jobs_table.sql
CREATE SCHEMA IF NOT EXISTS scientific;


CREATE TYPE scientific.job_type AS ENUM (
    'TRAINING',
    'ESTIMATION'
);

CREATE TYPE scientific.job_status AS ENUM (
    'PENDING',
    'IN_PROGRESS',
    'COMPLETED',
    'FAILED',
    'CANCELLED'
);


CREATE TABLE IF NOT EXISTS scientific.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    job_type scientific.job_type NOT NULL,
    status scientific.job_status NOT NULL DEFAULT 'PENDING',


    dataset_version_id UUID REFERENCES dataset.versions(id) ON DELETE SET NULL,
    model_version_id UUID,


    requested_by UUID REFERENCES public.users(id) ON DELETE SET NULL,


    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,


    result_metadata JSONB DEFAULT '{}'::jsonb,
    error_message TEXT
);


CREATE INDEX IF NOT EXISTS idx_scientific_jobs_status ON scientific.jobs(status);
CREATE INDEX IF NOT EXISTS idx_scientific_jobs_dataset_version ON scientific.jobs(dataset_version_id);
CREATE INDEX IF NOT EXISTS idx_scientific_jobs_requested_by ON scientific.jobs(requested_by);

-- 020_extend_training_manifest_metadata.sql
ALTER TABLE dataset.training_manifests
ADD COLUMN IF NOT EXISTS manifest_version TEXT NOT NULL DEFAULT '1.0.0',
ADD COLUMN IF NOT EXISTS sources TEXT[] NOT NULL DEFAULT '{}',
ADD COLUMN IF NOT EXISTS is_experimental BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS is_synthetic BOOLEAN NOT NULL DEFAULT false;

-- 20261030_add_organization_to_scientific_jobs.sql
ALTER TABLE scientific.jobs
    ALTER COLUMN status DROP DEFAULT,
    ALTER COLUMN job_type TYPE text USING lower(job_type::text),
    ALTER COLUMN status TYPE text USING CASE status::text
        WHEN 'IN_PROGRESS' THEN 'running'
        ELSE lower(status::text)
    END,
    ADD COLUMN organization_id UUID REFERENCES public.organizations(id) ON DELETE CASCADE,
    ADD COLUMN config JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN idempotency_key TEXT,
    ADD COLUMN result JSONB;

UPDATE scientific.jobs SET result = result_metadata
WHERE result_metadata IS NOT NULL AND result_metadata <> '{}'::jsonb;

ALTER TABLE scientific.jobs
    ALTER COLUMN status SET DEFAULT 'queued',
    ADD CONSTRAINT scientific_jobs_type_check
        CHECK (job_type IN ('training', 'modeling', 'estimation')),
    ADD CONSTRAINT scientific_jobs_status_check
        CHECK (status IN ('pending', 'queued', 'running', 'completed', 'failed', 'cancelled')),
    ADD CONSTRAINT scientific_jobs_organization_id_required
        CHECK (organization_id IS NOT NULL) NOT VALID;



CREATE INDEX idx_scientific_jobs_organization_id ON scientific.jobs(organization_id);
CREATE UNIQUE INDEX idx_scientific_jobs_idempotency_key
    ON scientific.jobs(organization_id, idempotency_key) WHERE idempotency_key IS NOT NULL;

-- 20261102_create_model_artifacts.sql
CREATE TABLE IF NOT EXISTS public.model_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    training_job_id UUID NOT NULL
        REFERENCES scientific.jobs(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    file_size BIGINT NOT NULL CHECK (file_size > 0),
    checksum TEXT NOT NULL CHECK (checksum ~ '^[a-f0-9]{64}$'),
    storage_path TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (training_job_id)
);
