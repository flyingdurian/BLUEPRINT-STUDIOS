/** Standalone proof of seed integrity. Requires TypeScript, installed by npm install.
 * It evaluates only the local data/time source files, not the React application.
 */
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
const require=createRequire(import.meta.url)
const ts=require('typescript')
const root=path.resolve('src')
function transpile(file) { return ts.transpileModule(fs.readFileSync(path.join(root,file),'utf8'), {fileName:file, compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText }
const time={exports:{}}
new Function('require','module','exports',transpile('utils/time.ts'))(require,time,time.exports)
const data={exports:{}}
new Function('require','module','exports',transpile('data/pilot.ts'))((n)=> n==='../utils/time'?time.exports:require(n), data,data.exports)
const pilot=data.exports.createPilot()
if(pilot.shotOrder.length!==14)throw new Error('Expected 14 shots')
let end=0
for(const id of pilot.shotOrder){const s=pilot.shots[id];if(s.startFrame!==end)throw new Error(`Gap/overlap before ${s.code}`);end+=s.durationFrames}
if(end!==2490)throw new Error(`Wrong frame count: ${end}`)
for(const l of pilot.links)if(!pilot.shots[l.shotId]||!pilot.assets[l.assetId])throw new Error('Dangling asset link')
console.log(`PASS: ${pilot.shotOrder.length} original shots, ${end} frames at 30 FPS, ${pilot.links.length} valid asset relationships`)
