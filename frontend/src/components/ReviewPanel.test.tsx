import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, run } from "../test/factories";
import { ReviewPanel } from "./ReviewPanel";

afterEach(() => vi.unstubAllGlobals());
const ACK = "POST /api/inspections/1/acknowledge-review/";
const pendingReview = () =>
  run({
    status: "REVIEW_REQUIRED",
    data_state: "needs_review",
    review: { reasons: ["mixed_source_methods"], outcome: "COMPLETED", acknowledged: null },
  });

describe("ReviewPanel", () => {
  it("tidak tampil untuk run yang tidak memerlukan tinjauan", () => {
    const { container } = render(<ReviewPanel run={run()} onAcknowledged={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("menjelaskan akibat mengakui tinjauan dan hasil yang dipulihkan", () => {
    render(<ReviewPanel run={pendingReview()} onAcknowledged={() => {}} />);
    expect(screen.getByRole("heading", { name: "Tinjauan diperlukan" })).toBeInTheDocument();
    expect(screen.getByText(/data run tidak diubah/)).toBeInTheDocument();
    expect(screen.getByText(/\(COMPLETED\)/)).toBeInTheDocument();
  });

  it("mengirim catatan, lalu memberi tahu induk", async () => {
    const { calls, fetchMock } = mockApi({ [ACK]: () => ({ body: run() }) });
    const done = vi.fn();
    render(<ReviewPanel run={pendingReview()} onAcknowledged={done} />);
    await userEvent.type(screen.getByLabelText(/Catatan tinjauan/), "sudah dicek");
    await userEvent.click(screen.getByRole("button", { name: "Akui tinjauan" }));
    expect(calls).toEqual([ACK]);
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ note: "sudah dicek" });
    expect(done).toHaveBeenCalledTimes(1);
  });

  it("galat server ditampilkan dan induk tidak diberi tahu", async () => {
    mockApi({ [ACK]: () => ({ status: 500, body: { detail: "Galat server." } }) });
    const done = vi.fn();
    render(<ReviewPanel run={pendingReview()} onAcknowledged={done} />);
    await userEvent.click(screen.getByRole("button", { name: "Akui tinjauan" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Galat server.");
    expect(done).not.toHaveBeenCalled();
  });

  it("sudah diakui dari tempat lain: pesan tampil dan induk memuat ulang", async () => {
    mockApi({
      [ACK]: () => ({
        status: 409,
        body: { detail: "Run ini tidak sedang menunggu tinjauan.", code: "not_awaiting_review" },
      }),
    });
    const done = vi.fn();
    render(<ReviewPanel run={pendingReview()} onAcknowledged={done} />);
    await userEvent.click(screen.getByRole("button", { name: "Akui tinjauan" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("tidak sedang menunggu tinjauan");
    expect(done).toHaveBeenCalledTimes(1);
  });

  it("run yang sudah diakui menampilkan siapa, kapan, dan catatan", () => {
    const r = run({
      review: {
        reasons: [],
        outcome: "COMPLETED",
        acknowledged: { by: "peninjau", at: "2026-10-17T02:00:00Z", note: "aman" },
      },
    });
    render(<ReviewPanel run={r} onAcknowledged={() => {}} />);
    expect(screen.getByText("peninjau")).toBeInTheDocument();
    expect(screen.getByText("aman")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Akui tinjauan" })).toBeNull();
  });

  it("catatan kosong pada tinjauan yang diakui ditulis apa adanya", () => {
    const r = run({
      review: {
        reasons: [],
        outcome: "COMPLETED",
        acknowledged: { by: "p", at: "2026-10-17T02:00:00Z", note: "" },
      },
    });
    render(<ReviewPanel run={r} onAcknowledged={() => {}} />);
    expect(screen.getByText("(tanpa catatan)")).toBeInTheDocument();
  });

  it("batas panjang catatan sama dengan server", () => {
    render(<ReviewPanel run={pendingReview()} onAcknowledged={() => {}} />);
    expect(screen.getByLabelText(/Catatan tinjauan/)).toHaveAttribute("maxlength", "2000");
  });
});
