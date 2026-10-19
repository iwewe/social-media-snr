import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Issue } from "../api/types";
import { mockApi } from "../test/factories";
import { IssueContext } from "./IssueContext";

afterEach(() => vi.unstubAllGlobals());

const v = (version: number, definition: string, by = "pemilik") => ({
  version,
  definition,
  created_at: "2026-10-19T01:00:00Z",
  created_by: by,
});
const issue = (history = [v(1, "Definisi awal.")]): Issue => ({
  id: 5,
  title: "Isu",
  created_at: "2026-10-19T00:00:00Z",
  context: { version: history[0].version, definition: history[0].definition },
  context_history: history,
  propositions: [],
});

describe("IssueContext", () => {
  it("menampilkan definisi dan versi terkini", () => {
    render(<IssueContext issue={issue()} writable={false} onRevised={() => undefined} />);
    expect(screen.getByText("Definisi awal.")).toBeInTheDocument();
    expect(screen.getByText("Konteks versi 1.")).toBeInTheDocument();
  });

  it("Pembaca tidak melihat tombol revisi", () => {
    render(<IssueContext issue={issue()} writable={false} onRevised={() => undefined} />);
    expect(screen.queryByRole("button", { name: "Revisi konteks isu" })).toBeNull();
  });

  it("Anggota merevisi: formulir terisi definisi saat ini, kiriman memuat definisi baru, lalu memuat ulang", async () => {
    let sent: unknown;
    mockApi({
      "POST /api/issues/5/context-versions/": (body) => {
        sent = body;
        return { status: 201, body: {} };
      },
    });
    const onRevised = vi.fn();
    render(<IssueContext issue={issue()} writable onRevised={onRevised} />);
    await userEvent.click(screen.getByRole("button", { name: "Revisi konteks isu" }));
    const box = screen.getByLabelText("Definisi / arahan konteks");
    expect(box).toHaveValue("Definisi awal.");
    await userEvent.clear(box);
    await userEvent.type(box, "Definisi baru.");
    expect(screen.getByText(/belum dibaca klasifier mesin/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Simpan revisi" }));
    await vi.waitFor(() => expect(onRevised).toHaveBeenCalled());
    expect(sent).toEqual({ definition: "Definisi baru." });
    expect(screen.queryByRole("form", { name: /Revisi konteks/ })).toBeNull();
  });

  it("galat server ditampilkan dan formulir tetap terbuka", async () => {
    mockApi({
      "POST /api/issues/5/context-versions/": () => ({
        status: 400,
        body: {
          detail: "Definisi sama dengan versi terbaru; tidak ada yang direvisi.",
          code: "InvalidContext",
        },
      }),
    });
    const onRevised = vi.fn();
    render(<IssueContext issue={issue()} writable onRevised={onRevised} />);
    await userEvent.click(screen.getByRole("button", { name: "Revisi konteks isu" }));
    await userEvent.click(screen.getByRole("button", { name: "Simpan revisi" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("tidak ada yang direvisi");
    expect(onRevised).not.toHaveBeenCalled();
    expect(screen.getByRole("form", { name: /Revisi konteks/ })).toBeInTheDocument();
  });

  it("Batal menutup formulir tanpa mengirim apa pun", async () => {
    const { calls } = mockApi({});
    render(<IssueContext issue={issue()} writable onRevised={() => undefined} />);
    await userEvent.click(screen.getByRole("button", { name: "Revisi konteks isu" }));
    await userEvent.click(screen.getByRole("button", { name: "Batal" }));
    expect(screen.queryByRole("form", { name: /Revisi konteks/ })).toBeNull();
    expect(calls).toEqual([]);
  });

  it("riwayat hanya muncul bila ada lebih dari satu versi dan memuat semua versi", async () => {
    const one = render(<IssueContext issue={issue()} writable onRevised={() => undefined} />);
    expect(screen.queryByRole("button", { name: /riwayat konteks/ })).toBeNull();
    one.unmount();
    render(
      <IssueContext
        issue={issue([v(2, "Revisi.", "anggota"), v(1, "Awal.")])}
        writable
        onRevised={() => undefined}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Lihat riwayat konteks \(2\)/ }));
    const list = screen.getByRole("list", { name: "Riwayat konteks isu" });
    expect(list).toHaveTextContent("Versi 2");
    expect(list).toHaveTextContent("Revisi.");
    expect(list).toHaveTextContent("Versi 1");
    expect(list).toHaveTextContent("Awal.");
    expect(list).toHaveTextContent("anggota");
  });

  it("definisi kosong ditampilkan jujur, bukan teks palsu", () => {
    render(<IssueContext issue={issue([v(1, "")])} writable={false} onRevised={() => undefined} />);
    expect(screen.getByText("Belum ada definisi konteks.")).toBeInTheDocument();
  });

  it("membuka ulang formulir setelah dibatalkan menampilkan definisi saat ini, bukan draf lama", async () => {
    render(<IssueContext issue={issue()} writable onRevised={() => undefined} />);
    await userEvent.click(screen.getByRole("button", { name: "Revisi konteks isu" }));
    await userEvent.type(screen.getByLabelText("Definisi / arahan konteks"), " draf yang dibuang");
    await userEvent.click(screen.getByRole("button", { name: "Batal" }));
    await userEvent.click(screen.getByRole("button", { name: "Revisi konteks isu" }));
    expect(screen.getByLabelText("Definisi / arahan konteks")).toHaveValue("Definisi awal.");
  });
});
