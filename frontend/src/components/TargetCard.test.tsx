import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Meta, Target, TargetContext } from "../api/types";
import { TargetCard } from "./TargetCard";

const meta: Meta = {
  platforms: [{ value: "x", label: "X" }],
  target_types: [{ value: "post", label: "Posting" }],
  initial_stances: [
    { value: "PRO", label: "PRO" },
    { value: "UNDETERMINED", label: "UNDETERMINED" },
  ],
};

const ctx = (version: number, note: string): TargetContext => ({
  version,
  note,
  created_at: "2026-10-16T05:00:00Z",
  created_by: "analis",
  stances: [{ proposition_id: 1, label: "P1", statement: "Perlu audit", stance: "CONTRA" }],
});

const target = (overrides: Partial<Target> = {}): Target => ({
  id: 1,
  platform: "x",
  target_type: "post",
  url: "https://twitter.com/u/status/1?s=20",
  normalized_url: "https://x.com/u/status/1",
  created_at: "2026-10-16T05:00:00Z",
  context: ctx(1, "  Catatan\nbaris dua  "),
  context_history: [ctx(1, "  Catatan\nbaris dua  ")],
  latest_inspection: null,
  ...overrides,
});

describe("TargetCard", () => {
  it("menandai target yang belum pernah diperiksa", () => {
    render(<TargetCard target={target()} meta={meta} onChanged={() => {}} />);
    const status = screen.getByText("Belum diperiksa");
    expect(status).toHaveAttribute("data-status", "not-inspected");
  });

  it("tombol inspeksi dinonaktifkan dan masing-masing punya petunjuk", () => {
    render(<TargetCard target={target()} meta={meta} onChanged={() => {}} />);
    expect(screen.getByRole("button", { name: "Inspect" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Inspect Again" })).toBeDisabled();
    expect(screen.getByLabelText("Petunjuk: Memulai inspeksi")).toBeInTheDocument();
    expect(screen.getByLabelText("Petunjuk: Inspeksi ulang")).toBeInTheDocument();
  });

  it("menampilkan catatan apa adanya dan posisi awal per proposition", () => {
    render(<TargetCard target={target()} meta={meta} onChanged={() => {}} />);
    const note = document.querySelector("p.note")!;
    expect(note.textContent).toBe("  Catatan\nbaris dua  ");
    expect(screen.getByText("CONTRA")).toBeInTheDocument();
    expect(screen.getByText(/P1:/)).toBeInTheDocument();
  });

  it("menautkan ke URL ternormalisasi dengan rel aman", () => {
    render(<TargetCard target={target()} meta={meta} onChanged={() => {}} />);
    const link = screen.getByRole("link", { name: "https://x.com/u/status/1" });
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("riwayat versi baru muncul bila ada lebih dari satu versi", async () => {
    const t = target({
      context: ctx(2, "Revisi"),
      context_history: [ctx(2, "Revisi"), ctx(1, "Awal")],
    });
    render(<TargetCard target={t} meta={meta} onChanged={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: /riwayat versi \(2\)/ }));
    const history = document.querySelector("ol") as HTMLElement;
    expect(within(history).getByText("Awal")).toBeInTheDocument();
    expect(within(history).getByText("Revisi")).toBeInTheDocument();
  });

  it("menampilkan 'sudah diperiksa' hanya bila ada data inspeksi", () => {
    const t = target({ latest_inspection: { status: "COMPLETED" } });
    render(<TargetCard target={t} meta={meta} onChanged={() => {}} />);
    expect(screen.getByText("Sudah diperiksa")).toHaveAttribute("data-status", "inspected");
  });
});
