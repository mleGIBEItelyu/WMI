# Audit — Weekly Market Insight: Kesiapan untuk Konsumsi Publik

**Tanggal audit:** 13 Juli 2026
**Ruang lingkup:** Apakah output layak dipublikasikan untuk publik di bawah brand
GIBEI Telkom University × Phillip Sekuritas? Apakah sistem benar-benar *membaca*
berita, atau hanya judul?
**Metode:** Pemeriksaan bukti langsung dari 2 run nyata (23–30 Jun & 5–12 Jul 2026)
— cache berisi flag `fetch_ok` dan panjang teks per artikel, jadi klaim di bawah
terverifikasi, bukan asumsi.

---

## Putusan singkat

> **Sistem BENAR-BENAR membaca isi artikel penuh — bukan sekadar judul — TAPI tidak
> selalu, dan belum layak dirilis ke publik tanpa perombakan (terutama: gerbang
> review manusia + kontrol kualitas sumber + transparansi provenance).**

Status: **BELUM SIAP untuk rilis publik tanpa syarat.** Perlu 4 perbaikan P0 di
bawah. Setelah itu, layak terbit dengan sign-off editor manusia.

---

## Pertanyaan 1 — Membaca isi berita, atau cuma judul?

**Jawaban: membaca isi penuh, terbukti — tapi rasionya tidak stabil dan kegagalan
fetch tersembunyi dari pembaca.**

Arsitektur memang mengambil body artikel (stage 4: `article_fetcher.py` → httpx +
trafilatura) untuk berita shortlist, lalu editor menulis dari teks itu
(`article_text`), fallback ke cuplikan (`raw_summary`, ±1–2 kalimat ≈ selevel judul)
kalau fetch gagal.

Bukti dari cache (jumlah karakter body yang benar-benar terbaca):

| Run | Full-read | Berita Indonesia dibaca penuh | Catatan |
|---|---|---|---|
| 23–30 Jun 2026 | **3 / 10** | **0 / 2** ❌ | Kedua berita Indonesia (BI-Rate, POJK OJK) **snippet-only** — analisa Indonesia-nya berbasis cuplikan, bukan artikel |
| 5–12 Jul 2026 | **8 / 10** | **3 / 3** ✅ | Semua berita Indonesia terbaca penuh (4059, 3180, 1213 char) |

**Temuan:** kualitas fetch sangat bervariasi (3/10 vs 8/10). Yang paling
mengkhawatirkan: pada run Juni, justru **berita Indonesia** — inti dari tujuan
produk — yang gagal dibaca penuh, padahal outputnya tetap tampil dengan otoritas
yang sama. Pembaca **tidak bisa membedakan** mana highlight yang bersumber artikel
penuh dan mana yang cuma cuplikan.

---

## Pertanyaan 2 — Layak konsumsi publik?

**Belum, tanpa perbaikan.** Empat masalah serius:

### 🔴 P0-1. Kontradiksi fakta lolos tanpa terdeteksi
Dalam **satu edisi yang sama** (5–12 Jul), dua highlight saling bertentangan:
- "BI **Holds** 6% Rate in July 2026" (sumber: JournalArta)
- "Bank Indonesia … cumulatively increased the BI Rate … to **5.75 percent**" (En.tempo)

Jadi 5,75% dan 6,00% muncul berdampingan sebagai fakta di publikasi yang sama.
Antar-edisi pun tak konsisten (Juni: naik ke 5,75%; Juli: tahan di 6%). Sistem tidak
punya pengecekan konsistensi silang. **Untuk publikasi finansial berbrand, ini fatal.**

### 🔴 P0-2. Kualitas sumber campur aduk
Sumber tier-1 (The Guardian, Washington Post, Trading Economics, Tempo, KOMPAS.TV)
bercampur dengan sumber lemah / blog SEO / opini-forecast:
`JournalArta`, `Golden Ark Reserve`, `West End Advisory Group`, `Mitrade`,
`"Macro & Market Musings"`. Beberapa "berita" sebenarnya artikel **forecast/outlook**
(opini), bukan berita primer. Di bawah brand institusi, ini risiko kredibilitas.

