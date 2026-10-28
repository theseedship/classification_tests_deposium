/** Persistent transport of the pinned application's exports; no routing rules. */
import { createRequire } from 'node:module'
import { readFileSync, realpathSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { performance } from 'node:perf_hooks'

const MAX_LINE = 1024 * 1024
const entries = {
  'mcps.document-plan': ['src/services/chat-document-request-plan.ts', 'normalizeChatDocumentRequest'],
  'mcps.document-followup': ['src/services/chat-document-selection.ts', 'resolveDocumentFollowUp'],
  'mcps.scope-dispatch': ['src/services/scope-dispatcher.ts', 'buildScopeDispatchDecision'],
  'mcps.semantic-source-route': ['src/services/source-route-resolver.ts', 'resolveSemanticSourceRoute'],
}
const write = process.stdout.write.bind(process.stdout)
process.stdout.write = () => true
console.log = console.info = console.warn = console.error = () => {}
const emit = async value => {
  const line = `${JSON.stringify(value)}\n`
  if (Buffer.byteLength(line) > MAX_LINE) throw new Error('response_too_large')
  await new Promise((done, reject) => write(line, error => error ? reject(error) : done()))
}
const forbidden = new Set(['gold', 'expected', 'expected_output', 'reference', 'reference_output',
  'annotations', 'annotation', 'assertions', 'rationale'])
function validateJson(value, input = false) {
  if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('nonfinite_json')
  if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      if (input && forbidden.has(key.toLowerCase())) throw new Error('reference_annotation')
      validateJson(child, input)
    }
  }
}
function runtimeRoots(requireFromRoot) {
  const packages = {}
  const packageResolver = (name, resolver) => {
    const manifest = realpathSync(resolver.resolve(`${name}/package.json`))
    packages[name] = dirname(manifest)
    return createRequire(pathToFileURL(manifest))
  }
  const tsx = packageResolver('tsx', requireFromRoot)
  const esbuild = packageResolver('esbuild', tsx)
  packageResolver(`@esbuild/${process.platform}-${process.arch}`, esbuild)
  packageResolver('zod', requireFromRoot)
  if (process.platform === 'darwin' &&
      JSON.parse(readFileSync(resolve(packages.tsx, 'package.json'), 'utf8')).optionalDependencies?.fsevents) {
    let installed = false
    try { tsx.resolve('fsevents/package.json'); installed = true } catch {}
    if (installed) packageResolver('fsevents', tsx)
  }
  return { node: realpathSync(process.execPath), packages }
}
function sameRoots(actual, expected) {
  return expected && typeof expected === 'object' && !Array.isArray(expected) &&
    Object.keys(expected).length === 2 && actual.node === expected.node &&
    expected.packages && typeof expected.packages === 'object' && !Array.isArray(expected.packages) &&
    Object.keys(actual.packages).length === Object.keys(expected.packages).length &&
    Object.entries(actual.packages).every(([name, root]) => expected.packages[name] === root)
}

let unregister
try {
  const start = performance.now()
  const root = resolve(process.argv[2])
  const expected = JSON.parse(process.argv[3])
  const requireFromRoot = createRequire(pathToFileURL(resolve(root, 'package.json')))
  const checkRoots = () => {
    if (!sameRoots(runtimeRoots(requireFromRoot), expected)) throw new Error('runtime_resolution_changed')
  }
  checkRoots()
  const api = await import(pathToFileURL(requireFromRoot.resolve('tsx/esm/api')).href)
  unregister = api.register({ tsconfig: false })
  const functions = {}
  for (const [id, [module, name]] of Object.entries(entries)) {
    const imported = await import(pathToFileURL(resolve(root, module)).href)
    const fn = imported[name] ?? imported.default?.[name]
    if (typeof fn !== 'function') throw new Error('export_missing')
    functions[id] = fn
  }
  checkRoots()
  await emit({ status: 'ready', worker_load_ms: performance.now() - start, capabilities: Object.keys(entries) })
  let buffer = Buffer.alloc(0)
  let expectedSequence = 1
  for await (const chunk of process.stdin) {
    buffer = Buffer.concat([buffer, chunk])
    let end
    while ((end = buffer.indexOf(10)) >= 0) {
      const line = buffer.subarray(0, end)
      buffer = buffer.subarray(end + 1)
      if (line.length + 1 > MAX_LINE) throw new Error('request_too_large')
      let request
      let result
      try {
        request = JSON.parse(line.toString('utf8'))
        if (!request || Object.keys(request).sort().join(',') !== 'contract_id,input,op,sequence' ||
            request.op !== 'predict' || !Number.isSafeInteger(request.sequence) ||
            request.sequence !== expectedSequence || typeof request.contract_id !== 'string' ||
            !request.input || typeof request.input !== 'object' || Array.isArray(request.input)) {
          throw new Error('request_invalid')
        }
        expectedSequence++
        validateJson(request.input, true)
        checkRoots()
        const fn = Object.hasOwn(functions, request.contract_id) ? functions[request.contract_id] : null
        if (!fn) result = { status: 'unsupported', output: null, raw_output: null, error: 'unsupported_contract' }
        else {
          // The common engine boundary starts from decoded JSON, before the call.
          const start = performance.now()
          const raw = await fn(request.input)
          validateJson(raw)
          const status = raw == null ? 'abstain' : 'ok'
          const output = raw == null ? null : raw
          const decision_ms = performance.now() - start
          result = { status, output, raw_output: { decision: output, timings: { decision_ms } }, error: null }
        }
        checkRoots()
      } catch {
        result = { status: 'error', output: null, raw_output: null, error: 'bridge_execution_failed' }
      }
      await emit({ sequence: Number.isSafeInteger(request?.sequence) ? request.sequence : 0, ...result })
    }
    if (buffer.length >= MAX_LINE) throw new Error('request_too_large')
  }
  if (buffer.length) throw new Error('incomplete_request')
} catch {
  // Error identifiers only; no exception, path, input, secret or application log.
  await emit({ status: 'error', error: 'bridge_initialization_or_transport_failed' }).catch(() => {})
  process.exitCode = 2
} finally {
  if (unregister) await unregister()
}
