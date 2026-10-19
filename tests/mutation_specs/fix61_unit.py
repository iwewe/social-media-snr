"""Mutasi unit aktivitas unik (satu Post = satu aktivitas) pada M3 dan M4."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

_BASE = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests -e POSTGRES_DB=snr_mut{job} web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_unique_activity.py'
COMMAND = _BASE + ' --reuse-db'
BASELINE_COMMAND = _BASE + ' --create-db'
CWD = '{origin}'
TIMEOUT = 900
P = 'backend/intelligence/profiles.py'
N = 'backend/intelligence/networks.py'
T = 'backend/intelligence/m3/profile.py'

MUTATIONS = [
    Mutation('M3: satu respons per observasi (perilaku lama)', P, '        history[a.observation.post_id].append(a)', '        history[a.observation_id].append(a)'),
    Mutation('M3: observasi terlama yang dipakai', P, '        a = versions[-1]\n', '        a = versions[0]\n'),
    Mutation('M3: urutan versi tak diurutkan menurut run', P, 'key=lambda x: (x.observation.run.sequence, x.observation_id)', 'key=lambda x: (-x.observation.run.sequence, x.observation_id)'),
    Mutation('M3: jumlah observasi riwayat hilang', P, '                observation_count=len(versions),', '                observation_count=1,'),
    Mutation('M3: varian teks tak dihitung', P, '                text_variants=len({v.observation.text for v in versions}),', '                text_variants=1,'),
    Mutation('M3: cakupan hanya run terbaru', P, '        for v in versions:  # cakupan mencatat SEMUA pemeriksaan yang berkontribusi\n            target_ids.add(v.observation.run.target_id)\n            run_ids.add(v.observation.run_id)\n', '        run_ids.add(versions[-1].observation.run_id)\n        target_ids.add(versions[-1].observation.run.target_id)\n'),
    Mutation('M3: jumlah observasi yang disatukan salah', P, '    collapsed = sum(len(versions) - 1 for versions in history.values())', '    collapsed = 0'),
    Mutation('M3: partisipasi tanpa observasi historis', T, '        "observations": sum(r.observation_count for r in records),', '        "observations": len(records),'),
    Mutation('M3: perubahan teks tak dilaporkan', T, '        "responses_with_changed_text": sum(1 for r in records if r.text_variants > 1),', '        "responses_with_changed_text": 0,'),
    Mutation('M3: unit tak dinyatakan', T, '        "unit": "satu Post = satu respons (observasi terbarunya dalam dataset)",\n', ''),
    Mutation('M4: relasi observasi lama ikut dihitung', N, '        if latest_by_post[rel["from_post_id"]]["id"] != origin["id"]:', '        if False:'),
    Mutation('M4: relasi observasi terlama yang dipakai', N, '        latest_by_post[o["post_id"]] = o', '        latest_by_post.setdefault(o["post_id"], o)'),
    Mutation('M4: relasi tergantikan tak dilaporkan', N, '    if superseded:\n        exclusions["relation_from_superseded_observation"] = superseded', '    pass'),
    Mutation('M4: relasi tergantikan salah hitung', N, '            superseded += 1\n', '            superseded += 2\n'),
    Mutation('M4: atribut posts memakai jumlah observasi', N, '"posts": per_actor_posts[actor], "observations": count', '"posts": count, "observations": count'),
    Mutation('M4: atribut observasi historis hilang', N, '"posts": per_actor_posts[actor], "observations": count', '"posts": per_actor_posts[actor], "observations": per_actor_posts[actor]'),
    Mutation('M4: stance node per observasi', N, '    for o in latest_by_post.values():\n        if o["author_id"] is not None and o["id"] in stance_by_obs:', '    for o in observations:\n        if o["author_id"] is not None and o["id"] in stance_by_obs:'),
    Mutation('M4: aturan bobot lama', N, '"jumlah Post berbeda pembentuk edge (satu Post = satu relasi, observasi terbarunya)"', '"jumlah observasi berbeda pembentuk edge"'),
    Mutation('M3 tak diberi versi baru', P, 'Method("m3-profile", "2", validate_m3_parameters, run_m3_profile)', 'Method("m3-profile", "1", validate_m3_parameters, run_m3_profile)'),
    Mutation('M4 tak diberi versi baru', N, 'Method("m4-network", "2", validate_m4_parameters, run_m4_network)', 'Method("m4-network", "1", validate_m4_parameters, run_m4_network)'),
]
