// Cloudflare Worker Telegram Bot: TikTok/Douyin Auto-Downloader to Google Drive (24/7 Serverless)

const DEFAULT_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36';

function extractUrl(text) {
  if (!text) return null;
  const clean = text.trim();
  if (/^\d{15,}$/.test(clean)) {
    return `https://www.tiktok.com/@video/video/${clean}`;
  }
  const match = text.match(/https?:\/\/[^\s]+/);
  return match ? match[0] : null;
}

async function resolveUrlAndItemId(url) {
  let finalUrl = url;
  try {
    if (/(vt\.tiktok\.com|vm\.tiktok\.com|v\.douyin\.com|t\.tiktok\.com)/.test(url)) {
      const resp = await fetch(url, {
        headers: { 'User-Agent': DEFAULT_UA },
        redirect: 'manual'
      });
      const location = resp.headers.get('Location');
      if (location) {
        finalUrl = location;
      } else {
        const followResp = await fetch(url, {
          headers: { 'User-Agent': DEFAULT_UA },
          redirect: 'follow'
        });
        finalUrl = followResp.url;
      }
    }
  } catch (err) {
    console.error('[Worker] Error resolving redirect:', err);
  }

  const idMatch = finalUrl.match(/(\d{18,21})/);
  const itemId = idMatch ? idMatch[1] : null;
  return { itemId, finalUrl };
}

async function fetchTikHubVideo(itemId, isDouyin, token) {
  if (!token) throw new Error('TIKHUB_API_TOKEN is not configured');

  const headers = {
    'Authorization': `Bearer ${token}`,
    'Accept': 'application/json'
  };

  if (isDouyin) {
    const apiUrl = `https://api.tikhub.io/api/v1/douyin/web/fetch_one_video?aweme_id=${itemId}`;
    const res = await fetch(apiUrl, { headers });
    if (!res.ok) throw new Error(`TikHub Douyin API returned status ${res.status}`);
    const data = await res.json();
    const aweme = data?.data?.aweme_detail || {};
    const video = aweme.video || {};
    const urlList = video.play_addr_h264?.url_list || video.play_addr?.url_list || video.download_addr?.url_list || [];
    if (urlList.length > 0) return urlList[0];
    throw new Error('No valid video URL returned from TikHub Douyin API');
  } else {
    const apiUrl = `https://api.tikhub.io/api/v1/tiktok/web/fetch_post_detail?itemId=${itemId}`;
    const res = await fetch(apiUrl, { headers });
    if (!res.ok) throw new Error(`TikHub TikTok API returned status ${res.status}`);
    const data = await res.json();
    const itemStruct = data?.data?.itemInfo?.itemStruct || {};
    const video = itemStruct.video || {};
    const playUrl = video.playAddr || video.downloadAddr;
    if (playUrl) return playUrl;
    throw new Error('No valid video URL returned from TikHub TikTok API');
  }
}

async function getGoogleAccessToken(clientId, clientSecret, refreshToken) {
  if (!refreshToken) throw new Error('GDRIVE_REFRESH_TOKEN is not configured');

  const res = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      refresh_token: refreshToken,
      grant_type: 'refresh_token'
    })
  });

  const data = await res.json();
  if (!res.ok || !data.access_token) {
    throw new Error(`Failed to refresh Google access token: ${JSON.stringify(data)}`);
  }
  return data.access_token;
}

async function uploadStreamToGoogleDrive(videoUrl, filename, folderId, accessToken, isDouyin) {
  const referer = isDouyin ? 'https://www.douyin.com/' : 'https://www.tiktok.com/';
  const videoResp = await fetch(videoUrl, {
    headers: {
      'User-Agent': DEFAULT_UA,
      'Referer': referer
    }
  });

  if (!videoResp.ok) throw new Error(`Failed to fetch video stream from CDN: HTTP ${videoResp.status}`);

  const contentLength = videoResp.headers.get('content-length');
  const sizeMb = contentLength ? (Number(contentLength) / (1024 * 1024)).toFixed(2) : 'Unknown';

  // 1. Initialize Resumable Upload Session
  const initHeaders = {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json; charset=UTF-8',
    'X-Upload-Content-Type': 'video/mp4'
  };
  if (contentLength) {
    initHeaders['X-Upload-Content-Length'] = contentLength;
  }

  const metadata = {
    name: filename,
    parents: [folderId]
  };

  const initRes = await fetch('https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable', {
    method: 'POST',
    headers: initHeaders,
    body: JSON.stringify(metadata)
  });

  if (!initRes.ok) {
    const errText = await initRes.text();
    throw new Error(`Google Drive Resumable Init failed (${initRes.status}): ${errText}`);
  }

  const uploadUrl = initRes.headers.get('Location');
  if (!uploadUrl) throw new Error('No Location header returned from Google Drive Resumable Init');

  // 2. Stream video body directly to Google Drive
  const putHeaders = {
    'Content-Type': 'video/mp4'
  };
  if (contentLength) {
    putHeaders['Content-Length'] = contentLength;
  }

  const uploadRes = await fetch(uploadUrl, {
    method: 'PUT',
    headers: putHeaders,
    body: videoResp.body
  });

  if (!uploadRes.ok) {
    const errText = await uploadRes.text();
    throw new Error(`Google Drive Stream Upload failed (${uploadRes.status}): ${errText}`);
  }

  const uploadedFile = await uploadRes.json();
  return {
    id: uploadedFile.id,
    name: uploadedFile.name,
    sizeMb: sizeMb
  };
}

