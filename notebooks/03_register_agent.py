# Databricks notebook source
# MAGIC %md
# MAGIC # Register & deploy the Reserving Workbench agent (Mosaic AI Agent Framework)
# MAGIC
# MAGIC `[reserving-workbench]` Registers the reserving supervisor + specialists as a single
# MAGIC **ChatAgent** (the current MLflow agent standard) in Unity Catalog, and deploys it to a
# MAGIC Model Serving endpoint via `databricks.agents.deploy` (scale-to-zero). The app invokes
# MAGIC this endpoint; it falls back to inline FMAPI only if the endpoint is cold. Every call is
# MAGIC traced in `5_ai_routing_trace` for governance.
# MAGIC
# MAGIC Run on serverless. Requires `databricks-agents`, `mlflow>=2.16`.

# COMMAND ----------
# MAGIC %pip install -U -q databricks-agents "mlflow>=2.16" databricks-sdk
# MAGIC dbutils.library.restartPython()

# COMMAND ----------
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
dbutils.widgets.text("schema", "reserving_workbench")
dbutils.widgets.text("fm_endpoint", "databricks-claude-sonnet-5")
dbutils.widgets.text("warehouse_id", "a3b61648ea4809e3")
CAT = dbutils.widgets.get("catalog"); SCH = dbutils.widgets.get("schema")
FM = dbutils.widgets.get("fm_endpoint"); WID = dbutils.widgets.get("warehouse_id")
MODEL = f"{CAT}.{SCH}.reserving_agent"

# COMMAND ----------
# MAGIC %md ## The agent — supervisor over 5 reserving specialists, grounded on live tables

# COMMAND ----------
agent_src = '''
import os, json, re
from mlflow.pyfunc import ChatAgent
from mlflow.types.agent import ChatAgentMessage, ChatAgentResponse
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

CAT = os.environ.get("CATALOG_NAME", "lr_dev_aws_us_catalog")
SCH = os.environ.get("SCHEMA_NAME", "reserving_workbench")
FM  = os.environ.get("FM_ENDPOINT", "databricks-claude-sonnet-5")
WID = os.environ.get("AGENT_WAREHOUSE_ID", "a3b61648ea4809e3")
FQ  = f"{CAT}.{SCH}"

SPECIALISTS = {
  "senior_reserving": {"name":"Senior Reserving Actuary","triggers":"brief committee emerging trends overall summary",
    "system":"You are the Senior Reserving Actuary for Bricksurance SE (commercial P&C). Brief the quarterly reserving committee: emerging trends, cohorts needing attention, judgement calls. Cite AYs, lines, figures. Concise. Synthetic demo data; no disclaimers."},
  "movement": {"name":"Movement Explainer","triggers":"why did reserves move movement roll-forward change driver",
    "system":"You explain reserve movements for Bricksurance SE from the roll-forward drivers (opening, expected run-off, experience, assumption change, large loss, expert judgement, closing). Quantify each. Concise."},
  "data_quality": {"name":"Data-Quality Investigator","triggers":"validation breach tolerance data quality anomaly outlier residual",
    "system":"You are a reserving data-quality investigator for Bricksurance SE. Given the actual-vs-expected breaches, point to the cohorts that need attention, quantify residuals, hypothesise the cause. Concise."},
  "committee_note": {"name":"Committee-Note Drafter","triggers":"draft note memo write up minute document rationale paper",
    "system":"You draft concise reserving-committee notes for Bricksurance SE: decision, rationale, quantified impact, basis. Ready for an actuary to edit."},
  "reviewer": {"name":"Reserving Peer Reviewer","triggers":"review check second opinion sense check reasonable peer challenge",
    "system":"You are an independent reserving peer reviewer for Bricksurance SE giving a colleague a second opinion on THEIR selection or overlay. Assess reasonableness vs empirical and prior; is any override justified and documented; what would you challenge before sign-off. End with a verdict: SUPPORT / SUPPORT WITH CONDITIONS / CHALLENGE. You advise; the actuary decides."},
}
CLASSIFIER = ("You route a reserving question to ONE specialist. Reply ONLY with a single-line JSON object: "
  '{"specialist_key":"<key>","confidence":<0-1>,"reason":"<short>"}. Keys: '
  + ", ".join(SPECIALISTS) + ". If unsure pick senior_reserving.")

class ReservingAgent(ChatAgent):
    def _w(self):
        return WorkspaceClient()
    def _fm(self, system, prompt):
        r = self._w().serving_endpoints.query(name=FM, messages=[
            ChatMessage(role=ChatMessageRole.SYSTEM, content=system),
            ChatMessage(role=ChatMessageRole.USER, content=prompt)], max_tokens=750)
        c = r.choices[0]
        content = c.message.content
        # sonnet-5 may return content as a list of blocks; flatten to text
        if isinstance(content, list):
            parts = []
            for b in content:
                if isinstance(b, dict):
                    parts.append(b.get("text") or b.get("summary") or "")
                else:
                    parts.append(str(getattr(b, "text", "") or ""))
            content = "".join(parts)
        content = content or ""
        usage = getattr(r, "usage", None)
        it = getattr(usage, "prompt_tokens", None) if usage else None
        ot = getattr(usage, "completion_tokens", None) if usage else None
        return str(content), it, ot
    def _sql(self, q):
        try:
            resp = self._w().statement_execution.execute_statement(statement=q, warehouse_id=WID, wait_timeout="30s")
            return resp.result.data_array if resp.result and resp.result.data_array else []
        except Exception:
            return []
    def _facts(self):
        ave = self._sql(f"SELECT line_of_business_code, accident_year, standardised_residual FROM {FQ}.actual_vs_expected WHERE within_tolerance=false ORDER BY abs(standardised_residual) DESC LIMIT 8")
        ibnr = self._sql(f"SELECT line_of_business_code, round(sum(ibnr),0) FROM {FQ}.reserve_estimate WHERE reserving_method_code='CHAIN_LADDER' GROUP BY line_of_business_code")
        roll = self._sql(f"SELECT driver, amount FROM {FQ}.reserve_rollforward WHERE line_of_business_code='COMMERCIAL_PROPERTY' ORDER BY display_order")
        return {"ave":ave, "ibnr":ibnr, "roll":roll}
    def _classify(self, q):
        try:
            txt,_,_ = self._fm(CLASSIFIER, q)
            obj = json.loads(re.search(r"\\{[^{}]+\\}", txt).group(0))
            k = obj.get("specialist_key","senior_reserving")
            if k not in SPECIALISTS: k="senior_reserving"
            return k, float(obj.get("confidence",0.6)), str(obj.get("reason",""))[:200]
        except Exception:
            ql=q.lower()
            for k,s in SPECIALISTS.items():
                if any(t in ql for t in s["triggers"].split()): return k,0.5,"keyword match"
            return "senior_reserving",0.4,"default"
    def predict(self, messages, context=None, custom_inputs=None) -> ChatAgentResponse:
        q = messages[-1].content if messages else ""
        ci = custom_inputs or {}
        key = ci.get("specialist")
        if key in SPECIALISTS:
            conf, reason = 1.0, "explicitly selected"
        else:
            key, conf, reason = self._classify(q)
        f = self._facts()
        s = SPECIALISTS[key]
        prompt = f"Question: {q}\\n\\nOut-of-tolerance cohorts: {json.dumps(f['ave'])}\\nIBNR by line: {json.dumps(f['ibnr'])}\\nRoll-forward (CP): {json.dumps(f['roll'])}"
        text, it, ot = self._fm(s["system"], prompt)
        return ChatAgentResponse(
            messages=[ChatAgentMessage(role="assistant", content=text, id="1")],
            custom_outputs={"specialist_key":key, "specialist_name":s["name"], "confidence":conf,
                            "reason":reason, "model":FM, "input_tokens":it, "output_tokens":ot})
'''
import os as _os
SRC_DIR = _os.getcwd()
SRC_PATH = _os.path.join(SRC_DIR, "reserving_agent.py")
with open(SRC_PATH, "w") as fh:
    fh.write(agent_src)
