# PROJECT BRIEF: Weekly Market Insight — Multi-Agent News Analyst System

## Konteks & Goal
Bangun backend Python yang menjalankan **3 AI agent berbasis Claude** untuk menganalisa berita ekonomi/market 7 hari terakhir, lalu menghasilkan output JSON terstruktur yang siap dipakai untuk mengisi template desain "Weekly Market Insight" (GIBEI Telkom University x Phillip Sekuritas).

Output akhir yang dibutuhkan template:
1. **3 Weekly Highlights** — berita paling penting buat pergerakan market minggu ini (judul, tanggal, ringkasan 2-4 kalimat, sumber)
2. **Major Headline** — 1 berita paling berdampak minggu ini (judul, ringkasan, sumber)
3. **Key Insight** — 1 paragraf analisa mendalam (bukan rangkuman berita, tapi "kenapa ini penting buat market", 5-8 kalimat)
4. Metadata: periode (start_date - end_date), source/department

Sistem ini akan dipanggil via terminal (CLI), generate file JSON, dan bisa di-extend nanti buat auto-fill ke template desain (Canva/Figma/HTML).

---

## Arsitektur: 3 Agent, 1 Round Pipeline

Bukan true multi-turn debate — tapi sequential handoff di mana tiap agent melihat output agent sebelumnya, dan agent terakhir (Lead Editor) yang membuat keputusan final dengan konteks penuh dari 2 agent lainnya. Ini = "1 ronde diskusi".

```
[Agent 1: News Research Analyst]
        |  (daftar kandidat berita 7 hari terakhir + raw summary)
        v
[Agent 2: Quant/Data Analyst]
        |  (scoring dampak market per berita + data kuantitatif pendukung)
        v
[Agent 3: Lead Market Analyst / Writer-Editor]
        |  (sintesis final: pilih 3 highlight, 1 major headline, tulis key insight)
        v
   weekly_insight.json
```

Implementasikan sebagai **sequential pipeline**, bukan parallel — tiap agent call menerima full output dari agent sebelumnya sebagai context di prompt-nya. Ini bikin hasil lebih reliable dan gampang di-debug dibanding orchestration paralel yang kompleks.

---

## Tech Stack — Groq (Free Tier)

- Python 3.11+
- `groq` SDK (pip install groq) — OpenAI-compatible, base url `https://api.groq.com/openai/v1`
- Model per agent (dipilih biar tetap efisien di free tier tapi output tetap gacor):
  - **Agent 1 (News Research):** `groq/compound` — sistem agentic Groq yang punya **built-in web search** (powered by Tavily), bisa multiple tool call dalam 1 request. Ini WAJIB dipakai karena Groq tidak punya akses internet di model biasa, dan compound bisa narik berita real-time tanpa lo perlu integrasi search API terpisah.
  - **Agent 2 (Quant Analyst):** `llama-3.3-70b-versatile` — murni reasoning di atas data yang sudah ada, tidak butuh tool, jadi pakai model standar yang lebih hemat TPM.
  - **Agent 3 (Lead Editor):** `llama-3.3-70b-versatile` — sama, reasoning + writing.
- `pydantic` untuk schema validasi output tiap agent
- `python-dotenv` untuk API key
- `argparse` untuk CLI
- `tenacity` untuk retry/backoff otomatis saat kena rate limit (429)
- `rich` (optional) buat pretty-print log tiap step di terminal

### Kenapa split model begini
Compound (Agent 1) sedikit lebih "mahal" dari sisi token karena underlying-nya pakai GPT-OSS-120B/Llama 4 + tool call, jadi cuma dipakai di tahap yang BENERAN butuh internet. Agent 2 & 3 nggak butuh browsing — pakai Llama 3.3 70B versatile yang rate limit-nya lebih longgar di free tier supaya budget token harian nggak kepotong di tahap yang sebenernya cuma reasoning di atas data yang sudah ada.

---

## Struktur Folder

