/** One offline graph control against a committed MCPs snapshot and in-memory DuckDB. */
import { createRequire, syncBuiltinESMExports } from 'node:module'
import { readFileSync, realpathSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { Socket } from 'node:net'
import { loadSnapshotIdentity } from './snapshot-identity.mjs'
import { loadDocumentSnapshot } from './graph-document-loader.mjs'

const write = process.stdout.write.bind(process.stdout)
for (const name of ['log', 'info', 'warn', 'error', 'debug', 'trace']) console[name] = () => {}
process.stdout.write = () => true
process.stderr.write = () => true
let networkAttempts = 0, blockedLoaderIpcAttempts = 0
const denyNetwork = () => { networkAttempts++; throw new Error('network_disabled') }
globalThis.fetch = denyNetwork
Socket.prototype.connect = function (...args) {
  const options = Array.isArray(args[0]) ? args[0][0] : args[0]
  const path = typeof options === 'string' ? options : options?.path
  if (typeof path === 'string' && path.startsWith('/') && path.endsWith(`/${process.ppid}.pipe`)
      && /node_modules\/tsx\//.test(new Error().stack || '')) {
    blockedLoaderIpcAttempts++
    throw new Error('loader_ipc_disabled')
  }
  return denyNetwork()
}
syncBuiltinESMExports()

const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const text = value => typeof value === 'string' && value.trim().length > 0
const exact = (value, keys) => object(value) && Object.keys(value).sort().join('|') === [...keys].sort().join('|')
const finite = value => {
  if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('nonfinite_json')
  if (value && typeof value === 'object') Object.values(value).forEach(finite)
}
const jsonSafe = value => JSON.parse(JSON.stringify(value, (_key, current) =>
  typeof current === 'bigint' ? Number(current)
    : current instanceof Map ? Array.from(current, ([depth, nodes]) => ({ depth, nodes }))
      : current))
const sqlLiteral = value => value === null || value === undefined ? 'NULL'
  : typeof value === 'number' && Number.isFinite(value) ? String(value)
    : `'${String(value).replaceAll("'", "''")}'`
const fixtureModules = {
  duckdb: 'exports.getDuckDBService = async function () { return globalThis.__graphFixture.db }',
  grants: `exports.authorizeSpaceViewers = async function (spaces, reader, options) {
    const f = globalThis.__graphFixture;
    f.calls.push({ kind:'authorize', spaces:[...spaces], reader, allowPartial:options?.allowPartial });
    if (f.data.faults?.authorization === 'unavailable') throw new Error('private authorization failure');
    return structuredClone(f.data.grants);
  }`,
  folders: `exports.getFolderIdsForSpace = async function (space) {
    const f = globalThis.__graphFixture;
    f.calls.push({ kind:'folders', space });
    if (f.data.faults?.folder === 'unavailable') throw new Error('private storage failure');
    return structuredClone(f.data.folders[space] ?? []);
  }`,
}

let stage = 'environment'
let unregister, connection, instance, result, snapshot, request, fixtureModuleHashes
let documentSnapshot, loadMs, executeMs
const calls = []
const queryCounts = { query: 0, queryWrite: 0, selected: 0, statements: 0 }
try {
  const allowed = new Set(['PATH', 'LANG', 'LC_ALL', 'TZ', 'TSX_DISABLE_CACHE',
    'GIT_OPTIONAL_LOCKS', 'GIT_TERMINAL_PROMPT', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL'])
  if (Object.keys(process.env).some(key => !allowed.has(key)) || process.argv.length !== 3) {
    throw new Error('isolated_driver_required')
  }
  process.env.MASTRA_TRANSPORT = 'in-process'
  process.env.GROQ_API_KEY = 'offline-graph-control-placeholder'
  process.env.MCP_MODE = 'true'
  process.env.NODE_ENV = 'production'
  stage = 'input'
  let bytes = 0
  const chunks = []
  for await (const chunk of process.stdin) {
    bytes += chunk.length
    if (bytes > 1024 * 1024) throw new Error('input_limit')
    chunks.push(chunk)
  }
  request = JSON.parse(Buffer.concat(chunks).toString('utf8'))
  finite(request)
  const documentary = object(request?.fixture?.document_snapshot)
  if (!exact(request, ['case_id', 'entrypoint', 'input', 'context', 'fixture', 'service'])
      || !text(request.case_id) || !['helper', 'legacy_service', 'strict_service'].includes(request.entrypoint)
      || !object(request.input) || !exact(request.context, ['tenant_id', 'space_ids'])
      || !text(request.context.tenant_id) || !Array.isArray(request.context.space_ids)
      || request.context.space_ids.length > 32 || request.context.space_ids.some(id => !text(id))
      || !object(request.fixture) || !Array.isArray(request.fixture.entities)
      || !Array.isArray(request.fixture.relations) || !Array.isArray(request.fixture.grants)
      || !object(request.fixture.folders) || !object(request.service)
      || (documentary && (!exact(request.fixture,
        ['grants', 'folders', 'entities', 'relations', 'document_snapshot'])
        || request.fixture.entities.length !== 0 || request.fixture.relations.length !== 0))
      || (!documentary && request.fixture.document_snapshot !== undefined)
      || (request.fixture.entities_add !== undefined && !Array.isArray(request.fixture.entities_add))
      || (request.fixture.relations_add !== undefined && !Array.isArray(request.fixture.relations_add))
      || request.fixture.entities.length + (request.fixture.entities_add?.length ?? 0) > 2000
      || request.fixture.relations.length + (request.fixture.relations_add?.length ?? 0) > 5000
      || !['search', 'neighbors', 'path'].includes(request.input.operation)) {
    throw new Error('input_invalid')
  }
  const root = realpathSync(resolve(process.argv[2]))
  snapshot = loadSnapshotIdentity(root)
  const requireFromRoot = createRequire(pathToFileURL(join(root, 'package.json')))
  const packages = {}
  for (const name of ['tsx', 'zod', '@mastra/core', '@mastra/mcp', '@ai-sdk/openai', '@duckdb/node-api']) {
    let path = dirname(realpathSync(requireFromRoot.resolve(name === 'tsx' ? 'tsx/esm/api' : name)))
    let metadata
    while (true) {
      try { metadata = JSON.parse(readFileSync(join(path, 'package.json'), 'utf8')) } catch {}
      if (metadata?.name === name) break
      const parent = dirname(path)
      if (parent === path) throw new Error('package_metadata_missing')
      path = parent
    }
    packages[name] = { version: metadata.version, package_json_sha256: sha(readFileSync(join(path, 'package.json'))) }
  }
  const { DuckDBInstance } = requireFromRoot('@duckdb/node-api')
  stage = 'database'
  // DuckDB needs local extension-registry access for duckdb_extensions(). Probe
  // that registry on a separate empty database, then keep the fixture sealed.
  const probeInstance = await DuckDBInstance.create(':memory:', {
    autoinstall_known_extensions: 'false', autoload_known_extensions: 'false',
  })
  const probeConnection = await probeInstance.connect()
  const actualExtension = (await probeConnection.runAndReadAll(`SELECT extension_name, extension_version,
    installed, loaded FROM duckdb_extensions() WHERE extension_name = 'duckpgq'`)).getRowObjectsJS()[0] ?? null
  probeConnection.disconnectSync()
  probeInstance.closeSync()
  instance = await DuckDBInstance.create(':memory:', {
    enable_external_access: 'false', autoinstall_known_extensions: 'false',
    autoload_known_extensions: 'false', threads: '2', memory_limit: '512MB',
  })
  connection = await instance.connect()
  const duckpgqProbe = {
    installed: actualExtension?.installed === true,
    loaded: actualExtension?.loaded === true,
    version: actualExtension?.extension_version ?? null,
    exposed_to_service: 'unavailable_for_isolated_cte',
  }
  const loadStarted = performance.now()
  try {
    if (documentary) {
      stage = 'document_load'
      documentSnapshot = await loadDocumentSnapshot(connection, request.fixture.document_snapshot)
    } else {
  await connection.run(`CREATE TABLE uploaded_files_graph_entities (
    tenant_id VARCHAR, space_id VARCHAR, file_id INTEGER, entity_id VARCHAR,
    entity_type VARCHAR, entity_name VARCHAR, properties JSON
  )`)
  await connection.run(`CREATE TABLE uploaded_files_graph_relations (
    tenant_id VARCHAR, space_id VARCHAR, file_id INTEGER, relation_id VARCHAR,
    source_id VARCHAR, target_id VARCHAR, relation_type VARCHAR, confidence DOUBLE,
    properties JSON
  )`)
  for (const row of [...request.fixture.entities, ...(request.fixture.entities_add ?? [])]) {
    if (!exact(row, ['tenant_id', 'space_id', 'file_id', 'entity_id', 'entity_type', 'entity_name', 'properties'])
        || !Number.isSafeInteger(row.file_id) || !object(row.properties)) throw new Error('entity_fixture_invalid')
    const values = [row.tenant_id, row.space_id, row.file_id, row.entity_id,
      row.entity_type, row.entity_name, JSON.stringify(row.properties)]
    await connection.run(`INSERT INTO uploaded_files_graph_entities VALUES (${values.map(sqlLiteral).join(',')})`)
  }
  for (const row of [...request.fixture.relations, ...(request.fixture.relations_add ?? [])]) {
    if (!exact(row, ['tenant_id', 'space_id', 'file_id', 'relation_id', 'source_id', 'target_id', 'relation_type', 'confidence'])
        || !Number.isSafeInteger(row.file_id)
        || !(row.confidence === null || typeof row.confidence === 'number')) throw new Error('relation_fixture_invalid')
    const values = [row.tenant_id, row.space_id, row.file_id, row.relation_id,
      row.source_id, row.target_id, row.relation_type, row.confidence]
    await connection.run(`INSERT INTO uploaded_files_graph_relations
      (tenant_id, space_id, file_id, relation_id, source_id, target_id, relation_type, confidence)
      VALUES (${values.map(sqlLiteral).join(',')})`)
  }
  if (request.fixture.faults?.sql === 'relations_missing') {
    await connection.run('DROP TABLE uploaded_files_graph_relations')
  }
    }
  } finally {
    loadMs = performance.now() - loadStarted
  }
  const query = async (sql, _params, method) => {
    queryCounts[method]++
    queryCounts.statements++
    const normalized = sql.trim()
    if (/duckdb_extensions\s*\(\s*\)/i.test(normalized)) {
      return [{ extension_name: 'duckpgq', extension_version: null, installed: false, loaded: false }]
    }
    if (/^(SELECT|WITH|PRAGMA|DESCRIBE|SHOW)\b/i.test(normalized)) {
      queryCounts.selected++
      return (await connection.runAndReadAll(sql)).getRowObjectsJS()
    }
    await connection.run(sql)
    return []
  }
  globalThis.__graphFixture = {
    data: structuredClone(request.fixture), calls,
    db: { query: (sql, params) => query(sql, params, 'query'),
      queryWrite: (sql, params) => query(sql, params, 'queryWrite') },
  }
  stage = 'loader'
  // These three explicit dependency seams are generated only inside the
  // disposable snapshot. Their bytes are fixed by this versioned bridge.
  const fixtureFiles = new Map([
    ['src/services/duckdb.js', fixtureModules.duckdb],
    ['src/services/space-access-batch.js', fixtureModules.grants],
    ['src/tools/search-duckdb-text.js', fixtureModules.folders],
  ])
  fixtureModuleHashes = {}
  for (const [path, source] of fixtureFiles) {
    const target = join(root, path)
    mkdirSync(dirname(target), { recursive: true })
    if (existsSync(target)) {
      if (readFileSync(target, 'utf8') !== source) throw new Error('fixture_module_changed')
    } else {
      try { writeFileSync(target, source, { flag: 'wx' }) }
      catch (error) {
        if (error?.code !== 'EEXIST' || readFileSync(target, 'utf8') !== source) throw error
      }
    }
    fixtureModuleHashes[path] = sha(Buffer.from(source))
  }
  const loader = await import(pathToFileURL(requireFromRoot.resolve('tsx/esm/api')).href)
  unregister = loader.register({ tsconfig: false })
  stage = 'execute'
  const executeStarted = performance.now()
  let output, outcome, nativeException
  try {
  if (request.entrypoint === 'helper') {
    const imported = await import(pathToFileURL(join(root, 'src/agents/deposium-agent.ts')).href)
    const agent = await imported.getDeposiumAgent()
    const tools = await agent.listTools()
    if (!tools?.deposium_graph || Object.keys(tools).length !== 6) throw new Error('graph_catalog_invalid')
    const { RequestContext } = await import(pathToFileURL(requireFromRoot.resolve('@mastra/core/request-context')).href)
    const context = new RequestContext()
    context.set('tenant_id', request.context.tenant_id)
    context.set('space_ids', [...request.context.space_ids])
    try {
      output = await tools.deposium_graph.execute(request.input, { requestContext: context })
      outcome = typeof output?.status === 'string' ? output.status : 'legacy_untyped_output'
    } catch (error) {
      // The factory and catalog loaded successfully: this is the native tool's
      // observed result. Never expose backend messages or stack traces.
      output = null
      outcome = 'error'
      nativeException = {
        name: typeof error?.name === 'string' ? error.name : 'Error',
        code: typeof error?.code === 'string' ? error.code : null,
      }
    }
    calls.push({ kind: 'factory_graph_execute' })
  } else {
    const imported = await import(pathToFileURL(join(root, 'src/services/duckdb-graph-advanced.ts')).href)
    const service = new imported.DuckDBAdvancedGraphService()
    const args = request.service
    if (!text(args.graph_name) || !Array.isArray(args.folder_ids) || args.folder_ids.some(id => !text(id))) {
      throw new Error('service_scope_invalid')
    }
    if (request.entrypoint === 'strict_service' && typeof service.findScopedShortestPath !== 'function') {
      output = null
      outcome = 'not_implemented'
    } else if (request.input.operation === 'search') {
      output = await service.matchPattern(args.graph_name, '', args.entity_id
        ? { entity_id: args.entity_id } : { query: request.input.entity }, args.limit ?? 20,
      args.folder_ids, request.entrypoint === 'strict_service' ? { strict: true } : undefined)
      outcome = output?.nodes?.length ? 'ok' : 'empty'
    } else if (request.input.operation === 'neighbors') {
      output = await service.findKHopNeighborhood(args.graph_name, args.source_id,
        args.max_depth ?? 2, undefined, true, args.owner_tenant_id,
        args.folder_ids, undefined, args.max_edges ?? 100,
        request.entrypoint === 'strict_service' ? { strict: true } : undefined)
      outcome = output?.layers instanceof Map && [...output.layers.values()].some(nodes => nodes.length) ? 'ok' : 'empty'
    } else if (request.entrypoint === 'strict_service') {
      output = await service.findScopedShortestPath(args.graph_name, args.source_id,
        args.target_id, args.max_hops ?? 4, args.folder_ids, args.path_options ?? {})
      outcome = output.status
    } else {
      output = await service.findShortestPath(args.graph_name, args.source_id,
        args.target_id, args.max_hops ?? 4, args.folder_ids)
      outcome = output === null ? 'legacy_null' : 'ok'
    }
    calls.push({ kind: 'service_method', method: request.input.operation, mode: request.entrypoint })
  }
  } finally {
    executeMs = performance.now() - executeStarted
  }
  if (networkAttempts) throw new Error('network_attempted')
  snapshot.verify()
  for (const [path, source] of fixtureFiles) {
    if (readFileSync(join(root, path), 'utf8') !== source) throw new Error('fixture_module_changed')
  }
  result = {
    status: 'ok', case_id: request.case_id, entrypoint: request.entrypoint,
    output: jsonSafe(output), outcome, ...(nativeException ? { native_exception: nativeException } : {}),
    captured_calls: calls, query_counts: queryCounts,
    duckpgq_probe: duckpgqProbe, capability_override: 'duckpgq_unavailable_for_isolated_cte',
    source_files_sha256: snapshot.sources, fixture_modules_sha256: fixtureModuleHashes,
    runtime: { node: process.version, packages },
    ...(documentary ? { document_snapshot: documentSnapshot } : {}),
    timings_ms: { load: loadMs, execute: executeMs },
    scope: { requested_space_count: request.context.space_ids.length,
      fixture_grant_count: request.fixture.grants.length,
      folder_count: request.service.folder_ids?.length ?? null },
    network_attempts: networkAttempts, blocked_loader_ipc_attempts: blockedLoaderIpcAttempts,
    model_calls: 0,
  }
} catch (error) {
  result = {
    status: 'error', error: `graph_${stage}_failed`,
    error_code: typeof error?.code === 'string' && /^GRAPH_[A-Z_]+$/.test(error.code) ? error.code : null,
    case_id: request?.case_id ?? null, entrypoint: request?.entrypoint ?? null,
    ...(loadMs !== undefined || executeMs !== undefined
      ? { timings_ms: { load: loadMs ?? null, execute: executeMs ?? null } } : {}),
    output: null, outcome: 'error', captured_calls: calls, query_counts: queryCounts,
    network_attempts: networkAttempts, blocked_loader_ipc_attempts: blockedLoaderIpcAttempts,
    model_calls: 0,
  }
} finally {
  delete globalThis.__graphFixture
  try {
    if (snapshot) snapshot.verify()
    if (unregister) await unregister()
    if (connection) connection.disconnectSync()
    if (instance) instance.closeSync()
  } catch {
    result = { status: 'error', error: 'graph_cleanup_failed', output: null, outcome: 'error' }
  }
}
let encoded = JSON.stringify(result)
if (Buffer.byteLength(encoded, 'utf8') > 1024 * 1024) encoded = '{"status":"error","error":"graph_output_limit","outcome":"error"}'
write(`${encoded}\n`, () => process.exit(0))
