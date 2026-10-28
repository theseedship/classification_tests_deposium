/** Native Mastra wrappers with two synthetic downstream fixtures; never a model call. */
import { createRequire, registerHooks, syncBuiltinESMExports } from 'node:module'
import { readFileSync, realpathSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { Socket } from 'node:net'
import { loadSnapshotIdentity } from './snapshot-identity.mjs'

const write = process.stdout.write.bind(process.stdout)
for (const name of ['log', 'info', 'warn', 'error', 'debug', 'trace']) console[name] = () => {}
process.stdout.write = () => true
process.stderr.write = () => true
let stage = 'environment', networkAttempts = 0, blockedLoaderIpcAttempts = 0
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
const sha = data => createHash('sha256').update(data).digest('hex')
const expected = ['abstain_decision', 'deposium_analyze', 'deposium_answer',
  'deposium_graph', 'deposium_search', 'escalate_decision']
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value)
const text = value => typeof value === 'string' && value.trim() && !/[\u0000-\u001f]/.test(value)
const uuid = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
const exact = (value, keys) => isObject(value) && Object.keys(value).sort().join('|') === keys.sort().join('|')
function finiteJson(value) {
  if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('nonfinite_json')
  if (value && typeof value === 'object') Object.values(value).forEach(finiteJson)
}
let unregister, hooks, result, request
const calls = []
try {
  const allowed = new Set(['PATH', 'LANG', 'LC_ALL', 'TZ', 'TSX_DISABLE_CACHE',
    'GIT_OPTIONAL_LOCKS', 'GIT_TERMINAL_PROMPT', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL'])
  if (Object.keys(process.env).some(key => !allowed.has(key)) || process.argv.length !== 3) throw new Error('isolated_driver_required')
  process.env.MASTRA_TRANSPORT = 'in-process'
  process.env.GROQ_API_KEY = 'offline-read-pilot-placeholder'
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
  finiteJson(request)
  const keys = ['case_id', 'action', 'message', 'context', 'fixture']
  if (Object.hasOwn(request, 'tool_args')) keys.push('tool_args')
  if (!exact(request, keys) || !text(request.case_id) || !text(request.message)
      || !['search', 'stats', 'fallback'].includes(request.action)
      || !exact(request.context, ['tenant_id', 'space_ids']) || !text(request.context.tenant_id)
      || !Array.isArray(request.context.space_ids) || request.context.space_ids.length !== 1
      || !uuid(request.context.space_ids[0]) || !exact(request.fixture, ['search', 'stats'])
      || !isObject(request.fixture.search) || !Array.isArray(request.fixture.search.documents)
      || !Array.isArray(request.fixture.search.blocks) || !isObject(request.fixture.stats)
      || Object.keys(request.fixture.search).some(key => !['documents', 'blocks', 'graph_context'].includes(key))
      || (Object.hasOwn(request.fixture.search, 'graph_context') && typeof request.fixture.search.graph_context !== 'string')) throw new Error('input_invalid')
  const args = request.tool_args ?? {}
  if (!isObject(args) || Object.keys(args).some(key => !['tenant_id', 'space_ids'].includes(key))
      || (Object.hasOwn(args, 'tenant_id') && !text(args.tenant_id))
      || (Object.hasOwn(args, 'space_ids') && (!Array.isArray(args.space_ids) || !args.space_ids.length
        || args.space_ids.length > 32 || args.space_ids.some(value => !text(value))))) throw new Error('tool_args_invalid')
  const root = realpathSync(resolve(process.argv[2]))
  const requireFromRoot = createRequire(pathToFileURL(join(root, 'package.json')))
  const snapshot = loadSnapshotIdentity(root)
  const sources = snapshot.sources
  const packages = {}
  for (const name of ['tsx', 'zod', '@mastra/core', '@mastra/mcp', '@ai-sdk/openai']) {
    let path = dirname(realpathSync(requireFromRoot.resolve(name === 'tsx' ? 'tsx/esm/api' : name)))
    let metadata
    while (true) {
      try { metadata = JSON.parse(readFileSync(join(path, 'package.json'), 'utf8')) } catch {}
      if (metadata?.name === name) break
      const parent = dirname(path)
      if (parent === path) throw new Error('package_metadata_missing')
      path = parent
    }
    packages[name] = { version: metadata.version,
      package_json_sha256: sha(readFileSync(join(path, 'package.json'))) }
  }
  globalThis.__deposiumReadFixture = { fixture: structuredClone(request.fixture), calls }
  const fixtureUrl = (name, exported) => 'data:text/javascript,' + encodeURIComponent(
    `export async function ${exported}(args) { const f=globalThis.__deposiumReadFixture; ` +
    `f.calls.push({handler:${JSON.stringify(exported)},input:structuredClone(args)}); ` +
    `return structuredClone(f.fixture[${JSON.stringify(name)}]); }`)
  const fixtureUrls = { search: fixtureUrl('search', 'searchHub'), stats: fixtureUrl('stats', 'getCorpusStats') }
  stage = 'loader'
  const loader = await import(pathToFileURL(requireFromRoot.resolve('tsx/esm/api')).href)
  unregister = loader.register({ tsconfig: false })
  hooks = registerHooks({ resolve(specifier, context, nextResolve) {
    if (context.parentURL?.startsWith('file:') && /^\.\.?\//.test(specifier)) {
      const path = fileURLToPath(new URL(specifier, context.parentURL))
      if ([join(root, 'src/tools/search.js'), join(root, 'src/tools/search.ts')].includes(path)) {
        return { url: fixtureUrls.search, shortCircuit: true }
      }
      if ([join(root, 'src/tools/corpus-stats.js'), join(root, 'src/tools/corpus-stats.ts')].includes(path)) {
        return { url: fixtureUrls.stats, shortCircuit: true }
      }
    }
    return nextResolve(specifier, context)
  } })
  stage = 'factory'
  const imported = await import(pathToFileURL(join(root, 'src/agents/deposium-agent.ts')).href)
  const agent = await imported.getDeposiumAgent()
  const tools = await agent.listTools()
  if (!tools || Object.keys(tools).sort().join('|') !== expected.join('|')) throw new Error('catalog_unexpected')
  const zod = await import(pathToFileURL(requireFromRoot.resolve('zod')).href)
  const catalog = expected.map(name => ({ name, description: tools[name].description,
    inputSchema: zod.toJSONSchema(tools[name].inputSchema) }))
  const { RequestContext } = await import(pathToFileURL(requireFromRoot.resolve('@mastra/core/request-context')).href)
  const requestContext = new RequestContext()
  requestContext.set('tenant_id', request.context.tenant_id)
  requestContext.set('space_ids', [...request.context.space_ids])
  stage = 'execute'
  let output = null
  if (request.action !== 'fallback') {
    const name = request.action === 'search' ? 'deposium_search' : 'deposium_analyze'
    const input = request.action === 'search' ? { query_text: request.message, top_k: 5, ...args } : args
    output = await tools[name].execute(input, { requestContext })
    if (calls.length !== 1 || calls[0].handler !== (request.action === 'search' ? 'searchHub' : 'getCorpusStats')
        || calls[0].input.tenant_id !== request.context.tenant_id
        || (request.action === 'search' && JSON.stringify(calls[0].input.space_ids) !== JSON.stringify(request.context.space_ids))
        || (request.action === 'stats' && calls[0].input.space_id !== request.context.space_ids[0])) throw new Error('scope_or_calls_invalid')
  }
  finiteJson(output)
  stage = 'integrity'
  snapshot.verify()
  if (networkAttempts) throw new Error('execution_changed')
  result = { status: 'ok', qualification: 'mock_native_contract', case_id: request.case_id,
    action: request.action, output, raw: { native_output: output, input_sha256: sha(JSON.stringify(request)),
      fixture_kind: 'synthetic', selection_origin: 'driver_action_not_model' }, captured_calls: calls,
    catalog, catalog_sha256: sha(JSON.stringify(catalog)), source_files_sha256: sources,
    runtime: { node: process.version, packages }, native_tool_executions: calls.length, model_calls: 0,
    network_attempts: networkAttempts, blocked_loader_ipc_attempts: blockedLoaderIpcAttempts }
} catch {
  result = { status: 'error', qualification: 'mock_native_contract', error: `mastra_read_${stage}_failed`,
    output: null, captured_calls: calls, model_calls: 0, network_attempts: networkAttempts,
    blocked_loader_ipc_attempts: blockedLoaderIpcAttempts }
} finally {
  delete globalThis.__deposiumReadFixture
  try { if (hooks) hooks.deregister(); if (unregister) await unregister() } catch {
    result = { status: 'error', error: 'mastra_read_cleanup_failed', qualification: 'mock_native_contract', output: null }
  }
}
let encoded = JSON.stringify(result)
if (Buffer.byteLength(encoded, 'utf8') > 1024 * 1024) encoded = '{"status":"error","error":"mastra_read_output_limit","qualification":"mock_native_contract"}'
write(`${encoded}\n`)
