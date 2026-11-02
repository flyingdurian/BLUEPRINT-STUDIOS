import type { ProductionData, Shot, Asset, AssetLink } from '../types/studio'
import { FPS } from '../utils/time'

// Timing and narration faithfully match Pilot 1's approved 83-second, 14-shot V2 storyboard.
const rows = [
  [0,4,'You finally mute the family group chat. Freedom.','Close-up: thumb taps mute. Relieved smile, eyes close; hold one beat.','The mute button','relief','phone'],
  [4,10,"For eleven beautiful minutes, nobody asks if you're coming to Sunday dinner.",'Wide shot: tea sip, peaceful exhale. Clock skips eleven minutes.','Eleven minutes of peace','calm','mug'],
  [10,15,'Then your aunt calls. Calls, apparently, were not part of the treaty.','Phone insert: incoming call. Finger hesitates; one suspicious eye appears.','Aunt calling','alarm','call'],
  [15,20,"She asks why you've ignored eighty-three messages. You say you were busy.",'Medium shot: defensive smile dissolves under a growing notification counter.','83 unread messages','nervous','notifications'],
  [20,26,"Busy doing what? You look at your tea. It's suddenly a private matter.",'Tight shot: character shields mug like secret evidence, side-eyes phone.','The suspicious tea','suspicious','mug'],
  [26,32,'You promise to check the chat. There are seven restaurant options, three polls, and a fight about parking.','Phone insert: rapid scroll through restaurant cards, polls, parking argument.','The group chat','overwhelmed','chat'],
  [32,39,"You don't care which restaurant wins. You type the safest sentence in history: 'Anything works for me.'",'Medium shot: careful typing, confidently press send. Smile of misplaced triumph.','Anything works for me','hopeful','typing'],
  [39,46,'Beautiful. Neutral. Not a single opinion anyone could argue with. You put the phone down.','Symmetrical wide shot: lean back, hands behind head. Hold stillness 1.2 seconds.','A false victory','peace','sofa'],
  [46,52,"Then your aunt calls again. 'Perfect! Since you don't mind, can you call all seven places?'",'Split-screen aunt avatar and hero. Smile freezes; eyebrows leap upward.','The assignment','shock','call'],
  [52,58,"You're now checking table sizes, allergies, and whether Uncle Ray needs a quiet corner.",'Imaginary cutaway: hero behind host stand, seven phones ringing at once.','Seventh phone ringing','chaos','restaurant'],
  [58,64,'The group chat starts thanking you. You have made exactly one contribution.','Medium: thank-you messages avalanche around a deadpan hero.','Unexpected appreciation','deadpan','notifications'],
  [64,71,"You try to say you can't organize. Someone replies, 'No stress, just do your best.' That's somehow worse.",'Phone insert: failed refusal, instant reply. Thumb freezes, shoulders slump.','No stress','defeat','chat'],
  [71,77,'You muted the group chat to avoid planning dinner.','Drawer insert: phone placed inside and drawer closes; muffled buzz.','Escape attempt','resigned','drawer'],
  [77,83,"Congratulations. You're now running it. And you're not even hungry.",'Medium-to-wide: DINNER COORDINATOR badge pops onto chest. Deadpan. Cut to black.','Dinner coordinator','payoff','badge'],
] as const

const assetsArr: Asset[] = [
  { id:'ast-lead', name:'Lead Character', category:'rig', status:'Tested & Ready', currentVersion:1, color:'#c4a18a', shorthand:'RIG' },
  { id:'ast-aunt', name:'Aunt Call Avatar', category:'rig', status:'Rigging', currentVersion:2, color:'#c596bb', shorthand:'AVT' },
  { id:'ast-apartment', name:'Apartment Nook', category:'environment', status:'Tested & Ready', currentVersion:3, color:'#80979d', shorthand:'ENV' },
  { id:'ast-phone', name:'Smartphone', category:'prop', status:'Tested & Ready', currentVersion:2, color:'#6c9fbf', shorthand:'PRP' },
  { id:'ast-mug', name:'Ceramic Tea Mug', category:'prop', status:'3D Modeling', currentVersion:1, color:'#cda973', shorthand:'PRP' },
  { id:'ast-drawer', name:'Side-table Drawer', category:'prop', status:'Concept', currentVersion:1, color:'#a68e77', shorthand:'PRP' },
  { id:'ast-chat', name:'Chat UI Kit', category:'graphic', status:'Tested & Ready', currentVersion:2, color:'#82aea2', shorthand:'GFX' },
  { id:'ast-restaurant', name:'Host Stand Cutaway', category:'environment', status:'Concept', currentVersion:1, color:'#b98d9e', shorthand:'ENV' },
  { id:'ast-badge', name:'Coordinator Badge', category:'graphic', status:'Concept', currentVersion:1, color:'#dcaa70', shorthand:'GFX' },
  { id:'ast-vo', name:'Narrator VO Scratch', category:'audio', status:'Concept', currentVersion:1, color:'#aa9db9', shorthand:'VO' },
]
const autoLinks: Record<number, string[]> = {
  1:['ast-lead','ast-apartment','ast-phone','ast-chat'],
  2:['ast-lead','ast-apartment','ast-phone','ast-mug'],
  3:['ast-lead','ast-phone','ast-chat','ast-aunt'],
  4:['ast-lead','ast-phone','ast-chat'],
  5:['ast-lead','ast-phone','ast-mug','ast-apartment'],
  6:['ast-lead','ast-phone','ast-chat'],
  7:['ast-lead','ast-phone','ast-chat'],
  8:['ast-lead','ast-phone','ast-apartment'],
  9:['ast-lead','ast-phone','ast-aunt','ast-chat'],
  10:['ast-lead','ast-restaurant','ast-phone'],
  11:['ast-lead','ast-phone','ast-chat'],
  12:['ast-lead','ast-phone','ast-chat'],
  13:['ast-lead','ast-phone','ast-drawer','ast-apartment'],
  14:['ast-lead','ast-apartment','ast-badge','ast-drawer'],
}
export function createPilot(): ProductionData {
  const shots: Record<string,Shot> = {}
  const shotOrder: string[] = []
  const assets: Record<string,Asset> = Object.fromEntries(assetsArr.map(a => [a.id, {...a}]))
  const links: AssetLink[] = []
  rows.forEach(([from,to,narration,visual,notes,mood,artKey], index) => {
    const id = `shot-${String(index+1).padStart(3,'0')}`
    shotOrder.push(id)
    shots[id] = { id, code:`SH_${String(index+1).padStart(3,'0')}`, startFrame:from*FPS, durationFrames:(to-from)*FPS, narration,visual,notes,mood,artKey }
    for(const aid of autoLinks[index+1] || []) links.push({shotId:id,assetId:aid,pinnedVersion:assets[aid].currentVersion})
  })
  return { shots, shotOrder, assets, links, nextShotNumber:15 }
}
