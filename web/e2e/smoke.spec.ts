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
