"""Mutasi generator dataset sintetis I2 (WP-2.0). Tidak butuh basis data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mutate import Mutation  # noqa: E402

COMMAND = 'docker compose run --rm -T -v {root}/backend:/app -v {root}/tests:/tests web pytest -c pyproject.toml -q -x -n0 -p no:cacheprovider ../tests/test_synthetic_dataset.py'
CWD = '{origin}'
TIMEOUT = 300
G = 'backend/intelligence/synthetic/generator.py'

MUTATIONS = [
    Mutation('jendela K melebar', G, 'offset = trigger + rng.randint(0, 90)', 'offset = trigger + rng.randint(0, 900)'),
    Mutation('anggota K berkurang', G, 'members = rng.sample(COORDINATED, 8)', 'members = rng.sample(COORDINATED, 6)'),
    Mutation('ledakan organik berkurang', G, 'burst_pool = rng.sample(ORGANIC_PRO + ORGANIC_CONTRA, 8)', 'burst_pool = rng.sample(ORGANIC_PRO + ORGANIC_CONTRA, 5)'),
    Mutation('ledakan organik melambat', G, '            rng.randint(60, 480),', '            rng.randint(60, 48000),'),
    Mutation('setuju mengikuti seed, bukan induk', G, '_truth(ps, SUPPORT, ["RC-01"]),', '_truth(cfg.seed_stance, SUPPORT, ["RC-01"]),'),
    Mutation('tidak setuju tidak membalik stance', G, '_truth(_flip(ps), OPPOSE, ["RC-03"]),', '_truth(ps, OPPOSE, ["RC-03"]),'),
    Mutation('ancaman tanpa tinjauan manusia', G, 'group="attacker", human_review=True', 'group="attacker", human_review=False'),
    Mutation('Lampiran A R2 membalas seed', G, '"t1-c2",\n            "s07",\n            4200,\n            "Setuju sekali!",\n            "t1-c1",', '"t1-c2",\n            "s07",\n            4200,\n            "Setuju sekali!",\n            seed_key,'),
    Mutation('Lampiran A R5 tanpa sentimen', G, 'sentiment="NEGATIVE"),\n            "A-R5",', 'sentiment=None),\n            "A-R5",'),
    Mutation('kritik sah dilabeli serangan', G, '_truth(UNDETERMINED, OPPOSE, ["RC-02"]),\n            "AT-10-kritik-sah",', '_truth(UNDETERMINED, OPPOSE, ["RC-05"]),\n            "AT-10-kritik-sah",'),
    Mutation('edit muncul terlalu dini', G, 'k >= 3 and o["text"]', 'k >= 2 and o["text"]'),
    Mutation('putaran parsial tidak ditandai', G, 'if k == 3 and gone_partial:', 'if False and gone_partial:'),
    Mutation('pernyataan tidak tersedia terlalu dini', G, 'if k == 4 and gone_confirmed:', 'if k == 3 and gone_confirmed:'),
    Mutation('objek hilang di putaran salah', G, '        if k == 3:\n            omit |= {e.key for e in gone_partial}', '        if k == 2:\n            omit |= {e.key for e in gone_partial}'),
    Mutation('induk boleh hilang', G, ' and e.key not in parent_keys', ''),
    Mutation('akun TikTok sama dengan akun X', G, '"actor": "tt-1",', '"actor": shared_handle_actor,'),
    Mutation('handle TikTok tidak sama', G, '"handle": f"akun_{shared_handle_actor}",', '"handle": "akun_tt_beda",'),
    Mutation('akun cakupan-sebagian muncul di mana-mana', G, 'ASKERS = [f"s{i:02d}" for i in range(25, 31)]', 'ASKERS = [f"s{i:02d}" for i in range(25, 31)] + ["s47"]'),
    Mutation('seed diabaikan', G, 'random.Random(f"{seed}-{cfg.n}")', 'random.Random(f"{cfg.n}")'),
    Mutation('jumlah balasan berkurang', G, 'REPLIES_PER_TARGET = 100', 'REPLIES_PER_TARGET = 60'),
]
