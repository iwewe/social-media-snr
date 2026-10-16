import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ContextHelp } from "./ContextHelp";
import { HELP } from "./helpTexts";

describe("ContextHelp", () => {
  it("memiliki nama yang dapat diakses dan isi dari berkas teks", () => {
    render(<ContextHelp id="reinspection" />);
    expect(screen.getByLabelText(`Petunjuk: ${HELP.reinspection.title}`)).toBeInTheDocument();
    expect(screen.getByRole("note", { hidden: true })).toHaveTextContent(HELP.reinspection.body);
  });

  it("terbuka saat diklik", async () => {
    render(<ContextHelp id="targetNote" />);
    const details = document.querySelector("details")!;
    expect(details.open).toBe(false);
    await userEvent.click(screen.getByText("?"));
    expect(details.open).toBe(true);
  });
});
