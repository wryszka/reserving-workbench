#!/usr/bin/env python3
"""reserving-workbench generator.

Compiles the model-as-code specs in model/ into Databricks DDL under build/,
plus a platform-neutral ontology JSON for gen2 hand-off. Vendored and
simplified from bricksurance-data-core/tools/generate.py, and kept spec-format
compatible so the specs import cleanly into the shared layer.

Differences from the core generator, all deliberate for a gen1 standalone:
  * Databricks only (one binding).
  * ONE schema for the whole workbench (binding schema_pattern is a constant),
    emitted with a rich project-level comment (asset labelling).
  * Table identifiers are backticked, so numbered names like `1_raw_claim` work.
  * Every table/view/function carries a `[reserving-workbench]` comment prefix
    and bxc_* tags (asset labelling; enforced by the smoke test).

Usage:
    uv run --native-tls --with pyyaml tools/generate.py
"""

import json
import re
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
LABEL = "[reserving-workbench]"

TYPE_MAP = {
    "string": "STRING", "integer": "BIGINT", "boolean": "BOOLEAN",
    "date": "DATE", "timestamp": "TIMESTAMP", "int": "INT", "double": "DOUBLE",
}


def esc(text):
    return " ".join(str(text).split()).replace("'", "''")


def sql_type(logical):
    logical = str(logical).strip().lower()
    if logical.startswith("decimal"):
        return logical.upper()
    return TYPE_MAP[logical]


def attr_type(attr):
    return attr.get("type", "string")


def load_model():
    manifest = yaml.safe_load((ROOT / "model" / "model.yaml").read_text())
    buckets = {"entity": [], "code_set": [], "view": [],
               "metric_view": [], "function": []}
    for path in sorted((ROOT / "model").rglob("*.yaml")):
        if path.name == "model.yaml":
            continue
        spec = yaml.safe_load(path.read_text())
        kind = spec.get("kind")
        if kind not in buckets:
            raise ValueError(f"{path}: unknown kind {kind!r}")
        # default domain for code sets is reference
        spec.setdefault("domain", "reference" if kind == "code_set" else None)
        buckets[kind].append(spec)
    return (manifest, buckets["entity"], buckets["code_set"],
            buckets["view"], buckets["metric_view"], buckets["function"])


def code_set_as_entity(cs):
    key = f"{cs['name']}_code"
    return {
        "kind": "entity", "name": cs["name"], "domain": "reference",
        "title": cs.get("title", cs["name"]), "description": cs["description"],
        "grain": f"One row per {cs.get('title', cs['name']).lower()} code.",
        "standards": cs.get("standards", {}),
        "attributes": [
            {"name": key, "type": "string", "required": True,
             "description": f"Code value; referenced by {key} columns across the model."},
            {"name": "label", "type": "string", "required": True,
             "description": "Short human-readable name for the code."},
            {"name": "description", "type": "string", "required": True,
             "description": "Business definition of the code."},
        ],
        "keys": {"primary": [key]},
        "tags": {"bxc_layer": "reference"},
        "_is_code_set": True,
    }


DICTIONARY_ENTITY = {
    "kind": "entity", "name": "data_dictionary", "domain": "reference",
    "title": "Data Dictionary",
    "description": ("Machine-readable dictionary of every entity and attribute, "
                    "generated from the specs, so semantics travel with the data."),
    "grain": "One row per attribute per entity per model version.",
    "standards": {}, "tags": {"bxc_layer": "reference"},
    "attributes": [
        {"name": "entity_name", "type": "string", "required": True, "description": "Entity the attribute belongs to."},
        {"name": "attribute_name", "type": "string", "required": True, "description": "Attribute name."},
        {"name": "data_type", "type": "string", "required": True, "description": "Logical data type."},
        {"name": "is_required", "type": "boolean", "required": True, "description": "Whether mandatory."},
        {"name": "definition", "type": "string", "required": True, "description": "Business definition."},
        {"name": "data_classification", "type": "string", "required": False, "description": "public/internal/confidential/pii."},
        {"name": "entity_owner", "type": "string", "required": False, "description": "Accountable business owner (org role)."},
        {"name": "entity_maturity", "type": "string", "required": False, "description": "draft or certified."},
        {"name": "model_version", "type": "string", "required": True, "description": "Model version this row came from."},
    ],
    "keys": {"primary": ["entity_name", "attribute_name", "model_version"]},
    "_is_dictionary": True,
}


