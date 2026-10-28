/** Thin, one-request transport. All decisions belong to the pinned MCPs checkout. */
import { createRequire } from 'node:module'
import { closeSync, openSync, readFileSync, readSync, readdirSync, realpathSync, statSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, extname, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const entries = {
  'mcps.document-plan': ['src/services/chat-document-request-plan.ts', 'normalizeChatDocumentRequest'],
  'mcps.document-followup': ['src/services/chat-document-selection.ts', 'resolveDocumentFollowUp'],
  'mcps.scope-dispatch': ['src/services/scope-dispatcher.ts', 'buildScopeDispatchDecision'],
  'mcps.semantic-source-route': ['src/services/source-route-resolver.ts', 'resolveSemanticSourceRoute'],
}
const envelope = (status, output = null, error = null) => ({ status, output, raw_output: output, error })
const forbiddenInputKeys = new Set(['gold', 'expected', 'expected_output', 'reference', 'reference_output',
  'annotations', 'annotation', 'assertions', 'rationale'])
function validateJson(value, rejectAnnotations = false) {
  if (typeof value === 'number' && !Number.isFinite(value)) throw new Error('nonfinite_json')
  if (value && typeof value === 'object') {
    for (const [key, item] of Object.entries(value)) {
      if (rejectAnnotations && forbiddenInputKeys.has(key.toLowerCase())) throw new Error('reference_annotation')
      validateJson(item, rejectAnnotations)
    }
  }
}
// Resolve only package manifests with Node builtins, before loading any loader.
function resolveRuntimeRoots(requireFromRoot) {
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
      JSON.parse(readFileSync(join(packages.tsx, 'package.json'), 'utf8')).optionalDependencies?.fsevents) {
    let installed = false
    try { tsx.resolve('fsevents/package.json'); installed = true } catch {}
    if (installed) packageResolver('fsevents', tsx)
  }
  return { node: realpathSync(process.execPath), packages }
}
function sameRuntimeRoots(actual, expected) {
  return expected && typeof expected === 'object' && !Array.isArray(expected) &&
    Object.keys(expected).length === 2 && actual.node === expected.node &&
    expected.packages && typeof expected.packages === 'object' && !Array.isArray(expected.packages) &&
    Object.keys(actual.packages).length === Object.keys(expected.packages).length &&
    Object.entries(actual.packages).every(([name, root]) => Object.hasOwn(expected.packages, name) && expected.packages[name] === root)
}
function runtimeArtifacts(requireFromRoot) {
  const maxBytes = 200 * 1024 * 1024
  const maxFiles = 5000
  const files = []
  const packages = {}
  let totalBytes = 0
  const describe = (path) => {
    const stat = statSync(path, { bigint: true })
    if (!stat.isFile()) throw new Error('runtime_file_invalid')
    return { size: Number(stat.size), mtime_ns: String(stat.mtimeNs), ctime_ns: String(stat.ctimeNs),
      device: String(stat.dev), inode: String(stat.ino) }
  }
  const addFile = (owner, filename) => {
    const path = realpathSync(filename)
    const before = describe(path)
    totalBytes += before.size
    if (totalBytes > maxBytes || files.length >= maxFiles) throw new Error('runtime_hash_limit')
    const hash = createHash('sha256')
    const buffer = Buffer.alloc(1024 * 1024)
    const fd = openSync(path, 'r')
    try {
      let count
      let readBytes = 0
      while ((count = readSync(fd, buffer, 0, buffer.length, null)) > 0) {
        readBytes += count
        if (readBytes > before.size) throw new Error('runtime_file_changed')
        hash.update(buffer.subarray(0, count))
      }
      if (readBytes !== before.size) throw new Error('runtime_file_changed')
    } finally {
      closeSync(fd)
    }
    if (JSON.stringify(before) !== JSON.stringify(describe(path))) throw new Error('runtime_file_changed')
    files.push({ owner, path, ...before, sha256: hash.digest('hex') })
  }
  const addPackage = (name, resolver) => {
    const manifest = realpathSync(resolver.resolve(`${name}/package.json`))
    const root = dirname(manifest)
    const metadata = JSON.parse(readFileSync(manifest, 'utf8'))
    packages[name] = { root, version: metadata.version }
    const walk = (directory) => {
      for (const entry of readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
        if (entry.name === 'node_modules') continue
        const path = join(directory, entry.name)
        if (entry.isSymbolicLink()) throw new Error('runtime_package_symlink')
        if (entry.isDirectory()) walk(path)
        else if (entry.isFile() && (['.js', '.cjs', '.mjs', '.json', '.node'].includes(extname(path)) ||
                 (entry.name === 'esbuild' && directory === join(root, 'bin')))) addFile(name, path)
      }
    }
    walk(root)
    return { metadata, resolver: createRequire(pathToFileURL(manifest)) }
  }
  addFile('node', process.execPath)
  const tsx = addPackage('tsx', requireFromRoot)
  if (Object.keys(tsx.metadata.dependencies ?? {}).some(name => name !== 'esbuild')) throw new Error('loader_dependency_graph_changed')
  // Hash the installed loader dependency tree, never unrelated node_modules.
  const esbuild = addPackage('esbuild', tsx.resolver)
  if (Object.keys(esbuild.metadata.dependencies ?? {}).length) throw new Error('loader_dependency_graph_changed')
  const platformPackage = `@esbuild/${process.platform}-${process.arch}`
  if (!Object.hasOwn(esbuild.metadata.optionalDependencies ?? {}, platformPackage)) throw new Error('unsupported_esbuild_platform')
  addPackage(platformPackage, esbuild.resolver)
  const zod = addPackage('zod', requireFromRoot)
  if (Object.keys(zod.metadata.dependencies ?? {}).length) throw new Error('loader_dependency_graph_changed')
  if (process.platform === 'darwin' && tsx.metadata.optionalDependencies?.fsevents) {
    let installed = false
    try { tsx.resolver.resolve('fsevents/package.json'); installed = true } catch {}
    if (installed) addPackage('fsevents', tsx.resolver)
  }
  return { schema_version: 'deposium.runtime-artifacts/v1',
    hash_scope: 'node_executable; selected_whole_package_js_json_native; esbuild_binaries',
    packages, files, total_bytes: totalBytes, limits: { max_bytes: maxBytes, max_files: maxFiles } }
}
// Suppress application logging: stdout is exclusively the JSON transport.
const write = process.stdout.write.bind(process.stdout)
console.log = console.info = console.warn = console.error = () => {}
let result
try {
  const root = resolve(process.argv[2])
  const requireFromRoot = createRequire(pathToFileURL(resolve(root, 'package.json')))
  const runtimeRoots = resolveRuntimeRoots(requireFromRoot)
  if (process.argv[3] === '--resolve-runtime') {
    result = runtimeRoots
  } else {
    if (process.argv[3] === '--expected-runtime') {
      if (!process.argv[4] || Buffer.byteLength(process.argv[4], 'utf8') > 64 * 1024 ||
          !sameRuntimeRoots(runtimeRoots, JSON.parse(process.argv[4]))) throw new Error('runtime_resolution_changed')
    } else if (process.argv[3] !== undefined && process.argv[3] !== '--probe') {
      throw new Error('invalid_bridge_mode')
    }
    const api = await import(pathToFileURL(requireFromRoot.resolve('tsx/esm/api')).href)
    const unregister = api.register({ tsconfig: false })
    try {
      if (process.argv[3] === '--probe') {
        for (const [module, name] of Object.values(entries)) {
          const imported = await import(pathToFileURL(resolve(root, module)).href)
          if (typeof (imported[name] ?? imported.default?.[name]) !== 'function') throw new Error('export_missing')
        }
        result = {
          status: 'ok', runtime: {
            node: process.version,
            tsx: JSON.parse(readFileSync(requireFromRoot.resolve('tsx/package.json'), 'utf8')).version,
            zod: JSON.parse(readFileSync(requireFromRoot.resolve('zod/package.json'), 'utf8')).version,
          }, capabilities: Object.keys(entries), runtime_artifacts: runtimeArtifacts(requireFromRoot), runtime_roots: runtimeRoots,
        }
      } else {
        let bytes = 0
        const chunks = []
        for await (const chunk of process.stdin) {
          bytes += chunk.length
          if (bytes > 1024 * 1024) throw new Error('request_too_large')
          chunks.push(chunk)
        }
        const request = JSON.parse(Buffer.concat(chunks).toString('utf8'))
        if (!request || typeof request.case_id !== 'string' || !request.case_id.trim() ||
            typeof request.contract_id !== 'string' ||
            !request.input || typeof request.input !== 'object' || Array.isArray(request.input) ||
            Object.keys(request).some(key => !['case_id', 'contract_id', 'input'].includes(key))) {
          throw new Error('invalid_request')
        }
        validateJson(request.input, true)
        const entry = Object.hasOwn(entries, request.contract_id) ? entries[request.contract_id] : undefined
        if (!entry) result = envelope('unsupported', null, 'unsupported_contract')
        else {
          const imported = await import(pathToFileURL(resolve(root, entry[0])).href)
          const fn = imported[entry[1]] ?? imported.default?.[entry[1]]
          if (typeof fn !== 'function') throw new Error('export_missing')
          const raw = await fn(request.input)
          validateJson(raw)
          result = raw == null ? envelope('abstain') : envelope('ok', raw)
        }
      }
    } finally {
      await unregister()
    }
    if (!sameRuntimeRoots(resolveRuntimeRoots(requireFromRoot), runtimeRoots)) throw new Error('runtime_resolution_changed')
    if (result.runtime_artifacts && Object.entries(result.runtime_artifacts.packages).some(
      ([name, metadata]) => metadata.root !== runtimeRoots.packages[name])) throw new Error('runtime_resolution_changed')
  }
} catch {
  // Never emit exception messages, paths, stack traces, input, or ambient secrets.
  result = envelope('error', null, 'bridge_execution_failed')
}
let response
try {
  response = JSON.stringify(result)
  if (Buffer.byteLength(response, 'utf8') > 1024 * 1024) throw new Error('response_too_large')
} catch {
  response = JSON.stringify(envelope('error', null, 'bridge_execution_failed'))
}
write(`${response}\n`)
