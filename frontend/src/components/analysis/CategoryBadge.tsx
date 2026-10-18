import type { Category } from "../../api/types";
import { CATEGORY_INFO } from "../../analysis/labels";

/** Lencana konsisten untuk empat kategori hasil (FR-094): warna dan teks tidak bergantung pada halaman. */
export function CategoryBadge({
  category,
  tier,
  label,
}: {
  category: Category;
  tier?: number;
  label?: string;
}) {
  const info = CATEGORY_INFO[category];
  return (
    <span
      className="badge category"
      data-category={category}
      data-tier={tier}
      title={info.description}
    >
      {label ?? info.label}
      {tier !== undefined && <span className="tier"> · tingkat {tier}</span>}
    </span>
  );
}