// Telegram Helpers
async function sendTelegramMessage(token, chatId, text, replyId = null, threadId = null) {
  const url = `https://api.telegram.org/bot${token}/sendMessage`;
  const body = {
    chat_id: chatId,
    text: text,
    parse_mode: 'HTML'
  };
  if (replyId) body.reply_to_message_id = replyId;
  if (threadId) body.message_thread_id = threadId;

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    return await res.json();
  } catch (err) {
    console.error('[Worker] Error sending Telegram message:', err);
    return null;
  }
}

async function editTelegramMessage(token, chatId, messageId, text) {
  const url = `https://api.telegram.org/bot${token}/editMessageText`;
  const body = {
    chat_id: chatId,
    message_id: messageId,
    text: text,
    parse_mode: 'HTML'
  };

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    return await res.json();
  } catch (err) {
    console.error('[Worker] Error editing Telegram message:', err);
    return null;
  }
}

async function sendTelegramVideo(token, chatId, videoUrl, caption = null, replyId = null, threadId = null) {
  const url = `https://api.telegram.org/bot${token}/sendVideo`;
  const body = {
    chat_id: chatId,
    video: videoUrl
  };
  if (caption) {
    body.caption = caption;
    body.parse_mode = 'HTML';
  }
  if (replyId) body.reply_to_message_id = replyId;
  if (threadId) body.message_thread_id = threadId;

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    return await res.json();
  } catch (err) {
    console.error('[Worker] Error sending Telegram video:', err);
    return null;
  }
}

function isAllowedChat(allowedConfig, chatId) {
  if (!allowedConfig) return true;
  const chatStr = String(chatId);
  const allowedList = allowedConfig.split(',').map(s => s.trim()).filter(Boolean);
  for (const gid of allowedList) {
    if (chatStr === gid) return true;
    const cleanG = gid.replace('-100', '').replace('-', '');
    const cleanC = chatStr.replace('-100', '').replace('-', '');
    if (cleanG && cleanG === cleanC) return true;
  }
  return false;
}

