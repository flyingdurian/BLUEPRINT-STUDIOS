from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("qc_production_render", ROOT / "tools/qc_production_render.py")
qc = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(qc)
STAGE = Path(__file__).resolve().parent / "fixtures" / "stage_plan.json"


def make_manifest(stage):
    shots = []
    for planned in stage["shots"]:
        cues = [dict(actionId=action,startLocalFrame=i,endLocalFrameExclusive=i+1)
                for i,action in enumerate(planned["performance"]["actionIds"])]
        shots.append({**planned,"actionCues":cues,"cameraPreset":planned["camera"]["preset"],
                      "stageApproval":"APPROVED","assets":[]})
    return {"schemaVersion":"blueprint.render-manifest.v2","quality":"production",
            "productionLocked":True,"proxy":False,"standIn":None,"stagePlanStatus":"APPROVED",
            "fps":30,"width":1080,"height":1920,"totalFrames":2490,"shots":shots}


class QCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stage = json.loads(STAGE.read_text())

    def test_full_pilot_contract(self):
        manifest = make_manifest(self.stage)
        report = qc.Report()
        actions = qc.validate_timeline(manifest, self.stage, report)
        self.assertEqual(len(actions), 34)
        self.assertEqual(report.findings, [])

    def test_missing_action_rejected(self):
        manifest = make_manifest(self.stage)
        manifest["shots"][4]["actionCues"].pop()
        report = qc.Report()
        qc.validate_timeline(manifest, self.stage, report)
        self.assertIn("ACTION_CUES", {f["code"] for f in report.findings})

    def test_proxy_and_pending_approval_rejected(self):
        manifest = make_manifest(self.stage)
        manifest["proxy"] = True
        manifest["shots"][0]["stageApproval"] = "PENDING"
        report = qc.Report()
        qc.validate_timeline(manifest, self.stage, report)
        self.assertTrue({"PROXY", "SHOT_APPROVAL"}.issubset({f["code"] for f in report.findings}))

    def test_frame_trace_exact(self):
        manifest = make_manifest(self.stage)
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "render_trace.jsonl"
            with path.open("w") as f:
                for shot in manifest["shots"]:
                    for frame in range(shot["startFrame"],shot["endFrameExclusive"]):
                        started = [x["actionId"] for x in shot["actionCues"]
                                   if frame == shot["startFrame"] + x["startLocalFrame"]]
                        f.write(json.dumps({"frame":frame,"shotId":shot["shotId"],"cameraPreset":shot["cameraPreset"],
                                            "faceChannelCount":22,"socketErrors":[],"materialErrors":[],"missingTextures":[],
                                            "startedActions":started})+"\n")
            report = qc.Report()
            qc.validate_trace(path,manifest,report)
            self.assertEqual(report.findings, [])
            self.assertEqual(report.metrics["evaluatedFrames"],2490)

    def test_trace_dropped_frame_rejected(self):
        manifest = make_manifest(self.stage)
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"trace.jsonl"
            p.write_text(json.dumps({"frame":1,"shotId":"shot-001","cameraPreset":"medium_three_quarter",
                "faceChannelCount":22,"socketErrors":[],"materialErrors":[],"missingTextures":[],"startedActions":[]})+"\n")
            report=qc.Report()
            qc.validate_trace(p,manifest,report)
            self.assertIn("TRACE_COUNT",{f["code"] for f in report.findings})

    def test_staged_asset_hash(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); (root/"media").mkdir(); p=root/"media"/"blob.png";p.write_bytes(b"image")
            d=qc.sha256_file(p)
            manifest={"shots":[{"assets":[{"assetId":"a","relativePath":"media/blob.png","sha256":d}]}]}
            report=qc.Report();qc.validate_staged_assets(root,manifest,report)
            self.assertEqual(report.findings,[])
            p.write_bytes(b"tampered")
            report=qc.Report();qc.validate_staged_assets(root,manifest,report)
            self.assertIn("STAGED_HASH", {f["code"] for f in report.findings})

    def test_caption_parser(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"captions.vtt"
            p.write_text("WEBVTT\n\n1\n00:00:00.000 --> 00:00:03.999\nYou &amp; me\n\n")
            self.assertEqual(qc.parse_vtt(p), [(0,3999,"You & me")])

    def test_material_and_texture_failure_rejected(self):
        rig = json.loads((STAGE.parent / "rig_contract.json").read_text())
        face = json.loads((STAGE.parent / "face_contract.json").read_text())
        actions = {a for sh in self.stage["shots"] for a in sh["performance"]["actionIds"]}
        engine = {
            "manifestSha256": "a"*64, "engineVersion":"4.7.2.stable", "rigSha256":"b"*64,
            "rigStatus":"OWNER_APPROVED", "boneNames":rig["requiredBones"],
            "blendShapeNames":[c["name"] for c in face["channels"]],
            "executableActionIds":list(actions), "cameraPresets":[s["camera"]["preset"] for s in self.stage["shots"]],
            "skeletonBindingsOk":True,"socketsCalibrated":True,
            "surfacesValidated":5,"texturesValidated":3,
            "materialErrors":["FaceMesh material null"],"missingTextures":["Mug albedo missing"],
            "socketErrors":[],"importErrors":[],"sceneWarnings":[],
        }
        report=qc.Report()
        qc.validate_engine(engine,"a"*64,rig,face,actions,report,{"shots":[],"production":{"rigSha256":"b"*64}})
        self.assertTrue({"MATERIALERRORS","MISSINGTEXTURES"}.issubset({f["code"] for f in report.findings}))

    def test_audio_shift_is_detected(self):
        import numpy as np
        manifest=make_manifest(self.stage)
        # Each shot gets deterministic non-silent test audio. Shift encoded mix by 120ms.
        rng=np.random.default_rng(123)
        samples=rng.normal(0,1000,2490//30*2000).astype(np.float32)
        shifted=np.concatenate([np.zeros(240,dtype=np.float32),samples])[:len(samples)]
        with patch.object(qc,"pcm_decode",side_effect=[samples,shifted]):
            report=qc.Report()
            qc.validate_audio_waveform(Path("unused"),Path("unused-candidate"),manifest,report)
        self.assertIn("AUDIO_OFFSET", {f["code"] for f in report.findings})

    def test_video_pts_anomaly_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"candidate.mp4";p.write_bytes(b"mock")
            meta={"streams":[{"codec_type":"video","codec_name":"h264","pix_fmt":"yuv420p",
                              "width":1080,"height":1920,"avg_frame_rate":"30/1","nb_read_frames":"2490",
                              "duration":"83.000","color_primaries":"bt709","color_transfer":"bt709","color_space":"bt709"},
                             {"codec_type":"audio","codec_name":"aac","sample_rate":"48000","duration":"83.0"}]}
            packet_frames={"frames":[{"best_effort_timestamp_time":f"{i/30:.6f}"} for i in range(2490)]}
            packet_frames["frames"][120]["best_effort_timestamp_time"]="3.966667"
            def probe(_path,frames=False):
                return packet_frames if frames else meta
            with patch.object(qc,"ffprobe",side_effect=probe):
                report=qc.Report();qc.validate_video(p,report)
            self.assertIn("PTS_DRIFT",{f["code"] for f in report.findings})


if __name__ == "__main__":
    unittest.main()