### 🔴 P0-3. Tidak ada transparansi provenance ke pembaca
Output final tidak menampilkan URL sumber, dan tidak menandai highlight mana yang
dibaca penuh vs cuplikan. Pembaca tak bisa verifikasi. (Datanya ada di internal —
`fetch_ok`, `url` — hanya tidak diekspos.)

### 🔴 P0-4. Tidak ada gerbang review manusia
Tidak ada langkah editor manusia sebelum publish. Standar minimum untuk publikasi
pasar modal: seseorang bertanggung jawab atas akurasi & kepatuhan sebelum terbit.

### 🟡 Masalah sekunder (P1)
- **Tanggal ke depan / sintetis:** window uji di 2026 membuat grounding sering
  mengembalikan artikel *forecast/outlook* alih-alih berita keras.
- **Duplikasi tema:** 2 artikel "Gold outlook" berbeda masuk shortlist yang sama.
- **Disclaimer sudah ada** (bagus): "not financial advice" tercantum di tiap output.

---

## Yang SUDAH benar (jangan dirombak)

- ✅ Membaca body artikel penuh (bukan halusinasi judul) — terbukti pada 8/10 run Juli.
- ✅ Angka konkret dari artikel muncul (Brent +6% >$80, S&P Q2 +14,87%, PMI 53,9).
- ✅ Kuota & korelasi Indonesia berjalan (BI-Rate jadi Major Headline, tiap highlight
  punya blok "Impact on Indonesia").
- ✅ Fallback anti-crash (paywall/403/404 → cuplikan, tidak error).
- ✅ Disclaimer kepatuhan otomatis; tanpa rekomendasi beli/jual.
- ✅ 42 unit test hijau; arsitektur env-driven tanpa hardcode.

---

## Rekomendasi perombakan (prioritas)

### P0 — wajib sebelum rilis publik
1. **Gerbang review manusia.** Pipeline menghasilkan *draft*; publish hanya setelah
   editor menandai `approved` (mis. field status + langkah CLI `--approve`).
2. **Kontrol kualitas sumber.** Allowlist/tiering outlet; demote/flag domain
   SEO/forecast; tandai item dari sumber lemah agar tidak jadi Major Headline.
3. **Transparansi provenance.** Tampilkan URL sumber tiap highlight + badge
   "Full article" vs "Summary only" (data `fetch_ok`/`url` sudah ada, tinggal
   diekspos ke JSON & front-end).
4. **Pengecekan konsistensi silang.** Deteksi angka bertentangan untuk entitas sama
   (mis. BI-Rate 5,75% vs 6,00%) dan tandai untuk editor sebelum publish.

### P1 — kualitas
5. Pisahkan **berita vs opini/forecast**; turunkan bobot judul mengandung
   "outlook/forecast/musings/prediction".
6. **Naikkan rasio full-read** (resolve URL publisher asli sebelum redirect grounding
   kadaluarsa; retry; dedup near-duplicate) — target ≥ 8/10, khususnya berita ID.
7. **Sanity tanggal:** peringatkan bila window melampaui data nyata / hasil didominasi
   forecast.
8. Tambah field **`confidence`/`sourced_from`** per highlight (full_article|snippet).

### P2 — penyempurnaan
9. Dedup tema, batasi maksimal N berita per tema.
10. Sitasi bergaya jurnalistik (outlet + tanggal) yang konsisten.

---

## Kesimpulan

Sistem sudah melakukan hal tersulit dengan benar — **membaca isi artikel dan
mengorelasikannya ke ekonomi Indonesia** — dan pada run yang sehat (Juli, 8/10)
hasilnya kaya dan faktual. Namun untuk **konsumsi publik di bawah brand institusi**,
belum aman: ada kontradiksi fakta yang lolos, sumber yang tak seragam mutunya,
tidak ada jejak verifikasi bagi pembaca, dan tidak ada tanggung jawab editorial
manusia.

**Rekomendasi:** perlakukan output saat ini sebagai **draft riset internal berkualitas
tinggi**, bukan produk siap-terbit. Implementasikan 4 item P0 (terutama gerbang
review manusia + kontrol sumber + transparansi provenance), lalu publikasikan dengan
sign-off editor. Dengan itu, sistem naik dari "gacor secara teknis" menjadi "layak
dikonsumsi publik".
