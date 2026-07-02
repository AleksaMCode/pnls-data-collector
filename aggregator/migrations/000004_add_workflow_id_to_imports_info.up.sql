CREATE TYPE public.workflow_status AS ENUM ('STARTED', 'COMPLETED', 'FAILED');

CREATE TABLE public.imports_workflow (
    id uuid NOT NULL,
    start timestamp with time zone NOT NULL,
    "end" timestamp with time zone,
    status public.workflow_status NOT NULL
);

ALTER TABLE ONLY public.imports_workflow
    ADD CONSTRAINT imports_workflow_pkey PRIMARY KEY (id);

ALTER TABLE public.imports_info
    ADD COLUMN workflow_id uuid;

ALTER TABLE ONLY public.imports_info
    ADD CONSTRAINT imports_info_workflow_id_fkey FOREIGN KEY (workflow_id)
    REFERENCES public.imports_workflow(id);
