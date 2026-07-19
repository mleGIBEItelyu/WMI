FOLLOW-UP — your previous attempt returned too few usable items.

Run MORE web searches — including in Bahasa Indonesia for Indonesian coverage
("berita ekonomi Indonesia", "IHSG", "rupiah", "Bank Indonesia") — broaden your
sources, and be stricter about the date window {start_date} .. {end_date}. Return
at least {min_valid} items (ideally {target_candidates}), each with a valid
published_date inside the window, a real source, a working url, and a factual 1-2
sentence summary. Include Indonesian stories, not only global ones.

Reply with the SAME JSON object shape as before:
{{ "news": [ {{ "title", "published_date", "source", "url", "raw_summary", "category", "region" }} ] }}
Return ONLY that JSON object — no prose, no markdown.
