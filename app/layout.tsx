import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'MediaFetch — Tải video, âm thanh và hình ảnh',
  description: 'Tải MP4, MP3 và JPG từ Facebook, Instagram, YouTube, TikTok, Reddit và X.',
  openGraph: { title: 'MediaFetch — Lưu nội dung bạn yêu thích', description: 'Trình tải media nhanh, riêng tư và tương thích với thiết bị Apple.', type: 'website' },
  twitter: { card: 'summary', title: 'MediaFetch', description: 'Tải media nhanh, riêng tư và dễ dùng.' },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="vi"><body>{children}</body></html>; }
