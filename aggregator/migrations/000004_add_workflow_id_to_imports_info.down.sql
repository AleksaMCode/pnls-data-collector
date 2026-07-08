ALTER TABLE ONLY public.imports_info
    DROP CONSTRAINT IF EXISTS imports_info_workflow_id_fkey;

ALTER TABLE public.imports_info
    DROP COLUMN IF EXISTS workflow_id;

DROP TABLE IF EXISTS public.imports_workflow;

DROP TYPE IF EXISTS public.workflow_status;
