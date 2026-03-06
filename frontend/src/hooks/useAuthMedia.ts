import { useEffect, useState } from "react";
import { fetchMediaBlobUrl } from "../services/api";

/**
 * Fetches an authenticated media URL and returns a local blob URL.
 * Falls back to base64 data URI if provided.
 */
export function useAuthMedia(
  getToken: (() => Promise<string>) | undefined,
  mediaUrl: string | undefined,
  base64: string | undefined,
  mimeType: string
): string | undefined {
  const [blobUrl, setBlobUrl] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (base64) return;
    if (!mediaUrl || !getToken) return;

    let revoked = false;
    let objectUrl: string | undefined;

    getToken()
      .then((token) => fetchMediaBlobUrl(mediaUrl, token))
      .then((url) => {
        if (revoked) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setBlobUrl(url);
      })
      .catch(() => {
        // Media fetch failed — leave as undefined
      });

    return () => {
      revoked = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [mediaUrl, base64, getToken, mimeType]);

  if (base64) return `data:${mimeType};base64,${base64}`;
  return blobUrl;
}
