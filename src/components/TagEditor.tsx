import { useMemo, useRef, useState } from 'react'
import { AtSign, Link2 } from 'lucide-react'
import { useStudioStore } from '../store/useStudioStore'
import type { Asset } from '../types/studio'

type Field = 'visual' | 'narration'
export function TagEditor({shotId,field,value,placeholder}:{shotId:string,field:Field,value:string,placeholder:string}) {
  const updateShot = useStudioStore(s=>s.updateShot)
  const linkAsset = useStudioStore(s=>s.linkAsset)
  const assets = useStudioStore(s=>s.assets)
  const selectShot = useStudioStore(s=>s.selectShot)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const [cursor,setCursor] = useState(0)
  const [menu,setMenu] = useState(false)
  const matching = useMemo(() => {
    const before = value.slice(0,cursor)
    const match = before.match(/(?:^|\s)@([\w-]*)$/)
    if(!match) return [] as Asset[]
    const term = match[1].replaceAll('_',' ').toLowerCase()
    return Object.values(assets).filter(a=>a.name.toLowerCase().includes(term)||a.shorthand.toLowerCase().includes(term)).slice(0,6)
  },[value,cursor,assets])
  const show = menu && matching.length>0
  function insertTag(asset:Asset) {
    const node = textarea.current
    const end = node?.selectionStart ?? cursor
    const before=value.slice(0,end)
    const match=before.match(/@([\w-]*)$/)
    if(!match) {setMenu(false);return}
    const tag=`@${asset.name.replaceAll(' ','_')}`
    const next=before.slice(0,before.length-match[0].length)+tag+' '+value.slice(end)
    updateShot(shotId,field,next);linkAsset(shotId,asset.id);setMenu(false)
    const position=before.length-match[0].length+tag.length+1
    requestAnimationFrame(()=> {if(node){node.setSelectionRange(position,position);setCursor(position)}})
  }
  return <div className="tag-editor">
    <textarea
      ref={textarea}
      aria-label={field==='visual'?'Visual cues':'Dialogue and narration'}
      placeholder={placeholder}
      spellCheck
      value={value}
      rows={field==='visual'?3:3}
      onClick={e=>{selectShot(shotId);setCursor(e.currentTarget.selectionStart)}}
      onKeyUp={e=>setCursor(e.currentTarget.selectionStart)}
      onChange={e=>{updateShot(shotId,field,e.target.value);setCursor(e.target.selectionStart);setMenu(true)}}
      onKeyDown={e=> {if(show && e.key==='Escape'){setMenu(false);e.stopPropagation()} else if(show && e.key==='Enter'){e.preventDefault();insertTag(matching[0])}}}
      onBlur={()=>window.setTimeout(()=>setMenu(false),130)}
    />
    {show && <div className="tag-menu" role="listbox" aria-label="Asset suggestions">
      <div className="tag-menu-title"><AtSign size={12}/> LINK AN ASSET</div>
      {matching.map(a=><button type="button" key={a.id} role="option" aria-selected={false} onMouseDown={e=>e.preventDefault()} onClick={()=>insertTag(a)}>
        <span className="asset-mini-dot" style={{background:a.color}}/><span>{a.name}</span><small>{a.shorthand}</small><Link2 size={12}/>
      </button>)}
    </div>}
  </div>
}
