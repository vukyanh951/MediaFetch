'use client';
/* eslint-disable @next/next/no-img-element -- thumbnails come from user-selected supported platforms */

import { FormEvent, useEffect, useMemo, useState } from 'react';

type Language = 'vi' | 'en';
type MediaType = 'MP4' | 'MP3' | 'JPG';
type MediaInfo = { title: string; creator: string; duration: string; platform: string; thumbnail: string | null; qualities: number[] };

const copy = {
  vi: {
    navHow: 'Cách hoạt động', navPlatforms: 'Nền tảng', navAbout: 'Giới thiệu', badge: 'NHANH • RIÊNG TƯ • DỄ DÙNG',
    titleA: 'Lưu nội dung bạn yêu thích.', titleB: 'Chất lượng nguyên bản.',
    intro: 'Tải video, âm thanh và ảnh từ các nền tảng phổ biến — trực tiếp, không quảng cáo phiền nhiễu.',
    placeholder: 'Dán liên kết Facebook, YouTube, TikTok…', analyze: 'Phân tích', analyzing: 'Đang phân tích…',
    supports: 'Hỗ trợ Facebook, Instagram, YouTube, TikTok, Reddit và X', preview: 'NỘI DUNG ĐÃ TÌM THẤY',
    quality: 'CHẤT LƯỢNG VIDEO', best: 'Tốt nhất hiện có', prepare: 'Chuẩn bị tải xuống', preparing: 'Đang chuẩn bị…', download: 'Tải về thiết bị',
    invalid: 'Vui lòng nhập một liên kết được hỗ trợ.', failed: 'Không thể xử lý liên kết này. Hãy thử lại.', ready: 'Tệp của bạn đã sẵn sàng.', connecting: 'Đang kết nối với dịch vụ tải xuống…', connectionLost: 'Kết nối tải xuống bị gián đoạn. Vui lòng thử lại sau vài giây.',
    howTitle: 'Chỉ ba bước đơn giản', howSub: 'Không cần đăng ký. Không lưu lịch sử liên kết.',
    steps: [['01', 'Dán liên kết', 'Sao chép URL của video hoặc bài đăng bạn muốn lưu.'], ['02', 'Chọn định dạng', 'Tải video MP4, âm thanh MP3 hoặc ảnh bìa JPG.'], ['03', 'Lưu về máy', 'Tệp được chuẩn bị và tải thẳng xuống thiết bị của bạn.']],
    apple: 'Tương thích Apple', appleBody: 'Video MP4 được ưu tiên H.264/AAC và tự động tối ưu để phát mượt trên Mac, iPhone và iPad.',
    private: 'Riêng tư theo thiết kế', privateBody: 'MediaFetch không tạo tài khoản và không lưu lịch sử tải xuống của bạn.', footer: 'Chỉ tải nội dung bạn sở hữu hoặc được phép lưu.', creator: 'Người đăng', duration: 'Thời lượng',
  },
  en: {
    navHow: 'How it works', navPlatforms: 'Platforms', navAbout: 'About', badge: 'FAST • PRIVATE • EASY',
    titleA: 'Save what inspires you.', titleB: 'Keep the original quality.',
    intro: 'Download video, audio, and images from popular platforms — directly, without distracting ads.',
    placeholder: 'Paste a Facebook, YouTube, TikTok… link', analyze: 'Analyze', analyzing: 'Analyzing…',
    supports: 'Supports Facebook, Instagram, YouTube, TikTok, Reddit, and X', preview: 'MEDIA FOUND',
    quality: 'VIDEO QUALITY', best: 'Best available', prepare: 'Prepare download', preparing: 'Preparing…', download: 'Download to device',
    invalid: 'Enter a supported media link.', failed: 'We could not process this link. Please try again.', ready: 'Your file is ready.', connecting: 'Connecting to the download service…', connectionLost: 'The download connection was interrupted. Please retry in a few seconds.',
    howTitle: 'Three simple steps', howSub: 'No account required. No link history stored.',
    steps: [['01', 'Paste a link', 'Copy the URL of the video or post you want to save.'], ['02', 'Choose a format', 'Download MP4 video, MP3 audio, or a JPG cover image.'], ['03', 'Save to your device', 'Your file is prepared and sent straight to your device.']],
    apple: 'Apple compatible', appleBody: 'MP4 video prefers H.264/AAC and is optimized automatically for smooth playback on Mac, iPhone, and iPad.',
    private: 'Private by design', privateBody: 'MediaFetch creates no account and keeps no history of your downloads.', footer: 'Only download content you own or have permission to save.', creator: 'Creator', duration: 'Duration',
  },
} as const;

