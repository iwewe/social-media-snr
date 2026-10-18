import { describe, expect, it } from "vitest";

import { queryString } from "./query";

describe("queryString", () => {
  it("mengurutkan kunci dan membuang nilai kosong", () => {
    expect(queryString({ page_size: 25, a: "x", empty: "", nul: null, undef: undefined })).toBe(
      "?a=x&page_size=25",
    );
  });
  it("kosong bila tak ada parameter", () => {
    expect(queryString({ a: "" })).toBe("");
  });
  it("mempertahankan nilai false dan 0", () => {
    expect(queryString({ b: false, n: 0 })).toBe("?b=false&n=0");
  });
  it("meng-encode nilai", () => {
    expect(queryString({ q: "a b&c" })).toBe("?q=a%20b%26c");
  });
});
