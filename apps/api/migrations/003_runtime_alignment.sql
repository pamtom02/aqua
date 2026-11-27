ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS email text;
ALTER TABLE public.lakes ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES public.organizations(id);
ALTER TABLE public.lakes ADD COLUMN IF NOT EXISTS is_active boolean GENERATED ALWAYS AS (status='active') STORED;
ALTER TABLE scientific.jobs ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
CREATE TRIGGER set_scientific_jobs_updated_at BEFORE UPDATE ON scientific.jobs
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();
ALTER TABLE dataset.versions ALTER COLUMN status SET DEFAULT 'DRAFT';
ALTER TABLE satellite.scenes ADD COLUMN IF NOT EXISTS provider text DEFAULT 'Sentinel-2';
ALTER TABLE satellite.scenes ADD COLUMN IF NOT EXISTS capture_date date GENERATED ALWAYS AS (acquisition_date) STORED;
CREATE TABLE public.audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id uuid NOT NULL REFERENCES public.users(id),
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.samples (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    station_id uuid NOT NULL REFERENCES public.stations(id),
    collected_at timestamptz NOT NULL DEFAULT now(),
    value double precision,
    metadata jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX ON public.lakes(region,status);
CREATE INDEX ON public.stations(lake_id,status);
CREATE INDEX ON public.memberships(user_id,status);
ALTER TABLE public.lakes ADD CONSTRAINT lakes_geojson_polygon CHECK(geom->>'type'='Polygon' AND jsonb_typeof(geom->'coordinates')='array');
ALTER TABLE public.stations ADD CONSTRAINT stations_geojson_point CHECK(point->>'type'='Point' AND jsonb_typeof(point->'coordinates')='array');