print("agent source written to", SRC_PATH)

# COMMAND ----------
# MAGIC %md ## Register to Unity Catalog

# COMMAND ----------
import mlflow
from mlflow.types.agent import ChatAgentMessage
import sys
sys.path.insert(0, SRC_DIR)
from reserving_agent import ReservingAgent  # noqa

mlflow.set_registry_uri("databricks-uc")
agent = ReservingAgent()
with mlflow.start_run(run_name="reserving_agent"):
    info = mlflow.pyfunc.log_model(
        name="reserving_agent",
        python_model=ReservingAgent(),
        code_paths=[SRC_PATH],
        pip_requirements=["mlflow>=2.16", "databricks-sdk"],
        registered_model_name=MODEL,
        resources=[],
    )
from mlflow.tracking import MlflowClient
c = MlflowClient()
ver = max(c.search_model_versions(f"name='{MODEL}'"), key=lambda v: int(v.version)).version
c.set_registered_model_alias(MODEL, "Production", ver)
print(f"registered {MODEL} v{ver} @Production")

# COMMAND ----------
# MAGIC %md ## Deploy to a serving endpoint (Agent Framework)

# COMMAND ----------
ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
env = {"CATALOG_NAME": CAT, "SCHEMA_NAME": SCH, "FM_ENDPOINT": FM,
       "AGENT_WAREHOUSE_ID": WID,
       "DATABRICKS_HOST": ctx.apiUrl().get(), "DATABRICKS_TOKEN": ctx.apiToken().get()}
try:
    from databricks import agents
    dep = agents.deploy(MODEL, ver, scale_to_zero=True, environment_vars=env,
                        tags={"project": "reserving-workbench"})
    print("deployed via agents.deploy:", getattr(dep, "endpoint_name", "(name pending)"))
except Exception as e:
    print("agents.deploy path unavailable, using serving_endpoints.create:", e)
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput
    w = WorkspaceClient()
    ep = "reserving-workbench-agent"
    se = ServedEntityInput(name="reserving", entity_name=MODEL, entity_version=ver,
                           workload_size="Small", scale_to_zero_enabled=True, environment_vars=env)
    try:
        w.serving_endpoints.get(ep); w.serving_endpoints.update_config(name=ep, served_entities=[se])
    except Exception:
        w.serving_endpoints.create(name=ep, config=EndpointCoreConfigInput(name=ep, served_entities=[se]))
    print("endpoint:", ep)
