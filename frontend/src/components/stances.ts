import type { InitialStance, StanceInput } from "../api/types";

export type StanceChoices = Record<number, InitialStance | "">;

export function toStanceInput(choices: StanceChoices): StanceInput[] {
  return Object.entries(choices)
    .filter(([, stance]) => stance !== "")
    .map(([proposition, stance]) => ({
      proposition: Number(proposition),
      stance: stance as InitialStance,
    }));
}
