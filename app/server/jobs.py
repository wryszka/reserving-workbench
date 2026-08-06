"""Triggering the LDF pipeline from the app — 'the decision picks the pipeline back up'.

The pipeline stops at stage 2 on purpose: an empirical pick must not reach the
loss-cost table until a human approves a pattern. So the approval in the app is
what resumes it. This module runs the stage-3-only job and reports its state, so
the actuary sees the consequence of their decision without leaving the workbench.

Job ids are resolved by NAME rather than hardcoded, so a redeploy that recreates
the job doesn't silently break the button.
"""
from functools import lru_cache

from . import config

STAGE3_JOB_NAME = "[reserving-workbench] LDF stage 3 — develop on the approved pattern"
FULL_JOB_NAME = "[reserving-workbench] LDF pipeline — prep · selection · output"


@lru_cache(maxsize=4)
def _job_id(name: str):
    """Resolve a job id by exact name; None if it isn't deployed here."""
    try:
        for j in config.get_workspace_client().jobs.list(limit=100):
            if (j.settings.name if j.settings else "") == name:
                return j.job_id
    except Exception:
        pass
    return None


def stage3_job_id():
    return _job_id(STAGE3_JOB_NAME)


def full_job_id():
    return _job_id(FULL_JOB_NAME)


def run_stage3():
    """Kick off the stage-3 job. Returns {ok, run_id, run_url} or {ok: False, error}."""
    jid = stage3_job_id()
    if not jid:
        return {"ok": False, "error": "The stage-3 job isn't deployed in this workspace."}
    try:
        w = config.get_workspace_client()
        wait = w.jobs.run_now(job_id=jid)
        run_id = wait.run_id
        host = config.workspace_host()
        return {"ok": True, "run_id": run_id, "job_id": jid,
                "run_url": f"{host}/#job/{jid}/run/{run_id}" if host else None}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def run_state(run_id: int):
    """Poll a run. Returns a small shape the UI can render into a status chip.

    `state` is one of PENDING / RUNNING / SUCCESS / FAILED / CANCELED so the
    front end doesn't have to know the Jobs API vocabulary. On failure the
    task's own error message is surfaced — for stage 3 that is the guard
    message, which is the thing worth showing.
    """
    try:
        w = config.get_workspace_client()
        r = w.jobs.get_run(run_id=run_id)
        life = r.state.life_cycle_state.value if (r.state and r.state.life_cycle_state) else ""
        result = (r.state.result_state.value if (r.state and r.state.result_state) else "") or ""
        if life in ("PENDING", "QUEUED"):
            state = "PENDING"
        elif life in ("RUNNING", "TERMINATING"):
            state = "RUNNING"
        else:
            state = result or "UNKNOWN"
        detail = ""
        if state == "FAILED":
            # prefer the failing task's message (the guard text) over the generic one
            for t in (r.tasks or []):
                if t.state and t.state.result_state and t.state.result_state.value == "FAILED":
                    try:
                        o = w.jobs.get_run_output(run_id=t.run_id)
                        detail = (o.error or "")[:400]
                    except Exception:
                        pass
                    break
            if not detail and r.state:
                detail = (r.state.state_message or "")[:400]
        return {"ok": True, "run_id": run_id, "state": state, "detail": detail,
                "run_url": r.run_page_url}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}
