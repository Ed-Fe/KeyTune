// Os posts da aba "Posts" (comunidade) de um canal e os votos nas enquetes deles.

import { accountClientFor, clientFor } from "../lib/clients.mjs";
import { rememberBounded } from "../lib/bounded.mjs";
import { assertOk } from "../lib/results.mjs";
import { collectEntries, listingPage, listings, pageBounds, rememberListing } from "../lib/listings.mjs";
import { requireChannelId, textOf } from "../lib/text.mjs";

const MAX_POSTS = 500;

// Os posts mostrados pela conta, pelo identificador: é neles que se vota na enquete.
const postRecords = new Map();

function attachmentText(attachment) {
  if (!attachment) {
    return { text: "", video_id: "" };
  }
  if (attachment.type === "Video" || attachment.type === "VideoCard") {
    return { text: textOf(attachment.title), video_id: attachment.video_id || attachment.id || "" };
  }
  if (attachment.type === "Poll") {
    const choices = (attachment.choices || []).map((choice) => textOf(choice.text));
    return { text: choices.filter(Boolean).join(" / "), video_id: "", poll: true, choices };
  }
  if (attachment.type === "BackstageImage" || attachment.type === "PostMultiImage") {
    return { text: "", video_id: "", image: true };
  }
  return { text: "", video_id: "" };
}

function postEntry(node, channelId, listing) {
  const post = node.type === "SharedPost" ? node.original_post || node : node;
  const id = node.id || post.id;
  if (!id) {
    return null;
  }
  const attachment = attachmentText(post.attachment);
  const canVote = Boolean(
    listing.account && attachment.poll && (post.attachment.choices || []).every((choice) => choice.select_endpoint),
  );
  if (canVote) {
    rememberBounded(postRecords, id, { poll: post.attachment, innertube: listing.innertube }, MAX_POSTS);
  }
  return {
    id,
    channel_id: channelId,
    author: textOf(node.author?.name) || textOf(post.author?.name),
    text: textOf(node.content) || textOf(post.content),
    published: textOf(node.published) || textOf(post.published),
    likes: textOf(post.vote_count),
    reply_count: textOf(post.action_buttons?.reply_button?.text),
    attachment_text: attachment.text,
    attachment_video_id: attachment.video_id,
    has_image: Boolean(attachment.image),
    has_poll: Boolean(attachment.poll),
    poll_choices: attachment.choices || [],
    can_vote: canVote,
    title: "-",
  };
}

// Os posts de um canal; não precisam da conta, mas com ela as enquetes vêm prontas para votar.
export async function channelPosts(request) {
  const channelId = requireChannelId(request);
  const { start, count } = pageBounds(request);
  const account = Boolean(String(request.cookie || "").trim());
  const key = JSON.stringify(["channel_posts", request.lang, request.location, account, channelId]);
  let listing = listings.get(key);
  if (!listing || start === 0) {
    const innertube = account ? await accountClientFor(request) : await clientFor(request);
    const channel = await innertube.getChannel(channelId);
    listing = { entries: [], seen: new Set(), feed: null, innertube, account };
    if (channel.has_community) {
      listing.feed = await channel.getCommunity();
      collectEntries(listing, listing.feed.posts, (node) => postEntry(node, channelId, listing));
    }
  }
  rememberListing(key, listing);
  while (listing.entries.length < start + count && listing.feed?.has_continuation) {
    listing.feed = await listing.feed.getContinuation();
    collectEntries(listing, listing.feed.posts, (node) => postEntry(node, channelId, listing));
  }
  return listingPage(listing, start, count, listing.feed?.has_continuation);
}

// Vota numa opção da enquete de um post, ou tira o voto dela (*operation* "unvote").
export async function postVote(request) {
  const record = postRecords.get(String(request.post_id || ""));
  const choice = record?.poll.choices?.[Number(request.choice)];
  if (!choice) {
    throw new Error("Abra os posts do canal de novo, com a conta conectada, para votar.");
  }
  const endpoint = request.operation === "unvote" ? choice.deselect_endpoint : choice.select_endpoint;
  if (!endpoint) {
    throw new Error("O YouTube não permite votar nesta enquete.");
  }
  assertOk(await endpoint.call(record.innertube.actions), "O YouTube recusou o voto");
  return { ok: true };
}
