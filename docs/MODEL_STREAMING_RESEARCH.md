# Model Streaming Research

Praetor exposes one normalized SSE contract at `POST /models:stream`, but each upstream provider has a different streaming envelope.

## OpenAI

Source: <https://developers.openai.com/api/docs/guides/streaming-responses>

- The Responses API streams over SSE when `stream=true`.
- Text arrives as semantic events such as `response.output_text.delta`.
- Completion arrives as `response.completed`.
- Praetor maps `response.output_text.delta` to `delta` and `response.completed` to `done`.

## Anthropic

Source: <https://docs.anthropic.com/claude/reference/messages-streaming>

- The Messages API streams with `stream: true`.
- Streams use named SSE events including `message_start`, `content_block_delta`, `message_delta`, and `message_stop`.
- Text arrives inside `content_block_delta` when `delta.type` is `text_delta`.
- Praetor maps text deltas to `delta`, usage-bearing `message_delta` events to `usage`, and `message_stop` to `done`.

## Google Gemini

Source: <https://ai.google.dev/api>

- Gemini uses `models/{model}:streamGenerateContent` for SSE streaming.
- Streaming responses are a stream of `GenerateContentResponse` objects.
- Text arrives under `candidates[].content.parts[].text`.
- Praetor maps each text-bearing response to `delta` and emits a final `done` event after the stream closes, carrying usage metadata when present.

## Normalized Praetor Events

- `start`: selected provider/model.
- `delta`: incremental text.
- `usage`: provider usage metadata when emitted before completion.
- `done`: final accumulated text and usage metadata.
- `error`: redacted provider error details.
