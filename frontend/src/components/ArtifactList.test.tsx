import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { artifact } from "../test/factories";
import { ArtifactList } from "./ArtifactList";

describe("ArtifactList", () => {
  it("menampilkan jenis, ukuran, dan hash (terpotong, lengkap pada title)", () => {
    const sha = "0123456789abcdef".repeat(4);
    render(
      <ArtifactList
        artifacts={[artifact({ sha256: sha, size_bytes: 2048 })]}
        preservation={null}
      />,
    );
    const table = screen.getByRole("table", { name: "Artefak" });
    expect(within(table).getByText("dom_snapshot")).toBeInTheDocument();
    expect(within(table).getByText("2.0 KiB")).toBeInTheDocument();
    const code = within(table).getByText("0123456789abcdef...");
    expect(code).toHaveAttribute("title", sha);
  });

  it.each([
    [100, "100 B"],
    [1536, "1.5 KiB"],
    [5 * 1024 * 1024, "5.0 MiB"],
  ])("ukuran %i byte ditulis %s", (bytes, text) => {
    render(<ArtifactList artifacts={[artifact({ size_bytes: bytes })]} preservation={null} />);
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it("tanpa artefak: pesan kosong, tanpa tabel", () => {
    render(<ArtifactList artifacts={[]} preservation={null} />);
    expect(screen.getByText("Tidak ada artefak tersimpan untuk run ini.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("selalu menyatakan batas makna hash (hash bukan bukti keaslian)", () => {
    render(<ArtifactList artifacts={[]} preservation={null} />);
    expect(screen.getByText(/tidak membuktikan keaslian konten platform/)).toBeInTheDocument();
  });

  it("melaporkan artefak yang ditolak karena tampak memuat kredensial, tanpa menyebut namanya", () => {
    render(
      <ArtifactList
        artifacts={[artifact()]}
        preservation={{ state: "FINISHED", stored: 1, rejected_count: 2, failed_count: 0 }}
      />,
    );
    expect(
      screen.getByText(/2 artefak tidak disimpan karena tampak memuat kredensial/),
    ).toBeInTheDocument();
  });

  it("tanpa artefak ditolak tidak ada catatan itu", () => {
    render(
      <ArtifactList
        artifacts={[artifact()]}
        preservation={{ state: "FINISHED", stored: 1, rejected_count: 0, failed_count: 0 }}
      />,
    );
    expect(screen.queryByText(/tidak disimpan karena/)).toBeNull();
  });
});
