import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { member, mockApi } from "../test/factories";
import { TeamPanel } from "./TeamPanel";

afterEach(() => vi.unstubAllGlobals());

const BASE = "/api/investigations/5/members/";
const LIST = `GET ${BASE}`;
const two = [
  member(),
  member({ user_id: 2, username: "sari", role: "MEMBER", added_by: "pemilik" }),
];

function panel(
  role: "OWNER" | "MEMBER" | "VIEWER" | "ADMIN",
  extra: Partial<Parameters<typeof TeamPanel>[0]> = {},
) {
  return render(<TeamPanel investigationId={5} role={role} username="pemilik" {...extra} />);
}

describe("TeamPanel: tampilan", () => {
  it("menampilkan anggota, peran, siapa yang menambahkan, dan penanda 'Anda'", async () => {
    mockApi({ [LIST]: () => ({ body: two }) });
    panel("OWNER");
    const table = await screen.findByRole("table", { name: "Anggota" });
    const own = table.querySelector("tr[data-member='pemilik']")!;
    expect(own).toHaveTextContent("(Anda)");
    expect(table.querySelector("tr[data-member='sari']")!).not.toHaveTextContent("(Anda)");
    expect(table.querySelector("tr[data-member='sari']")!).toHaveTextContent("pemilik"); // ditambahkan oleh
  });

  it.each(["MEMBER", "VIEWER"] as const)(
    "%s melihat tim tanpa kontrol pengelolaan",
    async (role) => {
      mockApi({ [LIST]: () => ({ body: two }) });
      panel(role);
      const table = await screen.findByRole("table", { name: "Anggota" });
      expect(within(table).queryByRole("combobox")).toBeNull();
      expect(within(table).queryByRole("button")).toBeNull();
      expect(screen.queryByRole("form", { name: "Tambah anggota" })).toBeNull();
      expect(
        screen.getByText(/Hanya Pemilik dan Super admin yang dapat mengubah tim/),
      ).toBeInTheDocument();
    },
  );

  it.each(["OWNER", "ADMIN"] as const)("%s dapat mengelola", async (role) => {
    mockApi({ [LIST]: () => ({ body: two }) });
    panel(role);
    await screen.findByRole("table", { name: "Anggota" });
    expect(screen.getByRole("form", { name: "Tambah anggota" })).toBeInTheDocument();
    expect(screen.getByLabelText("Peran sari")).toHaveValue("MEMBER");
  });

  it("galat memuat ditampilkan", async () => {
    mockApi({ [LIST]: () => ({ status: 500, body: { detail: "Galat server." } }) });
    panel("OWNER");
    expect(await screen.findByRole("alert")).toHaveTextContent("Galat server.");
  });

  it("menyediakan petunjuk peran", async () => {
    mockApi({ [LIST]: () => ({ body: two }) });
    panel("VIEWER");
    expect(await screen.findByLabelText("Petunjuk: Peran dalam tim")).toBeInTheDocument();
  });
});

