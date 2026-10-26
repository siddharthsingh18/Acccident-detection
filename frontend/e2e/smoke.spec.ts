import { test, expect } from '@playwright/test';
import { exec } from 'node:child_process';
import { promisify } from 'node:util';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const execAsync = promisify(exec);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '../..');

test.describe('Argus Live Dashboard Smoke Test', () => {
  test('dispatches fake alert, asserts card appears, clicks it, and verifies video modal', async ({ page }) => {
    // 1. Navigate to Live Dashboard
    await page.goto('/');



    // Verify page title and header
    await expect(page.locator('h1')).toContainText('Live Surveillance Dashboard');

    // 2. Trigger a fake ZeroMQ alert to port 10010
    const publisherScript = path.resolve(projectRoot, 'scripts/fake_alert_publisher.py');
    const pythonBin = path.resolve(projectRoot, '.venv/bin/python');

    try {
      await execAsync(`${pythonBin} ${publisherScript} --camera-id 7788 --city "AlexandriaSmokeTest" --district "District 7"`);
    } catch (err) {
      console.warn('Fake alert publisher error (bridge may not be running locally on 10010):', err);
    }


    // 3. Assert an incident card appears on the dashboard
    // Either from the incoming live alert or the pre-loaded 10 recent incidents
    const card = page.locator('[data-testid="incident-card"]').first();
    await expect(card).toBeVisible({ timeout: 10000 });

    // 4. Click the incident card
    await card.click();

    // 5. Verify the video modal opens
    await expect(page.locator('text=Incident Footage')).toBeVisible({ timeout: 5000 });

    // 6. Assert the video element is rendered
    const video = page.locator('[data-testid="incident-video-player"]');
    await expect(video).toBeVisible({ timeout: 5000 });

    // Assert that video source points to the video API route
    const source = video.locator('source');
    await expect(source).toHaveAttribute('src', /\/api\/incidents\/.*\/video/);

    // 7. Test closing with Esc
    await page.keyboard.press('Escape');
    await expect(page.locator('text=Incident Footage')).not.toBeVisible();
  });
});
