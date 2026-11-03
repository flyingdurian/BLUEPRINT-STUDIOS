#!/usr/bin/env python3
"""Validate M4-E *design contracts* against M4-C stage plan; not actual Godot assets."""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--examples', type=Path, default=Path(__file__).resolve().parent.parent / 'docs/examples')
    args = parser.parse_args()
    errors=[]
    plan=json.loads(args.plan.read_text(encoding='utf-8'))
    def get(name):return json.loads((args.examples/name).read_text(encoding='utf-8'))
    rig=get('BS-M4E-RIG-CONTRACT.json')
    face=get('BS-M4E-FACIAL-RIG.json')
    anim=get('BS-M4E-ACTION-BINDINGS.json')
    lights=get('BS-M4E-LIGHTING-PRESETS.json')
    if len(rig['requiredBones'])!=40 or len(set(rig['requiredBones']))!=40:errors.append('Expected 40 distinct canonical bones')
    channels=[r['name'] for r in face['channels']]
    if len(channels)!=22 or len(set(channels))!=22:errors.append('Expected 22 distinct facial channels')
    expressions=['relieved','polite','suspicious','confused','confident','frozen','deadpan','exhausted']
    if set(face['presets'])!=set(expressions):errors.append('All eight named facial presets required')
    for name,preset in face['presets'].items():
        for ch,value in preset['weights'].items():
            if ch not in channels or not isinstance(value,(int,float)) or not 0<=value<=1:errors.append(f'Invalid morph {name}:{ch}:{value}')
    if len(plan['shots'])!=14 or plan['totalFrames']!=2490 or plan['fps']!=30:errors.append('Stage plan must be 14 shots/2490 frames/30fps')
    expected={a for s in plan['shots'] for a in s['performance']['actionIds']}
    defined=set(anim['actionRegistry'])
    if expected!=defined:errors.append(f'Action registry difference: missing {expected-defined}, extra {defined-expected}')
    if len(expected)!=34:errors.append(f'Expected 34 unique action IDs, found {len(expected)}')
    if len(anim['shots'])!=len(plan['shots']):errors.append('Shot count mismatch')
    for p,s in zip(plan['shots'],anim['shots']):
        for k in ('shotId','code','startFrame','durationFrames'):
            if p[k]!=s[k]:errors.append(f'Wrong {k} in {p["code"]}')
        if s['cameraPreset']!=p['camera']['preset']:errors.append(f'Camera changed: {p["code"]}')
        if s['setKey']!=p['setKey']:errors.append(f'Set changed: {p["code"]}')
        if len(s['actionCues'])!=len(p['performance']['actionIds']):errors.append(f'Action cue count mismatch: {p["code"]}')
        for orig,cue in zip(p['performance']['actionIds'],s['actionCues']):
            if orig!=cue['actionId']:errors.append(f'Action reorder: {p["code"]}')
            if not 0<=cue['startLocalFrame']<cue['endLocalFrameExclusive']<=p['durationFrames']:errors.append(f'Bad local frame cue: {p["code"]}/{orig}')
        if s['initialFacePose'] not in face['presets']:errors.append(f'Unknown facial preset: {p["code"]}')
        if s['lightingPreset'] not in lights['presets']:errors.append(f'Unknown light preset: {p["code"]}')
    print(f'M4-E design validation: bones={len(rig["requiredBones"])} morphs={len(channels)} presets={len(face["presets"])} actions={len(defined)} shots={len(plan["shots"])} frames={plan["totalFrames"]}')
    for e in errors:print('ERROR:',e)
    print('RESULT:', 'FAIL' if errors else 'PASS (design only, no Godot runtime or art approval)')
    return int(bool(errors))

if __name__=='__main__':sys.exit(main())
