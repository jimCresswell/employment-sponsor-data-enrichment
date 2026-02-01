# Troubleshooting

## Companies House Authentication (401/403)

If Stage 2 fails with `401 Unauthorized` or `Invalid Authorization`:

- Confirm you created a **Companies House API Key** application (not OAuth).
- Set `CH_API_KEY` in `.env` or your environment.
- Stage 2 uses HTTP Basic Auth with the API key as the username and a blank password.
- If failures persist, regenerate the key and retry.
