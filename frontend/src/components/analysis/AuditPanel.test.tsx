import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuditEvent, AuditPage } from "../../api/types";
import { mockApi } from "../../test/factories";
import { AuditPanel } from "./AuditPanel";

afterEach(() => vi.unstubAllGlobals());

const event = (over: Partial<AuditEvent> = {}): AuditEvent => ({
  id: 2,
  at: "2026-10-18T01:00:00Z",
  actor: "anggota",
  action: "CLASSIFICATION_REVIEW",
  action_label: "Tinjauan klasifikasi",
  subject_type: "response_assessment",
  subject_type_label: "Klasifikasi respons",
  subject_id: 9,
  before: { assessment_id: 8, issue_stance: "PRO" },
  after: { assessment_id: 9, observation_id: 4, issue_stance: "CONTRA" },
  reason: "Sindiran, bukan dukungan.",
  ...over,
});

const page = (results: AuditEvent[], count = results.length): AuditPage => ({
  count,
  page: 1,
  page_size: 20,
  results,
  notice: "Jejak ini hanya dapat bertambah.",
});

const noop = () => undefined;

describe("AuditPanel", () => {
  it("menampilkan pelaku, alasan, dan perubahan sebelum/sesudah", async () => {
    mockApi({
      "GET /api/investigations/1/audit/?page=1&page_size=20": () => ({ body: page([event()]) }),
    });
    render(
      <AuditPanel
        investigationId={1}
        scope={null}
        onClearScope={noop}
        onOpenObservation={noop}
        onOpenFinding={noop}
      />,
    );
    const item = await screen.findByText("Tinjauan klasifikasi");
    expect(item).toBeInTheDocument();
    expect(screen.getByText(/oleh anggota/)).toBeInTheDocument();
    expect(screen.getByText("Sindiran, bukan dukungan.")).toBeInTheDocument();
    const row = document.querySelector("tr[data-field='issue_stance']") as HTMLElement;
    expect(within(row).getByText("Pro")).toBeInTheDocument();
    expect(within(row).getByText("Kontra")).toBeInTheDocument();
    expect(screen.getByText(/hanya dapat bertambah/)).toBeInTheDocument();
  });

  it("satu klik dari peristiwa menuju observasi dan temuan", async () => {
    const opened: number[] = [];
    const findings: number[] = [];
    mockApi({
      "GET /api/investigations/1/audit/?page=1&page_size=20": () => ({
        body: page([
          event(),
          event({
            id: 3,
            action: "FINDING_DRAFT",
            action_label: "Temuan dibuat",
            subject_type: "finding",
            subject_type_label: "Temuan",
            subject_id: 5,
            before: null,
            after: { finding_id: 5, title: "Pola" },
          }),
        ]),
      }),
    });
    render(
      <AuditPanel
        investigationId={1}
        scope={null}
        onClearScope={noop}
        onOpenObservation={(id) => opened.push(id)}
        onOpenFinding={(id) => findings.push(id)}
      />,
    );
    await userEvent.click(await screen.findByRole("button", { name: "Buka observasi #4" }));
    await userEvent.click(screen.getByRole("button", { name: "Buka temuan #5" }));
    expect(opened).toEqual([4]);
    expect(findings).toEqual([5]);
  });

  it("filter jenis perubahan dan cakupan objek diteruskan ke server", async () => {
    const { calls } = mockApi({
      "GET /api/investigations/1/audit/?page=1&page_size=20&subject_id=5&subject_type=finding":
        () => ({
          body: page([]),
        }),
      "GET /api/investigations/1/audit/?action=FINDING_ENDORSE&page=1&page_size=20&subject_id=5&subject_type=finding":
        () => ({
          body: page([]),
        }),
    });
    render(
      <AuditPanel
        investigationId={1}
        scope={{ subject_type: "finding", subject_id: 5 }}
        onClearScope={noop}
        onOpenObservation={noop}
        onOpenFinding={noop}
      />,
    );
    expect(await screen.findByText(/Belum ada perubahan/)).toBeInTheDocument();
    expect(screen.getByText(/Dibatasi pada satu objek/)).toBeInTheDocument();
    await userEvent.selectOptions(
      screen.getByLabelText("Filter jenis perubahan"),
      "FINDING_ENDORSE",
    );
    await screen.findByText(/Belum ada perubahan/);
    expect(calls.some((c) => c.includes("action=FINDING_ENDORSE"))).toBe(true);
  });

  it("paginasi: tombol berikutnya meminta halaman kedua", async () => {
    const { calls } = mockApi({
      "GET /api/investigations/1/audit/?page=1&page_size=20": () => ({ body: page([event()], 45) }),
      "GET /api/investigations/1/audit/?page=2&page_size=20": () => ({
        body: { ...page([event({ id: 1 })], 45), page: 2 },
      }),
    });
    render(
      <AuditPanel
        investigationId={1}
        scope={null}
        onClearScope={noop}
        onOpenObservation={noop}
        onOpenFinding={noop}
      />,
    );
    expect(await screen.findByText(/45 peristiwa, halaman 1 dari 3/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sebelumnya" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Berikutnya" }));
    expect(await screen.findByText(/halaman 2 dari 3/)).toBeInTheDocument();
    expect(calls).toContain("GET /api/investigations/1/audit/?page=2&page_size=20");
  });
});
