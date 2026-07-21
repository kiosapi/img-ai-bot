export type Lang = "id" | "en";

const T = {
  "app.name": { id: "imgaai", en: "imgaai" },
  "login.title": { id: "Masuk dengan Telegram", en: "Sign in with Telegram" },
  "login.sub": {
    id: "Klik login → buka bot → konfirmasi. Kuota & saldo sinkron.",
    en: "Click login → open bot → confirm. Quota & balance sync.",
  },
  "login.cta": { id: "Login via Telegram", en: "Login via Telegram" },
  "login.waiting": { id: "Menunggu konfirmasi di bot…", en: "Waiting for bot confirmation…" },
  "login.waitingHint": {
    id: "Di Telegram tekan Start / konfirmasi. Halaman ini auto-masuk.",
    en: "In Telegram press Start / confirm. This page signs in automatically.",
  },
  "login.openAgain": { id: "Buka bot lagi", en: "Open bot again" },
  "login.cancelWait": { id: "Batal / coba ulang", en: "Cancel / retry" },
  "login.expired": {
    id: "Kode login kadaluarsa. Klik login lagi.",
    en: "Login code expired. Click login again.",
  },
  "login.flowHint": {
    id: "Tanpa widget. Auth lewat deep-link bot (Model B).",
    en: "No widget. Auth via bot deep-link (Model B).",
  },
  "nav.home": { id: "Beranda", en: "Home" },
  "nav.generate": { id: "Generate", en: "Generate" },
  "nav.history": { id: "Riwayat", en: "History" },
  "nav.styles": { id: "Style", en: "Styles" },
  "nav.settings": { id: "Pengaturan", en: "Settings" },
  "home.balance": { id: "Saldo", en: "Balance" },
  "home.quota": { id: "Kuota hari ini", en: "Today quota" },
  "home.streak": { id: "Streak check-in", en: "Check-in streak" },
  "home.premium": { id: "Premium", en: "Premium" },
  "home.free": { id: "Free", en: "Free" },
  "home.welcome": { id: "Halo", en: "Hi" },
  "home.genCta": { id: "Generate gambar", en: "Generate image" },
  "home.soon": {
    id: "Generate web pakai antrian yang sama dengan bot.",
    en: "Web generate shares the bot queue.",
  },
  "history.empty": { id: "Belum ada riwayat generate.", en: "No generation history yet." },
  "history.title": { id: "Riwayat", en: "History" },
  "styles.title": { id: "Style aktif", en: "Active styles" },
  "styles.empty": { id: "Belum ada style.", en: "No styles yet." },
  "settings.title": { id: "Pengaturan", en: "Settings" },
  "settings.lang": { id: "Bahasa", en: "Language" },
  "settings.gallery": { id: "Gallery publik (opt-in)", en: "Public gallery (opt-in)" },
  "settings.galleryHint": {
    id: "Default private. Nyalakan kalau mau share karya ke explore (phase 2).",
    en: "Default private. Enable to share works on explore (phase 2).",
  },
  "settings.logout": { id: "Keluar", en: "Log out" },
  "settings.saved": { id: "Tersimpan", en: "Saved" },
  "err.generic": { id: "Gagal memuat", en: "Failed to load" },
  "loading": { id: "Memuat...", en: "Loading..." },
  "gen.title": { id: "Generate", en: "Generate" },
  "gen.prompt": { id: "Prompt", en: "Prompt" },
  "gen.placeholder": { id: "Deskripsikan gambar...", en: "Describe the image..." },
  "gen.submit": { id: "Generate", en: "Generate" },
  "gen.disabled": {
    id: "Generate web butuh API + bot worker live.",
    en: "Web generate needs live API + bot worker.",
  },
  "gen.queue": { id: "Antri…", en: "Queued…" },
  "gen.running": { id: "Memproses…", en: "Processing…" },
  "gen.done": { id: "Selesai", en: "Done" },
  "gen.eta": { id: "ETA", en: "ETA" },
  "gen.pos": { id: "Posisi", en: "Position" },
  "gen.persistHint": {
    id: "Progress tetap tampil saat pindah halaman",
    en: "Progress stays while you browse other pages",
  },
  "gen.toastDone": { id: "Generate berhasil", en: "Generation complete" },
  "gen.toastFail": { id: "Generate gagal", en: "Generation failed" },
  "gen.viewResult": { id: "Lihat hasil", en: "View result" },
  "gen.resultReady": {
    id: "Hasil siap. Cek riwayat jika gambar tidak tampil.",
    en: "Result ready. Check history if image is missing.",
  },
  "gen.clear": { id: "Tutup", en: "Dismiss" },
} as const;

export type Key = keyof typeof T;

export function t(key: Key, lang: Lang): string {
  return T[key][lang] || T[key].id;
}
