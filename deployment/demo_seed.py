"""Seed database demo (dijalankan lewat `manage.py shell`): data SINTETIS saja, bukan data nyata."""

import os
from io import StringIO

from collection.models import InspectionRun
from collection.orchestrator.service import request_inspection, run_inspection
from django.contrib.auth.models import User
from django.core.management import call_command
from intelligence import findings as fs
from intelligence.assessment import current_assessments, review_assessment
from intelligence.models import AnalysisRun
from investigations import services as inv
from investigations import team
from investigations.enums import Platform, Role, TargetType

PW = {k: os.environ[f"PW_{k}"] for k in ("ADMIN", "OWNER", "VIEWER")}
admin = User.objects.create_superuser("demo_admin", password=PW["ADMIN"])
owner = User.objects.create_user("demo_owner", password=PW["OWNER"])
viewer = User.objects.create_user("demo_viewer", password=PW["VIEWER"])

investigation = inv.create_investigation(
    user=owner, name="Demo: kebakaran hutan (data sintetis)", description="Data sintetis untuk uji alur."
)
team.grant(investigation=investigation, user=viewer, role=Role.VIEWER, added_by=owner)
issue = inv.create_issue(
    investigation=investigation,
    user=owner,
    title="Kebakaran hutan dan tanggung jawab korporasi",
    definition="Perdebatan tentang perlunya audit terhadap perusahaan yang diduga terkait.",
)
prop = inv.add_proposition(
    issue=issue,
    user=owner,
    statement="Perusahaan yang diduga terkait kebakaran hutan itu harus diaudit.",
)
urls = [
    "https://x.com/contoh_redaksi/status/9100000001",
    "https://x.com/contoh_redaksi/status/9100010001",
    "https://x.com/contoh_redaksi/status/9100020001",
]
targets = []
for i, url in enumerate(urls):
    targets.append(
        inv.register_target(
            investigation=investigation,
            user=owner,
            platform=Platform.X,
            target_type=TargetType.POST,
            url=url,
            stances={prop: "CONTRA"} if i == 0 else {},
        )
    )
for t in targets:
    for _ in range(4):
        run = request_inspection(target=t, user=owner, enqueue=False)
        run_inspection(run.pk, claimed_by="demo-seed")
print("inspeksi:", InspectionRun.objects.values_list("status", flat=True).distinct().count(), "status berbeda")

out = StringIO()
call_command(
    "run_analyses",
    "--investigation", str(investigation.pk),
    "--proposition", str(prop.pk),
    "--user", "demo_owner",
    "--pro-cue", "harus diaudit",
    "--pro-cue", "audit harus dilakukan",
    "--contra-cue", "tidak perlu diaudit",
    "--exploratory",
    stdout=out,
)
print(out.getvalue())

# Satu koreksi klasifikasi (jejak audit).
m2 = AnalysisRun.objects.filter(investigation=investigation, method="m2-rules").latest("id")
row = current_assessments(m2).filter(needs_human_review=True).first()
if row is not None:
    review_assessment(
        assessment=row,
        by=owner,
        reason="Konteks percakapan menunjukkan sindiran, bukan ancaman.",
        issue_stance="MIXED" if row.issue_stance != "MIXED" else "PRO",
    )

# Satu temuan yang disahkan, dari indikator CO-02 (plafon confidence sintetis: Rendah).
co = AnalysisRun.objects.filter(investigation=investigation, method="co-indicators").latest("id")
edges = list(co.coordination.edges.filter(indicator="CO-02").order_by("-support")[:1])
if edges:
    obs_ids = set(edges[0].observation_ids)
    suggestion = fs.evaluate_evidence(obs_ids)["suggestions"]
    ratings = {
        axis: {"level": s["level"], "reason": f"Sesuai saran sistem: {s['reason']}"}
        for axis, s in suggestion.items()
    }
    alternatives = {
        k: {"outcome": "NOT_RULED_OUT", "reasoning": f"Dikaji untuk demo: {k} belum dapat disingkirkan dengan data ini."}
        for k in ("organic_mobilization", "external_event", "public_content_copying", "sampling_bias")
    }
    finding = fs.draft_finding(
        investigation=investigation,
        analysis_runs=[co],
        indicator_edges=edges,
        observation_ids=[],
        title="Pola waktu dan teks serupa pada beberapa akun",
        statement="Beberapa akun membalas posting yang sama dalam waktu berdekatan dengan teks yang hampir sama.",
        interpretation="Pola ini terobservasi pada data sintetis; penyebabnya belum dapat disimpulkan.",
        evidence_ratings=ratings,
        alternatives=alternatives,
        confidence="LOW",
        confidence_reason="Data sintetis dan bukti belum independen.",
        by=owner,
    )
    fs.endorse_finding(finding=finding, by=owner, note="Ditinjau untuk demo.")
print("seed selesai")
