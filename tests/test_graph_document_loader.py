"""Small, offline tests for the private graph snapshot loading boundary."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOADER = ROOT / "bridges" / "graph-document-loader.mjs"
PKG = ROOT.parent / "deposium_fullstack" / "deposium_MCPs" / "package.json"

SCHEMA = {
    "embeddings_docs": [
        ("doc_id", "VARCHAR"), ("tenant_id", "VARCHAR"), ("space_id", "VARCHAR"),
        ("title", "VARCHAR"), ("content", "VARCHAR"), ("embedding", "FLOAT[]"),
        ("metadata", "JSON"), ("created_at", "TIMESTAMP"), ("file_name", "VARCHAR"),
        ("embedding_model", "VARCHAR"),
    ],
    "enriched_docs": [
        ("doc_id", "VARCHAR"), ("tenant_id", "VARCHAR"), ("space_id", "VARCHAR"),
        ("file_id", "INTEGER"), ("title", "VARCHAR"), ("content", "VARCHAR"),
        ("embedding", "FLOAT[]"), ("entities", "JSON"), ("relationships", "JSON"),
        ("temporal_events", "JSON"), ("temporal_summary", "JSON"),
        ("semantic_summary", "JSON"), ("metadata", "JSON"), ("created_at", "TIMESTAMP"),
        ("file_name", "VARCHAR"),
    ],
    "uploaded_files_graph_entities": [
        ("entity_id", "VARCHAR"), ("tenant_id", "VARCHAR"), ("space_id", "VARCHAR"),
        ("file_id", "INTEGER"), ("entity_type", "VARCHAR"), ("entity_name", "VARCHAR"),
        ("properties", "JSON"), ("created_at", "TIMESTAMP"), ("cluster_id", "INTEGER"),
        ("pagerank_score", "DOUBLE"), ("embedding", "FLOAT[]"),
    ],
    "uploaded_files_graph_relations": [
        ("relation_id", "VARCHAR"), ("tenant_id", "VARCHAR"), ("space_id", "VARCHAR"),
        ("file_id", "INTEGER"), ("source_id", "VARCHAR"), ("target_id", "VARCHAR"),
        ("relation_type", "VARCHAR"), ("causality_class", "VARCHAR"),
        ("semantic_primitive", "VARCHAR"), ("confidence", "DOUBLE"),
        ("properties", "JSON"), ("created_at", "TIMESTAMP"),
    ],
}

ENTITY = {
    "entity_id": "duplicate", "tenant_id": "tenant", "space_id": "folder",
    "file_id": 7, "entity_type": "person", "entity_name": "Example",
    "properties": {"doc_id": "doc", "source_pages": [1, 2], "nested": {"x": "quoted ' text"}},
    "created_at": "2026-01-02 03:04:05.123456", "cluster_id": None,
    "pagerank_score": 0.5,
}
RELATION = {
    "relation_id": "relation", "tenant_id": "tenant", "space_id": "folder",
    "file_id": 7, "source_id": "duplicate", "target_id": "duplicate",
    "relation_type": "related", "causality_class": None, "semantic_primitive": None,
    "confidence": 0.75, "properties": {"doc_id": "doc", "source_pages": [1]},
    "created_at": "2026-01-02 03:04:05",
}
PAGE = {
    "doc_id": "doc_page_1", "tenant_id": "tenant", "space_id": "folder",
    "title": "Sample", "content": "Private fixture text", "metadata": {"page_number": 1},
    "created_at": None, "file_name": None, "embedding_model": "test-model",
}

NODE_SCRIPT = r"""
import { pathToFileURL } from 'node:url'
import { createRequire } from 'node:module'
const { loadDocumentSnapshot } = await import(pathToFileURL(process.argv[1]).href)
const descriptor = JSON.parse(process.argv[2])
const real = process.argv[3] === 'real'
let connection, instance, tables = {}, ddls = []
if (real) {
  const require = createRequire(process.argv[4])
  const { DuckDBInstance } = require('@duckdb/node-api')
  instance = await DuckDBInstance.create(':memory:', { enable_external_access: 'false',
    autoinstall_known_extensions: 'false', autoload_known_extensions: 'false',
    threads: '2', memory_limit: '512MB' })
  connection = await instance.connect()
} else {
  connection = {
    async run(sql) { ddls.push(sql) },
    async createAppender(table) {
      const rows = tables[table] = []
      let row = []
      return {
        appendNull() { row.push(null) }, appendInteger(v) { row.push(v) },
        appendDouble(v) { row.push(v) }, appendVarchar(v) { row.push(v) },
        endRow() { rows.push(row); row = [] }, closeSync() {},
      }
    },
    async runAndReadAll(sql) {
      const table = sql.match(/FROM "([^"]+)"/)[1]
      return { getRowObjectsJS: () => [{ n: tables[table].length }] }
    },
  }
}
try {
  const meta = await loadDocumentSnapshot(connection, descriptor)
  if (real) {
    const rows = (await connection.runAndReadAll(`SELECT properties::VARCHAR AS properties,
      cluster_id, created_at::VARCHAR AS created_at, embedding IS NULL AS no_embedding
      FROM uploaded_files_graph_entities`)).getRowObjectsJS()
    const relationColumns = (await connection.runAndReadAll(`DESCRIBE uploaded_files_graph_relations`)).getRowObjectsJS()
    console.log(JSON.stringify({ meta, entity_count: rows.length,
      all_null_embedding: rows.every(row => row.no_embedding === true),
      all_null_cluster: rows.every(row => row.cluster_id === null),
      all_properties: rows.every(row => JSON.parse(row.properties).nested.x === "quoted ' text"),
      timestamp_retained: rows.every(row => row.created_at.startsWith('2026-01-02 03:04:05')),
      relations_have_properties: relationColumns.some(row => row.column_name === 'properties') }))
  } else {
    console.log(JSON.stringify({ meta, ddl_count: ddls.length, entity_rows:
      tables.uploaded_files_graph_entities, relation_rows: tables.uploaded_files_graph_relations }))
  }
} catch (error) {
  console.log(JSON.stringify({ error_code: error.code ?? null, ddl_count: ddls.length }))
} finally {
  if (connection?.disconnectSync) connection.disconnectSync()
  if (instance?.closeSync) instance.closeSync()
}
"""


@unittest.skipUnless(shutil.which("node"), "Node is optional")
class GraphDocumentLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = [
            {"kind": "entities", "row": deepcopy(ENTITY)},
            {"kind": "entities", "row": deepcopy(ENTITY)},
            {"kind": "relations", "row_json": json.dumps(RELATION)},
            {"kind": "pages", "row": deepcopy(PAGE)},
        ]
        self.schema_rows = [
            {"table_name": table, "column_name": column, "data_type": kind}
            for table, columns in SCHEMA.items() for column, kind in columns
        ]

    def invoke(self, *, expected_code: str | None = None, real: bool = False,
               bad_snapshot_hash: bool = False) -> dict:
        schema = [{"success": True, "rowCount": len(self.schema_rows), "data": self.schema_rows}]
        schema_path = self.root / "schema.json"
        snapshot_path = self.root / "snapshot.jsonl"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        snapshot_path.write_text("\n".join(json.dumps(row) for row in self.rows) + "\n", encoding="utf-8")
        descriptor = {
            "path": str(snapshot_path), "sha256": sha256(snapshot_path.read_bytes()).hexdigest(),
            "schema_path": str(schema_path), "schema_sha256": sha256(schema_path.read_bytes()).hexdigest(),
            "owner_tenant_id": "tenant", "folder_ids": ["folder"],
            "expected_counts": {"entities": 2, "pages": 1, "relations": 1, "enriched": 0},
        }
        if bad_snapshot_hash:
            descriptor["sha256"] = "0" * 64
        command = ["node", "--input-type=module", "-e", NODE_SCRIPT, str(LOADER),
                   json.dumps(descriptor), "real" if real else "fake", str(PKG)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                check=True, timeout=10)
        response = json.loads(result.stdout)
        if expected_code:
            self.assertEqual(response["error_code"], expected_code)
        else:
            self.assertNotIn("error_code", response)
        return response

    def test_duplicates_json_nulls_and_source_columns(self) -> None:
        response = self.invoke()
        self.assertEqual(response["meta"]["loaded_counts"],
                         {"entities": 2, "pages": 1, "relations": 1, "enriched": 0})
        self.assertEqual(response["meta"]["embedding"], "omitted_in_capture")
        self.assertEqual(response["ddl_count"], 4)
        entities = response["entity_rows"]
        self.assertEqual(len(entities), 2)
        self.assertEqual(entities[0], entities[1])
        self.assertEqual(json.loads(entities[0][6])["nested"]["x"], "quoted ' text")
        self.assertIn(None, entities[0])
        self.assertEqual(len(response["relation_rows"][0]), len(SCHEMA["uploaded_files_graph_relations"]))

    def test_hash_scope_schema_and_count_fail_closed(self) -> None:
        self.assertEqual(self.invoke(expected_code="GRAPH_DOCUMENT_HASH", bad_snapshot_hash=True)["ddl_count"], 0)
        self.rows[0]["row"]["space_id"] = "other-folder"
        self.invoke(expected_code="GRAPH_DOCUMENT_SCOPE")
        self.rows[0]["row"]["space_id"] = "folder"
        self.rows[0]["row"]["invented_column"] = "unexpected"
        self.invoke(expected_code="GRAPH_DOCUMENT_ROW")
        del self.rows[0]["row"]["invented_column"]
        self.schema_rows[0]["data_type"] = "TEXT DEFAULT 'unsafe'"
        self.assertEqual(self.invoke(expected_code="GRAPH_DOCUMENT_SCHEMA")["ddl_count"], 0)
        self.schema_rows[0]["data_type"] = "VARCHAR"
        self.rows.pop()
        self.invoke(expected_code="GRAPH_DOCUMENT_COUNTS")

    @unittest.skipUnless(PKG.is_file() and (PKG.parent / "node_modules/@duckdb/node-api").exists(),
                         "Local DuckDB Node dependency is optional")
    def test_small_fixture_in_real_sealed_duckdb(self) -> None:
        response = self.invoke(real=True)
        self.assertEqual(response["entity_count"], 2)
        self.assertTrue(response["all_null_embedding"])
        self.assertTrue(response["all_null_cluster"])
        self.assertTrue(response["all_properties"])
        self.assertTrue(response["timestamp_retained"])
        self.assertTrue(response["relations_have_properties"])


if __name__ == "__main__":
    unittest.main()
