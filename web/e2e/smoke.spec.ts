import { expect, test, type Page } from "@playwright/test";

const price = (page: Page) => page.getByTestId("headline-price").locator("span").first();

async function settledPrice(page: Page): Promise<string> {
  await expect(price(page)).not.toHaveText(/^[…—]$/);
  return (await price(page).textContent()) ?? "";
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
});

test("prices on load and reprices on keyboard nudge", async ({ page }) => {
  const before = await settledPrice(page);
  const spot = page.locator("#spot");
  await spot.focus();
  await spot.press("Shift+ArrowUp"); // +10
  await expect(spot).toHaveValue("110.00");
  await expect(price(page)).not.toHaveText(before);
});

test("greeks toggle between cash and pure units", async ({ page }) => {
  await settledPrice(page);
  const delta = page.getByTestId("greek-delta");
  await page.getByRole("radiogroup", { name: "Greek units" }).getByRole("radio", { name: "Cash" }).click();
  await expect(delta).toContainText("EUR");
  await page.getByRole("radiogroup", { name: "Greek units" }).getByRole("radio", { name: "Pure" }).click();
  await expect(delta.locator("td").last()).toHaveText("%");
});

test("command palette switches product", async ({ page }) => {
  await settledPrice(page);
  await page.keyboard.press("ControlOrMeta+k");
  const input = page.getByPlaceholder("Type a command…");
  await expect(input).toBeVisible();
  await input.fill("european put");
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Result")).toContainText("European put");
});

test("invalid input is flagged and not sent", async ({ page }) => {
  const before = await settledPrice(page);
  const strike = page.locator("#strike");
  await strike.fill("abc");
  await expect(strike).toHaveAttribute("aria-invalid", "true");
  await expect(price(page)).toHaveText(before);
});

test("engine errors surface without breaking the UI", async ({ page }) => {
  await settledPrice(page);
  await page.locator("#expiry").fill("2000-01-01");
  await expect(page.getByRole("alert")).toContainText("matured");
});

test("profiles chart renders and switches axis", async ({ page }) => {
  await settledPrice(page);
  await page.getByRole("tab", { name: "Profiles" }).click();
  await expect(page.getByTestId("chart").locator(".main-svg").first()).toBeVisible();
  await page.getByRole("radio", { name: "vs Time" }).click();
  await expect(page.getByLabel(/Position value profile/)).toContainText("Position value");
  await page.getByRole("combobox", { name: "Profile metric" }).selectOption("gamma");
  await expect(page.getByLabel(/Gamma/).first()).toBeVisible();
});

test("heatmap renders a spot-vol grid", async ({ page }) => {
  await settledPrice(page);
  await page.getByRole("tab", { name: "Heatmap" }).click();
  await expect(page.getByTestId("chart").locator(".main-svg").first()).toBeVisible();
  await expect(page.getByLabel("Spot-vol heatmap")).toContainText("Full-revaluation PnL");
});

test("pin and compare shows input changes and greek deltas", async ({ page }) => {
  await settledPrice(page);
  await page.getByRole("button", { name: "Pin", exact: true }).click();
  const bar = page.getByTestId("compare-bar");
  await expect(bar).toContainText("No input changes yet");
  await page.locator("#spot").focus();
  await page.locator("#spot").press("Shift+ArrowUp");
  await expect(bar).toContainText("Spot 100.00 → 110.00");
  await expect(bar).toContainText("Δ value +");
  await expect(page.getByTestId("greek-delta-delta")).toHaveText(/^\+/);
  await bar.getByRole("button", { name: "Unpin" }).click();
  await expect(bar).toBeHidden();
});

test("black-76 quotes the forward and disables carry inputs", async ({ page }) => {
  await settledPrice(page);
  await page.locator("#model").selectOption("black76");
  await expect(page.locator("#dividend-yield")).toBeDisabled();
  await expect(page.getByText("Forward", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Result")).toContainText("Black-76");
});

test("implied vol recovers the input vol from the model price", async ({ page }) => {
  const shown = await settledPrice(page);
  await page.locator("#iv-target").fill(shown);
  // The headline shows 4 dp, so σ is recovered to about 1e-4 vol points.
  await expect(page.getByTestId("implied-vol")).toHaveText(/^(19\.99\d\d|20\.00\d\d)$/);
});

test("diagnostics cross-checks analytic greeks against bumps", async ({ page }) => {
  await settledPrice(page);
  await page.getByRole("tab", { name: "Diagnostics" }).click();
  await expect(page.getByText("Greek check · analytic vs bump")).toBeVisible();
  await expect(page.getByText("σ (at strike, expiry)")).toBeVisible();
});

for (const theme of ["light", "dark"] as const) {
  test(`renders in ${theme} theme`, async ({ page }) => {
    await page
      .getByRole("radiogroup", { name: "Theme" })
      .getByRole("radio", { name: theme === "light" ? "Light" : "Dark" })
      .click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    await settledPrice(page);
    await page.screenshot({ path: `test-results/shell-${theme}.png` });
  });
}