```
weekly-market-insight/
├── main.py                      # CLI entrypoint
├── orchestrator.py              # menjalankan pipeline 3 agent
├── schemas.py                   # pydantic models
├── agents/
│   ├── __init__.py
│   ├── news_research_agent.py
│   ├── quant_analyst_agent.py
│   └── lead_editor_agent.py
├── prompts/
│   ├── news_research_system.md
│   ├── quant_analyst_system.md
│   └── lead_editor_system.md
├── output/                      # hasil JSON per run, named by date range
├── .env.example
├── requirements.txt
└── README.md
```

---

## Schemas (pydantic) — `schemas.py`

```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class NewsCandidate(BaseModel):
    title: str
    published_date: date
    source: str
    url: Optional[str] = None
    raw_summary: str
    category: str  # "macro" | "geopolitics" | "equity" | "commodity" | "crypto" | "monetary_policy" | "other"

class ScoredNews(NewsCandidate):
    market_impact_score: float   # 0-10
    quantitative_evidence: str   # angka/data pendukung dampaknya (%, bps, index points, dll)
    affected_assets: List[str]   # ex: ["XAU/USD", "IHSG", "S&P500", "DXY"]

class HighlightItem(BaseModel):
    title: str
    date: date
    summary: str       # 2-4 kalimat, gaya jurnalistik netral
    source: str

class MajorHeadline(BaseModel):
    title: str
    summary: str
    source: str

class KeyInsight(BaseModel):
    summary: str        # 1 paragraf, 5-8 kalimat, analisa mendalam bukan rangkuman berita
    source: str

class WeeklyMarketInsight(BaseModel):
    period_start: date
    period_end: date
    weekly_highlights: List[HighlightItem]   # selalu 3 item
    major_headline: MajorHeadline
    key_insight: KeyInsight
    source_department: str = "Research and Education Department"
```

---

## Agent 1 — News Research Analyst

**File:** `prompts/news_research_system.md`

```
Kamu adalah News Research Analyst di sebuah divisi riset pasar modal.

TUGAS:
Cari dan kumpulkan berita ekonomi/pasar global & Indonesia dari {start_date} sampai {end_date}
yang berpotensi mempengaruhi pergerakan market (saham, forex, komoditas, crypto, obligasi).

Gunakan web search tool untuk mencari berita REAL dan TERKINI — jangan mengarang atau
mengandalkan ingatan tanpa verifikasi, karena pengetahuanmu punya batas waktu.

Fokus kategori:
- Kebijakan moneter (The Fed, BI rate, ECB, dll)
- Data ekonomi makro (inflasi, NFP, GDP, consumer confidence, dll)
- Geopolitik yang berdampak ke market (perang dagang, sanksi, konflik, pemilu)
- Pergerakan signifikan indeks (IHSG, S&P500, Nasdaq, DXY) atau komoditas (XAU/USD, minyak)
- Kebijakan pemerintah/regulator yang relevan ke pasar modal IDX

OUTPUT:
Kembalikan minimal 8-12 kandidat berita dalam format JSON list sesuai schema NewsCandidate.
Setiap item harus punya tanggal publikasi yang valid dalam rentang {start_date} - {end_date},
sumber yang jelas (nama media/lembaga), dan ringkasan faktual 2-3 kalimat (bukan opini).

Jangan menilai mana yang paling penting — itu tugas analyst berikutnya.
Tugasmu murni riset dan pengumpulan data yang akurat dan terverifikasi.
```

