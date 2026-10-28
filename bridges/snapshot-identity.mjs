/** Verify the committed snapshot before import and after execution; no backend logic. */
import { readFileSync, realpathSync, existsSync } from 'node:fs'
import { join, relative, isAbsolute } from 'node:path'
import { createHash } from 'node:crypto'

const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const required = ['src/agents/deposium-agent.ts', 'src/agents/use-mastra-transport.ts',
  'src/services/explicit-no-info-answer.ts', 'src/utils/mcp-logger.ts',
  'src/utils/trace-context.ts', 'package.json', 'package-lock.json']

export function loadSnapshotIdentity(root) {
  const manifestPath = join(root, '.deposium-snapshot.json')
  const manifestBytes = readFileSync(manifestPath)
  const manifest = JSON.parse(manifestBytes)
  const sources = manifest.files_sha256
  if (manifest.schema_version !== 'deposium.mcps-snapshot/v1'
      || !/^[0-9a-f]{40}$/.test(manifest.revision)
      || !sources || Array.isArray(sources) || typeof sources !== 'object'
      || Object.keys(sources).length > 128 || required.some(path => !Object.hasOwn(sources, path))) {
    throw new Error('snapshot_manifest_invalid')
  }
  for (const [path, digest] of Object.entries(sources)) {
    if ((!/^src\/[a-zA-Z0-9_./-]+\.(?:ts|js|json)$/.test(path)
         && !['package.json', 'package-lock.json'].includes(path))
        || path.split('/').some(part => !part || part === '.' || part === '..')
        || !/^[0-9a-f]{64}$/.test(digest)) throw new Error('snapshot_path_invalid')
  }
  const installedLock = join(root, 'node_modules/.package-lock.json')
  const verify = () => {
    if (!manifestBytes.equals(readFileSync(manifestPath))) throw new Error('snapshot_manifest_changed')
    for (const [path, digest] of Object.entries(sources)) {
      const file = realpathSync(join(root, path))
      const local = relative(root, file)
      if (isAbsolute(local) || local.startsWith('../') || sha(readFileSync(file)) !== digest) {
        throw new Error('snapshot_source_changed')
      }
    }
    const installed = existsSync(installedLock) ? sha(readFileSync(installedLock)) : null
    if (installed !== manifest.installed_package_lock_sha256) throw new Error('snapshot_dependencies_changed')
  }
  verify()
  const agent = readFileSync(join(root, required[0]), 'utf8')
  if (/\.\/deposium-graph-tool\.(?:js|ts)/.test(agent)
      && !Object.hasOwn(sources, 'src/agents/deposium-graph-tool.ts')) {
    throw new Error('snapshot_graph_helper_missing')
  }
  return { sources: Object.freeze({ ...sources }), verify }
}
