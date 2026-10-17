import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, obsPage, row } from "../test/factories";
import { ObservationTable } from "./ObservationTable";

afterEach(() => vi.unstubAllGlobals());

const URL1 = "GET /api/inspections/7/observations/?page=1&page_size=25";

describe("ObservationTable", () => {
  it("menampilkan baris mentah dengan penulis, isi, waktu, induk, dan status perubahan", async () => {
    mockApi({ [URL1]: () => ({ body: obsPage([row()]) }) });
    render(<ObservationTable runId={7} dataState="has_data" />);
    const table = await screen.findByRole("table", { name: "Respons mentah" });
    const cells = within(table);
    expect(cells.getByText("akun_a02")).toBeInTheDocument();
    expect(cells.getByText("ID a02")).toBeInTheDocument();
    expect(cells.getByText("Setuju, kajian publik perlu dilakukan.")).toBeInTheDocument();
    expect(cells.getByText("9000000001")).toBeInTheDocument();
    expect(cells.getByText("Baru")).toHaveAttribute("data-reconciliation-badge", "NEW");
    expect(screen.getByText("Menampilkan 1-1 dari 1 objek")).toBeInTheDocument();
  });

  it("nilai tidak diketahui ditulis apa adanya, bukan kosong", async () => {
    const r = row({
      external_post_id: null,
      author: {
        external_actor_id: null,
        handle: null,
        display_name: null,
        needs_verification: true,
      },
      text: null,
      published_at: null,
      parent_external_post_id: null,
      parent_unknown: true,
    });
    mockApi({ [URL1]: () => ({ body: obsPage([r]) }) });
    render(<ObservationTable runId={7} dataState="has_data" />);
    const table = await screen.findByRole("table", { name: "Respons mentah" });
    expect(within(table).getByText("tanpa ID (perlu verifikasi)")).toBeInTheDocument();
    expect(within(table).getByText("ID tidak diketahui (perlu verifikasi)")).toBeInTheDocument();
    expect(within(table).getByText("tidak tersedia")).toBeInTheDocument();
    expect(within(table).getByText("induk tidak diketahui")).toBeInTheDocument();
    expect(within(table).getAllByText("tidak diketahui").length).toBeGreaterThanOrEqual(2); // penulis + waktu
  });

  it("objek tidak teramati ditandai, dengan terakhir terlihat, dan tidak disebut dihapus", async () => {
    const r = row({
      reconciliation: "NOT_OBSERVED",
      observed_in_this_run: false,
      last_seen_run_sequence: 2,
      observed_at: null,
    });
    mockApi({ [URL1]: () => ({ body: obsPage([r]) }) });
    render(<ObservationTable runId={7} dataState="partial" />);
    const table = await screen.findByRole("table", { name: "Respons mentah" });
    expect(within(table).getByText("Tidak teramati kali ini")).toBeInTheDocument();
    expect(
      within(table).getByText(/Terakhir terlihat pada run #2; tidak muncul pada run ini\./),
    ).toBeInTheDocument();
    expect(table.textContent!.toLowerCase()).not.toContain("hapus");
    expect(table.querySelector("tr[data-observed='false']")).not.toBeNull();
  });

  it("menampilkan bukti dari sumber untuk objek yang dinyatakan tidak tersedia", async () => {
    const r = row({
      reconciliation: "CONFIRMED_UNAVAILABLE",
      observed_in_this_run: false,
      last_seen_run_sequence: 3,
      evidence: "Halaman menampilkan 'komentar telah dihapus'.",
    });
    mockApi({ [URL1]: () => ({ body: obsPage([r]) }) });
    render(<ObservationTable runId={7} dataState="has_data" />);
    expect(await screen.findByText(/Bukti dari sumber: Halaman menampilkan/)).toBeInTheDocument();
    expect(screen.getByText("Dinyatakan tidak tersedia")).toBeInTheDocument();
  });

  it("menampilkan kolom yang berubah dan jumlah bukti terkait", async () => {
    const r = row({ reconciliation: "MODIFIED", changed_fields: ["text"], artifact_ids: [4, 5] });
    mockApi({ [URL1]: () => ({ body: obsPage([r]) }) });
    render(<ObservationTable runId={7} dataState="has_data" />);
    expect(await screen.findByText(/Berubah: text\./)).toBeInTheDocument();
    expect(screen.getByText(/Bukti terkait: 2 artefak\./)).toBeInTheDocument();
  });

  it("run yang belum direkonsiliasi diberi catatan dan 'belum direkonsiliasi' per baris", async () => {
    mockApi({
      [URL1]: () => ({ body: obsPage([row({ reconciliation: null })], { reconciled: false }) }),
    });
    render(<ObservationTable runId={7} dataState="has_data" />);
    expect(await screen.findByText("belum direkonsiliasi")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("belum tersedia untuk run ini");
  });

  it("induk kosong pada posting utama ditulis '-'", async () => {
    mockApi({
      [URL1]: () => ({
        body: obsPage([row({ object_type: "post", parent_external_post_id: null })]),
      }),
    });
    render(<ObservationTable runId={7} dataState="has_data" />);
    const table = await screen.findByRole("table", { name: "Respons mentah" });
    expect(within(table).getByText("-")).toBeInTheDocument();
  });

  it("memecah halaman dan berpindah halaman", async () => {
    const page1 = Array.from({ length: 25 }, (_, i) =>
      row({ post_id: i + 1, external_post_id: `p${i + 1}` }),
    );
    const page2 = Array.from({ length: 25 }, (_, i) =>
      row({ post_id: i + 26, external_post_id: `p${i + 26}` }),
    );
    const { calls } = mockApi({
      [URL1]: () => ({ body: obsPage(page1, { count: 60 }) }),
      "GET /api/inspections/7/observations/?page=2&page_size=25": () => ({
        body: obsPage(page2, { count: 60, page: 2 }),
      }),
    });
    render(<ObservationTable runId={7} dataState="has_data" />);
    expect(await screen.findByText("Menampilkan 1-25 dari 60 objek")).toBeInTheDocument();
    expect(screen.getByText("Halaman 1 dari 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sebelumnya" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Berikutnya" }));
    expect(await screen.findByText("Menampilkan 26-50 dari 60 objek")).toBeInTheDocument();
    expect(calls).toHaveLength(2);
    expect(screen.getByText("p26")).toBeInTheDocument();
    expect(screen.queryByText("p1")).toBeNull();
  });

  it("halaman terakhir mengunci 'Berikutnya'", async () => {
    mockApi({ [URL1]: () => ({ body: obsPage([row()], { count: 1 }) }) });
    render(<ObservationTable runId={7} dataState="has_data" />);
    await screen.findByRole("table", { name: "Respons mentah" });
    expect(screen.getByRole("button", { name: "Berikutnya" })).toBeDisabled();
  });

  it.each([
    ["access_failed", "Ini bukan berarti tidak ada balasan"],
    ["partial", "jangan simpulkan tidak ada balasan"],
    ["no_data", "Tidak ada respons pada run ini."],
  ] as const)("daftar kosong pada keadaan %s dijelaskan dengan benar", async (state, text) => {
    mockApi({ [URL1]: () => ({ body: obsPage([]) }) });
    render(<ObservationTable runId={7} dataState={state} />);
    expect(await screen.findByText(new RegExp(text.replace(/[.]/g, "\\.")))).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("gagal akses tidak pernah dijelaskan sebagai 'tidak ada respons pada run ini'", async () => {
    mockApi({ [URL1]: () => ({ body: obsPage([]) }) });
    render(<ObservationTable runId={7} dataState="access_failed" />);
    await screen.findByText(/pengambilan gagal/);
    expect(screen.queryByText("Tidak ada respons pada run ini.")).toBeNull();
  });

  it("teks panjang dilipat dan teks HTML ditampilkan sebagai teks biasa", async () => {
    const long = "x".repeat(400);
    const html = row({
      post_id: 2,
      external_post_id: "h",
      text: "<script>window.hacked=1</script><b>tebal</b>",
    });
    mockApi({ [URL1]: () => ({ body: obsPage([row({ text: long }), html]) }) });
    const { container } = render(<ObservationTable runId={7} dataState="has_data" />);
    await screen.findByRole("table", { name: "Respons mentah" });
    expect(container.querySelector("details summary")!.textContent).toBe("x".repeat(300) + "...");
    expect(container.querySelector("td script")).toBeNull();
    expect(container.querySelector("td b")).toBeNull();
    expect(screen.getByText("<script>window.hacked=1</script><b>tebal</b>")).toBeInTheDocument();
  });

  it("galat memuat menampilkan alert dan 'Muat ulang' mencoba lagi", async () => {
    let fail = true;
    const { calls } = mockApi({
      [URL1]: () =>
        fail ? { status: 500, body: { detail: "Galat server." } } : { body: obsPage([row()]) },
    });
    render(<ObservationTable runId={7} dataState="has_data" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Galat server.");
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Muat ulang" }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(await screen.findByRole("table", { name: "Respons mentah" })).toBeInTheDocument();
    expect(calls).toHaveLength(2);
  });

  it("tidak menampilkan klasifikasi, stance, atau skor", async () => {
    mockApi({ [URL1]: () => ({ body: obsPage([row()]) }) });
    const { container } = render(<ObservationTable runId={7} dataState="has_data" />);
    await screen.findByRole("table", { name: "Respons mentah" });
    const heads = [...container.querySelectorAll("th")].map((th) => th.textContent!.toLowerCase());
    for (const h of heads) expect(h).not.toMatch(/stance|skor|score|klasifikasi|label/);
  });
});
