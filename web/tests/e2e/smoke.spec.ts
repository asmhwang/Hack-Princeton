import { expect, test } from "@playwright/test";

test("war room shell renders", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByText(/0 active \| \$0 at risk/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Simulate event" }).first()).toBeVisible();
  await expect(page.getByText("Scanning 47 signals")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Agent activity" })).toBeVisible();
  await expect(page.getByTestId("supply-globe-panel")).toBeVisible();
  await expect(page.getByText("Global lane map")).toBeVisible();
});

test("analytics and exec pages render", async ({ page }) => {
  await page.goto("/analytics");
  await expect(page.getByRole("heading", { name: "Exposure attribution" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Export CSV" })).toBeVisible();

  await page.goto("/exec");
  await expect(page.getByRole("heading", { name: "Supply chain posture — today" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Top active disruptions" })).toBeVisible();
});

test("globe canvas renders", async ({ page }) => {
  await page.goto("/");
  const canvas = page.getByTestId("supply-globe-panel").locator("canvas").first();
  await expect(canvas).toBeVisible();
  const box = await canvas.boundingBox();
  expect(box?.width).toBeGreaterThan(300);
  expect(box?.height).toBeGreaterThan(300);
});

test("globe is usable on mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  await expect(page.getByTestId("supply-globe-panel")).toBeVisible();
  await expect(page.getByText("Global lane map")).toBeVisible();
});
