import type { ImageContent } from "@mariozechner/pi-ai";

// --- Provider registry ---

interface EndpointConfig {
  url: string;
  model: string;
  priority: number;
}

interface MediaProvider {
  name: string;
  getApiKey: () => string | undefined;
  image?: EndpointConfig;
  audio?: EndpointConfig;
  video?: EndpointConfig;
}

const providers: MediaProvider[] = [
  {
    name: "MiniMax",
    getApiKey: () => process.env.MINIMAX_API_KEY,
    image: {
      url: "https://api.minimaxi.com/v1/chat/completions",
      model: "MiniMax-M3",
      priority: 10,
    },
    video: {
      url: "https://api.minimaxi.com/v1/chat/completions",
      model: "MiniMax-M3",
      priority: 10,
    },
  },
  {
    name: "GLM",
    getApiKey: () => process.env.ZAI_API_KEY || process.env.Z_AI_API_KEY,
    audio: {
      url: "https://open.bigmodel.cn/api/paas/v4/audio/transcriptions",
      model: "glm-asr-2512",
      priority: 10,
    },
  },
];

// --- Helpers ---

async function callOpenAIChat(url: string, apiKey: string, body: object): Promise<string> {
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const errText = await resp.text();
    throw new Error(`HTTP ${resp.status}: ${errText.slice(0, 200)}`);
  }
  const data = await resp.json();
  const text = data.choices?.[0]?.message?.content?.trim();
  if (!text) throw new Error("Empty response");
  return text;
}

function providersFor(kind: "image" | "audio" | "video"): Array<{ provider: MediaProvider; endpoint: EndpointConfig }> {
  return providers
    .filter((p) => p[kind])
    .map((p) => ({ provider: p, endpoint: p[kind]! }))
    .sort((a, b) => a.endpoint.priority - b.endpoint.priority);
}

function isAsrEndpoint(url: string): boolean {
  return url.includes("/audio/transcriptions") || url.includes("/audio/asr");
}

async function callAsrEndpoint(url: string, apiKey: string, audioBase64: string, model: string): Promise<string> {
  const audioBuffer = Buffer.from(audioBase64, "base64");
  const boundary = "----FormBoundary" + Math.random().toString(36).slice(2);
  const parts: Buffer[] = [];

  parts.push(Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n${model}\r\n`));
  parts.push(Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="response_format"\r\n\r\njson\r\n`));
  parts.push(Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.wav"\r\nContent-Type: audio/wav\r\n\r\n`));
  parts.push(audioBuffer);
  parts.push(Buffer.from(`\r\n--${boundary}--\r\n`));

  const resp = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": `multipart/form-data; boundary=${boundary}`,
    },
    body: Buffer.concat(parts),
  });
  if (!resp.ok) {
    const errText = await resp.text();
    throw new Error(`HTTP ${resp.status}: ${errText.slice(0, 200)}`);
  }
  const data = await resp.json();
  const text = data.text?.trim();
  if (!text) throw new Error("Empty response");
  return text;
}

// --- Image understanding ---

function buildImagePrompt(count: number): string {
  if (count === 1) {
    return "请详细描述这张图片的内容，包括其中的文字、图表、UI界面、代码等所有可见信息。";
  }
  return `请依次详细描述以下图片的内容（共${count}张），每张图片单独描述并用"第X张图片"标注，包括其中的文字、图表、UI界面、代码等所有可见信息。`;
}

export async function describeImages(images: ImageContent[]): Promise<string> {
  const candidates = providersFor("image");
  if (candidates.length === 0) return "[图片理解失败：无可用视觉模型]";

  const imageBlocks = images.map((img) => ({
    type: "image_url" as const,
    image_url: { url: `data:${img.mimeType};base64,${img.data}` },
  }));

  for (const { provider, endpoint } of candidates) {
    const apiKey = provider.getApiKey();
    if (!apiKey) continue;
    try {
      console.log(`[media-provider] image → ${provider.name} (${endpoint.model}), ${images.length} image(s)`);
      const text = await callOpenAIChat(endpoint.url, apiKey, {
        model: endpoint.model,
        messages: [
          { role: "user", content: [{ type: "text", text: buildImagePrompt(images.length) }, ...imageBlocks] },
        ],
        stream: false,
        max_tokens: 2048,
      });
      console.log(`[media-provider] image ← ${provider.name} ok (${text.length} chars)`);
      return text;
    } catch (err: any) {
      console.warn(`[media-provider] image × ${provider.name} failed: ${err.message}`);
    }
  }
  return "[图片理解失败：所有视觉模型均不可用]";
}

// --- Video understanding ---

export async function describeVideo(data: string, mimeType: string): Promise<string> {
  const candidates = providersFor("video");
  if (candidates.length === 0) return "[视频理解失败：无可用视频模型]";

  for (const { provider, endpoint } of candidates) {
    const apiKey = provider.getApiKey();
    if (!apiKey) continue;
    try {
      console.log(`[media-provider] video → ${provider.name} (${endpoint.model}), ${mimeType}`);
      const text = await callOpenAIChat(endpoint.url, apiKey, {
        model: endpoint.model,
        messages: [
          {
            role: "user",
            content: [
              { type: "text", text: "请详细描述这个视频的内容，包括画面场景、人物动作、文字信息、对话内容等所有可见可听的信息。" },
              { type: "video_url", video_url: { url: `data:${mimeType};base64,${data}` } },
            ],
          },
        ],
        stream: false,
        max_tokens: 4096,
      });
      console.log(`[media-provider] video ← ${provider.name} ok (${text.length} chars)`);
      return text;
    } catch (err: any) {
      console.warn(`[media-provider] video × ${provider.name} failed: ${err.message}`);
    }
  }
  return "[视频理解失败：所有视频模型均不可用]";
}

// --- Audio transcription (STT) ---

export async function transcribeAudio(audioBase64: string, format: string = "wav"): Promise<string> {
  const candidates = providersFor("audio");
  if (candidates.length === 0) throw new Error("No audio transcription provider available");

  for (const { provider, endpoint } of candidates) {
    const apiKey = provider.getApiKey();
    if (!apiKey) continue;
    try {
      console.log(`[media-provider] audio → ${provider.name} (${endpoint.model}), ${audioBase64.length} chars base64`);
      let text: string;
      if (isAsrEndpoint(endpoint.url)) {
        text = await callAsrEndpoint(endpoint.url, apiKey, audioBase64, endpoint.model);
      } else {
        text = await callOpenAIChat(endpoint.url, apiKey, {
          model: endpoint.model,
          messages: [
            {
              role: "user",
              content: [
                { type: "text", text: "请将这段语音逐字转录为文字。如果没有任何语音内容，只回复一个空字符串。" },
                { type: "input_audio", input_audio: { data: audioBase64, format } },
              ],
            },
          ],
          stream: false,
          max_tokens: 2048,
        });
      }
      const cleaned = text.replace(/^["「『]|["」』]$/g, "").trim();
      console.log(`[media-provider] audio ← ${provider.name} ok (${cleaned.length} chars)`);
      return cleaned;
    } catch (err: any) {
      console.warn(`[media-provider] audio × ${provider.name} failed: ${err.message}`);
    }
  }
  throw new Error("All audio transcription providers failed");
}
