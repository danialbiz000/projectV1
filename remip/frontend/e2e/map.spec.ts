import { expect, test } from "@playwright/test";

test.describe("interactive map", () => {
  test("loads markers for the default area and switches to heatmap", async ({ page }) => {
    await page.goto("/map");
    await expect(page.getByTestId("property-map")).toBeVisible();
    await expect(page.getByText(/immobili trovati/)).toBeVisible({ timeout: 15000 });

    await page.getByLabel("Visualizzazione").selectOption("heatmap");
    // switching layers must not error or clear the result count
    await expect(page.getByText(/immobili trovati/)).toBeVisible();
    await page.getByLabel("Visualizzazione").selectOption("markers");
  });

  test("radius search narrows results and shows the search context", async ({ page }) => {
    await page.goto("/map");
    await expect(page.getByText(/immobili trovati/)).toBeVisible({ timeout: 15000 });
    const areaCountText = await page.getByText(/immobili trovati/).innerText();
    const areaCount = Number(areaCountText.match(/(\d+) immobili/)?.[1]);
    expect(areaCount).toBeGreaterThan(0);

    await page.getByRole("button", { name: /Cerca per raggio/ }).click();
    await page.getByLabel("Raggio (km)").fill("2");
    await page.getByRole("button", { name: "Applica raggio" }).click();

    await expect(page.getByText(/raggio 2 km/)).toBeVisible();
    const radiusText = await page.getByText(/immobili trovati/).innerText();
    const radiusCount = Number(radiusText.match(/(\d+) immobili/)?.[1]);
    expect(radiusCount).toBeGreaterThanOrEqual(0);
    expect(radiusCount).toBeLessThanOrEqual(areaCount);
  });

  test("drawing a polygon on the map triggers a spatial search", async ({ page }) => {
    await page.goto("/map");
    await expect(page.getByText(/immobili trovati/)).toBeVisible({ timeout: 15000 });

    await page.getByRole("button", { name: /Disegna un'area/ }).click();
    const mapLocator = page.getByTestId("property-map");
    await mapLocator.scrollIntoViewIfNeeded();
    const box = await mapLocator.boundingBox();
    if (!box) throw new Error("map bounding box not available");
    const cx = box.x + box.width / 2;
    const cy = box.y + box.height / 2;
    await page.mouse.click(cx - 150, cy - 100);
    await page.mouse.click(cx + 150, cy - 100);
    await page.mouse.click(cx, cy + 150);

    await expect(page.getByTestId("polygon-vertex-count")).toContainText("3");
    await page.getByRole("button", { name: "Chiudi poligono e cerca" }).click();

    await expect(page.getByText(/area disegnata/)).toBeVisible();
    const drawnText = await page.getByText(/immobili trovati/).innerText();
    expect(drawnText).toMatch(/\d+ immobili trovati/);

    await page.getByRole("button", { name: "Annulla" }).click();
    await expect(page.getByRole("button", { name: /Disegna un'area/ })).toBeVisible();
  });
});
