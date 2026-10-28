/** Bounded, lossless (apart from absent embeddings) private graph snapshot loader. */
import { createHash } from 'node:crypto'
import { closeSync, fstatSync, lstatSync, openSync, readSync } from 'node:fs'
import { isAbsolute } from 'node:path'

const MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024
const MAX_SCHEMA_BYTES = 64 * 1024
const MAX_ROWS = 50_000
const MAX_LINE_BYTES = 1024 * 1024
const SHA256 = /^[a-f0-9]{64}$/
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const exact = (value, keys) => object(value) && Object.keys(value).sort().join('|') === [...keys].sort().join('|')

// These are the complete observed source columns. The schema payload may reorder
// them, but may neither add a column nor change a type without a reviewed bridge.
const TABLES = Object.freeze({
  embeddings_docs: {
    kind: 'pages', columns: {
      doc_id: 'VARCHAR', tenant_id: 'VARCHAR', space_id: 'VARCHAR', title: 'VARCHAR',
      content: 'VARCHAR', embedding: 'FLOAT[]', metadata: 'JSON', created_at: 'TIMESTAMP',
      file_name: 'VARCHAR', embedding_model: 'VARCHAR',
    },
  },
  enriched_docs: {
    kind: 'enriched', columns: {
      doc_id: 'VARCHAR', tenant_id: 'VARCHAR', space_id: 'VARCHAR', file_id: 'INTEGER',
      title: 'VARCHAR', content: 'VARCHAR', embedding: 'FLOAT[]', entities: 'JSON',
      relationships: 'JSON', temporal_events: 'JSON', temporal_summary: 'JSON',
      semantic_summary: 'JSON', metadata: 'JSON', created_at: 'TIMESTAMP', file_name: 'VARCHAR',
    },
  },
  uploaded_files_graph_entities: {
    kind: 'entities', columns: {
      entity_id: 'VARCHAR', tenant_id: 'VARCHAR', space_id: 'VARCHAR', file_id: 'INTEGER',
      entity_type: 'VARCHAR', entity_name: 'VARCHAR', properties: 'JSON',
      created_at: 'TIMESTAMP', cluster_id: 'INTEGER', pagerank_score: 'DOUBLE',
      embedding: 'FLOAT[]',
    },
  },
  uploaded_files_graph_relations: {
    kind: 'relations', columns: {
      relation_id: 'VARCHAR', tenant_id: 'VARCHAR', space_id: 'VARCHAR', file_id: 'INTEGER',
      source_id: 'VARCHAR', target_id: 'VARCHAR', relation_type: 'VARCHAR',
      causality_class: 'VARCHAR', semantic_primitive: 'VARCHAR', confidence: 'DOUBLE',
      properties: 'JSON', created_at: 'TIMESTAMP',
    },
  },
})
const BY_KIND = Object.fromEntries(Object.entries(TABLES).map(([name, value]) => [value.kind, name]))
const COUNT_KEYS = ['entities', 'pages', 'relations', 'enriched']

export class GraphDocumentError extends Error {
  constructor(code) { super(code); this.name = 'GraphDocumentError'; this.code = code }
}
const fail = code => { throw new GraphDocumentError(`GRAPH_DOCUMENT_${code}`) }

function boundedFile(path, expectedHash, maxBytes) {
  if (typeof path !== 'string' || !isAbsolute(path) || !SHA256.test(expectedHash)) fail('INPUT')
  let fd
  try {
    if (!lstatSync(path).isFile()) fail('INPUT')
    fd = openSync(path, 'r')
    const size = fstatSync(fd).size
    if (!Number.isSafeInteger(size) || size < 1 || size > maxBytes) fail('BUDGET')
    const buffer = Buffer.allocUnsafe(size)
    let offset = 0
    while (offset < size) {
      const n = readSync(fd, buffer, offset, size - offset, null)
      if (n === 0) fail('IO')
      offset += n
    }
    const extra = Buffer.allocUnsafe(1)
    if (readSync(fd, extra, 0, 1, null) !== 0) fail('BUDGET')
    if (createHash('sha256').update(buffer).digest('hex') !== expectedHash) fail('HASH')
    return buffer
  } catch (error) {
    if (error instanceof GraphDocumentError) throw error
    fail('IO')
  } finally {
    if (fd !== undefined) closeSync(fd)
  }
}

function descriptorValid(value) {
  if (!exact(value, ['path', 'sha256', 'schema_path', 'schema_sha256',
    'owner_tenant_id', 'folder_ids', 'expected_counts'])
      || typeof value.owner_tenant_id !== 'string' || !value.owner_tenant_id.trim()
      || !Array.isArray(value.folder_ids) || value.folder_ids.length === 0
      || value.folder_ids.length > 256
      || value.folder_ids.some(id => typeof id !== 'string' || !id.trim())
      || new Set(value.folder_ids).size !== value.folder_ids.length
      || !exact(value.expected_counts, COUNT_KEYS)
      || COUNT_KEYS.some(key => !Number.isSafeInteger(value.expected_counts[key])
        || value.expected_counts[key] < 0)
      || COUNT_KEYS.reduce((n, key) => n + value.expected_counts[key], 0) > MAX_ROWS) fail('INPUT')
}

