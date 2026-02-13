import { test, expect } from "@playwright/test";

/**
 * E2E tests for the recency (posted within) filter on the Jobs page.
 *
 * Prerequisites: backend + frontend must be running, and the database should
 * contain jobs with varying posted_date values. If no services are running
 * these tests will fail with connection errors — that is expected in CI
 * without the full Docker stack.
 */

test.describe("Recency filter on Jobs page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/jobs");
    // Open the filters panel
    await page.getByRole("button", { name: /filters/i }).click();
  });

  test("recency filter dropdown is visible with correct options", async ({
    page,
  }) => {
    const select = page.getByTestId("recency-filter");
    await expect(select).toBeVisible();

    const options = select.locator("option");
    await expect(options).toHaveCount(6);
    await expect(options.nth(0)).toHaveText("Any time");
    await expect(options.nth(1)).toHaveText("Today");
    await expect(options.nth(2)).toHaveText("Last 3 days");
    await expect(options.nth(3)).toHaveText("Last 7 days");
    await expect(options.nth(4)).toHaveText("Last 2 weeks");
    await expect(options.nth(5)).toHaveText("Last 30 days");
  });

  test("selecting a recency option triggers a filtered request", async ({
    page,
  }) => {
    const requestPromise = page.waitForRequest((req) =>
      req.url().includes("/api/jobs") && req.url().includes("posted_days=7")
    );

    await page.getByTestId("recency-filter").selectOption("7");
    const request = await requestPromise;
    expect(request.url()).toContain("posted_days=7");
  });

  test("selecting 'Any time' clears the recency filter", async ({ page }) => {
    // First set a filter
    await page.getByTestId("recency-filter").selectOption("7");
    // Then clear it
    const requestPromise = page.waitForRequest(
      (req) =>
        req.url().includes("/api/jobs") && !req.url().includes("posted_days")
    );

    await page.getByTestId("recency-filter").selectOption("");
    const request = await requestPromise;
    expect(request.url()).not.toContain("posted_days");
  });

  test("reset all filters clears the recency filter", async ({ page }) => {
    await page.getByTestId("recency-filter").selectOption("3");

    const requestPromise = page.waitForRequest(
      (req) =>
        req.url().includes("/api/jobs") && !req.url().includes("posted_days")
    );

    await page.getByRole("button", { name: /reset all filters/i }).click();
    const request = await requestPromise;
    expect(request.url()).not.toContain("posted_days");

    // Verify dropdown is back to default
    await expect(page.getByTestId("recency-filter")).toHaveValue("");
  });
});