def schema_name(binding):
    return binding["schema_pattern"].format(domain="reserving")


def bt(ident):
    """Backtick a table identifier (numbered names like 1_raw_claim need it)."""
    return f"`{ident}`"


def fqn(binding, domain, table):
    return f"{binding['catalog']}.{schema_name(binding)}.{bt(table)}"


def labelled(text):
    return f"{LABEL} {text}"


def entity_tags(binding, manifest, entity):
    prefix = binding.get("tag_prefix", "")
    tags = {
        f"{prefix}project": "reserving-workbench",
        f"{prefix}model_version": manifest["version"],
        f"{prefix}domain": entity["domain"],
        f"{prefix}gen": "gen1",
    }
    tags.update({f"{prefix}{k}": v for k, v in entity.get("tags", {}).items()})
    if entity.get("standards", {}).get("acord"):
        tags[f"{prefix}acord_ref"] = entity["standards"]["acord"]
    return tags


def entity_ddl(binding, manifest, entity):
    table = fqn(binding, entity["domain"], entity["name"])
    cols = []
    for a in entity["attributes"]:
        col = f"  {a['name']} {sql_type(attr_type(a))}"
        if a.get("required"):
            col += " NOT NULL"
        col += f" COMMENT '{esc(a['description'])}'"
        cols.append(col)
    comment = labelled(f"{entity['description']} Grain: {entity['grain']}")
    stmts = [f"CREATE TABLE IF NOT EXISTS {table} (\n" + ",\n".join(cols)
             + f"\n)\nCOMMENT '{esc(comment)}';"]
    pk = entity["keys"]["primary"]
    stmts.append(f"ALTER TABLE {table} ADD CONSTRAINT pk_{entity['name']} "
                 f"PRIMARY KEY ({', '.join(pk)});")
    tags = entity_tags(binding, manifest, entity)
    tag_sql = ", ".join(f"'{k}' = '{esc(v)}'" for k, v in tags.items())
    stmts.append(f"ALTER TABLE {table} SET TAGS ({tag_sql});")
    prefix = binding.get("tag_prefix", "")
    for a in entity["attributes"]:
        if a.get("classification"):
            stmts.append(f"ALTER TABLE {table} ALTER COLUMN {a['name']} "
                         f"SET TAGS ('{prefix}classification' = '{a['classification']}');")
    return "\n\n".join(stmts)


def fk_targets(entity, entity_index):
    if entity.get("_is_code_set") or entity.get("_is_dictionary"):
        return
    for a in entity["attributes"]:
        if a.get("code_set"):
            yield a["name"], "reference", a["code_set"], f"{a['code_set']}_code"
        elif a.get("references"):
            ref = entity_index[a["references"]]
            pk = ref["keys"]["primary"]
            if len(pk) != 1:
                raise ValueError(f"{entity['name']}.{a['name']} → composite PK")
            yield a["name"], ref["domain"], ref["name"], pk[0]


def entity_fk_ddl(binding, entity, entity_index):
    table = fqn(binding, entity["domain"], entity["name"])
    stmts = []
    for attr, ref_domain, ref_table, ref_col in fk_targets(entity, entity_index):
        stmts.append(f"ALTER TABLE {table} ADD CONSTRAINT fk_{entity['name']}_{attr} "
                     f"FOREIGN KEY ({attr}) "
                     f"REFERENCES {fqn(binding, ref_domain, ref_table)} ({ref_col});")
    return stmts


def resolve_refs(binding, sql):
    return re.sub(r"\{(\w+)\.([\w]+)\}",
                  lambda m: fqn(binding, m.group(1), m.group(2)), sql)


def view_ddl(binding, view):
    table = fqn(binding, view["domain"], view["name"])
    comment = labelled(f"{view['description']} Grain: {view['grain']}"
                       if view.get("grain") else view["description"])
    return (f"CREATE OR REPLACE VIEW {table}\n"
            f"COMMENT '{esc(comment)}'\n"
            f"AS\n{resolve_refs(binding, view['sql']).strip()};")