**Implementasi (`agents/news_research_agent.py`):**
- Call Groq API dengan `model="groq/compound"`
- System prompt minta model melakukan **beberapa pencarian dalam SATU request** (compound mendukung multiple tool call per call) — jangan bikin loop Python yang manggil API berkali-kali per kategori berita, karena itu boros RPM. Cukup satu call yang instruksinya eksplisit suruh search beberapa topik berbeda (moneter, makro, geopolitik, indeks, IDX) sebelum jawab final.
- Pakai `response_format={"type": "json_object"}` (Groq mendukung JSON mode di model dasarnya) supaya output langsung JSON valid, mengurangi token terbuang buat reparsing/retry.
- Cek field `executed_tools` di response buat logging — biar lo bisa lihat search apa aja yang sebenarnya dijalankan di balik layar (transparansi research trail).
- Parse response → validasi tiap item ke `NewsCandidate`, buang yang gagal parse/di luar rentang tanggal
- Kalau hasil < 5 item valid, retry SEKALI saja dengan prompt yang lebih spesifik (jangan retry berkali-kali, itu yang paling cepat bikin kena 429 di free tier)

---

## Agent 2 — Quant/Data Analyst

**File:** `prompts/quant_analyst_system.md`

```
Kamu adalah Quant/Data Analyst di divisi riset pasar modal.

KONTEKS:
Kamu menerima daftar kandidat berita dari News Research Analyst (lihat di bawah).
Tugasmu adalah menilai DAMPAK KUANTITATIF tiap berita terhadap market — bukan menulis ulang
beritanya, tapi mengevaluasi seberapa besar dan terukur efeknya.

KANDIDAT BERITA:
{news_candidates_json}

TUGAS:
Untuk setiap berita, berikan:
1. market_impact_score (0-10): seberapa besar potensi pergerakan market yang ditimbulkan
   - 0-3: dampak minor/lokal
   - 4-6: dampak sedang, mempengaruhi 1-2 aset/sektor
   - 7-10: dampak besar, mempengaruhi market secara luas/multi-aset
2. quantitative_evidence: data pendukung konkret (% perubahan, basis points, index points,
   forecast vs actual, dll). Kalau tidak ada data eksplisit di berita, cari implikasi
   kuantitatif yang logis dari konteksnya.
3. affected_assets: daftar aset/instrumen yang paling terdampak (ex: XAU/USD, IHSG, DXY,
   US10Y, S&P500, dll)

Jangan menambahkan berita baru. Jangan mengubah judul atau tanggal. Murni evaluasi dampak.

OUTPUT: JSON list sesuai schema ScoredNews, urutkan dari market_impact_score tertinggi ke terendah.
```

**Implementasi (`agents/quant_analyst_agent.py`):**
- Input: list `NewsCandidate` dari Agent 1 (serialize ke JSON, inject ke prompt)
- Tidak perlu web search tool (murni reasoning atas data yang sudah ada)
- Output divalidasi ke `ScoredNews`

---

## Agent 3 — Lead Market Analyst / Writer & Financial Editor

**File:** `prompts/lead_editor_system.md`

```
Kamu adalah Lead Market Analyst sekaligus Financial Editor di divisi riset pasar modal kampus
(GIBEI Telkom University). Kamu menulis untuk publikasi mingguan "Weekly Market Insight" yang
dibaca mahasiswa dan calon investor ritel.

KONTEKS:
Kamu menerima:
1. Daftar berita ter-scoring dari Quant Analyst (sudah diurutkan berdasarkan market_impact_score)
2. Rentang periode laporan: {start_date} - {end_date}

DAFTAR BERITA TER-SCORE:
{scored_news_json}

TUGAS EDITORIAL:
1. PILIH 3 "Weekly Highlights" — berita dengan dampak market tertinggi DAN paling relevan/
   dipahami audiens (boleh override skor murni quant kalau ada pertimbangan editorial, misalnya
   diversifikasi topik/kategori biar tidak semua tentang topik yang sama).
2. PILIH 1 "Major Headline" — berita PALING penting dari ke-3 highlight di atas, yang jadi
   sorotan utama minggu ini.
3. TULIS 1 "Key Insight" — paragraf analisa mendalam (5-8 kalimat) yang menjelaskan KENAPA
   tren/berita minggu ini penting buat market, bukan sekadar mengulang ringkasan berita.
   Hubungkan beberapa berita kalau relevan, beri konteks dampak ke investor.

GAYA PENULISAN:
- Nada profesional finansial, netral, faktual (gaya seperti Reuters/Bloomberg ringkas)
- Judul: deskriptif dan tidak clickbait, maksimal ~15 kata
- Ringkasan highlight: 2-4 kalimat, padat, fokus fakta dan implikasi
- Key Insight: lebih naratif dan analitis, boleh menjelaskan mekanisme sebab-akibat
- JANGAN memberikan rekomendasi beli/jual eksplisit (compliance: not financial advice)
- Bahasa Inggris (mengikuti gaya template existing)

OUTPUT:
JSON sesuai schema WeeklyMarketInsight lengkap (period_start, period_end, weekly_highlights x3,
major_headline, key_insight, source_department).
```

