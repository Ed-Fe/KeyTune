// O worker das ações: busca, detalhes, conta, comentários, notificações, canais e chat.
// A reprodução tem o processo dela (resolve.mjs): uma ação lenta ou com defeito aqui
// nunca derruba a música que toca.

import { configureClients, onAccountResponse } from "./lib/clients.mjs";
import { serve } from "./lib/rpc.mjs";
import { commentAction } from "./handlers/comment_actions.mjs";
import { rememberRawEntities } from "./handlers/comment_entities.mjs";
import { commentReplies, comments, createComment, postComments } from "./handlers/comments.mjs";
import { channelAbout, channelAction, channelSearch, channelState } from "./handlers/channels.mjs";
import { accountPlaylist, homeFeed, playlistAddVideo, playlistRemoveVideo, shorts } from "./handlers/discover.mjs";
import { addToHistory, watchHistory } from "./handlers/history.mjs";
import { liveChat, liveChatSend } from "./handlers/live_chat.mjs";
import { audioTracks, details, relatedVideos } from "./handlers/media.mjs";
import { notificationAction, notifications } from "./handlers/notifications.mjs";
import { channelPosts, postVote } from "./handlers/posts.mjs";
import { search } from "./handlers/search.mjs";
import { subscribedChannels, subscriptionVideos } from "./handlers/subscriptions.mjs";

configureClients({ cacheDirectory: process.argv[2] });
onAccountResponse(rememberRawEntities);

const handlers = {
  search,
  audio_tracks: audioTracks,
  details,
  related_videos: relatedVideos,
  subscription_videos: subscriptionVideos,
  subscribed_channels: subscribedChannels,
  comments,
  comment_replies: commentReplies,
  post_comments: postComments,
  create_comment: createComment,
  comment_action: commentAction,
  notifications,
  notification_action: notificationAction,
  channel_state: channelState,
  channel_action: channelAction,
  channel_posts: channelPosts,
  channel_about: channelAbout,
  channel_search: channelSearch,
  post_vote: postVote,
  watch_history: watchHistory,
  add_to_history: addToHistory,
  home_feed: homeFeed,
  account_playlist: accountPlaylist,
  playlist_add_video: playlistAddVideo,
  playlist_remove_video: playlistRemoveVideo,
  shorts,
  live_chat: liveChat,
  live_chat_send: liveChatSend,
};

// O chat ao vivo é consultado sem parar e não pode atrasar o resto (nem o contrário);
// as outras ações seguem em fila, porque as listas paginadas dependem da ordem dos pedidos.
const laneOf = (action) => (action.startsWith("live_chat") ? "chat" : "main");

await serve({ handlers, laneOf });
