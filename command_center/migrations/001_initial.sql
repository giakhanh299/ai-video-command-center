CREATE SCHEMA IF NOT EXISTS command_center;
CREATE TABLE command_center.projects (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL, name text NOT NULL CHECK(length(name) BETWEEN 1 AND 120),
 version integer NOT NULL DEFAULT 1 CHECK(version>0), archived_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ON command_center.projects(owner_id,id);
CREATE TABLE command_center.agents (
 id uuid PRIMARY KEY, owner_id uuid NOT NULL, machine_id uuid NOT NULL,
 credential_hash text NOT NULL UNIQUE, capabilities jsonb NOT NULL DEFAULT '[]',
 capability_version text NOT NULL DEFAULT '1.0.0', disabled_at timestamptz, last_seen_at timestamptz
);
CREATE TABLE command_center.jobs (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES command_center.projects(id),
 preset_id text NOT NULL, preset_version text NOT NULL, manifest jsonb NOT NULL,
 status text NOT NULL CHECK(status IN ('queued','running','cancelling','needs_review','needs_attention','failed','cancelled')),
 version integer NOT NULL DEFAULT 1 CHECK(version>0), cancel_requested boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 error_code text
);
CREATE INDEX ON command_center.jobs(project_id,id);
CREATE TABLE command_center.tasks (
 id uuid PRIMARY KEY, job_id uuid NOT NULL REFERENCES command_center.jobs(id), task_key text NOT NULL,
 module text NOT NULL, module_version text NOT NULL, config jsonb NOT NULL, resource text NOT NULL,
 status text NOT NULL CHECK(status IN ('queued','leased','running','succeeded','failed','cancelled','needs_attention')),
 attempt integer NOT NULL DEFAULT 0 CHECK(attempt>=0), agent_id uuid REFERENCES command_center.agents(id),
 lease_token uuid, lease_expires_at timestamptz, completion_digest text, error_code text,
 input_refs jsonb NOT NULL, output_refs jsonb NOT NULL DEFAULT '[]', UNIQUE(job_id,task_key)
);
CREATE INDEX ON command_center.tasks(status,job_id);
CREATE TABLE command_center.task_dependencies (
 task_id uuid NOT NULL REFERENCES command_center.tasks(id), dependency_id uuid NOT NULL REFERENCES command_center.tasks(id),
 PRIMARY KEY(task_id,dependency_id), CHECK(task_id<>dependency_id)
);
CREATE TABLE command_center.attempts (
 id uuid PRIMARY KEY, task_id uuid NOT NULL REFERENCES command_center.tasks(id), number integer NOT NULL CHECK(number>0),
 agent_id uuid NOT NULL REFERENCES command_center.agents(id), lease_token uuid NOT NULL UNIQUE,
 started_at timestamptz NOT NULL DEFAULT clock_timestamp(), finished_at timestamptz, outcome text,
 UNIQUE(task_id,number)
);
CREATE TABLE command_center.resources (
 machine_id uuid NOT NULL, resource text NOT NULL, task_id uuid NOT NULL UNIQUE REFERENCES command_center.tasks(id),
 PRIMARY KEY(machine_id,resource)
);
CREATE TABLE command_center.files (
 id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES command_center.projects(id),
 job_id uuid REFERENCES command_center.jobs(id), task_id uuid REFERENCES command_center.tasks(id), attempt integer,
 logical_name text NOT NULL, kind text NOT NULL CHECK(kind IN ('video','audio','subtitle','report','packet')),
 media_type text NOT NULL, size_bytes bigint NOT NULL CHECK(size_bytes>0 AND size_bytes<=524288000),
 sha256 text NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$'), storage_key text NOT NULL UNIQUE,
 verification text NOT NULL CHECK(verification IN ('pending','verified','rejected')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(task_id,attempt,logical_name)
);
CREATE TABLE command_center.events (
 sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, id uuid NOT NULL UNIQUE,
 job_id uuid NOT NULL REFERENCES command_center.jobs(id), task_id uuid REFERENCES command_center.tasks(id),
 timestamp timestamptz NOT NULL DEFAULT clock_timestamp(), level text NOT NULL,
 code text NOT NULL, message text NOT NULL
);
CREATE INDEX ON command_center.events(job_id,sequence);
CREATE TABLE command_center.idempotency_keys (
 owner_id uuid NOT NULL, route text NOT NULL, key text NOT NULL, request_digest text NOT NULL,
 resource_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(owner_id,route,key)
);
