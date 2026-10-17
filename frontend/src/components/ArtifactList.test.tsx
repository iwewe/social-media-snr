import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { artifact, mockApi, runVerification, verification } from "../test/factories";
import { ArtifactList } from "./ArtifactList";

afterEach(() => vi.restoreAllMocks());
afterEach(() => vi.unstubAllGlobals());

const VERIFY = (id: number) => `POST /api/artifacts/${id}/verify/`;
const VERIFY_RUN = "POST /api/inspections/7/verify-artifacts/";

function list(artifacts = [artifact()], preservation = null as never) {
  return render(<ArtifactList runId={7} artifacts={artifacts} preservation={preservation} />);
}

describe("ArtifactList: tampilan", () => {
  it("menampilkan jenis, ukuran, dan hash (terpotong, lengkap pada title)", () => {
    const sha = "0123456789abcdef".repeat(4);
    list([artifact({ sha256: sha, size_bytes: 2048 })]);
    const table = screen.getByRole("table", { name: "Artefak" });
    expect(within(table).getByText("dom_snapshot")).toBeInTheDocument();
    expect(within(table).getByText("2.0 KiB")).toBeInTheDocument();
    expect(within(table).getByText("0123456789abcdef...")).toHaveAttribute("title", sha);
  });

  it.each([
    [100, "100 B"],
    [1536, "1.5 KiB"],
    [5 * 1024 * 1024, "5.0 MiB"],
  ])("ukuran %i byte ditulis %s", (bytes, text) => {
    list([artifact({ size_bytes: bytes })]);
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it("tanpa artefak: pesan kosong, tanpa tabel dan tanpa tombol verifikasi", () => {
    list([]);
    expect(screen.getByText("Tidak ada artefak tersimpan untuk run ini.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByRole("button", { name: /Verifikasi/ })).toBeNull();
  });

  it("selalu menyatakan batas makna hash dan syarat unduhan", () => {
    list([]);
    expect(screen.getByText(/tidak membuktikan keaslian konten platform/)).toBeInTheDocument();
    expect(screen.getByText(/hanya dapat diunduh bila hash-nya cocok/)).toBeInTheDocument();
  });

  it("melaporkan artefak yang ditolak karena tampak memuat kredensial, tanpa menyebut namanya", () => {
    list([artifact()], {
      state: "FINISHED",
      stored: 1,
      rejected_count: 2,
      failed_count: 0,
    } as never);
    expect(
      screen.getByText(/2 artefak tidak disimpan karena tampak memuat kredensial/),
    ).toBeInTheDocument();
  });

  it("tanpa artefak ditolak tidak ada catatan itu", () => {
    list([artifact()], {
      state: "FINISHED",
      stored: 1,
      rejected_count: 0,
      failed_count: 0,
    } as never);
    expect(screen.queryByText(/tidak disimpan karena/)).toBeNull();
  });
});

describe("ArtifactList: riwayat verifikasi terakhir", () => {
  it("belum pernah diverifikasi ditulis apa adanya", () => {
    list();
    expect(screen.getByText("Belum pernah diverifikasi.")).toBeInTheDocument();
  });

  it("menampilkan verifikasi terakhir dari server, termasuk yang gagal", () => {
    list([
      artifact({
        id: 1,
        last_verification: {
          result: "MATCH",
          verified_at: "2026-10-17T02:00:00Z",
          verified_by: "analis",
          purpose: "verify",
        },
      }),
      artifact({
        id: 2,
        kind: "screenshot",
        last_verification: {
          result: "MISMATCH",
          verified_at: "2026-10-17T02:05:00Z",
          verified_by: "peninjau",
          purpose: "download",
        },
      }),
    ]);
    const marks = document.querySelectorAll("[data-last-verification]");
    expect([...marks].map((m) => m.getAttribute("data-last-verification"))).toEqual([
      "MATCH",
      "MISMATCH",
    ]);
    expect(
      screen.getByText(/Terakhir: Berbeda dari saat disimpan oleh peninjau/),
    ).toBeInTheDocument();
  });
});

describe("ArtifactList: verifikasi satu artefak", () => {
  it("hash cocok: pesan sukses (status) dan siapa yang memeriksa", async () => {
    const { calls } = mockApi({ [VERIFY(1)]: () => ({ body: verification("MATCH") }) });
    list();
    await userEvent.click(
      screen.getByRole("button", { name: "Verifikasi artefak dom_snapshot #1" }),
    );
    const box = await screen.findByRole("status");
    expect(calls).toEqual([VERIFY(1)]);
    expect(within(box).getByText("Cocok")).toBeInTheDocument();
    expect(box).toHaveAttribute("data-verification", "MATCH");
    expect(box).toHaveTextContent("Diperiksa oleh analis");
    expect(screen.queryByText("Belum pernah diverifikasi.")).toBeNull();
  });

  it("hash berbeda: alert dengan kedua hash dan peringatan tidak boleh dipakai sebagai bukti", async () => {
    mockApi({ [VERIFY(1)]: () => ({ body: verification("MISMATCH") }) });
    list();
    await userEvent.click(screen.getByRole("button", { name: /Verifikasi artefak/ }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveAttribute("data-verification", "MISMATCH");
    expect(alert).toHaveTextContent("Berbeda dari saat disimpan");
    expect(alert).toHaveTextContent("tidak boleh dipakai sebagai bukti");
    expect(within(alert).getByText("aaaaaaaaaaaaaaaa...")).toHaveAttribute("title", "a".repeat(64));
    expect(within(alert).getByText("bbbbbbbbbbbbbbbb...")).toHaveAttribute("title", "b".repeat(64));
  });

  it.each([
    ["MISSING", "Berkas hilang"],
    ["UNREADABLE", "Tidak dapat diverifikasi"],
  ] as const)("hasil %s ditampilkan sebagai alert, bukan sukses", async (result, label) => {
    mockApi({ [VERIFY(1)]: () => ({ body: verification(result) }) });
    list();
    await userEvent.click(screen.getByRole("button", { name: /Verifikasi artefak/ }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(label);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("hasil segar menggantikan 'terakhir diverifikasi'", async () => {
    mockApi({ [VERIFY(1)]: () => ({ body: verification("MATCH") }) });
    list([
      artifact({
        last_verification: {
          result: "MISMATCH",
          verified_at: "2026-10-17T02:00:00Z",
          verified_by: "x",
          purpose: "verify",
        },
      }),
    ]);
    await userEvent.click(screen.getByRole("button", { name: /Verifikasi artefak/ }));
    await screen.findByRole("status");
    expect(document.querySelector("[data-last-verification]")).toBeNull();
  });

  it("galat server ditampilkan dan tidak dianggap cocok", async () => {
    mockApi({ [VERIFY(1)]: () => ({ status: 500, body: { detail: "Galat server." } }) });
    list();
    await userEvent.click(screen.getByRole("button", { name: /Verifikasi artefak/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Galat server.");
    expect(screen.queryByText("Cocok")).toBeNull();
  });

  it("tombol dikunci selama pemeriksaan berjalan", async () => {
    let release: (() => void) | undefined;
    document.cookie = "csrftoken=uji";
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            release = () =>
              resolve(
                new Response(JSON.stringify(verification("MATCH")), {
                  status: 200,
                  headers: { "Content-Type": "application/json" },
                }),
              );
          }),
      ),
    );
    list();
    await userEvent.click(screen.getByRole("button", { name: /Verifikasi artefak/ }));
    expect(screen.getByRole("button", { name: /Verifikasi artefak/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Verifikasi semua artefak" })).toBeDisabled();
    release!();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Verifikasi artefak/ })).toBeEnabled(),
    );
  });
});

describe("ArtifactList: verifikasi seluruh run", () => {
  const two = [artifact({ id: 1 }), artifact({ id: 2, kind: "manifest" })];

  it("semua cocok dan manifest konsisten", async () => {
    const { calls } = mockApi({ [VERIFY_RUN]: () => ({ body: runVerification() }) });
    list(two);
    await userEvent.click(screen.getByRole("button", { name: "Verifikasi semua artefak" }));
    const box = await screen.findByText("Semua artefak cocok dan manifest konsisten");
    expect(calls).toEqual([VERIFY_RUN]);
    const summary = box.closest("[data-run-verification]")!;
    expect(summary).toHaveAttribute("data-run-verification", "ok");
    expect(summary).toHaveTextContent("2 artefak diperiksa: 2 cocok");
    expect(summary.querySelector("[data-manifest]")).toHaveAttribute("data-manifest", "CONSISTENT");
    expect(document.querySelectorAll("tr[data-kind] [data-verification='MATCH']")).toHaveLength(2);
  });

  it("ada masalah: alert dengan ringkasan, status manifest, dan daftar masalah", async () => {
    const bad = runVerification({
      all_match: false,
      summary: { MATCH: 1, MISMATCH: 1 },
      verifications: [
        verification("MATCH", { artifact_id: 1 }),
        verification("MISMATCH", { artifact_id: 2, id: 2 }),
      ],
      manifest: {
        state: "INCONSISTENT",
        problems: ["artefak #2 (manifest) berbeda dari manifest"],
        message: {
          code: "manifest_inconsistent",
          level: "error",
          title: "Manifest tidak sesuai dengan catatan artefak",
          detail: "Salah satunya tidak utuh.",
          action: null,
        },
      },
    });
    mockApi({ [VERIFY_RUN]: () => ({ body: bad }) });
    list(two);
    await userEvent.click(screen.getByRole("button", { name: "Verifikasi semua artefak" }));
    const summary = (await screen.findByText("Ada artefak atau manifest yang bermasalah")).closest(
      "[data-run-verification]",
    )!;
    expect(summary).toHaveAttribute("data-run-verification", "problem");
    expect(summary).toHaveAttribute("role", "alert");
    expect(summary).toHaveTextContent("1 cocok, 1 berbeda dari saat disimpan");
    expect(summary.querySelector("[data-manifest]")).toHaveAttribute(
      "data-manifest",
      "INCONSISTENT",
    );
    expect(
      within(summary as HTMLElement).getByText("artefak #2 (manifest) berbeda dari manifest"),
    ).toBeInTheDocument();
    expect(
      document.querySelector("tr[data-kind='manifest'] [data-verification='MISMATCH']"),
    ).not.toBeNull();
  });

  it("manifest tidak dapat dipercaya tidak pernah ditampilkan sebagai sukses", async () => {
    const out = runVerification({
      all_match: false,
      manifest: {
        state: "UNTRUSTED",
        problems: ["manifest tidak lolos verifikasi hash"],
        message: {
          code: "manifest_untrusted",
          level: "error",
          title: "Manifest tidak dapat dipercaya",
          detail: "x",
          action: null,
        },
      },
    });
    mockApi({ [VERIFY_RUN]: () => ({ body: out }) });
    list(two);
    await userEvent.click(screen.getByRole("button", { name: "Verifikasi semua artefak" }));
    await screen.findByText("Ada artefak atau manifest yang bermasalah");
    expect(screen.queryByText("Semua artefak cocok dan manifest konsisten")).toBeNull();
  });
});

describe("ArtifactList: unduh hanya setelah verifikasi", () => {
  let clicked: { href: string | null; download: boolean }[];
  beforeEach(() => {
    clicked = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked.push({ href: this.getAttribute("href"), download: this.hasAttribute("download") });
    });
  });

  it("hash cocok: memverifikasi dulu, lalu memicu unduhan dari endpoint isi", async () => {
    const { calls } = mockApi({ [VERIFY(1)]: () => ({ body: verification("MATCH") }) });
    list();
    await userEvent.click(screen.getByRole("button", { name: "Unduh artefak dom_snapshot #1" }));
    await waitFor(() => expect(clicked).toHaveLength(1));
    expect(calls).toEqual([VERIFY(1)]); // verifikasi lebih dulu
    expect(clicked[0]).toEqual({ href: "/api/artifacts/1/content/", download: true });
  });

  it.each(["MISMATCH", "MISSING", "UNREADABLE"] as const)(
    "hasil %s: tidak mengunduh dan menampilkan alasannya",
    async (result) => {
      mockApi({ [VERIFY(1)]: () => ({ body: verification(result) }) });
      list();
      await userEvent.click(screen.getByRole("button", { name: /Unduh artefak/ }));
      expect(await screen.findByRole("alert")).toHaveAttribute("data-verification", result);
      expect(clicked).toEqual([]);
    },
  );

  it("galat saat memverifikasi: tidak mengunduh", async () => {
    mockApi({ [VERIFY(1)]: () => ({ status: 500, body: { detail: "Galat server." } }) });
    list();
    await userEvent.click(screen.getByRole("button", { name: /Unduh artefak/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Galat server.");
    expect(clicked).toEqual([]);
  });

  it("tautan sementara dilepas dari dokumen setelah dipakai", async () => {
    mockApi({ [VERIFY(1)]: () => ({ body: verification("MATCH") }) });
    list();
    await userEvent.click(screen.getByRole("button", { name: /Unduh artefak/ }));
    await waitFor(() => expect(clicked).toHaveLength(1));
    expect(document.querySelector("a[download]")).toBeNull();
  });
});
