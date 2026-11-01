import { test, expect } from '@playwright/test';

test.describe('Argus Video Playback End-to-End Verification', () => {
  test('plays incident video clip, asserts readyState >= 3 and currentTime advances', async ({ page }) => {
    // Navigate to Review Queue where incident video is loaded
    await page.goto('/review');

    // Wait for the Review Queue workspace to load
    const videoLocator = page.locator('[data-testid="review-video-player"]');
    await expect(videoLocator).toBeVisible({ timeout: 15000 });

    // Wait for video to reach readyState >= 3 (HAVE_FUTURE_DATA or HAVE_ENOUGH_DATA)
    await page.waitForFunction(
      () => {
        const v = document.querySelector('video[data-testid="review-video-player"]') as HTMLVideoElement | null;
        return v !== null && v.readyState >= 3;
      },
      undefined,
      { timeout: 15000 }
    );

    // Verify readyState directly in browser context
    const readyState = await videoLocator.evaluate((v: HTMLVideoElement) => v.readyState);
    expect(readyState).toBeGreaterThanOrEqual(3);

    // Play the video and assert currentTime advances
    await videoLocator.evaluate(async (v: HTMLVideoElement) => {
      v.muted = true; // ensure unmuted autoplay policy does not block play in automated tests
      await v.play();
    });

    // Wait 500ms for playback progress
    await page.waitForTimeout(600);

    const currentTime = await videoLocator.evaluate((v: HTMLVideoElement) => v.currentTime);
    expect(currentTime).toBeGreaterThan(0);
  });

  test('previews test dataset sample video, asserts readyState >= 3 and playback progress', async ({ page }) => {
    // Navigate to Camera Feeder page
    await page.goto('/feeder');

    // Ensure sample catalog cards are rendered
    const sampleCard = page.locator('[data-testid^="sample-card-"]').first();
    await expect(sampleCard).toBeVisible({ timeout: 15000 });

    // Open sample preview modal using preview button
    const previewBtn = page.locator('[data-testid^="sample-preview-btn-"]').first();
    await previewBtn.click();

    // Video inside sample preview modal
    const sampleVideo = page.locator('[data-testid="sample-preview-video"]');
    await expect(sampleVideo).toBeVisible({ timeout: 15000 });

    // Wait for transcoded web MP4 readyState >= 3
    await page.waitForFunction(
      () => {
        const v = document.querySelector('video[data-testid="sample-preview-video"]') as HTMLVideoElement | null;
        return v !== null && v.readyState >= 3;
      },
      undefined,
      { timeout: 20000 }
    );

    const readyState = await sampleVideo.evaluate((v: HTMLVideoElement) => v.readyState);
    expect(readyState).toBeGreaterThanOrEqual(3);

    // Play sample video
    await sampleVideo.evaluate(async (v: HTMLVideoElement) => {
      v.muted = true;
      await v.play();
    });

    await page.waitForTimeout(600);

    const currentTime = await sampleVideo.evaluate((v: HTMLVideoElement) => v.currentTime);
    expect(currentTime).toBeGreaterThan(0);

    // Close preview modal via Escape
    await page.keyboard.press('Escape');
    await expect(sampleVideo).not.toBeVisible();
  });
});