function parseSchema(buffer) {
  let payload
  try { payload = JSON.parse(buffer.toString('utf8')) } catch { fail('SCHEMA') }
  if (!Array.isArray(payload) || payload.length !== 1 || !object(payload[0])
      || !Array.isArray(payload[0].data) || payload[0].data.length !== 48
      || payload[0].rowCount !== payload[0].data.length) fail('SCHEMA')
  const columns = Object.fromEntries(Object.keys(TABLES).map(name => [name, []]))
  for (const row of payload[0].data) {
    if (!exact(row, ['table_name', 'column_name', 'data_type'])) fail('SCHEMA')
    const spec = TABLES[row.table_name]
    if (!spec || spec.columns[row.column_name] !== row.data_type
        || columns[row.table_name].includes(row.column_name)) fail('SCHEMA')
    columns[row.table_name].push(row.column_name)
  }
  for (const [name, spec] of Object.entries(TABLES)) {
    if (columns[name].length !== Object.keys(spec.columns).length) fail('SCHEMA')
  }
  return columns
}

function finite(value) {
  const pending = [{ value, depth: 0 }]
  let examined = 0
  while (pending.length) {
    const current = pending.pop()
    if (++examined > MAX_LINE_BYTES || current.depth > 64) fail('BUDGET')
    if (typeof current.value === 'number' && !Number.isFinite(current.value)) fail('ROW')
    const children = Array.isArray(current.value) ? current.value
      : object(current.value) ? Object.values(current.value) : []
    for (const child of children) pending.push({ value: child, depth: current.depth + 1 })
  }
}

function validatedRow(item, columns, descriptor, allowedFolders) {
  if (!object(item) || !Object.hasOwn(BY_KIND, item.kind)
      || !exact(item, ['kind', 'row']) && !exact(item, ['kind', 'row_json'])) fail('ROW')
  let row = item.row ?? item.row_json
  if (typeof row === 'string' && Object.hasOwn(item, 'row_json')) {
    try { row = JSON.parse(row) } catch { fail('ROW') }
  }
  const table = BY_KIND[item.kind]
  const expected = columns[table].filter(name => name !== 'embedding')
  if (!exact(row, expected)) fail('ROW')
  if (row.tenant_id !== descriptor.owner_tenant_id || !allowedFolders.has(String(row.space_id))) fail('SCOPE')
  for (const name of expected) {
    const value = row[name]
    if (value === null) continue
    const type = TABLES[table].columns[name]
    if (type === 'VARCHAR' && typeof value !== 'string') fail('ROW')
    if (type === 'INTEGER' && (!Number.isInteger(value) || value < -2147483648 || value > 2147483647)) fail('ROW')
    if (type === 'DOUBLE' && (typeof value !== 'number' || !Number.isFinite(value))) fail('ROW')
    if (type === 'TIMESTAMP' && (typeof value !== 'string'
        || !/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?$/.test(value))) fail('ROW')
    if (type === 'JSON') finite(value)
  }
  return { table, row }
}

function appendCell(appender, type, value) {
  if (value === null || value === undefined) appender.appendNull()
  else if (type === 'INTEGER') appender.appendInteger(value)
  else if (type === 'DOUBLE') appender.appendDouble(value)
  else if (type === 'JSON') appender.appendVarchar(JSON.stringify(value))
  else appender.appendVarchar(value)
}

/** The connection must already be a sealed, disposable in-memory DuckDB. */
export async function loadDocumentSnapshot(connection, descriptor) {
  descriptorValid(descriptor)
  const schemaBytes = boundedFile(descriptor.schema_path, descriptor.schema_sha256, MAX_SCHEMA_BYTES)
  const snapshotBytes = boundedFile(descriptor.path, descriptor.sha256, MAX_SNAPSHOT_BYTES)
  const columns = parseSchema(schemaBytes)
  const counts = { entities: 0, pages: 0, relations: 0, enriched: 0 }
  const folders = new Set(descriptor.folder_ids)
  const appenders = {}
  try {
    for (const [table, names] of Object.entries(columns)) {
      const ddl = names.map(name => `"${name}" ${TABLES[table].columns[name]}`).join(', ')
      await connection.run(`CREATE TABLE "${table}" (${ddl})`)
      appenders[table] = await connection.createAppender(table)
    }
    let start = 0
    for (let end = 0; end <= snapshotBytes.length; end++) {
      if (end !== snapshotBytes.length && snapshotBytes[end] !== 10) continue
      if (end === start && end === snapshotBytes.length) break
      if (end - start > MAX_LINE_BYTES) fail('BUDGET')
      if (end === start) fail('ROW')
      let item
      try { item = JSON.parse(snapshotBytes.toString('utf8', start, end)) } catch { fail('ROW') }
      const { table, row } = validatedRow(item, columns, descriptor, folders)
      const kind = TABLES[table].kind
      if (++counts[kind] > descriptor.expected_counts[kind]
          || Object.values(counts).reduce((n, count) => n + count, 0) > MAX_ROWS) fail('COUNTS')
      const appender = appenders[table]
      for (const name of columns[table]) appendCell(appender, TABLES[table].columns[name], row[name])
      appender.endRow()
      start = end + 1
    }
    if (COUNT_KEYS.some(key => counts[key] !== descriptor.expected_counts[key])) fail('COUNTS')
    for (const appender of Object.values(appenders)) appender.closeSync()
    for (const [table, spec] of Object.entries(TABLES)) {
      const rows = (await connection.runAndReadAll(`SELECT COUNT(*) AS n FROM "${table}"`)).getRowObjectsJS()
      if (Number(rows[0]?.n) !== counts[spec.kind]) fail('COUNTS')
    }
  } catch (error) {
    if (error instanceof GraphDocumentError) throw error
    fail('SQL')
  } finally {
    // closeSync also flushes, including when validation found a later bad row.
    for (const appender of Object.values(appenders)) {
      try { appender.closeSync() } catch {}
    }
  }
  return {
    snapshot_sha256: descriptor.sha256, schema_sha256: descriptor.schema_sha256,
    expected_counts: { ...descriptor.expected_counts }, loaded_counts: counts,
    embedding: 'omitted_in_capture',
  }
}
