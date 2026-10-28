/** Opt-in native declaration probe. The Python driver owns revision and limits. */
import { createRequire, syncBuiltinESMExports } from 'node:module'
import { readFileSync, realpathSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { Socket } from 'node:net'

const write = process.stdout.write.bind(process.stdout)
for (const name of ['log', 'info', 'warn', 'error', 'debug', 'trace']) console[name] = () => {}
process.stdout.write = () => true
process.stderr.write = () => true
let stage = 'environment'
let networkAttempts = 0
let blockedLoaderIpcAttempts = 0
const denyNetwork = () => {
  networkAttempts++
  throw new Error('network_disabled')
}
globalThis.fetch = denyNetwork
Socket.prototype.connect = function (...args) {
  const options = Array.isArray(args[0]) ? args[0][0] : args[0]
  const path = typeof options === 'string' ? options : options?.path
  // tsx probes a parent notification pipe even when used as a library.
  // Deny that IPC too, but distinguish it from a network/service attempt.
  if (typeof path === 'string' && path.startsWith('/') && path.endsWith(`/${process.ppid}.pipe`)
      && /node_modules\/tsx\//.test(new Error().stack || '')) {
    blockedLoaderIpcAttempts++
    throw new Error('loader_ipc_disabled')
  }
  return denyNetwork()
}
syncBuiltinESMExports()
let unregister
let result
const expected = ['abstain_decision', 'deposium_analyze', 'deposium_answer',
  'deposium_graph', 'deposium_search', 'escalate_decision']
const files = ['src/agents/deposium-agent.ts', 'src/agents/use-mastra-transport.ts',
  'src/utils/mcp-logger.ts', 'src/utils/trace-context.ts',
  'src/services/explicit-no-info-answer.ts', 'package.json', 'package-lock.json']
const sha = data => createHash('sha256').update(data).digest('hex')
try {
  const allowed = new Set(['PATH', 'LANG', 'LC_ALL', 'TZ', 'TSX_DISABLE_CACHE',
    'GIT_OPTIONAL_LOCKS', 'GIT_TERMINAL_PROMPT', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL'])
  if (Object.keys(process.env).some(key => !allowed.has(key)) || process.argv.length !== 3) {
    throw new Error('isolated_driver_required')
  }
  process.env.MASTRA_TRANSPORT = 'in-process'
  process.env.GROQ_API_KEY = 'offline-surface-probe-placeholder'
  process.env.MCP_MODE = 'true'
  process.env.NODE_ENV = 'production'
  const root = realpathSync(resolve(process.argv[2]))
  const requireFromRoot = createRequire(pathToFileURL(join(root, 'package.json')))
  const hashFiles = () => Object.fromEntries(files.map(path => [path, sha(readFileSync(join(root, path)))]))
  const sources = hashFiles()
  const packages = {}
  stage = 'loader'
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
    packages[name] = { version: metadata.version, package_json_sha256: sha(readFileSync(join(path, 'package.json'))) }
  }
  stage = 'loader'
  const loader = await import(pathToFileURL(requireFromRoot.resolve('tsx/esm/api')).href)
  unregister = loader.register({ tsconfig: false })
  stage = 'factory'
  const imported = await import(pathToFileURL(join(root, 'src/agents/deposium-agent.ts')).href)
  const agent = await imported.getDeposiumAgent()
  stage = 'catalog'
  const nativeTools = await agent.listTools()
  if (!nativeTools || Object.keys(nativeTools).sort().join('|') !== expected.join('|')) throw new Error('catalog_unexpected')
  stage = 'schema'
  const zod = await import(pathToFileURL(requireFromRoot.resolve('zod')).href)
  const tools = expected.map(name => {
    const tool = nativeTools[name]
    if (typeof tool.description !== 'string' || !tool.description.trim() || !tool.inputSchema) throw new Error('tool_invalid')
    const inputSchema = zod.toJSONSchema(tool.inputSchema)
    return { name, description: tool.description, inputSchema }
  })
  stage = 'integrity'
  if (networkAttempts || JSON.stringify(hashFiles()) !== JSON.stringify(sources)) throw new Error('probe_changed')
  result = { status: 'ok', qualification: 'native_catalog_probe_only', probe_only: true,
    cases_scored: 0, tool_executions: 0, model_calls: 0, network_attempts: networkAttempts,
    blocked_loader_ipc_attempts: blockedLoaderIpcAttempts,
    transport: 'in-process', tools, source_files_sha256: sources, runtime: { node: process.version, packages } }
} catch {
  result = { status: 'error', error: `mastra_surface_${stage}_failed`, probe_only: true,
    cases_scored: 0, tool_executions: 0, model_calls: 0, network_attempts: networkAttempts,
    blocked_loader_ipc_attempts: blockedLoaderIpcAttempts }
} finally {
  try { if (unregister) await unregister() } catch {
    result = { status: 'error', error: 'mastra_surface_cleanup_failed', probe_only: true }
  }
}
let encoded = JSON.stringify(result)
if (Buffer.byteLength(encoded, 'utf8') > 1024 * 1024) encoded = '{"status":"error","error":"mastra_surface_output_limit","probe_only":true}'
write(`${encoded}\n`)
