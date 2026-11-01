import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { VideoPlayer, mapMediaErrorCode } from '@/components/VideoPlayer';

describe('VideoPlayer and mapMediaErrorCode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('mapMediaErrorCode', () => {
    it('maps code 1 (aborted) to human message', () => {
      expect(mapMediaErrorCode(1)).toContain('aborted by the browser');
    });

    it('maps code 2 (network) to human message', () => {
      expect(mapMediaErrorCode(2)).toContain('Network error');
    });

    it('maps code 3 (decode) to human message', () => {
      expect(mapMediaErrorCode(3)).toContain('Decoding error');
    });

    it('maps code 4 (unsupported format/codec) to human message', () => {
      expect(mapMediaErrorCode(4)).toContain('format or codec is not supported');
    });

    it('maps custom raw message or fallback when code is undefined', () => {
      expect(mapMediaErrorCode(undefined, 'Custom server error')).toBe('Custom server error');
      expect(mapMediaErrorCode(undefined, '')).toContain('Failed to load video stream');
    });
  });

  describe('VideoPlayer component', () => {
    it('renders video element with preload="metadata", controls, and playsInline', () => {
      render(
        <VideoPlayer
          src="/api/incidents/1528_76/video"
          poster="/media/thumbnails/1528_76.jpg"
          title="Incident Footage #1528_76"
          safeDownloadName="incident_1528_76.mp4"
          testId="test-video-elem"
        />
      );

      const video = screen.getByTestId('test-video-elem') as HTMLVideoElement;
      expect(video).toBeInTheDocument();
      expect(video).toHaveAttribute('src', '/api/incidents/1528_76/video');
      expect(video).toHaveAttribute('preload', 'metadata');
      expect(video).toHaveAttribute('poster', '/media/thumbnails/1528_76.jpg');
      expect(video.controls).toBe(true);
      expect(video.playsInline).toBe(true);

      // Loading state is initially visible
      expect(screen.getByTestId('video-loading-state')).toBeInTheDocument();
      expect(screen.getByText(/Preparing video stream/i)).toBeInTheDocument();
    });

    it('hides loading state when onLoadedData fires', () => {
      render(
        <VideoPlayer
          src="/api/incidents/1528_76/video"
          testId="test-video-elem"
        />
      );

      const video = screen.getByTestId('test-video-elem');
      fireEvent.loadedData(video);

      expect(screen.queryByTestId('video-loading-state')).not.toBeInTheDocument();
    });

    it('displays error banner, mapped error code, retry button, and download link on error', () => {
      render(
        <VideoPlayer
          src="/api/samples/test.avi/video"
          safeDownloadName="test_sample.mp4"
          testId="test-video-elem"
        />
      );

      const video = screen.getByTestId('test-video-elem') as HTMLVideoElement;

      // Mock media error on HTMLVideoElement
      Object.defineProperty(video, 'error', {
        value: {
          code: 4,
          message: 'DEMUXER_ERROR_COULD_NOT_OPEN',
        },
        configurable: true,
      });

      fireEvent.error(video);

      // Error state should be visible
      expect(screen.getByTestId('video-error-state')).toBeInTheDocument();
      expect(screen.getByText(/Video format or codec is not supported by your browser/i)).toBeInTheDocument();
      expect(screen.getByText(/Error Code: 4/i)).toBeInTheDocument();

      // Download link
      const downloadLink = screen.getByTestId('video-download-link');
      expect(downloadLink).toBeInTheDocument();
      expect(downloadLink).toHaveAttribute('href', '/api/samples/test.avi/video');
      expect(downloadLink).toHaveAttribute('download', 'test_sample.mp4');

      // Retry button resets error state
      const retryBtn = screen.getByTestId('video-retry-button');
      fireEvent.click(retryBtn);

      expect(screen.queryByTestId('video-error-state')).not.toBeInTheDocument();
      expect(screen.getByTestId('video-loading-state')).toBeInTheDocument();
    });

    it('handles keyboard spacebar for play/pause and Escape for modal close', () => {
      const handleClose = vi.fn();
      render(
        <VideoPlayer
          src="/api/incidents/1528_76/video"
          title="Incident Player"
          onClose={handleClose}
          testId="test-video-elem"
        />
      );

      const region = screen.getByRole('region', { name: 'Incident Player' });

      // Press Space to toggle playback
      fireEvent.keyDown(region, { key: ' ', code: 'Space' });

      // Press Escape to close modal
      fireEvent.keyDown(region, { key: 'Escape', code: 'Escape' });
      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it('falls back cleanly if poster image triggers error', () => {
      render(
        <VideoPlayer
          src="/api/incidents/1528_76/video"
          poster="/non-existent-thumb.jpg"
          testId="test-video-elem"
        />
      );

      // Hidden test image triggers error
      const hiddenImg = document.querySelector('img.hidden');
      if (hiddenImg) {
        fireEvent.error(hiddenImg);
      }

      const video = screen.getByTestId('test-video-elem') as HTMLVideoElement;
      expect(video.poster).toBe('');
    });
  });
});
