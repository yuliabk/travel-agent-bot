const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript')
let missing = false
const exportsObject = {}
const code = ts.transpileModule(fs.readFileSync(path.resolve(__dirname,'../app/api/map-route/route.ts'),'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
vm.runInNewContext(code,{exports:exportsObject,Response,URLSearchParams,require:()=>({geocodePlaces:async(names,city)=>names.slice(0,missing?1:undefined).map((name,i)=>({name,lat:50+i,lng:19+i}))})})
async function main(){
 const result=await exportsObject.POST({json:async()=>({places:['First','Second'],destination:'Krakow'})})
 const data=await result.json(),url=new URL(data.url)
 assert.equal(url.searchParams.get('origin'),'50,19');assert.equal(url.searchParams.get('destination'),'51,20')
 assert.ok(!data.url.includes('undefined'))
 missing=true
 const failure=await exportsObject.POST({json:async()=>({places:['First','Missing'],destination:'Krakow'})})
 assert.equal(failure.status,422);assert.equal((await failure.json()).url,undefined)
 console.log('Verified coordinate route and unresolved-place regression tests passed')
}
main().catch(e=>{console.error(e);process.exitCode=1})
