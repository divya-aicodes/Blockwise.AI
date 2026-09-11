import { test, expect } from "@playwright/test";

test("Complete corridor → risk → planning → simulation → playback → human decision workflow", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  await page.goto("/map");
  await expect(page.getByText("Backend connected")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Operations corridor." }),
  ).toBeVisible();
  await expect(page.locator("canvas")).toBeVisible();
  await expect(page.getByText("NDLS", { exact: true }).first()).toBeVisible();
  await page.screenshot({
    path: "test-results/corridor-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Start guided demo", exact: true })
    .click();
  await expect(page.getByText("SELECTED ASSET", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Inspect asset", exact: true })
    .click();
  await expect(page).toHaveURL(/\/asset\/AST-/);
  await page
    .getByRole("button", { name: "Calculate risk", exact: true })
    .click();
  await expect(
    page.getByText("Predicted risk class", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/asset-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Plan maintenance", exact: true })
    .click();
  const sheet = page.getByRole("dialog", { name: "Plan maintenance" });
  await expect(sheet).toBeVisible();
  await sheet.getByText("Duration override · optional").click();
  await sheet.getByLabel("Minimum duration (minutes)").fill("60");
  await sheet
    .getByRole("button", { name: "Create requirement", exact: true })
    .click();
  await expect(page).toHaveURL(/\/plan$/);
  await page
    .getByRole("button", { name: "Detect conflicts", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Check again", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Generate alternatives", exact: true })
    .click();
  await expect(page.locator(".recommended-plan")).toBeVisible({
    timeout: 65000,
  });
  await expect(page.locator(".plans-list article")).toHaveCount(5, {
    timeout: 65000,
  });
  await page
    .getByRole("checkbox", { name: "Compare", exact: true })
    .nth(0)
    .check();
  await page
    .getByRole("checkbox", { name: "Compare", exact: true })
    .nth(1)
    .check();
  await expect(
    page.getByRole("heading", { name: "Compare alternatives", exact: true }),
  ).toBeVisible();
  await page
    .locator(".recommended-plan")
    .getByRole("button", { name: "Simulate plan", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: "Open digital twin", exact: true }),
  ).toBeVisible({ timeout: 65000 });
  await expect(
    page.getByRole("heading", { name: "Simulation feedback", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/planning-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Open digital twin", exact: true })
    .click();
  await expect(page).toHaveURL(/\/twin$/);
  await expect(page.locator("canvas")).toBeVisible();
  await page
    .getByRole("button", { name: "Jump to maintenance", exact: true })
    .click();
  await expect(page.getByText("ACTIVE", { exact: true })).toBeVisible();
  await expect(
    page.getByText("MAINTENANCE ACTIVE", { exact: true }),
  ).toBeVisible();
  const before = await page.locator(".playback-time").innerText();
  await page.getByRole("button", { name: "Step forward one minute" }).click();
  await expect(page.locator(".playback-time")).not.toHaveText(before);
  await page.getByRole("button", { name: "Play playback" }).click();
  await expect(
    page.getByRole("button", { name: "Pause playback" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Pause playback" }).click();
  await page.getByLabel("Playback speed").selectOption("2");
  await page.getByRole("slider", { name: "Simulation time" }).focus();
  await page.keyboard.press("End");
  await expect(page.getByText("COMPLETED", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Jump to maintenance", exact: true })
    .click();
  await page.screenshot({
    path: "test-results/twin-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await page
    .getByRole("dialog", { name: "Review final decision" })
    .getByRole("button", { name: "Approve plan", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "MAINTENANCE PLAN APPROVED",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reject", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "PLAN REJECTED", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Modify", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "Revise maintenance requirement" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close dialog" }).click();
  for (const size of [
    { width: 1920, height: 1080 },
    { width: 1280, height: 720 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(size);
    await page.screenshot({
      path: `test-results/twin-${size.width}.png`,
      fullPage: true,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
  }
  expect(errors).toEqual([]);
});

test("Backend errors and empty pages remain usable", async ({ page }) => {
  await page.goto("/plan");
  await expect(
    page.getByText(
      "Select an asset and create a requirement to open the planning workspace.",
    ),
  ).toBeVisible();
  await page.goto("/asset/AST-99-99");
  await expect(
    page.getByRole("heading", { name: "Asset not found" }),
  ).toBeVisible();
  await page.goto("/twin");
  await expect(page.getByRole("link", { name: "Open planning" })).toBeVisible();
  await page.route("**/api/health", (route) => route.abort());
  await page.goto("/map");
  await expect(page.getByText("Backend offline")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Retry connection" }),
  ).toBeVisible();
  await page.unroute("**/api/health");
  await page.getByRole("button", { name: "Retry connection" }).click();
  await expect(page.getByText("Backend connected")).toBeVisible();
  await page.getByLabel("Search assets").fill("no matching assets");
  await expect(
    page.getByText("No assets match the current filters."),
  ).toBeVisible();
});