const supported = ['facebook.com', 'fb.watch', 'instagram.com', 'youtube.com', 'youtu.be', 'tiktok.com', 'reddit.com', 'redd.it', 'x.com', 'twitter.com'];
const platforms = [['▶', 'YouTube'], ['f', 'Facebook'], ['◎', 'Instagram'], ['♪', 'TikTok'], ['●', 'Reddit'], ['𝕏', 'X']];

export default function Home() {
  const [language, setLanguage] = useState<Language>('vi');
  const [url, setUrl] = useState('');
  const [type, setType] = useState<MediaType>('MP4');
  const [quality, setQuality] = useState('');
  const [info, setInfo] = useState<MediaInfo | null>(null);
  const [state, setState] = useState<'idle' | 'analyzing' | 'preparing' | 'ready'>('idle');
  const [error, setError] = useState('');
  const [jobId, setJobId] = useState('');
  const t = copy[language];

  useEffect(() => {
    const saved = window.localStorage.getItem('mediafetch-language');
    if (saved === 'en' || saved === 'vi') queueMicrotask(() => setLanguage(saved));
  }, []);
  useEffect(() => { document.documentElement.lang = language; window.localStorage.setItem('mediafetch-language', language); }, [language]);
  const validUrl = useMemo(() => { try { const host = new URL(url).hostname; return supported.some((domain) => host === domain || host.endsWith(`.${domain}`)); } catch { return false; } }, [url]);

  function errorMessage(reason: unknown) {
    const message = reason instanceof Error ? reason.message : '';
    return /string did not match|load failed|failed to fetch|network/i.test(message) ? t.connectionLost : message || t.failed;
  }

  async function responseData(response: Response) {
    const body = await response.text();
    try { return JSON.parse(body); }
    catch { throw new Error(response.ok ? t.failed : t.connectionLost); }
  }

  async function analyze(event: FormEvent) {
    event.preventDefault(); setError(''); setInfo(null);
    if (!validUrl) { setError(t.invalid); return; }
    setState('analyzing');
    try {
      const response = await fetch('/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) });
      const data = await responseData(response); if (!response.ok) throw new Error(data.detail || t.failed);
      setInfo(data); setState('idle'); setQuality('');
    } catch (reason) { setError(errorMessage(reason)); setState('idle'); }
  }

  async function prepare() {
    setError(''); setState('preparing');
    try {
      const response = await fetch('/api/download', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, media_type: type, quality: quality ? Number(quality) : null }) });
      const data = await responseData(response); if (!response.ok) throw new Error(data.detail || t.failed);
      setJobId(data.job_id); poll(data.job_id);
    } catch (reason) { setError(errorMessage(reason)); setState('idle'); }
  }

  async function poll(id: string) {
    try {
      const response = await fetch(`/api/jobs/${id}`); const data = await responseData(response);
      if (!response.ok || data.status === 'error') throw new Error(data.error || t.failed);
      if (data.status === 'complete') { setState('ready'); return; }
      window.setTimeout(() => poll(id), 900);
    } catch (reason) { setError(errorMessage(reason)); setState('idle'); }
  }

  function saveFile() {
    window.location.href = `/api/files/${encodeURIComponent(jobId)}`;
  }

  return <main>
    <header className="site-header">
      <a className="brand" href="#top" aria-label="MediaFetch"><span className="brand-mark">↓</span><span>MediaFetch</span></a>
      <nav><a href="#how">{t.navHow}</a><a href="#platforms">{t.navPlatforms}</a><a href="#about">{t.navAbout}</a></nav>
      <div className="language" role="group" aria-label="Language"><button className={language === 'vi' ? 'active' : ''} onClick={() => setLanguage('vi')}>VI</button><span>/</span><button className={language === 'en' ? 'active' : ''} onClick={() => setLanguage('en')}>EN</button></div>
    </header>
    <section className="hero" id="top">
      <div className="hero-glow glow-one"/><div className="hero-glow glow-two"/>
      <p className="eyebrow"><span>✦</span>{t.badge}</p><h1>{t.titleA}<br/><em>{t.titleB}</em></h1><p className="hero-copy">{t.intro}</p>
      <form className="search" onSubmit={analyze}><span className="link-icon">↗</span><input value={url} onChange={(event) => setUrl(event.target.value)} placeholder={t.placeholder} aria-label={t.placeholder}/><button type="submit" disabled={state === 'analyzing'}>{state === 'analyzing' ? t.analyzing : t.analyze}<span>→</span></button></form>
      <p className="support-line"><span className="pulse"/>{t.supports}</p>{error && <p className="error" role="alert">{error}</p>}
      {info && <section className="media-card" aria-live="polite"><div className="media-image">{info.thumbnail ? <img src={info.thumbnail} alt=""/> : <span>♪</span>}<span className="platform-pill">{info.platform}</span></div><div className="media-detail"><p className="section-label">{t.preview}</p><h2>{info.title}</h2><p className="meta">{t.creator}: {info.creator} <span>•</span> {t.duration}: {info.duration}</p><div className="format-row">{(['MP4','MP3','JPG'] as MediaType[]).map((item) => <button key={item} className={type === item ? 'active' : ''} onClick={() => setType(item)}>{item}</button>)}</div>{type === 'MP4' && <label className="quality">{t.quality}<select value={quality} onChange={(event) => setQuality(event.target.value)}><option value="">{t.best}</option>{info.qualities.map((item) => <option key={item} value={item}>{item}p</option>)}</select></label>}{state !== 'ready' ? <button className="primary-action" onClick={prepare} disabled={state === 'preparing'}>{state === 'preparing' ? t.preparing : t.prepare}<span>↓</span></button> : <button className="primary-action" onClick={saveFile}>{t.download}<span>↓</span></button>}{state === 'preparing' && <p className="job-status">{t.connecting}</p>}{state === 'ready' && <p className="job-status ready">✓ {t.ready}</p>}</div></section>}
    </section>
    <section className="platform-strip" id="platforms">{platforms.map(([icon, name]) => <div key={name}><span>{icon}</span>{name}</div>)}</section>
    <section className="how" id="how"><div className="section-heading"><p className="section-label">MEDIAFETCH</p><h2>{t.howTitle}</h2><p>{t.howSub}</p></div><div className="steps">{t.steps.map(([number,title,body]) => <article key={number}><span className="step-number">{number}</span><div className="step-icon">{number === '01' ? '↗' : number === '02' ? '◇' : '↓'}</div><h3>{title}</h3><p>{body}</p></article>)}</div></section>
    <section className="trust" id="about"><article><span className="trust-icon">⌁</span><div><h3>{t.apple}</h3><p>{t.appleBody}</p></div></article><article><span className="trust-icon">○</span><div><h3>{t.private}</h3><p>{t.privateBody}</p></div></article></section>
    <footer><a className="brand" href="#top"><span className="brand-mark">↓</span><span>MediaFetch</span></a><p>{t.footer}</p><p>© 2026 MediaFetch</p></footer>
  </main>;
}
