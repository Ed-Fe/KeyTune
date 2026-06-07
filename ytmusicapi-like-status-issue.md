## Summary

In ytmusicapi 1.12.1, `rate_song()` appears to succeed, but an immediate `get_song()` call can still return the previous `likeStatus`.

## Reproduction

1. Authenticate with a valid YouTube Music account.
2. Call `rate_song(videoId, LikeStatus.LIKE)` or `rate_song(videoId, LikeStatus.DISLIKE)`.
3. Immediately call `get_song(videoId)`.
4. Inspect `song['likeStatus']`.

## Expected behavior

`get_song(videoId)['likeStatus']` should reflect the new rating right after `rate_song()` succeeds, or the library should document that the change is eventually consistent.

## Actual behavior

The write call succeeds, but the subsequent read can still return the old `likeStatus` for a while, which makes it hard to know whether the rating was applied.

## Why this matters

A downstream app uses `rate_song()` followed by `get_song()` to avoid repeated like/dislike actions. With 1.12.1, it can still think the track is un-rated and send the action again.

## Notes

This was observed while integrating playback controls against ytmusicapi 1.12.1. If eventual consistency is expected here, it would help to document that behavior.
