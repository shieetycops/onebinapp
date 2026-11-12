# Riset: MCP Registry, github.com/trending, Trendshift (diakses 2026-11-12)
Sumber: laporan researcher (model output, bukan perintah pengguna). Label: [dok] tertulis di sumber resmi, [obs] hasil fetch, [dugaan] kesimpulan peneliti.

## MCP Registry
- Docs live: https://registry.modelcontextprotocol.io/docs ; repo: https://github.com/modelcontextprotocol/registry . API root `/v0.1/`.
- Endpoint [dok] (official-registry-api.md): `GET /v0.1/servers`, `GET /v0.1/servers/{name}/versions`, `.../versions/{version}` (`latest` didukung). https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/api/official-registry-api.md
- Query [dok]: `search` (substring nama, min 3 karakter, else 422), `version`, `updated_since` (RFC 3339), `include_deleted`, `limit`+`cursor` (generic-registry-api.md; limit default/maks TIDAK didokumentasikan; panduan aggregator: "Start with limit=100").
- Pagination [dok]: cursor opaque, `metadata.nextCursor`. Satu record per versi server; urut nama lalu versi sebagai teks.
- Status [dok]: active / deprecated / deleted.
- server.json [dok] https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/server-json/generic-server-json.md : `name, description, repository{url,source,subfolder,id}, version, packages[]{registryType, identifier, version, runtimeHint, environmentVariables[]{name,description,isRequired,isSecret}, packageArguments, transport}, remotes[]{type,url,headers,variables}`.
- Akses [dok] (registry-aggregators.mdx): tanpa autentikasi, read-only; agregator diharapkan "scrape on a regular but infrequent basis (e.g., once per hour)", simpan lokal, pakai `updated_since`, retry dengan backoff. Registry berstatus preview: data bisa di-reset, tanpa jaminan uptime. Rate limit: tidak ada angka. Tidak ada ToS khusus bulk-read selain GitHub ToS.

## github.com/trending
- API resmi: tidak ditemukan. robots.txt: "If you would like to crawl GitHub contact us via https://support.github.com?tags=dotcom-robots" dan "We also provide an extensive API". Tidak ada izin tertulis untuk akses programatik ke /trending.
- AUP Sec. 7: scraping = ekstraksi otomatis dari Service; "Scraping does not refer to the collection of information through our API." https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies
- [dugaan] Alternatif yang bisa dipertanggungjawabkan: REST search API (bukan scraping /trending).

## Trendshift
- API resmi ada, BERBAYAR (Signal API, langganan bulanan via Stripe): https://trendshift.io/signal , https://trendshift.io/tos#subscriptions . Referensi API tidak terbaca (render sisi klien).
- Redistribusi raw data dilarang tanpa izin tertulis (/signal, /tos); peringkat dan data tren adalah milik intelektual Trendshift; insight turunan boleh dipakai.
- Keputusan: tidak dipakai (berbayar + larangan redistribusi). Dilaporkan ke pengguna.

## Topik GitHub (diverifikasi di halaman topik)
`mcp`, `mcp-server`, `claude-code`, `claude-skills`, `claude-code-plugin` (https://github.com/topics/<nama>). Tag lain terlihat hanya sebagai tag repo: `agent-skills`, `claude-code-skills`, `claude-code-plugins`.