describe("TeamPanel: menambah anggota", () => {
  it("mengirim nama dan peran, mengosongkan isian, memuat ulang daftar", async () => {
    let calls = 0;
    const { fetchMock } = mockApi({
      [LIST]: () => ({ body: ++calls === 1 ? [member()] : two }),
      [`POST ${BASE}`]: () => ({ status: 201, body: member({ user_id: 2, username: "sari" }) }),
    });
    panel("OWNER");
    await screen.findByRole("table", { name: "Anggota" });
    await userEvent.type(screen.getByLabelText("Nama pengguna"), "  sari  ");
    await userEvent.selectOptions(screen.getByLabelText("Peran"), "MEMBER");
    await userEvent.click(screen.getByRole("button", { name: "Tambahkan" }));
    await waitFor(() => expect(screen.getByText("sari")).toBeInTheDocument());
    const post = fetchMock.mock.calls.find((c) => c[1]?.method === "POST")!;
    expect(JSON.parse(String(post[1]?.body))).toEqual({ username: "sari", role: "MEMBER" });
    expect(screen.getByLabelText("Nama pengguna")).toHaveValue("");
  });

  it("tombol Tambahkan nonaktif selama nama kosong", async () => {
    mockApi({ [LIST]: () => ({ body: two }) });
    panel("OWNER");
    await screen.findByRole("table", { name: "Anggota" });
    expect(screen.getByRole("button", { name: "Tambahkan" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Nama pengguna"), "   ");
    expect(screen.getByRole("button", { name: "Tambahkan" })).toBeDisabled();
  });

  it.each([
    [404, "Pengguna dengan nama itu tidak ditemukan.", "user_not_found"],
    [409, "Pengguna itu sudah menjadi anggota investigasi ini.", "already_member"],
    [400, "Akun pengguna itu tidak aktif.", "inactive_user"],
  ])("galat server %i ditampilkan apa adanya", async (status, detail, code) => {
    mockApi({
      [LIST]: () => ({ body: two }),
      [`POST ${BASE}`]: () => ({ status, body: { detail, code } }),
    });
    panel("OWNER");
    await screen.findByRole("table", { name: "Anggota" });
    await userEvent.type(screen.getByLabelText("Nama pengguna"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Tambahkan" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(detail);
  });
});

describe("TeamPanel: mengubah peran dan mencabut", () => {
  it("mengubah peran lewat pilihan dan memuat ulang", async () => {
    const { calls, fetchMock } = mockApi({
      [LIST]: () => ({ body: two }),
      [`POST ${BASE}2/role/`]: () => ({
        body: member({ user_id: 2, username: "sari", role: "VIEWER" }),
      }),
    });
    panel("OWNER");
    await userEvent.selectOptions(await screen.findByLabelText("Peran sari"), "VIEWER");
    await waitFor(() => expect(calls.filter((c) => c === LIST)).toHaveLength(2));
    const post = fetchMock.mock.calls.find((c) => c[1]?.method === "POST")!;
    expect(JSON.parse(String(post[1]?.body))).toEqual({ role: "VIEWER" });
  });

  it("pencabutan meminta konfirmasi dua langkah; Batal tidak mengirim apa pun", async () => {
    const { calls } = mockApi({ [LIST]: () => ({ body: two }) });
    panel("OWNER");
    await userEvent.click(await screen.findByRole("button", { name: "Cabut sari" }));
    expect(screen.getByText("Cabut akses?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Batal" }));
    expect(screen.queryByText("Cabut akses?")).toBeNull();
    expect(calls).toEqual([LIST]);
  });

  it("konfirmasi 'Ya' mencabut dan memuat ulang tanpa memanggil onLeft untuk orang lain", async () => {
    const onLeft = vi.fn();
    const { calls } = mockApi({
      [LIST]: () => ({ body: two }),
      [`POST ${BASE}2/revoke/`]: () => ({ status: 204, body: null }),
    });
    panel("OWNER", { onLeft });
    await userEvent.click(await screen.findByRole("button", { name: "Cabut sari" }));
    await userEvent.click(screen.getByRole("button", { name: "Ya" }));
    await waitFor(() => expect(calls).toContain(`POST ${BASE}2/revoke/`));
    expect(onLeft).not.toHaveBeenCalled();
  });

  it("keluar sendiri bertanya 'Keluar dari investigasi?' dan memanggil onLeft", async () => {
    const onLeft = vi.fn();
    mockApi({
      [LIST]: () => ({ body: two }),
      [`POST ${BASE}1/revoke/`]: () => ({ status: 204, body: null }),
    });
    panel("OWNER", { onLeft });
    await userEvent.click(await screen.findByRole("button", { name: "Cabut pemilik" }));
    expect(screen.getByText("Keluar dari investigasi?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ya" }));
    await waitFor(() => expect(onLeft).toHaveBeenCalledTimes(1));
  });

  it("Pemilik terakhir: pesan server ditampilkan dan onLeft tidak dipanggil", async () => {
    const onLeft = vi.fn();
    mockApi({
      [LIST]: () => ({ body: [member()] }),
      [`POST ${BASE}1/revoke/`]: () => ({
        status: 409,
        body: { detail: "Investigasi harus memiliki setidaknya satu OWNER.", code: "last_owner" },
      }),
    });
    panel("OWNER", { onLeft });
    await userEvent.click(await screen.findByRole("button", { name: "Cabut pemilik" }));
    await userEvent.click(screen.getByRole("button", { name: "Ya" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("setidaknya satu OWNER");
    expect(onLeft).not.toHaveBeenCalled();
  });

  it("menurunkan Pemilik terakhir: pesan server ditampilkan", async () => {
    mockApi({
      [LIST]: () => ({ body: [member()] }),
      [`POST ${BASE}1/role/`]: () => ({
        status: 409,
        body: { detail: "Investigasi harus memiliki setidaknya satu OWNER.", code: "last_owner" },
      }),
    });
    panel("OWNER");
    await userEvent.selectOptions(await screen.findByLabelText("Peran pemilik"), "VIEWER");
    expect(await screen.findByRole("alert")).toHaveTextContent("setidaknya satu OWNER");
  });
});
