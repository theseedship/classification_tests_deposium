/** Real generate contract, scripted provider + backends. Full native pool, NOT a model comparison. */
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
const calls = [], providerRequests = []
let providerResponse = null
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
  if (!exact(request, ['case_id', 'message', 'context', 'fixture', 'provider_fixture'])
      || !text(request.case_id) || !text(request.message)
      || !exact(request.context, ['tenant_id', 'space_ids']) || !text(request.context.tenant_id)
      || !Array.isArray(request.context.space_ids) || request.context.space_ids.length !== 1
      || !uuid(request.context.space_ids[0]) || !exact(request.fixture, ['search', 'stats'])
      || !isObject(request.fixture.search) || !Array.isArray(request.fixture.search.documents)
      || !Array.isArray(request.fixture.search.blocks) || !isObject(request.fixture.stats)
      || Object.keys(request.fixture.search).some(key => !['documents', 'blocks', 'graph_context'].includes(key))
      || (Object.hasOwn(request.fixture.search, 'graph_context') && typeof request.fixture.search.graph_context !== 'string')) throw new Error('input_invalid')
  const decision = request.provider_fixture
  if (decision?.kind === 'text') {
    if (!exact(decision, ['kind', 'text']) || !text(decision.text) || decision.text.length > 4096) throw new Error('text_fixture_invalid')
  } else {
    if (!exact(decision, ['kind', 'tool_name', 'arguments']) || decision.kind !== 'tool_call'
        || !['deposium_search', 'deposium_analyze'].includes(decision.tool_name)
        || !isObject(decision.arguments)) throw new Error('tool_fixture_invalid')
    const args = decision.arguments
    const allowedArgs = decision.tool_name === 'deposium_search'
      ? ['query_text', 'top_k', 'tenant_id', 'space_ids'] : ['tenant_id', 'space_ids']
    if (Object.keys(args).some(key => !allowedArgs.includes(key))
        || (Object.hasOwn(args, 'tenant_id') && !text(args.tenant_id))
        || (Object.hasOwn(args, 'space_ids') && (!Array.isArray(args.space_ids) || !args.space_ids.length
          || args.space_ids.length > 32 || args.space_ids.some(value => !text(value))))
        || (decision.tool_name === 'deposium_search' && (!text(args.query_text)
          || (Object.hasOwn(args, 'top_k') && (!Number.isInteger(args.top_k) || args.top_k < 1 || args.top_k > 5))))) throw new Error('tool_arguments_invalid')
  }
  // This fetch is a pure in-memory provider boundary; no native fetch is retained.
  globalThis.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input?.url
    if (url !== 'https://api.groq.com/openai/v1/responses') return denyNetwork()
    if (providerRequests.length || init?.method?.toUpperCase() !== 'POST' || typeof init.body !== 'string'
        || Buffer.byteLength(init.body, 'utf8') > 1024 * 1024) throw new Error('provider_contract_invalid')
    const body = JSON.parse(init.body)
    finiteJson(body)
    if (!Array.isArray(body.tools) || body.tools.map(tool => tool.name).sort().join('|') !== expected.join('|')) throw new Error('provider_pool_invalid')
    // Headers deliberately excluded: the local placeholder Authorization is not evidence.
    providerRequests.push({ url, method: 'POST', body, body_sha256: sha(init.body) })
    providerResponse = { id: 'resp-offline-planner-1', created_at: 1786534200,
      model: 'openai/gpt-oss-120b', output: decision.kind === 'tool_call'
        ? [{ type: 'function_call', id: 'fc-offline-1', call_id: 'call-offline-1',
          name: decision.tool_name, arguments: JSON.stringify(decision.arguments) }]
        : [{ type: 'message', id: 'msg-offline-1', role: 'assistant',
          content: [{ type: 'output_text', text: decision.text, annotations: [] }] }],
      usage: { input_tokens: 10, output_tokens: 5 } }
    return new Response(JSON.stringify(providerResponse), { status: 200, headers: { 'content-type': 'application/json' } })
  }
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
  stage = 'generate'
  const response = await agent.generate(request.message, { maxSteps: 1, toolChoice: 'auto', requestContext })
  const steps = response.steps
  if (!Array.isArray(steps) || steps.length !== 1 || providerRequests.length !== 1) throw new Error('step_count_invalid')
  const first = steps[0]
  const observedCalls = (first.toolCalls ?? []).map(call => {
    const native = call.payload ?? call
    return { tool_name: native.toolName, tool_call_id: native.toolCallId, arguments: native.args }
  })
  const observedResults = (first.toolResults ?? []).map(item => {
    const native = item.payload ?? item
    return { tool_name: native.toolName, tool_call_id: native.toolCallId, result: native.result }
  })
  let output
  if (decision.kind === 'tool_call') {
    if (observedCalls.length !== 1 || observedCalls[0].tool_name !== decision.tool_name
        || observedResults.length !== 1 || observedResults[0].tool_name !== decision.tool_name
        || calls.length !== 1 || calls[0].handler !== (decision.tool_name === 'deposium_search' ? 'searchHub' : 'getCorpusStats')
        || calls[0].input.tenant_id !== request.context.tenant_id
        || (decision.tool_name === 'deposium_search' && JSON.stringify(calls[0].input.space_ids) !== JSON.stringify(request.context.space_ids))
        || (decision.tool_name === 'deposium_analyze' && calls[0].input.space_id !== request.context.space_ids[0])) throw new Error('native_dispatch_invalid')
    output = { kind: 'tool_call', tool_calls: observedCalls, tool_results: observedResults }
  } else {
    if (observedCalls.length || observedResults.length || calls.length || response.text !== decision.text) throw new Error('text_stop_invalid')
    output = { kind: 'text_stop', text: response.text, fallback_equivalent: false }
  }
  finiteJson(output)
  stage = 'integrity'
  snapshot.verify()
  if (networkAttempts) throw new Error('execution_changed')
  result = { status: 'ok', qualification: 'mock_native_planner_contract', mode: 'full_native_pool_capture',
    comparable_to_three_label_candidate: false, cases_scored: 0, case_id: request.case_id, output,
    raw: { first_provider_request: providerRequests[0], scripted_provider_response: providerResponse,
      ordered_native_tool_calls: observedCalls, ordered_native_tool_results: observedResults,
      native_text: response.text ?? '', input_sha256: sha(JSON.stringify(request)), fixture_kind: 'synthetic',
      selection_origin: 'scripted_provider_not_model_prediction', max_steps: 1, tool_choice: 'auto' },
    captured_calls: calls, catalog, catalog_sha256: sha(JSON.stringify(catalog)), source_files_sha256: sources,
    runtime: { node: process.version, packages }, native_tool_executions: calls.length,
    scripted_provider_requests: providerRequests.length, real_provider_calls: 0,
    network_attempts: networkAttempts, blocked_loader_ipc_attempts: blockedLoaderIpcAttempts,
    limitations: ['Native six-tool pool differs from candidate search/stats/fallback labels.',
      'Text stop is neither demonstrated fallback nor planner transfer.',
      'Provider response and token usage are scripted fixtures; no quality or latency comparison.'] }
} catch {
  result = { status: 'error', qualification: 'mock_native_planner_contract', error: `mastra_planner_${stage}_failed`,
    output: null, captured_calls: calls, first_provider_request: providerRequests[0] ?? null, real_provider_calls: 0, network_attempts: networkAttempts,
    blocked_loader_ipc_attempts: blockedLoaderIpcAttempts }
} finally {
  delete globalThis.__deposiumReadFixture
  try { if (hooks) hooks.deregister(); if (unregister) await unregister() } catch {
    result = { status: 'error', error: 'mastra_planner_cleanup_failed', qualification: 'mock_native_planner_contract', output: null }
  }
}
let encoded = JSON.stringify(result)
if (Buffer.byteLength(encoded, 'utf8') > 1024 * 1024) encoded = '{"status":"error","error":"mastra_planner_output_limit","qualification":"mock_native_planner_contract"}'
write(`${encoded}\n`)