// Background Task: Process Video & Upload to Drive
async function handleVideoTask(env, chatId, messageId, statusMsgId, text, threadId) {
  const token = env.TELEGRAM_BOT_TOKEN;
  try {
    const rawUrl = extractUrl(text);
    if (!rawUrl) return;

    const { itemId, finalUrl } = await resolveUrlAndItemId(rawUrl);
    const videoIdStr = itemId || String(Date.now());
    const isDouyin = finalUrl.includes('douyin.com') || rawUrl.includes('douyin.com');

    // 1. Get HD video stream URL via TikHub
    const streamUrl = await fetchTikHubVideo(videoIdStr, isDouyin, env.TIKHUB_API_TOKEN);

    // 2. Upload to Google Drive if credentials available
    let gdriveResult = null;
    if (env.GDRIVE_REFRESH_TOKEN && env.GDRIVE_CLIENT_ID && env.GDRIVE_CLIENT_SECRET) {
      if (statusMsgId) {
        await editTelegramMessage(
          token, chatId, statusMsgId,
          '⏳ <b>Đang tải lên Google Drive...</b>\nĐang truyền dữ liệu luồng HD từ Cloudflare ➔ Google Drive...'
        );
      }
      const accessToken = await getGoogleAccessToken(
        env.GDRIVE_CLIENT_ID,
        env.GDRIVE_CLIENT_SECRET,
        env.GDRIVE_REFRESH_TOKEN
      );
      const folderId = env.GDRIVE_FOLDER_ID || '1fV0GyTCBblUHQIpJ1Kzsh6rho8oYwY8b';
      gdriveResult = await uploadStreamToGoogleDrive(
        streamUrl,
        `${videoIdStr}.mp4`,
        folderId,
        accessToken,
        isDouyin
      );
    }

    const fileSizeMb = gdriveResult?.sizeMb || 'HD';
    const driveLink = gdriveResult?.id ? `https://drive.google.com/file/d/${gdriveResult.id}/view` : 'Video titok Trinh';

    // 3. Notify success
    const successText = [
      '✅ <b>TẢI VIDEO LÊN GOOGLE DRIVE THÀNH CÔNG!</b> 🚀',
      '',
      `🆔 <b>Mã Video:</b> <code>${videoIdStr}</code>`,
      `📊 <b>Dung lượng:</b> <code>${fileSizeMb} MB</code>`,
      `📁 <b>Google Drive:</b> <a href="${driveLink}">Xem trên Google Drive</a>`,
      '✨ <b>Chất lượng:</b> HD Gốc không logo',
      '⚡ <b>Xử lý bởi:</b> Cloudflare Worker 24/7 (Máy tính tắt vẫn hoạt động)'
    ].join('\n');

    if (statusMsgId) {
      await editTelegramMessage(token, chatId, statusMsgId, successText);
    } else {
      await sendTelegramMessage(token, chatId, successText, messageId, threadId);
    }

    // 4. Send video directly to group if < 50MB
    const numericMb = parseFloat(fileSizeMb);
    if (!isNaN(numericMb) && numericMb <= 49) {
      await sendTelegramVideo(
        token, chatId, streamUrl,
        `🎬 <b>${videoIdStr}.mp4</b> (${fileSizeMb} MB)`,
        messageId, threadId
      );
    }

  } catch (err) {
    console.error('[Worker] Task Error:', err);
    if (statusMsgId) {
      await editTelegramMessage(token, chatId, statusMsgId, `❌ <b>Lỗi xử lý:</b> ${err.message || err}`);
    }
  }
}

// Export Cloudflare Worker
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Health check
    if (url.pathname === '/health' || url.pathname === '/') {
      return new Response(JSON.stringify({
        status: 'ok',
        service: 'tiktok-telegram-bot',
        timestamp: new Date().toISOString()
      }), {
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Webhook endpoint
    if (url.pathname === '/webhook' && request.method === 'POST') {
      try {
        const update = await request.json();
        const message = update.message || update.channel_post;
        if (!message) {
          return new Response('OK', { status: 200 });
        }

        const chatId = message.chat?.id;
        const messageId = message.message_id;
        const threadId = message.message_thread_id;
        const text = message.text || message.caption || '';

        // Allow commands /start, /id
        if (text.startsWith('/start') || text.startsWith('/id') || text.startsWith('/help')) {
          ctx.waitUntil(
            sendTelegramMessage(
              env.TELEGRAM_BOT_TOKEN,
              chatId,
              `🤖 <b>Cloudflare 24/7 Telegram Bot Đang Hoạt Động!</b>\n\n` +
              `🆔 <b>Chat ID:</b> <code>${chatId}</code>\n` +
              `📁 <b>Google Drive:</b> <code>Video titok Trinh</code>\n` +
              `⚡ Máy tính tắt bot vẫn tự động tải video HD không logo vào Google Drive!`,
              messageId,
              threadId
            )
          );
          return new Response('OK', { status: 200 });
        }

        // Check allowed chat
        if (isAllowedChat(env.TELEGRAM_GROUP_ID, chatId) || message.chat?.type === 'private') {
          if (/https?:\/\/|douyin\.com|tiktok\.com|v\.douyin|vt\.tiktok/.test(text)) {
            // Send quick status message
            const statusPromise = (async () => {
              const statusMsg = await sendTelegramMessage(
                env.TELEGRAM_BOT_TOKEN,
                chatId,
                '⏳ <b>Đang tải video...</b>\nĐang kết nối Cloudflare ➔ TikHub bóc tách luồng HD không logo...',
                messageId,
                threadId
              );
              const statusMsgId = statusMsg?.result?.message_id;
              await handleVideoTask(env, chatId, messageId, statusMsgId, text, threadId);
            })();

            ctx.waitUntil(statusPromise);
          }
        }

        return new Response('OK', { status: 200 });
      } catch (err) {
        console.error('[Worker] Webhook error:', err);
        return new Response('Error: ' + err.message, { status: 500 });
      }
    }

    return new Response('Not Found', { status: 404 });
  }
};
