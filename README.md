# MediaFetch Web

Phiên bản website độc lập của MediaFetch, mặc định bằng tiếng Việt và có thể
chuyển sang tiếng Anh ngay trên giao diện.

An independent website edition of MediaFetch. Vietnamese is the default
language, with a persistent English toggle.

## Tính năng / Features

- Phân tích và tải media từ Facebook, Instagram, YouTube, TikTok, Reddit và X
- MP4, MP3 và ảnh bìa JPG
- MP4 tương thích Apple: ưu tiên H.264/AAC và tự chuyển đổi VP9/Opus khi cần
- Tiến trình tải chạy nền, giới hạn tải đồng thời và tự xóa tệp sau một giờ
- Kiểm tra tên miền chặt chẽ để tránh sử dụng dịch vụ làm proxy tùy ý
- Giao diện responsive, tối ưu cho điện thoại và desktop
- Vietnamese-first UI with a remembered VI/EN preference

## Chạy bằng Docker / Run with Docker

```bash
docker compose up --build
```

Mở `http://localhost:3000`.

## Phát triển cục bộ / Local development

Website:

```bash
pnpm install
pnpm dev
```

API (mở terminal thứ hai):

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
PYTHONPATH=backend backend/.venv/bin/uvicorn app.main:app --reload
```

The web layer proxies `/api/*` to `MEDIAFETCH_API_URL`, which defaults to
`http://127.0.0.1:8000`.

## Kiểm thử / Tests

```bash
pnpm build
PYTHONPATH=backend backend/.venv/bin/pytest -q backend/tests
```

## Triển khai / Deployment

Deploy the full Docker Compose stack to a host that supports long-running
Python processes and sufficient temporary disk space. Media extraction and
video transcoding cannot run on static hosting alone.

The included `render.yaml` deploys the complete website and Python downloader
as one Docker web service on Render. Render provides an HTTPS `onrender.com`
domain automatically. The free instance may sleep after periods of inactivity;
use a paid instance for an always-on production service.

Only download content you own or have permission to save. Platform changes can
occasionally require an update to `yt-dlp`.