def metric_view_ddl(binding, mv):
    body = [f"version: {mv.get('spec_version', '0.1')}", ""]
    src_domain, src_table = mv["source"].split(".")
    body.append(f"source: {fqn(binding, src_domain, src_table)}")
    if mv.get("joins"):
        body += ["", "joins:"]
        for j in mv["joins"]:
            jd, jt = j["source"].split(".")
            body += [f"  - name: {j['name']}", f"    source: {fqn(binding, jd, jt)}",
                     f"    on: {j['condition']}"]
    body += ["", "dimensions:"]
    for d in mv["dimensions"]:
        body += [f"  - name: {d['name']}", f"    expr: {d['expr']}"]
    body += ["", "measures:"]
    for m in mv["measures"]:
        body += [f"  - name: {m['name']}", f"    expr: {m['expr']}"]
    table = fqn(binding, mv["domain"], mv["name"])
    return (f"CREATE OR REPLACE VIEW {table}\n"
            f"COMMENT '{esc(labelled(mv['description']))}'\n"
            f"WITH METRICS\nLANGUAGE YAML\nAS $$\n" + "\n".join(body) + "\n$$;")


def function_ddl(binding, fn):
    name = fqn(binding, fn["domain"], fn["name"])
    params = ", ".join(
        f"{p['name']} {sql_type(p['type'])} COMMENT '{esc(p['description'])}'"
        for p in fn["inputs"])
    comment = labelled(f"{fn['description']} Returns: {fn['returns']['description']}")
    return (f"CREATE OR REPLACE FUNCTION {name}({params})\n"
            f"RETURNS {sql_type(fn['returns']['type'])}\n"
            f"COMMENT '{esc(comment)}'\n"
            f"RETURN {resolve_refs(binding, fn['sql']).strip()};")


def code_set_seed(binding, cs):
    table = fqn(binding, "reference", cs["name"])
    rows = ",\n".join(
        f"  ('{esc(c['code'])}', '{esc(c['label'])}', '{esc(c['description'])}')"
        for c in cs["codes"])
    return f"INSERT OVERWRITE {table} VALUES\n{rows};"


def dictionary_rows(manifest, all_entities):
    rows = []
    for e in all_entities:
        owner = e.get("owner", "")
        maturity = (e.get("tags", {}) or {}).get("maturity", "")
        for a in e["attributes"]:
            rows.append((e["name"], a["name"], attr_type(a), bool(a.get("required")),
                         a["description"], a.get("classification", ""),
                         owner, maturity, manifest["version"]))
    return rows


def dictionary_seed(binding, manifest, all_entities, extra_rows=()):
    table = fqn(binding, "reference", "data_dictionary")
    values = []
    for r in list(dictionary_rows(manifest, all_entities)) + list(extra_rows):
        vals = ", ".join(("TRUE" if v else "FALSE") if isinstance(v, bool)
                         else f"'{esc(v)}'" for v in r)
        values.append(f"  ({vals})")
    return f"INSERT OVERWRITE {table} VALUES\n" + ",\n".join(values) + ";"


def semantic_dictionary_rows(manifest, metric_views):
    rows = []
    for mv in metric_views:
        owner, maturity = mv.get("owner", ""), mv.get("certification", "")
        for d in mv["dimensions"]:
            rows.append((mv["name"], d["name"], "dimension", False,
                         d["description"], "", owner, maturity, manifest["version"]))
        for m in mv["measures"]:
            rows.append((mv["name"], m["name"], "measure", False,
                         m["description"], "", owner, maturity, manifest["version"]))
    return rows