**Implementasi (`agents/lead_editor_agent.py`):**
- Input: list `ScoredNews` dari Agent 2 + period dates
- Output divalidasi ke `WeeklyMarketInsight` (final schema)
- Simpan ke `output/weekly_insight_{start_date}_{end_date}.json`

---

## Efisiensi & Strategi Rate Limit (Groq Free Tier)

Free tier Groq itu ketat: kira-kira **30 request/menit**, **~6-12K token/menit** (tergantung model), dan **~1000 request/hari** per model — limit berlaku di level organisasi/akun, bukan per API key, dan kena limit mana pun yang lebih dulu tercapai (RPM/TPM/RPD). Karena tujuan lo "se-efisien mungkin tapi output segacor mungkin", desain ini WAJIB:

1. **Total 3 API call per run** (1 call per agent), bukan loop per item berita. Semua orkestrasi tool-search ada di dalam 1 call `groq/compound`, bukan di-loop dari sisi Python.
2. **Trim payload antar-agent.** Jangan kirim full JSON mentah dari Agent 1 ke Agent 2 ke Agent 3 — strip field yang nggak perlu (ex: `url` panjang) sebelum di-inject ke prompt agent berikutnya. Ini langsung motong TPM yang kepake.
3. **Set `max_tokens` eksplisit** di tiap call (jangan default/unlimited) — kira-kira 1500-2000 token cukup buat tiap tahap, biar nggak ada output bertele-tele yang makan TPM percuma.
4. **Retry/backoff pakai `tenacity`**, baca header `retry-after` dari response 429 Groq dan tunggu sesuai itu — jangan retry langsung beruntun karena cuma bikin tambah kena limit.
5. **Cache hasil per hari.** Kalau lo run beberapa kali di hari yang sama dengan rentang tanggal yang sama, simpan hasil Agent 1 (research) ke file lokal dan reuse — research adalah tahap termahal (pakai compound), jangan re-run kalau cuma mau tweak output Agent 3 (editorial).
6. **Mode dev terpisah dari mode "final run".** Saat develop/debug prompt Agent 3, jangan re-run full pipeline dari Agent 1 — buat flag `--from-cache` di CLI biar Agent 3 bisa dites ulang pakai hasil Agent 1 & 2 yang sudah tersimpan, tanpa makan quota lagi.
7. Kalau ke depannya mau scale (run harian otomatis / multi-user), baru worth dipertimbangkan upgrade ke Groq Developer tier (gratis, cuma perlu nambahin kartu kredit, dapat ~10x limit) — tapi untuk sekarang free tier udah cukup buat 1 run mingguan.

---



Logic utama:
```python
def run_pipeline(start_date: date, end_date: date, from_cache: bool = False) -> WeeklyMarketInsight:
    cache_path = f"output/cache_{start_date}_{end_date}.json"

    if from_cache and os.path.exists(cache_path):
        print("[1-2/3] Pakai cache research+scoring dari run sebelumnya...")
        with open(cache_path) as f:
            scored = [ScoredNews(**item) for item in json.load(f)]
    else:
        print(f"[1/3] News Research Analyst mencari berita {start_date} - {end_date}...")
        candidates = news_research_agent.run(start_date, end_date)

        print(f"[2/3] Quant Analyst menilai dampak {len(candidates)} kandidat berita...")
        scored = quant_analyst_agent.run(candidates)

        with open(cache_path, "w") as f:
            json.dump([s.model_dump(mode="json") for s in scored], f, indent=2)

    print(f"[3/3] Lead Editor menyusun output final...")
    final_output = lead_editor_agent.run(scored, start_date, end_date)

    return final_output
```

