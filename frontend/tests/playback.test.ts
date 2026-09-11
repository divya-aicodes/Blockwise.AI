import { test } from "node:test";
import assert from "node:assert/strict";
import {
  trainPosition,
  simulationBounds,
  operatingDate,
  toIST,
} from "../src/lib.ts";
import type { Train, SimulationResult } from "../src/types/index.ts";
const timestamp = (clock: string) => "2026-09-09T" + clock + ":00+05:30";
const t: Train = {
  train_id: "TRN-TEST",
  priority: "HIGH",
  planned_delay_min: 10,
  additional_simulation_wait_min: 0,
  total_delay_min: 10,
  completion_status: "COMPLETED",
  section_events: [
    {
      train_id: "TRN-TEST",
      section_id: "SEC-NDLS-RE",
      scheduled_entry_time: timestamp("08:00"),
      scheduled_exit_time: timestamp("09:00"),
      simulated_entry_time: timestamp("08:10"),
      simulated_exit_time: timestamp("09:10"),
      planned_delay_min: 10,
      additional_wait_min: 0,
      delay_added_min: 10,
      total_delay_min: 10,
    },
  ],
};
test("Train waits until its returned entry timestamp then interpolates only inside occupancy", () => {
  assert.equal(trainPosition(t, Date.parse(timestamp("07:59"))), null);
  assert.equal(
    trainPosition(t, Date.parse(timestamp("08:05")))?.state,
    "WAITING",
  );
  assert.equal(
    trainPosition(t, Date.parse(timestamp("08:05")))?.waitMinutes,
    5,
  );
  assert.equal(trainPosition(t, Date.parse(timestamp("08:40")))?.km, 42);
  assert.equal(trainPosition(t, Date.parse(timestamp("09:10"))), null);
});
test("Playback always spans 24 operating hours in IST", () => {
  const bounds = simulationBounds({
    simulation_date: "2026-09-09",
  } as SimulationResult);
  assert.equal(bounds[1] - bounds[0], 86400000);
  assert.equal(bounds[0], Date.parse(timestamp("00:00")));
});
test("Operating date is resolved in IST across UTC midnight", () => {
  assert.equal(operatingDate("2026-09-08T20:00:00Z"), "2026-09-09");
  assert.equal(toIST("2026-09-09T08:00"), timestamp("08:00"));
});