def generate(binding, manifest, entities, code_sets, views, metric_views, functions):
    out = BUILD / "databricks"
    out.mkdir(parents=True, exist_ok=True)
    header = (f"-- Generated by tools/generate.py from reserving-workbench "
              f"v{manifest['version']}.\n-- Do not edit: change the spec and regenerate.\n\n")

    # 00 - ONE schema, rich project-level comment (asset labelling)
    schema_comment = (
        f"{LABEL} Reserving Workbench — governed end-to-end actuarial reserving "
        f"for Bricksurance SE (fictional; synthetic data). Model v{manifest['version']}. "
        f"Methodology library, LDF selection (with external-tool/ResQ seam), model "
        f"validation, expert-judgement repository, reserve→QRT lineage. Repo "
        f"wryszka/reserving-workbench. Owner: laurence.ryszka. gen1; convertible to "
        f"the bricksurance-data-core shared layer (gen2)."
    )
    schema = f"{binding['catalog']}.{schema_name(binding)}"
    stmts = [f"CREATE SCHEMA IF NOT EXISTS {schema}\nCOMMENT '{esc(schema_comment)}';"]
    prefix = binding.get("tag_prefix", "")
    stmts.append(f"ALTER SCHEMA {schema} SET TAGS "
                 f"('{prefix}project' = 'reserving-workbench', '{prefix}gen' = 'gen1');")
    (out / "00_schema.sql").write_text(header + "\n\n".join(stmts) + "\n")

    # 10 - reference: code sets + dictionary + seeds
    ref_entities = [code_set_as_entity(cs) for cs in code_sets] + [DICTIONARY_ENTITY]
    all_entities = ref_entities + entities
    parts = [entity_ddl(binding, manifest, e) for e in ref_entities]
    parts += [code_set_seed(binding, cs) for cs in code_sets]
    parts.append(dictionary_seed(binding, manifest, all_entities,
                                 semantic_dictionary_rows(manifest, metric_views)))
    (out / "10_reference.sql").write_text(header + "\n\n".join(parts) + "\n")

    # 20+ - business entities
    for e in entities:
        (out / f"20_{e['name']}.sql").write_text(header + entity_ddl(binding, manifest, e) + "\n")
    # 30 - views, 35 - metric views, 40 - functions
    for v in views:
        (out / f"30_{v['name']}.sql").write_text(header + view_ddl(binding, v) + "\n")
    for mv in metric_views:
        (out / f"35_{mv['name']}.sql").write_text(header + metric_view_ddl(binding, mv) + "\n")
    for fn in functions:
        (out / f"40_{fn['name']}.sql").write_text(header + function_ddl(binding, fn) + "\n")

    # 90 - foreign keys, after all tables exist
    entity_index = {e["name"]: e for e in all_entities}
    fks = []
    for e in all_entities:
        fks.extend(entity_fk_ddl(binding, e, entity_index))
    (out / "90_relationships.sql").write_text(header + "\n\n".join(fks) + "\n")


def generate_ontology(manifest, entities, code_sets, views, metric_views, functions):
    """Platform-neutral ontology JSON — the gen2 hand-off artifact."""
    entity_index = {e["name"]: e for e in entities}
    relationships = []
    for e in entities:
        for attr, ref_domain, ref_table, ref_col in fk_targets(e, entity_index):
            relationships.append({
                "from_entity": e["name"], "attribute": attr, "to": ref_table,
                "to_kind": "code_set" if ref_domain == "reference" and attr.endswith("_code") else "entity",
                "to_attribute": ref_col})
    doc = {
        "ontology_format": "bricksurance-data-core/ontology-v1",
        "name": manifest["model"], "title": manifest["title"],
        "version": manifest["version"],
        "description": " ".join(str(manifest["description"]).split()),
        "domains": manifest["domains"], "code_sets": code_sets,
        "entities": entities, "views": views, "metric_views": metric_views,
        "functions": functions, "relationships": relationships,
    }
    out = BUILD / "ontology"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{manifest['model']}.ontology.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def main():
    manifest, entities, code_sets, views, metric_views, functions = load_model()
    if BUILD.exists():
        shutil.rmtree(BUILD)
    binding = yaml.safe_load((ROOT / "bindings" / "databricks.yaml").read_text())
    generate(binding, manifest, entities, code_sets, views, metric_views, functions)
    generate_ontology(manifest, entities, code_sets, views, metric_views, functions)
    n = sum(1 for _ in BUILD.rglob("*") if _.is_file())
    print(f"Generated {n} files from {len(entities)} entities, {len(code_sets)} code sets, "
          f"{len(views)} views, {len(metric_views)} metric views, {len(functions)} functions "
          f"(model v{manifest['version']}).")


if __name__ == "__main__":
    main()