Tambahkan logging tiap step (print judul-judul yang lolos di tiap tahap) biar lo bisa lihat reasoning trail-nya di terminal, bukan cuma hasil akhir.

---

## CLI — `main.py`

```python
import argparse
from datetime import date, timedelta
import json

def main():
    parser = argparse.ArgumentParser(description="Weekly Market Insight Multi-Agent Generator")
    parser.add_argument("--end-date", type=str, default=None,
                         help="Format YYYY-MM-DD, default = hari ini")
    parser.add_argument("--days", type=int, default=7,
                         help="Jumlah hari ke belakang dari end-date, default 7")
    parser.add_argument("--output", type=str, default=None,
                         help="Path file output JSON")
    parser.add_argument("--from-cache", action="store_true",
                         help="Pakai hasil Agent 1+2 yang sudah tersimpan (hemat quota saat develop Agent 3)")
    args = parser.parse_args()

    end_date = date.fromisoformat(args.end_date) if args.end_date else date.today()
    start_date = end_date - timedelta(days=args.days)

    result = run_pipeline(start_date, end_date, from_cache=args.from_cache)

    output_path = args.output or f"output/weekly_insight_{start_date}_{end_date}.json"
    with open(output_path, "w") as f:
        json.dump(result.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

    print(f"\n✅ Selesai. Output tersimpan di: {output_path}")

if __name__ == "__main__":
    main()
```

---

## requirements.txt
```
groq>=0.13.0
pydantic>=2.0
python-dotenv
tenacity
rich
```

## .env.example
```
GROQ_API_KEY=gsk_xxxxx
```

---

## Cara Test via Terminal (setelah Claude Code selesai build)

```bash
pip install -r requirements.txt
cp .env.example .env   # lalu isi GROQ_API_KEY dari console.groq.com/keys
python main.py --days 7
# atau spesifik tanggal:
python main.py --end-date 2026-06-30 --days 7 --output output/test_run.json
# develop ulang Agent 3 tanpa makan quota research:
python main.py --end-date 2026-06-30 --days 7 --from-cache
```

Expected: terminal menampilkan log 3 step (research → scoring → editorial), lalu file JSON
final tersimpan dengan struktur sesuai `WeeklyMarketInsight` schema, siap di-mapping ke
field template desain (3 highlight cards, 1 major headline block, 1 key insight block).

---

## TODO untuk Claude Code

1. Setup struktur folder & file sesuai di atas
2. Implementasikan ketiga agent dengan system prompt yang sudah didefinisikan (boleh disempurnakan kalimatnya, tapi pertahankan struktur tugas & output schema-nya)
3. Implementasikan orchestrator sequential pipeline dengan caching hasil Agent 1+2 (`--from-cache`)
4. Implementasikan CLI dengan argparse
5. Tambahkan retry/backoff dengan `tenacity` yang membaca header `retry-after` dari Groq saat kena 429 — JANGAN retry agresif, free tier gampang kena limit
6. Tambahkan error handling: kalau Agent 1 gagal dapat berita yang cukup (< 5 valid item), retry MAKSIMAL SEKALI dengan prompt yang lebih spesifik
7. Tambahkan unit test sederhana untuk schema validation (pydantic)
8. Tulis README.md singkat berisi cara install, run, dan catatan soal rate limit Groq free tier
9. JANGAN hardcode API key di kode — selalu via .env
10. Pastikan Agent 1 pakai `model="groq/compound"` dengan satu request yang menyuruh model melakukan multiple web search sekaligus (bukan loop call Python terpisah per kategori berita)
11. Set `max_tokens` eksplisit di tiap call (jangan default) untuk kontrol budget TPM
